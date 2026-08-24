"""The seam/pole triangulation path (algorithm.md 3.1).

DEVIATION FROM THE PLAN TEXT. The plan's tests call `triangulate(s, agents, 1.0)`, via
`Parameters(count=150).spacing or 1.0` -- `spacing` defaults to 0.0, so that expression is
always 1.0 and never the auto spacing it was meant to stand for. Measured, the relaxed
sphere's auto spacing is 3.1102 and its mean nearest-neighbour distance is 2.934, so a
`2 * 1.0` search radius sees NO neighbours whatever and every one of these tests would fail
against a correct implementation. The fixture therefore carries the run's own spacing, which
is what the plan meant. The test was wrong, not the implementation.
"""

import numpy as np
import pytest

from abm.plates import (assert_half_edge_invariant, fill_small_holes, triangulate,
                        triangulate_closed)
from abm.solver import Parameters, Solver
from abm.surfaces import SphereSurface


@pytest.fixture(scope="module")
def sphere_relaxed():
    s = SphereSurface(radius=10.0)
    result = Solver(s, Parameters(count=150, layout="random", rng_seed=1)).run()
    return s, result.agents, result.spacing


def test_sphere_closes_and_every_agent_gets_a_plate(sphere_relaxed):
    """algorithm.md 8: sphere, plates = agents. On a closed surface, unlike an open patch."""
    s, agents, spacing = sphere_relaxed
    tris = triangulate(s, agents, spacing)
    assert set(np.unique(tris).tolist()) == set(range(len(agents.p)))


def test_sphere_triangulation_is_closed_and_euler_is_two(sphere_relaxed):
    """Reported as an IDENTITY (8c): 'a jittered seed with zero iterations passes it'."""
    s, agents, spacing = sphere_relaxed
    tris = triangulate(s, agents, spacing)
    v = len(agents.p)
    edges = {tuple(sorted((int(t[i]), int(t[(i + 1) % 3])))) for t in tris for i in range(3)}
    assert v - len(edges) + len(tris) == 2
    assert_half_edge_invariant(tris)


def test_triangle_count_is_2n_minus_4(sphere_relaxed):
    """Also an identity, not evidence."""
    s, agents, spacing = sphere_relaxed
    assert len(triangulate(s, agents, spacing)) == 2 * len(agents.p) - 4


def test_unanimity_leaves_holes_that_the_filler_closes(sphere_relaxed):
    """algorithm.md 3.1: near-cocircular quads leave small holes where nobody is unanimous."""
    s, agents, spacing = sphere_relaxed
    raw = triangulate_closed(agents.p, agents.n, spacing)
    filled = fill_small_holes(raw, agents.p)
    assert len(filled) >= len(raw)
    assert len(filled) == 2 * len(agents.p) - 4


def test_fill_small_holes_leaves_a_long_loop_open():
    """algorithm.md 3.1: 'Longer loops are real boundaries (cylinder-like surfaces) and stay
    open.' A 12-edge ring must not be ear-clipped shut."""
    m = 12
    ang = np.linspace(0, 2 * np.pi, m, endpoint=False)
    p = np.column_stack([np.cos(ang), np.sin(ang), np.zeros(m)])
    p = np.vstack([p, np.column_stack([np.cos(ang), np.sin(ang), np.ones(m)])])
    tris = []
    for i in range(m):                       # an open tube band: two 12-edge boundary loops
        j = (i + 1) % m
        tris += [[i, j, m + i], [j, m + j, m + i]]
    tris = np.array(tris)
    assert np.array_equal(fill_small_holes(tris, p), tris)


def test_triangulate_dispatches_on_topology(sphere_relaxed):
    """algorithm.md 3.1: 'Do not use the unanimity path on an open patch.'"""
    from abm.surfaces import MongeSurface
    s, agents, spacing = sphere_relaxed
    assert s.topology.is_non_trivial
    assert not MongeSurface().topology.is_non_trivial


def test_a_boundary_chain_through_a_pinch_vertex_splits_into_its_sub_cycles():
    """A pinch vertex appears TWICE in one boundary chain. Ear-clipping that as a single
    polygon spans the pinch and adds overlapping triangles; splitting at the repeat gives
    two genuine holes. Measured on sphere seed 5, where the chain is
    [86, 58, 138, 145, 58, 51] -- two triangular holes meeting at agent 58."""
    from abm.plates import _split_at_repeats
    assert _split_at_repeats([86, 58, 138, 145, 58, 51]) == [[58, 138, 145], [86, 58, 51]]
    assert _split_at_repeats([1, 2, 3, 4]) == [[1, 2, 3, 4]]        # no repeat, no split


def test_the_pinch_vertex_seed_closes_the_sphere_completely():
    """Regression for the one seed in six that produces a pinch vertex.

    Before the split, this seed left a hole open: 292 of 296 triangles, Euler 1, and 138 of
    150 plates -- twelve agents losing their plate to one unfilled triangle. Filling the
    pinched chain as a single polygon was worse still (298 triangles, Euler 3, 113 plates).
    """
    s = SphereSurface(radius=10.0)
    result = Solver(s, Parameters(count=150, layout="random", rng_seed=5)).run()
    agents = result.agents
    stats = {}
    raw = triangulate_closed(agents.p, agents.n, result.spacing)
    filled = fill_small_holes(raw, agents.p, stats=stats)
    assert stats["pinch_vertices"] == 1
    assert len(filled) == 2 * len(agents.p) - 4
    assert_half_edge_invariant(filled)
    edges = {tuple(sorted((int(t[i]), int(t[(i + 1) % 3])))) for t in filled for i in range(3)}
    assert len(agents.p) - len(edges) + len(filled) == 2


def test_local_triangulation_survives_a_degenerate_neighbourhood():
    """Most library Delaunay implementations raise on collinear/cocircular sets."""
    p = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    n = np.tile(np.array([0.0, 0.0, 1.0]), (4, 1))
    tris = triangulate_closed(p, n, 10.0)                # collinear: no triangle, no exception
    assert len(tris) == 0
