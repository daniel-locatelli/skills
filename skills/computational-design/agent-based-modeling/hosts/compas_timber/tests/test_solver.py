import math

import numpy as np
import pytest

from abm.seeding import auto_spacing, hex_seed
from abm.solver import Parameters, Solver, alignment_force, cohesion, separation
from abm.surfaces import MongeSurface, SphereSurface


def test_separation_is_zero_at_the_target_spacing():
    """algorithm.md 1: 'a separation force that does NOT vanish at s has its equilibrium at
    the cutoff radius ... maxDisp saturates at the step cap forever'."""
    assert separation(1.0, 1.0) == pytest.approx(0.0)
    assert separation(1.5, 1.0) == pytest.approx(0.0)
    assert separation(0.0, 1.0) == pytest.approx(1.0)          # full strength s at contact
    assert separation(0.5, 1.0) == pytest.approx(0.5)


def test_cohesion_is_zero_at_s_and_at_r_and_pulls_in_between():
    s, r = 1.0, 1.5
    assert cohesion(s, s, r) == pytest.approx(0.0)
    assert cohesion(r, s, r) == pytest.approx(0.0)
    assert cohesion(2.0, s, r) == pytest.approx(0.0)           # beyond the cutoff
    assert cohesion(0.5, s, r) == pytest.approx(0.0)           # below s: separation's job
    assert cohesion(1.25, s, r) < 0.0                          # toward the neighbour


def test_alignment_pushes_a_neighbour_off_an_asymptote_toward_a_principal_direction():
    """algorithm.md 1: U = -cos(12.phi), so the force must DECREASE |phi| for phi in
    (0, 15 deg). Get this backwards and the field becomes a repeller that drives the
    packing ONTO the asymptotic directions -- the exact failure the behaviour exists to
    fix, and one that no convergence test detects."""
    n = np.array([0.0, 0.0, 1.0])
    e1 = np.array([1.0, 0.0, 0.0])
    r, s, w, d = 1.5, 1.0, 0.3, 1.0
    for phi in [math.radians(3.0), math.radians(10.0), math.radians(14.0)]:
        t = d * np.array([math.cos(phi), math.sin(phi), 0.0])
        f = alignment_force(n, e1, 1.0, t, d, r, w, s)
        t2 = t - f                                             # agent a moves by +f
        assert abs(math.atan2(float(t2[1]), float(t2[0]))) < abs(phi)


def test_alignment_vanishes_at_the_fixed_points_of_the_12_fold_field():
    n, e1 = np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])
    for deg in [0.0, 15.0, 30.0, 45.0, 90.0]:
        phi = math.radians(deg)
        t = np.array([math.cos(phi), math.sin(phi), 0.0])
        assert np.linalg.norm(alignment_force(n, e1, 1.0, t, 1.0, 1.5, 0.3, 1.0)) < 1e-12


def test_alignment_is_inert_where_anisotropy_is_zero():
    """A sphere is umbilic; the field must do nothing there."""
    n, e1 = np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])
    t = np.array([math.cos(0.2), math.sin(0.2), 0.0])
    assert np.linalg.norm(alignment_force(n, e1, 0.0, t, 1.0, 1.5, 0.3, 1.0)) == 0.0


def test_alignment_is_not_pair_antisymmetric():
    """algorithm.md 1: evaluated in each agent's OWN frame with its OWN anisotropy. The
    natural vectorised 'visit each pair once, apply +/-f' formulation silently halves and
    corrupts the field."""
    n = np.array([0.0, 0.0, 1.0])
    e1_a = np.array([1.0, 0.0, 0.0])
    e1_b = np.array([math.cos(0.4), math.sin(0.4), 0.0])
    t = np.array([math.cos(0.2), math.sin(0.2), 0.0])
    f_ab = alignment_force(n, e1_a, 1.0, t, 1.0, 1.5, 0.3, 1.0)
    f_ba = alignment_force(n, e1_b, 0.6, -t, 1.0, 1.5, 0.3, 1.0)
    assert not np.allclose(f_ab, -f_ba)


def test_containment_foot_point_is_isoparametric_not_closest_on_the_curve():
    """algorithm.md 1: the foot point for the u = u0 edge is S(u0, a.v), and the force acts
    along the 3D direction from that point to the agent. It is NOT the closest point on the
    boundary curve. This changes every interior-plate statistic, so it is normative even
    though a true closest-point rule is defensible."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    solver = Solver(s, Parameters(count=150, layout="hex"))
    solver.place(np.array([[-9.7, 3.3]]))
    f = solver.containment_vector(0)
    away = solver.agents.p[0] - s.point_at(s.domain.u0, 3.3)
    assert np.linalg.norm(f) > 0.0
    assert float(f @ away) > 0.0
    assert np.linalg.norm(np.cross(f, away)) < 1e-9


def test_containment_is_zero_far_from_every_boundary():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    solver = Solver(s, Parameters(count=150))
    solver.place(np.array([[0.0, 0.0]]))
    assert np.linalg.norm(solver.containment_vector(0)) == 0.0


def test_no_containment_on_a_seam_or_a_pole():
    """algorithm.md 1/5: real boundaries get containment; seams and poles do not."""
    s = SphereSurface(radius=10.0)
    solver = Solver(s, Parameters(count=150, layout="random"))
    solver.place(np.array([[0.001, 1.5]]))                     # hard against seam and pole
    assert np.linalg.norm(solver.containment_vector(0)) == 0.0


def test_neighbour_set_is_exactly_the_agents_within_1_5_spacing():
    """algorithm.md 1: 'The neighbour set is EXACTLY the agents within r in 3D -- the data
    structure that finds them is free, the result set is not.'"""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    solver = Solver(s, p)
    solver.place(hex_seed(s, 150, rng=np.random.default_rng(1)))
    r = p.neighbour_radius_factor * p.spacing
    pos = solver.agents.p
    for i, ids in enumerate(solver.neighbours()):
        brute = {j for j in range(len(pos)) if j != i and np.linalg.norm(pos[j] - pos[i]) < r}
        assert set(int(x) for x in ids) == brute


