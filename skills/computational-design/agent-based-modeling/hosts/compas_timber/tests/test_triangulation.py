import numpy as np
import pytest

from abm.plates import (assert_half_edge_invariant, flip_3d, half_edge_table, hull_agents,
                        orient_ccw, triangulate_open)
from abm.solver import Parameters, Solver
from abm.surfaces import MongeSurface

UP = np.array([0.0, 0.0, 1.0])


@pytest.fixture(scope="module")
def relaxed():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    result = Solver(s, Parameters(count=150, layout="hex", rng_seed=1)).run()
    return s, result.agents


def test_orient_ccw_flips_a_clockwise_triangle():
    """algorithm.md 3.1: Qhull and most library triangulators return simplices in arbitrary
    orientation, and the fan walk, the hole finder and the convexity test all read
    orientation. All three break SILENTLY on a mixed mesh."""
    p = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    n = np.tile(UP, (3, 1))
    out = orient_ccw(np.array([[0, 2, 1]]), p, n)
    assert list(out[0]) in ([0, 1, 2], [1, 2, 0], [2, 0, 1])


def test_orient_ccw_leaves_a_ccw_triangle_alone():
    p = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    n = np.tile(UP, (3, 1))
    assert list(orient_ccw(np.array([[0, 1, 2]]), p, n)[0]) == [0, 1, 2]


def test_half_edge_invariant_holds_on_a_relaxed_patch(relaxed):
    """algorithm.md 3.1: every interior edge carries exactly two oppositely-directed
    half-edges. This is the invariant to assert."""
    s, agents = relaxed
    assert_half_edge_invariant(triangulate_open(agents.uv, agents.p, agents.n))


def test_half_edge_invariant_rejects_a_mixed_orientation_mesh():
    """Two triangles sharing edge (1,2) but traversing it in the SAME direction."""
    bad = np.array([[0, 1, 2], [1, 2, 3]])
    table = half_edge_table(bad)
    assert table[(1, 2)] == 2                       # the same half-edge twice: not a manifold
    with pytest.raises(AssertionError):
        assert_half_edge_invariant(bad)


def test_flip_3d_shortens_the_diagonal_on_a_stretched_quad():
    """algorithm.md 3.1: uv-Delaunay is not 3D-Delaunay on a stretched patch (S14/T08).

    A thin rhombus: the long diagonal 0-2 is 10 units, the short diagonal 1-3 is 0.4.
    (A rectangle is the wrong test shape here -- both of its diagonals are the same
    length, so a correct implementation makes no flip and the test proves nothing.)
    """
    quad = np.array([[0.0, 0.0], [5.0, -0.2], [10.0, 0.0], [5.0, 0.2]])
    p = np.column_stack([quad, np.zeros(4)])
    out = flip_3d(np.array([[0, 1, 2], [0, 2, 3]]), quad, p)
    edges = {tuple(sorted((int(t[i]), int(t[(i + 1) % 3])))) for t in out for i in range(3)}
    assert (1, 3) in edges and (0, 2) not in edges          # flipped to the shorter diagonal


def test_flip_3d_makes_no_flip_when_the_diagonals_tie():
    """Ties are broken strictly with `<` (algorithm.md 3.1), so a rectangle is left alone.
    Without the strict comparison the pass would flip back and forth and never converge."""
    quad = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 1.0], [0.0, 1.0]])
    p = np.column_stack([quad, np.zeros(4)])
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    assert np.array_equal(flip_3d(tris, quad, p), tris)


def test_flip_3d_refuses_a_flip_that_would_leave_a_non_convex_quad():
    """algorithm.md 3.1: 'if the flipped pair stays a convex CCW quad in uv'."""
    uv01 = np.array([[0.0, 0.0], [1.0, 0.0], [0.45, 0.1], [0.0, 1.0]])   # 2 is reflex
    p = np.column_stack([uv01, np.zeros(4)])
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    assert np.array_equal(flip_3d(tris, uv01, p), tris)


def test_flip_3d_terminates_and_preserves_the_triangle_count(relaxed):
    """The pass is order-dependent by design -- at most one flip per triangle per pass,
    ties broken strictly -- so it must be shown to terminate. A flip never changes the
    triangle count."""
    s, agents = relaxed
    uv01 = (agents.uv - agents.uv.min(axis=0)) / (agents.uv.max(axis=0) - agents.uv.min(axis=0))
    tris = triangulate_open(agents.uv, agents.p, agents.n)
    assert len(flip_3d(tris, uv01, agents.p)) == len(tris)


def test_triangle_count_matches_the_planar_euler_identity(relaxed):
    """Reported as an IDENTITY (algorithm.md 8c), never as evidence: F = 2n - 2 - h for a
    triangulated planar point set with h hull points. Included so that a wrong triangle
    count is caught early, not so that a right one proves anything."""
    s, agents = relaxed
    tris = triangulate_open(agents.uv, agents.p, agents.n)
    assert len(tris) == 2 * len(agents.uv) - 2 - len(hull_agents(tris))


def test_hull_agents_lie_on_the_domain_edge(relaxed):
    """Hull agents are those incident to an open edge of the mesh (AbmCore.cs:734).

    On the egg-crate that is a SMALL set -- the convex-hull ring, measured 12 of 131, not
    the whole outer band. The boundary drop is much wider than hull adjacency for two other
    reasons: an agent on the hull never produces a plate at all (it fails 3.3's interior
    test), and TouchesBoundary also fires on the ill-shaped condition. Asserting a large
    hull here would have encoded a misreading of 3.3 into the test suite.
    """
    s, agents = relaxed
    hull = hull_agents(triangulate_open(agents.uv, agents.p, agents.n))
    assert 8 <= len(hull) <= 24
    d = s.domain
    for i in hull:
        u, v = agents.uv[i]
        assert min(u - d.u0, d.u1 - u, v - d.v0, d.v1 - v) < 3.0
