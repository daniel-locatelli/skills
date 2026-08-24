import math

import numpy as np
import pytest

from abm.surfaces import (MongeSurface, SphereSurface, TubeSurface, anisotropy,
                          fd_principal)


def test_monge_gaussian_matches_closed_form():
    """K = (fxx.fyy - fxy^2)/(1 + fx^2 + fy^2)^2 for a height field (algorithm.md 5.1)."""
    h, w = 3.0, 2.0 * math.pi / 20.0
    s = MongeSurface(h=h, periods=2.0, length=20.0)
    for u, v in [(0.0, 0.0), (2.5, 2.5), (-5.0, 5.0), (1.3, -4.1)]:
        fx = -h * w * math.sin(w * u) * math.cos(w * v)
        fy = -h * w * math.cos(w * u) * math.sin(w * v)
        fxx = fyy = -h * w * w * math.cos(w * u) * math.cos(w * v)
        fxy = h * w * w * math.sin(w * u) * math.sin(w * v)
        expected = (fxx * fyy - fxy * fxy) / (1.0 + fx * fx + fy * fy) ** 2
        assert s.gaussian_at(u, v) == pytest.approx(expected, rel=1e-9, abs=1e-15)


def test_monge_dome_is_elliptic_and_saddle_is_hyperbolic_with_equal_magnitude():
    """algorithm.md 9: 'four flat strongly anticlastic saddles with |K| equal to the dome's'."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    assert s.gaussian_at(0.0, 0.0) > 0.0
    assert s.gaussian_at(5.0, 5.0) < 0.0
    assert abs(s.gaussian_at(0.0, 0.0)) == pytest.approx(abs(s.gaussian_at(5.0, 5.0)), rel=1e-9)


def test_monge_saddle_principal_directions_are_the_diagonals():
    """algorithm.md 9: principal directions at the saddles are the diagonals, asymptotic
    directions the axes -- which is exactly why a uv-aligned hex seed fails there."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    k1, k2, e1 = s.principal_at(5.0, 5.0)
    assert k1 == pytest.approx(-k2, rel=1e-9)
    assert math.degrees(math.atan2(e1[1], e1[0])) % 90.0 == pytest.approx(45.0, abs=1e-6)


def test_principal_ordering_is_by_magnitude():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    for u, v in [(1.0, 2.0), (-3.0, 4.5), (7.0, -1.0), (0.4, 0.4)]:
        k1, k2, _ = s.principal_at(u, v)
        assert abs(k1) >= abs(k2)


