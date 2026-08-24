"""The two normative metrics of algorithm.md 4, and the identities of 8(c).

They exist in their own module for one reason: their POPULATIONS differ, and a metric that
lives next to its consumer quietly inherits that consumer's population. Both headline
numbers are quoted to two decimals in 8, so the populations are part of the specification.

  - Side ratio       -- over PLATES, after the boundary drop, per curvature class, headline
                        number hyperbolic.
  - Alignment mean   -- over ordered AGENT->NEIGHBOUR pairs, no drop, no band exclusion,
                        hull agents included, gated only on anisotropy >= 0.5.

And they look at almost disjoint parts of the surface: `anisotropy -> 1` as `k2 -> 0`, so
the alignment population is concentrated in exactly the parabolic band the side-ratio
metric excludes. A host that reports different numbers from another on the same
configuration has a different population, not a different algorithm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class SideRatioStats:
    count: int
    median: float
    p10: float
    mean: float
    minimum: float


def side_ratio(plate) -> float:
    """`min(edge) / max(edge)` over the ring, 0 when the longest edge is zero (4)."""
    ring = np.asarray(plate.ring, dtype=float).reshape(-1, 3)
    if len(ring) < 2:
        return 0.0
    edges = np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1)
    longest = float(edges.max())
    return float(edges.min()) / longest if longest > 0.0 else 0.0


def side_ratio_stats(plates, values: Optional[Sequence[float]] = None) -> SideRatioStats:
    """Order statistics by RAW NEAREST RANK -- `rs[n // 2]`, `rs[n // 10]` -- not interpolated.

    numpy's `percentile` interpolates by default and would report a slightly different
    number from the reference on the same plate set; 4 requires the raw rank and requires a
    host to say which it used. This one uses the raw rank.

    `values` bypasses the rings, so the rank rule can be tested without constructing
    geometry that only exists to carry a number.
    """
    rs = sorted(float(v) for v in (values if values is not None else (side_ratio(p) for p in plates)))
    n = len(rs)
    if n == 0:
        return SideRatioStats(0, 0.0, 0.0, 0.0, 0.0)
    return SideRatioStats(
        count=n,
        median=rs[n // 2],
        p10=rs[n // 10],
        mean=float(sum(rs) / n),
        minimum=rs[0],
    )


def side_ratio_by_class(plates) -> Dict[str, SideRatioStats]:
    """Per curvature class, over the plate set AFTER the boundary drop (4).

    The drop is applied here rather than assumed of the caller, because "the plate set after
    the boundary drop" is half of what makes this number comparable across hosts. Plates
    with no class -- boundary plates, which `build_plates` deliberately leaves unclassified
    -- cannot appear, since they are exactly the ones dropped.

    The headline number is the hyperbolic class.
    """
    out: Dict[str, List[float]] = {}
    for plate in plates:
        if plate.touches_boundary or plate.curvature_class is None:
            continue
        out.setdefault(plate.curvature_class, []).append(side_ratio(plate))
    return {cls: side_ratio_stats([], values=vals) for cls, vals in out.items()}


def alignment_mean(
    p: np.ndarray,
    n: np.ndarray,
    e1: np.ndarray,
    anis: np.ndarray,
    neighbours: Sequence[np.ndarray],
    spacing: float,
    min_anisotropy: float = 0.5,
) -> Tuple[float, int]:
    """`mean(cos 12 phi)` over ORDERED agent->neighbour pairs (4).

    Ordered, because alignment is not pair-antisymmetric: `phi` is measured in the agent's
    own frame, and the reverse pair generally gives a different angle. Visiting each pair
    once would halve the population and mix two frames.

    Population is AGENTS, not plates -- no boundary drop, no parabolic-band exclusion, hull
    agents included. The only gate is `anisotropy >= 0.5`, and since anisotropy tends to 1
    as `k2` tends to 0, that gate SELECTS the parabolic band rather than excluding it.

    Returns `(0.0, 0)` when no pair qualifies, and the pair count is not decoration: on a
    sphere every agent is umbilic, the population is empty, and "0.00 over 0 pairs" is an
    absent metric rather than a measured zero. Only the count tells them apart.
    """
    p = np.asarray(p, dtype=float).reshape(-1, 3)
    n = np.asarray(n, dtype=float).reshape(-1, 3)
    e1 = np.asarray(e1, dtype=float).reshape(-1, 3)
    anis = np.asarray(anis, dtype=float).reshape(-1)
    floor = 1e-9 * float(spacing) if spacing > 0 else 1e-9

    total = 0.0
    pairs = 0
    for i in range(len(p)):
        if anis[i] < min_anisotropy:
            continue
        e2 = np.cross(n[i], e1[i])
        for j in np.asarray(neighbours[i], dtype=int).reshape(-1):
            if int(j) == i:
                continue
            t = p[int(j)] - p[i]
            t = t - n[i] * float(t @ n[i])         # into THIS agent's tangent plane
            if float(np.linalg.norm(t)) < floor:
                continue                           # the angle is undefined here (4)
            phi = math.atan2(float(t @ e2), float(t @ e1[i]))
            total += math.cos(12.0 * phi)
            pairs += 1
    return (total / pairs, pairs) if pairs else (0.0, 0)


def valence_tally(plates) -> Dict[int, int]:
    """Ring length -> how many plates have it. Six is the hexagonal ideal; 5 and 7 are the
    irreducible defects a relaxed packing carries."""
    out: Dict[int, int] = {}
    for plate in plates:
        m = len(np.asarray(plate.ring).reshape(-1, 3))
        out[m] = out.get(m, 0) + 1
    return dict(sorted(out.items()))


def euler(agents, tris: np.ndarray) -> int:
    """`V - E + F`. An IDENTITY, not evidence (8c): a jittered seed with zero iterations
    passes it. Reported because a violation is a real failure, not because passing means
    anything about the packing."""
    tris = np.asarray(tris, dtype=int).reshape(-1, 3)
    v = len(np.asarray(agents.p).reshape(-1, 3))
    edges = {
        tuple(sorted((int(t[i]), int(t[(i + 1) % 3]))))
        for t in tris
        for i in range(3)
    }
    return v - len(edges) + len(tris)
