import numpy as np
import pytest

from abm.plates import Plate, build_plates, circumcentre, classify, tpi_point, triangulate
from abm.solver import Parameters, Solver
from abm.surfaces import MongeSurface, SphereSurface


class _A:
    def __init__(self, p, n):
        self.p, self.n = np.asarray(p, float), np.asarray(n, float)


def test_tpi_of_three_coplanar_tangent_planes_is_the_common_plane_fallback():
    """algorithm.md 3.2: near K = 0 the three planes are almost parallel, the system is
    ill-conditioned and the point flies off -- the parabolic band ALWAYS needs the fallback.

    DEVIATION FROM THE PLAN TEXT. The plan asserts the fallback point is the CENTROID. It is
    not: 3.2's last line is `if not solved: x = cc`, and `cc` is the centroid only when the
    triangle is ill-shaped or its circumcentre denominator is degenerate. Neither holds here
    -- the circumradius is 0.625 against a `2 * spacing` limit of 2.0 -- so the fallback is
    the Voronoi vertex, which is what "plates degrade to Voronoi cells there" means. What
    the test's own name claims is still true and is what is asserted: the fallback point
    lies in the three agents' common tangent plane.
    """
    a = _A([0.0, 0.0, 0.0], [0.0, 0.0, 1.0])
    b = _A([1.0, 0.0, 0.0], [0.0, 0.0, 1.0])
    c = _A([0.5, 1.0, 0.0], [0.0, 0.0, 1.0])
    x, fallback = tpi_point(a, b, c, 1.0)
    assert fallback
    assert np.allclose(x, circumcentre(a.p, b.p, c.p, 1.0), atol=1e-12)
    assert abs(float(x[2])) < 1e-12                   # in the common tangent plane z = 0
    assert not np.allclose(x, (a.p + b.p + c.p) / 3.0, atol=1e-9)


def test_the_fallback_is_the_centroid_only_when_the_triangle_is_ill_shaped():
    """The other half of the same rule: `cc = centroid` is set INSIDE the ill-shaped branch.

    Same three coplanar tangent planes, spacing shrunk until the circumradius exceeds
    `2 * spacing`. Nothing about the geometry changed; only which branch it lands in.
    """
    a = _A([0.0, 0.0, 0.0], [0.0, 0.0, 1.0])
    b = _A([1.0, 0.0, 0.0], [0.0, 0.0, 1.0])
    c = _A([0.5, 1.0, 0.0], [0.0, 0.0, 1.0])
    x, fallback = tpi_point(a, b, c, 0.1)             # R = 0.625 > 2 * 0.1
    assert fallback
    assert np.allclose(x, (a.p + b.p + c.p) / 3.0, atol=1e-12)


def test_tpi_of_a_spherical_triple_is_above_the_triangle():
    """Three tangent planes of a sphere meet outside it, on the far side of the triangle."""
    s = SphereSurface(radius=10.0)
    uvs = [(0.0, 0.0), (0.12, 0.0), (0.06, 0.11)]
    tri = [_A(s.point_at(u, v), s.normal_at(u, v)) for u, v in uvs]
    x, fallback = tpi_point(tri[0], tri[1], tri[2], 1.0)
    assert not fallback
    assert np.linalg.norm(x) > 10.0


def test_ill_shaped_triangle_skips_the_circumcircle_test_entirely():
    """algorithm.md 3.2: the branches are mutually exclusive (if / elif). An ill-shaped
    triangle NEVER reaches the S14 validity test."""
    s = SphereSurface(radius=10.0)
    uvs = [(0.0, 0.0), (0.02, 0.0), (0.9, 0.0005)]        # near-collinear, huge circumradius
    tri = [_A(s.point_at(u, v), s.normal_at(u, v)) for u, v in uvs]
    x, fallback = tpi_point(tri[0], tri[1], tri[2], 0.2)
    centroid = sum(t.p for t in tri) / 3.0
    assert fallback or np.linalg.norm(x - centroid) <= 2 * 0.2


def test_fallback_share_on_the_eggcrate_is_in_the_measured_band():
    """algorithm.md 8: 'TPI fallbacks 25-35% of triangles', same for both seeds."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    agents = Solver(s, p).run().agents
    tris = triangulate(s, agents, p.spacing)
    ps = build_plates(s, agents, tris, p.spacing)
    share = ps.fallback_count / ps.triangle_count
    assert 0.25 <= share <= 0.35


def test_sphere_has_zero_fallbacks():
    """algorithm.md 8: sphere R=10, '0 TPI fallbacks'. Uniform positive curvature, no
    parabolic band anywhere."""
    s = SphereSurface(radius=10.0)
    p = Parameters(count=150, layout="random", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    assert ps.fallback_count == 0


def _tangent_plane_deviation(plate, agents):
    n = agents.n[plate.agent_index]
    return np.abs((plate.ring - agents.p[plate.agent_index]) @ n)


def test_a_genuine_tpi_vertex_is_planar_by_construction():
    """algorithm.md 3.3: 'planar by construction (all points lie in the agent's tangent
    plane)' -- true of a vertex that came from the three-plane solve, because the agent's
    own tangent plane is one of the three. Exactly, to machine precision."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    for plate in ps.plates:
        d = _tangent_plane_deviation(plate, agents)[~plate.ring_is_fallback]
        if len(d):
            assert float(np.max(d)) < 1e-9 * p.spacing


