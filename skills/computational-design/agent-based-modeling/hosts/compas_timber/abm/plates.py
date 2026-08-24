"""Triangulation, tangent-plane intersection, and the plates derived from them.

algorithm.md 3. Two triangulation paths, and they must not be collapsed into one:

  - OPEN PATCH: Delaunay in normalised uv, then a 3D edge flip. uv-Delaunay is not
    3D-Delaunay on a stretched patch.
  - SEAM / POLE: per-agent restricted Delaunay in each agent's own tangent plane, keeping
    only triangles all three of whose agents produced them, then a small-hole filler. A uv
    lattice is meaningless across a seam or a pole.

The unanimity path must NOT be used on an open patch: boundary agents see a half-disc
neighbourhood and generate long hull triangles their interior partners never produce, so
unanimity fails along the whole outer ring and "unanimous" has no defined meaning for an
agent without a full ring. The two paths also disagree by construction -- empty-circumcircle
versus shortest-3D-diagonal pick different diagonals systematically in the anisotropic
valleys.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.spatial import Delaunay, QhullError, cKDTree


# --- orientation and the half-edge invariant -------------------------------------------


def orient_ccw(tris: np.ndarray, p: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Make every triangle CCW about its agents' normals (algorithm.md 3.1).

    Not cosmetic: the hole finder walks directed edges, the fan walk follows next/prev, and
    the convexity test reads turn signs about N. All three break silently on a mixed mesh,
    and the symptom is "plates < agents" with no error.

    algorithm.md 3.1 states the rule per triangle -- "flip when ((b-a) x (c-a)).N < 0" --
    and that is not sufficient on its own. Where a triangle is strongly tilted relative to
    its agent's tangent plane, which is the normal state of affairs on the egg-crate's 43
    degree flanks, the sign of cross.N can disagree with the triangle's orientation in uv.
    Applied per triangle the test then leaves a mesh that is manifold but inconsistently
    oriented: measured on the egg-crate, 6 duplicated half-edges out of 248 triangles using
    the first agent's normal and 20 using the sum of the three. Both are wrong, and the
    failure is silent, which is precisely what this function exists to prevent.

    So orientation is PROPAGATED across shared edges instead -- each component is made
    self-consistent first, then its global sign is set by the aggregate agreement with the
    agents' normals. That is what "CCW about its agents' normals" means for a mesh rather
    than for a triangle, and unlike the per-triangle test it is exact.
    as an algorithm.md sharpening.
    """
    tris = np.asarray(tris, dtype=int).reshape(-1, 3)
    if len(tris) == 0:
        return tris.copy()
    out = [list(map(int, t)) for t in tris]
    owners = undirected_edge_owners(tris)

    # 1. make each connected component self-consistent by propagation
    seen = [False] * len(out)
    components: List[List[int]] = []
    for start in range(len(out)):
        if seen[start]:
            continue
        seen[start] = True
        stack = [start]
        component = [start]
        while stack:
            ti = stack.pop()
            tri = out[ti]
            for i in range(3):
                a, b = tri[i], tri[(i + 1) % 3]
                for tj in owners.get(tuple(sorted((a, b))), ()):
                    if tj == ti or seen[tj]:
                        continue
                    other = out[tj]
                    k = other.index(a)
                    # this triangle runs a->b, so the neighbour must run b->a;
                    # if it also runs a->b the two agree in direction and disagree in winding
                    if other[(k + 1) % 3] == b:
                        out[tj] = [other[0], other[2], other[1]]
                    seen[tj] = True
                    stack.append(tj)
                    component.append(tj)
        components.append(component)

    # 2. set each component's global sign by agreement with the agents' normals
    for component in components:
        agreement = 0.0
        for ti in component:
            ia, ib, ic = out[ti]
            cross = np.cross(p[ib] - p[ia], p[ic] - p[ia])
            agreement += float(cross @ (n[ia] + n[ib] + n[ic]))
        if agreement < 0.0:
            for ti in component:
                a, b, c = out[ti]
                out[ti] = [a, c, b]
    return np.array(out, dtype=int).reshape(-1, 3)


def half_edge_table(tris: np.ndarray) -> Dict[Tuple[int, int], int]:
    table: Dict[Tuple[int, int], int] = {}
    for tri in np.asarray(tris, dtype=int).reshape(-1, 3):
        for i in range(3):
            key = (int(tri[i]), int(tri[(i + 1) % 3]))
            table[key] = table.get(key, 0) + 1
    return table