def test_spacing_is_auto_and_written_back_once():
    """algorithm.md 6: written back into the parameter object once computed, and NOT
    recomputed after the seed rejects agents -- so an equilibrium packing sits about
    spacing.sqrt(count/realised) apart, ~7% above spacing at the default."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex")
    solver = Solver(s, p)
    assert p.spacing == pytest.approx(auto_spacing(s, 150), rel=1e-12)
    before = p.spacing
    solver.run()
    assert p.spacing == before


def test_the_step_is_jacobi_not_gauss_seidel():
    """algorithm.md 1: 'A Jacobi update is required, not incidental: a sequential
    (Gauss-Seidel) sweep converges to a different packing.' Under Jacobi, permuting the
    agent order permutes the result; under Gauss-Seidel it does not."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    uv = hex_seed(s, 60, rng=np.random.default_rng(5))
    perm = np.random.default_rng(0).permutation(len(uv))

    def one_step(seed_uv):
        solver = Solver(s, Parameters(count=60, layout="hex"))
        solver.place(seed_uv)
        solver.step()
        return solver.agents.p

    assert np.allclose(one_step(uv)[perm], one_step(uv[perm]), atol=1e-12)


def test_do_nothing_detector_is_seed_dependent():
    """algorithm.md 8 says 'maxDisplacement must fall by >= 2 orders of magnitude from the
    first iteration'. Unqualified, that criterion is SELF-FAILING on the hexagonal seed --
    measured here and confirmed against the C# reference, which is the implementation the
    criterion was written from:

        this host, hex seed 1/2/3 : 0.108/0.114/0.116 -> ~0.0019, ratio 57-61x
        C# harness, hex           : 0.1272 -> 0.0019 in 51 its, ratio 67x
        this host, random 1/2/3   : 0.960/0.696/0.894 -> ~0.0019, ratio 367-501x

    The reason is structural rather than Python-specific: a jittered hex seed at the auto
    angle starts close to equilibrium, so the first displacement is only ~0.06 of spacing,
    while the run terminates at 1e-3 of spacing. Two orders of magnitude is not available.
    The detector is sound -- it is the only thing here that catches a solver that runs but
    does nothing -- but its threshold has to be stated per seed. It is an
    algorithm.md defect for the Phase-4 skill edit.
    """
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    hexh = Solver(s, Parameters(count=150, layout="hex", rng_seed=1)).run().max_disp_history
    assert hexh[0] / hexh[-1] >= 40.0
    rndh = Solver(s, Parameters(count=150, layout="random", rng_seed=1)).run().max_disp_history
    assert rndh[0] / rndh[-1] >= 100.0                         # 2 orders, where it is available


def test_hex_seed_converges_within_the_measured_band():
    """algorithm.md 8: the hexagonal seed converges in ~50-200 iterations (measured 51-56)."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    result = Solver(s, Parameters(count=150, layout="hex", rng_seed=1)).run()
    assert result.converged
    assert result.iterations_run <= 200


def test_convergence_is_on_realised_post_reprojection_displacement():
    """algorithm.md 1: 'a step that gets projected back onto the surface counts as smaller'."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    p = Parameters(count=150, layout="hex", rng_seed=1)
    result = Solver(s, p).run()
    assert result.max_disp_history[-1] < p.convergence_factor * p.spacing


def test_agents_stay_on_the_surface():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    agents = Solver(s, Parameters(count=150, layout="hex", rng_seed=2)).run().agents
    for uv, p in zip(agents.uv, agents.p):
        assert np.allclose(s.point_at(uv[0], uv[1]), p, atol=1e-9)


def test_principal_frame_is_evaluated_with_the_alignment_field_off():
    """algorithm.md 4: gating the frame on the weight makes the alignment mean unmeasurable
    with the field off, which is exactly the before/after comparison section 8 needs."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    agents = Solver(s, Parameters(count=150, layout="hex", alignment_weight=0.0)).run().agents
    assert float(np.max(agents.anis)) > 0.5


def test_centroid_weight_is_not_implemented_in_v1():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    with pytest.raises(NotImplementedError):
        Solver(s, Parameters(count=60, centroid_weight=0.2)).run()