def test_principal_direction_is_unit_and_tangent():
    """algorithm.md 4: E1 is re-tangentialised and re-normalised after evaluation."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    for u, v in [(1.0, 2.0), (-3.0, 4.5), (5.0, 5.0)]:
        _, _, e1 = s.principal_at(u, v)
        assert np.linalg.norm(e1) == pytest.approx(1.0, abs=1e-12)
        assert abs(float(e1 @ s.normal_at(u, v))) < 1e-12


def test_fd_principal_matches_analytic():
    """The 5.1 finite-difference fallback is the portable path for kernels without a
    curvature API; it must agree with the analytic one.

    Compared as an UNORDERED pair, and the direction compared only where |k1| and |k2|
    are distinguishable. At a symmetric saddle |k1| = |k2| exactly, so which one is
    'larger' is a coin flip between any two evaluations -- algorithm.md 1 names this
    ('the numerically larger principal direction swaps between E1 and E2 from agent to
    agent') and it is precisely why the alignment field must be 12-fold rather than
    6-fold. Asserting an ordering here would assert something the spec calls undefined.
    """
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    for u, v in [(1.0, 2.0), (-3.0, 4.5), (5.0, 5.0), (0.0, 0.0)]:
        k1a, k2a, e1a = s.principal_at(u, v)
        k1f, k2f, e1f = fd_principal(s, u, v)
        assert sorted([k1f, k2f]) == pytest.approx(sorted([k1a, k2a]), rel=1e-4, abs=1e-8)
        if abs(abs(k1a) - abs(k2a)) > 1e-3 * max(abs(k1a), abs(k2a), 1e-12):
            assert abs(abs(float(e1a @ e1f)) - 1.0) < 1e-4      # direction, sign free


def test_principal_directions_are_orthogonal_even_at_a_symmetric_saddle():
    """The E1/E2 assignment is ambiguous where |k1| = |k2|, but the FRAME is not: the two
    principal directions are orthogonal, and both are 45 degrees off the axes at the
    egg-crate saddle. The 12-fold field is invariant to the swap; a 6-fold field is not."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    _, _, e1a = s.principal_at(5.0, 5.0)
    _, _, e1f = fd_principal(s, 5.0, 5.0)
    dot = abs(float(e1a @ e1f))
    assert dot < 1e-4 or dot > 1.0 - 1e-4                 # parallel or perpendicular
    for e in (e1a, e1f):
        assert math.degrees(math.atan2(e[1], e[0])) % 90.0 == pytest.approx(45.0, abs=1e-4)


def test_monge_derivatives_match_central_differences():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    u, v, eps = 2.0, -3.0, 1e-6
    su, sv = s.derivatives_at(u, v)
    assert np.allclose(su, (s.point_at(u + eps, v) - s.point_at(u - eps, v)) / (2 * eps), atol=1e-6)
    assert np.allclose(sv, (s.point_at(u, v + eps) - s.point_at(u, v - eps)) / (2 * eps), atol=1e-6)


def test_monge_surface_area_exceeds_plan_area():
    """algorithm.md 1: plan 400 vs surface 479 -- the ~12% that makes lattice pitch and
    spacing disagree. A host that 'fixes' either will not reproduce section 8."""
    assert 470.0 < MongeSurface(h=3.0, periods=2.0, length=20.0).area() < 490.0


def test_monge_topology_is_all_real_boundaries():
    t = MongeSurface().topology
    assert t.boundary_u0 and t.boundary_u1 and t.boundary_v0 and t.boundary_v1
    assert not t.is_non_trivial and not t.is_closed_surface


def test_monge_closest_uv_is_the_true_closest_point_not_a_vertical_drop():
    """algorithm.md 5: closest_uv is the closest point on the surface. The reference harness's
    vertical drop is a flagged approximation kept here only to make divergence attributable."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    drop = MongeSurface(h=3.0, periods=2.0, length=20.0, projection="vertical")
    u0, v0 = 2.5, 0.0                                    # a steep flank
    p = s.point_at(u0, v0) + np.array([0.3, 0.0, 0.0])
    cu, cv = s.closest_uv(p, u0, v0)
    du, dv = drop.closest_uv(p, u0, v0)
    assert np.linalg.norm(s.point_at(cu, cv) - p) <= np.linalg.norm(s.point_at(du, dv) - p) + 1e-12
    assert abs(cu - du) > 1e-6


def test_sphere_curvature_is_uniform():
    s = SphereSurface(radius=10.0)
    for u, v in [(0.0, 0.0), (1.0, 0.5), (4.0, -1.2)]:
        assert s.gaussian_at(u, v) == pytest.approx(0.01, rel=1e-9)
        k1, k2, _ = s.principal_at(u, v)
        assert abs(k1) == pytest.approx(0.1, rel=1e-6)
        assert abs(k2) == pytest.approx(0.1, rel=1e-6)


def test_sphere_is_umbilic_so_anisotropy_is_zero():
    """algorithm.md 8 / STATUS: the sphere's 'alignment 0.00 over 0 pairs' is an ABSENT
    population, not a broken metric. This is why."""
    k1, k2, _ = SphereSurface(radius=10.0).principal_at(1.0, 0.5)
    assert anisotropy(k1, k2) < 1e-6


def test_sphere_topology_is_closed_in_u_and_singular_in_v():
    t = SphereSurface().topology
    assert t.closed_u and t.singular_v0 and t.singular_v1
    assert t.is_non_trivial and t.is_closed_surface
    assert not t.boundary_u0 and not t.boundary_v0


def test_sphere_closest_uv_wraps_the_seam():
    """algorithm.md 5: clamping at a seam piles agents against both ends of it."""
    s = SphereSurface(radius=10.0)
    p = s.point_at(0.05, 0.0)
    u, v = s.closest_uv(p, 6.25, 0.0)                    # hint just below 2pi
    assert 0.0 <= u < 2.0 * math.pi
    assert min(abs(u - 0.05), 2 * math.pi - abs(u - 0.05)) < 1e-6
    assert np.allclose(s.point_at(u, v), p, atol=1e-9)


def test_anisotropy_clamps_and_handles_zero():
    assert anisotropy(0.0, 0.0) == 0.0
    assert anisotropy(1.0, -1.0) == pytest.approx(1.0)
    assert anisotropy(1.0, 0.0) == pytest.approx(1.0)
    assert anisotropy(1.0, 1.0) == pytest.approx(0.0)


def _tube_analytic(surface, v):
    """Meridian and hoop curvature of a surface of revolution, closed form."""
    r, dr = surface._r(v), surface._dr(v)
    d2r = -surface.radius * surface.barrel * (math.pi / surface.height) ** 2 * math.sin(
        math.pi * v / surface.height
    )
    return -d2r / (1.0 + dr * dr) ** 1.5, 1.0 / (r * math.sqrt(1.0 + dr * dr))


def test_tube_curvature_matches_the_surface_of_revolution_closed_form():
    s = TubeSurface(radius=5.0, height=20.0, barrel=0.35)
    for v in (5.0, 10.0, 15.0):
        k1, k2, _ = s.principal_at(1.0, v)
        km, kh = _tube_analytic(s, v)
        assert sorted((abs(k1), abs(k2))) == pytest.approx(sorted((km, kh)), rel=1e-4)


def test_a_principal_parametrisation_still_yields_a_usable_principal_direction():
    """REGRESSION. On any surface of revolution u and v are ALREADY principal, so the shape
    operator's off-diagonals are rounding noise -- 1e-17, not 0. `_eig2` tested them against
    an absolute 1e-300, took the `(a12, k1 - a11)` branch, and built an eigenvector out of
    two quantities that are both noise; `_principal_from_shape` then found its norm below
    1e-14 and returned the zero vector. `anisotropy` is forced to 0 whenever e1 is zero, so
    the 12-fold alignment field went silently inert on every dome, tube, cone and vault --
    the exact "misaligned seed" failure mode the strategy warns about, with no symptom
    except bad plates.

    Found by the developable-tube caveat, not by any test that existed. The
    egg-crate's parametrisation is not principal so it never hit this; the sphere is
    umbilic so its anisotropy is 0 either way; and the DEVELOPABLE tube has exact symbolic
    zeros off the diagonal, so it took the correct branch. Only the barrelled tube exposes
    it. §2's "every geometric tolerance is relative" is the rule that was broken.
    """
    s = TubeSurface(radius=5.0, height=20.0, barrel=0.35)
    for v in (5.0, 10.0, 15.0):
        k1, k2, e1 = s.principal_at(1.0, v)
        assert float(np.linalg.norm(e1)) == pytest.approx(1.0)
        assert anisotropy(k1, k2) > 0.4
        # u and v ARE the principal directions here, so e1 must lie along one of them
        su, sv = s.derivatives_at(1.0, v)
        su, sv = su / np.linalg.norm(su), sv / np.linalg.norm(sv)
        assert max(abs(float(e1 @ su)), abs(float(e1 @ sv))) == pytest.approx(1.0, abs=1e-6)


def test_a_developable_tube_is_flat_and_its_second_curvature_is_zero():
    """K = 0 everywhere on a right circular cylinder. This is the surface the tube caveat
    is about: every plate lands in the parabolic band and TPI is ill-conditioned."""
    s = TubeSurface(radius=5.0, height=20.0)
    assert s.is_developable
    for v in (1.0, 10.0, 19.0):
        k1, k2, _ = s.principal_at(0.7, v)
        assert abs(k1) == pytest.approx(1.0 / 5.0, rel=1e-6)
        assert k2 == pytest.approx(0.0, abs=1e-9)
        assert s.gaussian_at(0.7, v) == pytest.approx(0.0, abs=1e-9)


def test_the_tube_seam_wraps_and_its_ends_are_real_boundaries():
    s = TubeSurface(radius=5.0, height=20.0, barrel=0.2)
    assert s.topology.closed_u and not s.topology.is_closed_surface
    assert s.topology.boundary_v0 and s.topology.boundary_v1
    p = s.point_at(0.05, 7.0)
    u, v = s.closest_uv(p, 6.25, 7.0)
    assert min(abs(u - 0.05), 2 * math.pi - abs(u - 0.05)) < 1e-9
    assert np.allclose(s.point_at(u, v), p, atol=1e-9)


def test_the_developable_tube_area_is_the_closed_form_and_the_grid_agrees():
    from abm.surfaces import _grid_area
    s = TubeSurface(radius=5.0, height=20.0)
    assert s.area() == pytest.approx(2.0 * math.pi * 5.0 * 20.0)
    assert _grid_area(s, 48) == pytest.approx(s.area(), rel=1e-6)