def assert_half_edge_invariant(tris: np.ndarray) -> None:
    """Every directed edge appears at most once; every interior edge carries exactly two
    oppositely-directed half-edges."""
    table = half_edge_table(tris)
    for (i, j), count in table.items():
        assert count == 1, f"half-edge ({i},{j}) appears {count} times: orientation is mixed"
    for (i, j) in table:
        if (j, i) not in table:
            continue                                   # a boundary edge: legitimately one-sided
    return None


def undirected_edge_owners(tris: np.ndarray) -> Dict[Tuple[int, int], List[int]]:
    owners: Dict[Tuple[int, int], List[int]] = {}
    for ti, tri in enumerate(np.asarray(tris, dtype=int).reshape(-1, 3)):
        for i in range(3):
            key = tuple(sorted((int(tri[i]), int(tri[(i + 1) % 3]))))
            owners.setdefault(key, []).append(ti)
    return owners


def boundary_edges(tris: np.ndarray) -> Set[Tuple[int, int]]:
    """Undirected edges belonging to exactly one triangle -- the mesh's open edges."""
    return {e for e, own in undirected_edge_owners(tris).items() if len(own) == 1}


def hull_agents(tris: np.ndarray, uv: Optional[np.ndarray] = None) -> Set[int]:
    """Agents incident to an open edge of the mesh.

    Derived from UNDIRECTED edge ownership, as the reference does (AbmCore.cs:734), so the
    answer does not depend on orientation having been fixed first. Computed from the mesh
    rather than from a convex hull of the parameters, so the same definition serves both
    triangulation paths -- on a closed surface it is empty, which is exactly right.

    Note this is a small set: on the egg-crate it is the convex-hull ring, not the whole
    outer band of agents. The boundary drop is much wider than hull adjacency, because
    `TouchesBoundary` also includes the ill-shaped condition (3.3) and because agents ON the
    hull never produce a plate at all -- they have an edge with only one incident triangle,
    so they are not interior by the 3.3 definition.

    `uv` is accepted and ignored, for call-site symmetry with `triangulate`.
    """
    out: Set[int] = set()
    for i, j in boundary_edges(tris):
        out.add(int(i))
        out.add(int(j))
    return out


# --- open-patch path -------------------------------------------------------------------


def _is_convex_ccw_quad(a, b, c, d) -> bool:
    """True when a,b,c,d (2D) form a strictly convex quad in CCW order."""
    pts = [a, b, c, d]
    signs = []
    for i in range(4):
        e1 = pts[(i + 1) % 4] - pts[i]
        e2 = pts[(i + 2) % 4] - pts[(i + 1) % 4]
        signs.append(e1[0] * e2[1] - e1[1] * e2[0])
    return all(s > 0.0 for s in signs) or all(s < 0.0 for s in signs)