def test_a_fallback_vertex_is_not_planar_and_the_ring_needs_planarising():
    """algorithm.md 3.3: the ring is planar only where every vertex came from the TPI solve.

    The plan asserts EVERY ring is planar to `1e-9 * spacing`. It is not, and cannot be: a
    fallback vertex is a circumcentre or a centroid, neither of which lies in the agent's
    tangent plane, and 3.2 puts 29 % of the egg-crate's triangles on that path. Measured
    here: 50 of 85 interior plates carry at least one fallback vertex, deviating by up to
    0.208 against a spacing of 1.9207, i.e. 11 % of spacing -- not a rounding error.

    So the ring is planar by construction only where no guard fired, and the planarisation
    step in timber.py is mandatory rather than a nicety. This test pins that, so a later
    change that quietly projects the ring into the tangent plane cannot pass unnoticed."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    interior = [pl for pl in ps.plates if not pl.touches_boundary]
    with_fallback = [pl for pl in interior if pl.ring_is_fallback.any()]
    assert 0.4 <= len(with_fallback) / len(interior) <= 0.8
    worst = max(float(np.max(_tangent_plane_deviation(pl, agents))) for pl in with_fallback)
    assert 0.02 * p.spacing < worst < 0.30 * p.spacing


def test_on_the_sphere_every_ring_is_planar_because_nothing_falls_back():
    """The clean case, and the reason A4 is about the fallback and not about TPI: the
    sphere has 0 fallbacks (8), so every ring there IS planar by construction."""
    s = SphereSurface(radius=10.0)
    p = Parameters(count=150, layout="random", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    assert ps.fallback_count == 0
    for plate in ps.plates:
        assert float(np.max(_tangent_plane_deviation(plate, agents))) < 1e-9 * p.spacing


def _plate(k):
    ring = np.zeros((6, 3))
    return Plate(agent_index=0, ring=ring, ring_is_fallback=np.zeros(6, bool),
                 touches_boundary=False, is_convex=True, k=k, side_ratio=1.0)


def test_the_band_is_recomputed_over_whatever_plate_list_is_passed():
    """algorithm.md, Classification: 'max|K| is taken over the CURRENT plate set,
    recomputed on every call.'

    DEVIATION FROM THE PLAN TEXT. The plan tests this by asserting that dropping the
    egg-crate's boundary plates MOVES max|K|. Measured, it does not: max|K| = 0.087664 over
    all 119 plates and over the 85 interior ones alike, because the extreme curvature of an
    egg-crate sits at the dome tops and valley floors, which are interior. That is an
    accident of this surface, not the rule -- so the rule is tested directly instead, and
    the accident is what the next test records.
    """
    plates = [_plate(1.0), _plate(0.05)]
    classify(plates)
    assert [pl.curvature_class for pl in plates] == ["elliptic", "parabolic"]
    classify(plates[1:])                              # same plate, smaller population
    assert plates[1].curvature_class == "elliptic"    # now it IS the maximum


def test_boundary_plates_are_left_unclassified_because_the_drop_comes_first():
    """algorithm.md 3: 'build plates -> drop boundary plates -> classify.' A boundary plate
    is dropped before classification, so a class on it would come from a band it was never
    measured in. Also records the egg-crate accident: the drop leaves max|K| where it was."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    interior = [pl for pl in ps.plates if not pl.touches_boundary]
    assert all(pl.curvature_class is None for pl in ps.plates if pl.touches_boundary)
    assert all(pl.curvature_class is not None for pl in interior)
    assert max(abs(pl.k) for pl in interior) == max(abs(pl.k) for pl in ps.plates)


def test_touches_boundary_includes_ill_shaped_not_only_hull_adjacency():
    """algorithm.md 3.3: 'Both conditions, not just hull adjacency.'"""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    agents = Solver(s, p).run().agents
    ps = build_plates(s, agents, triangulate(s, agents, p.spacing), p.spacing)
    assert sum(1 for pl in ps.plates if pl.touches_boundary) > 0