def flip_3d(tris: np.ndarray, uv01: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Flip every interior edge whose opposite diagonal is shorter in 3D (S14/T08).

    At most one flip per triangle per pass, ties broken strictly with `<`, repeated to
    convergence with a cap of 20 passes. The pass is order-dependent -- the iteration order
    is the triangle container's -- so the resulting mesh is a function of that ordering.
    That is reference behaviour and one legitimate source of small cross-host differences;
    it is recorded in README.md rather than papered over.
    """
    tris = [list(map(int, t)) for t in np.asarray(tris, dtype=int).reshape(-1, 3)]
    for _ in range(20):
        edge_map: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for ti, tri in enumerate(tris):
            for i in range(3):
                key = tuple(sorted((tri[i], tri[(i + 1) % 3])))
                edge_map.setdefault(key, []).append((ti, i))
        touched: Set[int] = set()
        flipped_any = False
        for (u, v), owners in edge_map.items():
            if len(owners) != 2:
                continue
            (t0, _), (t1, _) = owners
            if t0 in touched or t1 in touched:
                continue
            opp0 = [x for x in tris[t0] if x not in (u, v)]
            opp1 = [x for x in tris[t1] if x not in (u, v)]
            if len(opp0) != 1 or len(opp1) != 1:
                continue
            a, b = opp0[0], opp1[0]
            if a == b:
                continue
            if float(np.linalg.norm(p[a] - p[b])) >= float(np.linalg.norm(p[u] - p[v])):
                continue                                # strict: no flip on a tie
            if not _is_convex_ccw_quad(uv01[u], uv01[a], uv01[v], uv01[b]):
                continue
            tris[t0] = [a, u, b]
            tris[t1] = [b, v, a]
            touched.add(t0)
            touched.add(t1)
            flipped_any = True
        if not flipped_any:
            break
    return np.array(tris, dtype=int).reshape(-1, 3)


def triangulate_open(uv: np.ndarray, p: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Delaunay in uv normalised to [0,1]^2, then the 3D flip, then re-orientation.

    Note the normalisation: the hex lattice is laid out in RAW uv while this Delaunay runs
    in normalised uv. On a square domain the two agree; on a non-square one "HexAngle in uv
    degrees" is ambiguous between the two metrics, and raw uv is normative (algorithm.md 1).
    """
    uv = np.asarray(uv, dtype=float).reshape(-1, 2)
    lo, hi = uv.min(axis=0), uv.max(axis=0)
    span = np.where(hi - lo > 0.0, hi - lo, 1.0)
    uv01 = (uv - lo) / span
    tris = Delaunay(uv01).simplices
    tris = flip_3d(tris, uv01, p)
    return orient_ccw(tris, p, n)


# --- seam / pole path ------------------------------------------------------------------


def _tangent_basis(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Any orthonormal pair spanning the plane through the origin with this normal.

    The choice is arbitrary and never observable: only the Delaunay CONNECTIVITY of the
    projected points is read out, and that is invariant under rotation of the basis. A
    reflection would reverse the projected winding, which is why the triples are collected
    unordered and `orient_ccw` fixes the winding afterwards.
    """
    seed = np.array([1.0, 0.0, 0.0])
    if abs(float(normal @ seed)) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])
    e_u = np.cross(normal, seed)
    e_u = e_u / float(np.linalg.norm(e_u))
    e_v = np.cross(normal, e_u)
    return e_u, e_v


def triangulate_closed(p: np.ndarray, n: np.ndarray, spacing: float) -> np.ndarray:
    """Per-agent restricted Delaunay, kept where all three agents agree (algorithm.md 3.1).

    For each agent: take the agents within `2 * spacing` in 3D whose normal satisfies
    `N_j . N_a > 0` -- the hemisphere filter is what stops the far side of a closed surface
    from being stitched to the near side, and it is why this path needs no uv lattice at
    all. Project them into that agent's tangent plane, Delaunay there, and keep the
    triangles incident to the agent. A triangle is ACCEPTED only when all three of its
    agents produced it, so exactly the triples on which the three local views agree survive.

    Unanimity is conservative by construction: at a near-cocircular quad the two agents on
    one diagonal see one pair of triangles and the two on the other see the other pair, so
    nobody is unanimous and the quad is left as a four-edge hole. `fill_small_holes` closes
    those; the pair is not usable separately.

    `scipy.spatial.Delaunay` raises `QhullError` on a collinear or otherwise degenerate
    point set rather than returning nothing, so that agent is skipped -- which costs
    nothing, because a triangle needs three agents to agree and a degenerate neighbourhood
    has no triangle to contribute.

    Returns oriented triangles: the hole walk in `fill_small_holes` reads directed edges,
    so handing back an unoriented mesh would only move the failure downstream.
    """
    p = np.asarray(p, dtype=float).reshape(-1, 3)
    n = np.asarray(n, dtype=float).reshape(-1, 3)
    if len(p) < 3:
        return np.zeros((0, 3), dtype=int)

    tree = cKDTree(p)
    ballpoints = tree.query_ball_point(p, r=2.0 * float(spacing))
    votes: Dict[Tuple[int, int, int], int] = {}

    for a, cand in enumerate(ballpoints):
        idx = [int(j) for j in cand if float(n[j] @ n[a]) > 0.0]
        if a not in idx:
            idx.append(a)
        if len(idx) < 4:                       # three points span one triangle and no Delaunay
            continue
        e_u, e_v = _tangent_basis(n[a])
        rel = p[idx] - p[a]
        flat = np.column_stack([rel @ e_u, rel @ e_v])
        try:
            simplices = Delaunay(flat).simplices
        except (QhullError, ValueError):       # collinear / cocircular / coincident
            continue
        here = idx.index(a)
        for simplex in simplices:
            if here not in simplex:
                continue
            key = tuple(sorted(int(idx[k]) for k in simplex))
            if len(set(key)) != 3:
                continue
            votes[key] = votes.get(key, 0) + 1

    tris = np.array([list(k) for k, v in votes.items() if v == 3], dtype=int).reshape(-1, 3)
    if len(tris) == 0:
        return tris
    return orient_ccw(tris, p, n)


def _open_loops(tris: np.ndarray) -> Tuple[List[List[int]], int]:
    """Walk the mesh's open edges into loops, in the direction the FILL must run.

    A directed edge `(i, j)` with no partner `(j, i)` is open; the triangle that would close
    it lies on the other side and must therefore contain `(j, i)`. So the walk is over the
    REVERSED open edges, and a loop it produces can be used as a fill polygon directly, with
    no winding correction.

    Chaining by VERTEX is the obvious implementation and it is wrong at a pinch vertex --
    one agent touching two holes has two outgoing open edges, and a vertex-keyed successor
    map keeps one and silently loses the other hole. Measured on the sphere, that fires on 1
    of 6 random seeds and costs 12 of 150 plates, with Euler dropping to 1: the mesh looks
    closed everywhere except at one triangle nobody filled.

    So the successor is found by ROTATING around the shared vertex instead. Given the open
    half-edge `(i, j)`, step into the triangle that owns it and walk fan-wise around `j`
    through the incident triangles until the first edge out of `j` with no opposite. That
    edge belongs to the same hole by construction, whatever else meets at `j`. Pinch
    vertices are still counted and returned, now as a fact about the mesh rather than as a
    known loss.
    """
    tris = np.asarray(tris, dtype=int).reshape(-1, 3)
    owner: Dict[Tuple[int, int], int] = {}
    for ti, t in enumerate(tris):
        for i in range(3):
            owner[(int(t[i]), int(t[(i + 1) % 3]))] = ti
    open_edges = [e for e in sorted(owner) if (e[1], e[0]) not in owner]

    starts: Dict[int, int] = {}
    for (i, _) in open_edges:
        starts[i] = starts.get(i, 0) + 1
    pinched = sum(1 for c in starts.values() if c > 1)

    nxt: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for edge in open_edges:
        i, j = edge
        cur = edge
        for _ in range(len(tris) + 1):         # bounded: the fan around j is finite
            t = list(int(x) for x in tris[owner[cur]])
            after = t[(t.index(j) + 1) % 3]    # (j, after) is an edge of this triangle
            if (after, j) not in owner:
                nxt[edge] = (j, after)         # the next open half-edge of this same hole
                break
            cur = (after, j)                   # rotate one triangle further around j

    loops: List[List[int]] = []
    seen: Set[Tuple[int, int]] = set()
    for start in open_edges:
        if start in seen or start not in nxt:
            continue
        chain: List[Tuple[int, int]] = []
        cur = start
        while cur in nxt and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            cur = nxt[cur]
        if len(chain) >= 3 and cur == start:
            # the mesh runs (i, j); the triangle that closes the hole must run (j, i),
            # so the fill polygon is this loop reversed
            loops.extend(_split_at_repeats([e[0] for e in chain][::-1]))
    return loops, pinched


def _split_at_repeats(loop: List[int]) -> List[List[int]]:
    """Cut a boundary chain that revisits a vertex into its simple sub-cycles.

    A pinch vertex can appear TWICE in one chain -- the mesh boundary runs into it, out
    again around a flap, and back. Ear-clipping that as a single polygon is not merely
    inaccurate, it is invalid: it spans the pinch and adds triangles that overlap the ones
    already there. Measured on the sphere at seed 5, doing so takes the mesh from 292
    triangles to 298 where 296 is closed, and Euler from 1 to 3 -- further from a sphere
    than leaving the hole open was.

    Split at the repeat instead and each piece is a genuine hole with a genuine fill. What
    the split cannot repair is the underlying condition: a vertex whose triangle fan is two
    arcs is non-manifold, so that ONE agent still fails 3.3's interior test and produces no
    plate. Losing one plate to a real defect in the mesh is the honest outcome; losing
    twelve to an unfilled hole, or corrupting the mesh to hide it, is not.
    """
    out: List[List[int]] = []
    stack: List[int] = []
    for v in loop:
        if v in stack:
            cut = stack.index(v)
            piece = stack[cut:]
            if len(piece) >= 3:
                out.append(piece)
            del stack[cut:]
        stack.append(v)
    if len(stack) >= 3:
        out.append(stack)
    return out


def _ear_clip_shortest_diagonal(loop: List[int], p: np.ndarray) -> List[List[int]]:
    """Clip the ear whose diagonal is shortest in 3D, repeatedly (the flip's criterion).

    Shortest-3D-diagonal, not empty-circumcircle: the same choice the open path's flip
    makes, so a quad hole closes the way its neighbours already did.
    """
    ring = list(loop)
    out: List[List[int]] = []
    while len(ring) > 3:
        m = len(ring)
        best: Optional[Tuple[float, int, List[int]]] = None
        for i in range(m):
            a, b, c = ring[(i - 1) % m], ring[i], ring[(i + 1) % m]
            if a == c:
                continue
            d = float(np.linalg.norm(p[a] - p[c]))
            if best is None or d < best[0]:
                best = (d, i, [a, b, c])
        if best is None:
            return []
        _, i, tri = best
        out.append(tri)
        ring.pop(i)
    out.append(list(ring))
    return out


def fill_small_holes(
    tris: np.ndarray,
    p: np.ndarray,
    max_loop: int = 8,
    interior_only: bool = True,
    boundary_agents: Optional[Set[int]] = None,
    stats: Optional[Dict[str, int]] = None,
) -> np.ndarray:
    """Ear-clip every open loop of at most `max_loop` edges (algorithm.md 3.1).

    Longer loops are real boundaries -- a cylinder-like surface has two of them -- and stay
    open. Length alone is not a sufficient test, though: a boundary notch, or any trimmed
    patch, can present a short loop that must NOT be filled. `interior_only` is that guard,
    and it needs to know which agents sit on a real domain boundary; positions alone cannot
    say. So `boundary_agents` carries that knowledge, and a loop all of whose agents lie on
    a real boundary is left open. With `boundary_agents=None` nothing is known and only
    `max_loop` applies -- correct on a closed surface, where every loop is a hole, and the
    reason `triangulate` supplies the set for a seamed-but-open surface instead.

    `stats`, if given, receives `pinch_vertices` and `holes_filled`. A pinch vertex is a
    fact about the mesh, not a loss: `_open_loops` separates the holes that meet there.
    """
    tris = np.asarray(tris, dtype=int).reshape(-1, 3)
    loops, pinched = _open_loops(tris)
    added: List[List[int]] = []
    filled = 0
    for loop in loops:
        if len(loop) > max_loop:
            continue
        if interior_only and boundary_agents and all(v in boundary_agents for v in loop):
            continue                           # a notch in a real boundary, not a hole
        patch = _ear_clip_shortest_diagonal(loop, p)
        if not patch:
            continue
        added.extend(patch)
        filled += 1
    if stats is not None:
        stats["pinch_vertices"] = pinched
        stats["holes_filled"] = filled
    if not added:
        return tris
    return np.vstack([tris, np.array(added, dtype=int).reshape(-1, 3)])


def _real_boundary_agents(surface, uv: np.ndarray, p: np.ndarray, spacing: float) -> Set[int]:
    """Agents within half a spacing of a REAL domain boundary -- not a seam, not a pole.

    Measured in 3D against the boundary curve itself rather than in uv, because a uv
    tolerance means different things in the two directions and different things again at
    different v.
    """
    d = surface.domain
    sides: List[Tuple[str, float]] = []
    if surface.topology.boundary_u0:
        sides.append(("u", d.u0))
    if surface.topology.boundary_u1:
        sides.append(("u", d.u1))
    if surface.topology.boundary_v0:
        sides.append(("v", d.v0))
    if surface.topology.boundary_v1:
        sides.append(("v", d.v1))
    out: Set[int] = set()
    if not sides:
        return out
    tol = 0.5 * float(spacing)
    for i, (u, v) in enumerate(np.asarray(uv, dtype=float).reshape(-1, 2)):
        for axis, value in sides:
            foot = surface.point_at(value, v) if axis == "u" else surface.point_at(u, value)
            if float(np.linalg.norm(p[i] - foot)) <= tol:
                out.add(i)
                break
    return out


def triangulate(surface, agents, spacing: float) -> np.ndarray:
    """The single public entry point; dispatches on topology (algorithm.md 3.1).

    A trivial topology means a uv lattice is meaningful and the open path applies. Anything
    else -- a seam, a pole -- makes uv Delaunay meaningless and selects the unanimity path.
    The two must never be swapped: on an open patch, boundary agents see a half-disc
    neighbourhood and produce long hull triangles their interior partners never do, so
    unanimity fails along the whole outer ring.
    """
    if not surface.topology.is_non_trivial:
        return triangulate_open(agents.uv, agents.p, agents.n)
    tris = triangulate_closed(agents.p, agents.n, spacing)
    boundary = (
        None
        if surface.topology.is_closed_surface
        else _real_boundary_agents(surface, agents.uv, agents.p, spacing)
    )
    tris = fill_small_holes(tris, agents.p, boundary_agents=boundary)
    return orient_ccw(tris, agents.p, agents.n)


# --- tangent-plane intersection (algorithm.md 3.2) --------------------------------------


def _intersect_planes(p1, n1, p2, n2, p3, n3) -> Tuple[np.ndarray, bool]:
    """Point common to three planes, or `solved=False` when they are near-parallel.

    Solved through the cofactor form rather than `np.linalg.solve` so the failure test is
    the determinant itself: with UNIT normals `det` is dimensionless, which is why `1e-9`
    here is the one permitted absolute constant in the whole host (algorithm.md 2).
    """
    d1, d2, d3 = float(n1 @ p1), float(n2 @ p2), float(n3 @ p3)
    c23, c31, c12 = np.cross(n2, n3), np.cross(n3, n1), np.cross(n1, n2)
    det = float(n1 @ c23)
    if abs(det) < 1e-9:
        return np.zeros(3), False
    return (c23 * d1 + c31 * d2 + c12 * d3) / det, True


def circumcentre(a: np.ndarray, b: np.ndarray, c: np.ndarray, spacing: float) -> np.ndarray:
    """Circumcentre of a 3D triangle; the centroid when the triangle is degenerate.

    The denominator has units of length^4, so its threshold is `1e-18 * spacing^4`
    (algorithm.md 2). The reference writes a bare `1e-18` (AbmCore.cs:975), which is the
    same number only when spacing is 1; at millimetre scale it is 10^12 times too strict
    and at metre-scale models built in millimetres it never fires.
    """
    ab, ac = b - a, c - a
    cross = np.cross(ab, ac)
    denom = 2.0 * float(cross @ cross)
    if denom < 1e-18 * (spacing ** 4 if spacing > 0 else 1.0):
        return (a + b + c) / 3.0
    to_centre = (
        np.cross(cross, ab) * float(ac @ ac) + np.cross(ac, cross) * float(ab @ ab)
    ) / denom
    return a + to_centre


def _tpi(a, b, c, spacing: float) -> Tuple[np.ndarray, bool, bool]:
    """The 3.2 block. Returns (point, was_fallback, ill_shaped).

    The two branches are MUTUALLY EXCLUSIVE and that is the whole subtlety: an ill-shaped
    triangle never reaches the S14 circumcircle test. Reaching it would reject almost every
    near-collinear boundary triangle whose TPI point is perfectly usable, and the "25-35 %
    of triangles" figure of 8 would not reproduce.

    `ill_shaped` is returned as well as `was_fallback` because they answer different
    questions and only one of them is a fallback: an ill-shaped triangle whose point stayed
    within `2 * spacing` of the centroid is NOT counted as a fallback, but it does still
    mark its plate as touching the boundary (3.3).
    """
    x, solved = _intersect_planes(a.p, a.n, b.p, b.n, c.p, c.n)
    cc = circumcentre(a.p, b.p, c.p, spacing)
    radius = float(np.linalg.norm(cc - a.p))
    centroid = (a.p + b.p + c.p) / 3.0
    ill_shaped = spacing > 0 and radius > 2.0 * spacing

    if ill_shaped:
        cc = centroid                                  # bounded fallback (LLW15 centroid rule)
        if solved and float(np.linalg.norm(x - centroid)) > 2.0 * spacing:
            solved = False                             # keep a bounded point, drop a far one
        # the circumcircle validity test is SKIPPED ENTIRELY in this branch
    elif solved:
        tn = np.cross(b.p - a.p, c.p - a.p)
        norm = float(np.linalg.norm(tn))
        floor = 1e-12 * (spacing * spacing if spacing > 0 else 1.0)
        if norm > floor:                               # a zero-area triangle has no plane
            tn = tn / norm
            xp = x - tn * float((x - a.p) @ tn)
            if float(np.linalg.norm(xp - cc)) > radius:
                solved = False                         # S14: outside the circumcircle
    if not solved:
        return cc, True, ill_shaped
    return x, False, ill_shaped


def tpi_point(a, b, c, spacing: float) -> Tuple[np.ndarray, bool]:
    """Public form of the 3.2 block: (point, was_fallback).

    `a`, `b`, `c` are anything carrying `.p` and `.n`.
    """
    x, fallback, _ = _tpi(a, b, c, spacing)
    return x, fallback


# --- convexity (algorithm.md 3.3, normative) --------------------------------------------


CONVEXITY_EPS = 1e-12


def is_convex_ring(ring: np.ndarray, normal: np.ndarray, spacing: float) -> bool:
    """All turns one sign about N, AND the ring simple (algorithm.md 3.3).

    The simplicity half needs no segment-intersection test. Once the turns agree in sign
    the total turning is exactly `2 pi k` with `k >= 1`, and the ring is simple iff `k = 1`
    -- so accumulating the signed turn angles and requiring `|turning| < 3 pi` decides it,
    with half a turn of margin either side. Without this half, a pentagram and a hexagon
    walked twice both read as convex: every turn agrees in sign.

    The turn threshold is `1e-12 * spacing^2`, RELATIVE, because a turn's magnitude is an
    area. An absolute threshold silently changes the answer with the model's units.

    Two degenerate cases fall out of the same rule rather than being special-cased: a ring
    whose every turn fell below the threshold is collinear and not a plate, and a
    sub-threshold turn whose two edges are ANTIPARALLEL is the ring doubling back on
    itself, which no amount of sign agreement makes convex.
    """
    ring = np.asarray(ring, dtype=float).reshape(-1, 3)
    m = len(ring)
    if m < 3:
        return False
    eps = CONVEXITY_EPS * (spacing * spacing if spacing > 0 else 1.0)
    sign = 0
    turning = 0.0
    for i in range(m):
        e1 = ring[(i + 1) % m] - ring[i]
        e2 = ring[(i + 2) % m] - ring[(i + 1) % m]
        dot = float(e1 @ e2)
        s = float(np.cross(e1, e2) @ normal)
        if abs(s) < eps:
            if dot < 0.0:
                return False                           # a reversal, not noise
            continue
        cur = 1 if s > 0.0 else -1
        if sign == 0:
            sign = cur
        elif cur != sign:
            return False
        turning += math.atan2(s, dot)
    if sign == 0:
        return False                                   # every turn skipped: collinear
    return abs(turning) < 3.0 * math.pi


# --- triangles to plates (algorithm.md 3.3) ---------------------------------------------


@dataclass
class Plate:
    """A plate is DERIVED, never stored on the agent (algorithm.md 1).

    `curvature_class` is None until `classify` runs, and stays None on a boundary plate:
    classification is defined on the plate set AFTER the boundary drop (3, normative order),
    so a class on a dropped plate would be read from a band that plate was not in.

    `ring_is_fallback` marks, per ring vertex, whether that vertex came from the 3.2
    fallback rather than from a genuine three-plane solve. It is the difference between a
    vertex that lies EXACTLY in the agent's tangent plane and one that does not, so it is
    what a planarisation step has to be driven by.
    """

    agent_index: int
    ring: np.ndarray
    ring_is_fallback: np.ndarray
    touches_boundary: bool
    is_convex: bool
    k: float
    side_ratio: float
    curvature_class: Optional[str] = None


@dataclass
class PlateSet:
    """`rejections` accounts for every agent that produced no plate, by reason.

    Without it "plates < agents" is a number with no cause attached, and 3.3 names that as
    the failure mode most likely to pass unnoticed. The three reasons are disjoint and are
    checked in the order 3.3 states them.
    """

    plates: List[Plate]
    fallback_count: int
    triangle_count: int
    unclosed_fan_count: int
    rejections: Dict[str, int] = field(default_factory=dict)
    # per TRIANGLE, where `Plate.ring_is_fallback` is per ring vertex. Same quantity, the
    # other way round: the ring view drives planarisation, the triangle view is what a
    # picture of the mesh needs in order to shade where the guard fired.
    tri_is_fallback: Optional[np.ndarray] = None


def _ring_side_ratio(ring: np.ndarray) -> float:
    if len(ring) < 2:
        return 0.0
    edges = np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1)
    longest = float(edges.max())
    return float(edges.min()) / longest if longest > 0.0 else 0.0


def _walk_fan(i: int, fan: List[int], tris: np.ndarray) -> Optional[List[int]]:
    """Order the fan triangle-to-triangle by shared edges, COMBINATORIALLY (3.3).

    Combinatorial and not angular: sorting the fan by angle about the agent would quietly
    unfold a folded ring, and a folded ring is exactly what the convexity test exists to
    catch on an anticlastic surface. Each triangle contributes the vertex that follows the
    agent in CCW order and the one before it; the walk chains next-to-prev.

    Returns None when the ring does not close. That is not an impossible state -- it is the
    usual cause of `plates < agents` -- so the caller counts it instead of ignoring it.
    """
    by_prev: Dict[int, int] = {}
    next_of: Dict[int, int] = {}
    for t in fan:
        v = [int(x) for x in tris[t]]
        k = v.index(i)
        next_of[t] = v[(k + 1) % 3]
        by_prev[v[(k + 2) % 3]] = t
    ring: List[int] = []
    cur = fan[0]
    for _ in range(len(fan)):
        ring.append(cur)
        nxt = next_of[cur]
        if nxt not in by_prev:
            return None
        cur = by_prev[nxt]
    return ring if cur == fan[0] else None


def build_plates(
    surface, agents, tris: np.ndarray, spacing: float, band_fraction: float = 0.1
) -> PlateSet:
    """Triangles -> TPI points -> per-agent rings, in the normative order (algorithm.md 3).

    Build plates, then drop boundary plates, then classify -- and classify only the
    survivors, because `max|K|` is taken over the CURRENT plate set and the drop moves the
    band. The drop itself is the caller's (`touches_boundary` is reported, not applied), so
    both populations stay available to the diagnostics.

    `touches_boundary` is BOTH conditions of 3.3: a ring triangle carrying a hull agent, or
    an ill-shaped one. Hull adjacency alone leaves the ill-shaped boundary triangles in the
    interior population, where they are the largest single distortion of the side-ratio
    statistic.
    """
    tris = np.asarray(tris, dtype=int).reshape(-1, 3)
    n_agents = len(agents.p)

    class _Ag:
        __slots__ = ("p", "n")

        def __init__(self, p, n):
            self.p, self.n = p, n

    points = np.zeros((len(tris), 3))
    is_fallback = np.zeros(len(tris), dtype=bool)
    is_ill = np.zeros(len(tris), dtype=bool)
    incident: List[List[int]] = [[] for _ in range(n_agents)]
    fallback_count = 0
    for t, (ia, ib, ic) in enumerate(tris):
        x, fallback, ill = _tpi(
            _Ag(agents.p[ia], agents.n[ia]),
            _Ag(agents.p[ib], agents.n[ib]),
            _Ag(agents.p[ic], agents.n[ic]),
            spacing,
        )
        points[t] = x
        is_fallback[t] = fallback
        is_ill[t] = ill
        fallback_count += int(fallback)
        for j in (ia, ib, ic):
            incident[int(j)].append(t)

    owners = undirected_edge_owners(tris)
    on_hull = hull_agents(tris)

    plates: List[Plate] = []
    unclosed = 0
    few_incident = 0
    non_manifold = 0
    for i in range(n_agents):
        fan = incident[i]
        if len(fan) < 3:
            few_incident += 1
            continue
        interior = True
        for t in fan:
            for j in (int(x) for x in tris[t]):
                if j != i and len(owners.get(tuple(sorted((i, j))), ())) != 2:
                    interior = False
                    break
            if not interior:
                break
        if not interior:
            non_manifold += 1
            continue
        order = _walk_fan(i, fan, tris)
        if order is None:
            unclosed += 1
            continue
        ring = points[order]
        touches = any(
            is_ill[t] or any(int(j) in on_hull for j in tris[t]) for t in order
        )
        plates.append(
            Plate(
                agent_index=i,
                ring=ring,
                ring_is_fallback=is_fallback[order].copy(),
                touches_boundary=bool(touches),
                is_convex=is_convex_ring(ring, agents.n[i], spacing),
                k=float(agents.k[i]),
                side_ratio=_ring_side_ratio(ring),
            )
        )

    classify([pl for pl in plates if not pl.touches_boundary], band_fraction)
    return PlateSet(
        plates=plates,
        fallback_count=fallback_count,
        triangle_count=len(tris),
        unclosed_fan_count=unclosed,
        rejections={
            "few_incident_triangles": few_incident,
            "non_manifold_fan": non_manifold,
            "unclosed_fan": unclosed,
        },
        tri_is_fallback=is_fallback.copy(),
    )


def classify(plates: List[Plate], band_fraction: float = 0.1) -> None:
    """In place, over the CURRENT plate list (algorithm.md, Classification).

    `max|K|` is recomputed on every call and is deliberately NOT cached: the boundary drop
    happens before classification, so the surviving set has a different maximum and plates
    move between classes. A third `max|K|`, over all AGENTS, belongs to the fallback-by-class
    diagnostic and is not this one.

    `K` is the AGENT's Gaussian curvature, never a triangle average.
    """
    if not plates:
        return None
    kmax = max(abs(pl.k) for pl in plates)
    band = band_fraction * kmax
    for pl in plates:
        if abs(pl.k) <= band:
            pl.curvature_class = "parabolic"
        elif pl.k > 0.0:
            pl.curvature_class = "elliptic"
        else:
            pl.curvature_class = "hyperbolic"
    return None
