"""Level 2 -- plate rings to `compas_timber` `Plate`s in a `TimberModel`.

This file and `btlx.py` are the only ones that import COMPAS. Everything upstream is
numpy, so a Level 1 geometry regression can never be masked by a fabrication-library
failure, and `run.py --no-timber` is a path that touches no COMPAS code at all.

**The metre/millimetre boundary is here and nowhere else.** The solver, the plates and
every Level 1 statistic are in metres (`spacing` ~ 1.92 on the egg-crate). `compas_timber`
is given millimetres, with `TimberModel(tolerance=Tolerance(unit="MM"))` so the BTLx writer
does not silently scale by 1000 a second time. A conversion applied twice is a factor of
1e6 and looks entirely plausible in a viewport, which is why the test asserts it against
the declared thickness rather than by eye.

Two upstream behaviours shape the code and are not defensive programming:

  - `PlateGeometry` derives its frame from `Frame.from_points(outline[0], outline[1],
    pt_c)`, and its search for `pt_c` never breaks out of its loop, so `pt_c` always ends
    up as `outline[2]`. The frame therefore comes from three CONSECUTIVE vertices and its
    conditioning depends on where the ring starts. `rotate_to_sharpest_corner` chooses that
    start.
  - A true bow-tie is accepted silently: the resulting Brep reports `is_solid=True` with a
    NEGATIVE volume and `is_valid=False`. A host guarding on `is_solid` -- the obvious
    guard -- passes it straight through. `is_valid_solid` guards on validity and volume.

And one of our own: algorithm.md §3.3 claims the plate ring is "planar by construction",
which is false for every vertex produced by §3.2's fallback -- 50 of 85 interior plates on
the egg-crate, deviating by up to 11 % of spacing. Planarisation is therefore
mandatory, not a refinement, and the shift it costs is reported rather than hidden.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from compas.geometry import Polyline, Vector
from compas.tolerance import Tolerance
from compas_timber.elements import Plate as CtPlate
from compas_timber.model import TimberModel

# The MEASURED usable planarity budget, not `PlateGeometry`'s nominal 1e-9. It varies by
# vertex index -- the derived frame passes through vertices 0, 1 and 2, so lifting one of
# those tilts the frame and amplifies the residual elsewhere -- and 3.3e-10 is the value
# that holds whichever vertex is lifted. Absolute, in model units (millimetres).
PLANARITY_BUDGET = 3.3e-10


class RejectionReason(Enum):
    """Every plate either builds or is rejected by a NAMED, pre-declared criterion.

    "plates in, fewer elements out" with no reason attached is the failure mode the spec
    names as most likely to pass unnoticed, so the tally is by reason and the reasons are
    fixed before the run rather than discovered during it.
    """

    NON_PLANAR = "non_planar"
    SELF_INTERSECTING = "self_intersecting"
    MIN_SIDE = "min_side"
    BUILD_FAILED = "build_failed"


@dataclass
class TimberStage:
    """The model is not JSON-serialisable and the diagnostics are; they travel separately.

    `run.py` publishes `diagnostics` as the payload's `timber` block and keeps `model` for
    the BTLx stage. Putting the model in the payload would have `--json` fail at the very
    end of a two-minute run.
    """

    model: Any
    diagnostics: Dict[str, Any]
    rejections: List[Tuple[int, RejectionReason]] = field(default_factory=list)


def planarise(ring: np.ndarray) -> Tuple[np.ndarray, float]:
    """Project a ring onto its own least-squares plane. Returns `(ring_out, residual)`.

    `residual` is the ring's worst distance from that plane BEFORE projection: a first
    class diagnostic, because corners that do not lie near a common plane are not a
    manufacturable plate whatever we do to them afterwards.

    The plane is the total-least-squares one (the smallest right singular vector of the
    centred points), not a graph fit `z = ax + by + c`, so it is orientation-independent --
    a ring standing vertically on the egg-crate's flanks is fitted as well as a flat one.
    Every vertex moves along the plane normal only, so the in-plane footprint is preserved
    and the outline stays the shape the geometry produced.
    """
    ring = np.asarray(ring, dtype=float)
    if len(ring) < 3:
        return ring.copy(), 0.0
    centroid = ring.mean(axis=0)
    centred = ring - centroid
    normal = np.linalg.svd(centred, full_matrices=False)[2][-1]
    signed = centred @ normal
    residual = float(np.max(np.abs(signed)))
    return ring - np.outer(signed, normal), residual


def _triple_conditioning(ring: np.ndarray) -> np.ndarray:
    """|(p1-p0) x (p2-p0)| / (|p1-p0||p2-p0|) at every rotation of the ring."""
    a = ring
    b = np.roll(ring, -1, axis=0)
    c = np.roll(ring, -2, axis=0)
    u, v = b - a, c - a
    cross = np.linalg.norm(np.cross(u, v), axis=1)
    denom = np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1)
    return np.divide(cross, denom, out=np.zeros(len(ring)), where=denom > 0.0)


def rotate_to_sharpest_corner(ring: np.ndarray) -> np.ndarray:
    """Rotate the ring's start index so `PlateGeometry`'s frame triple is best conditioned.

    The name is the plan's. What is actually maximised is the conditioning of the triple
    `(p0, p1, p2)` -- see the module docstring for why those three and not any others --
    and on a mixed outline that is not the sharpest corner but usually the flattest, since
    a flat vertex at `p0` puts two long, widely separated edges into the cross product.
    Kept under the plan's name so the plan, the test and the code agree.
    """
    ring = np.asarray(ring, dtype=float)
    if len(ring) < 3:
        return ring.copy()
    return np.roll(ring, -int(np.argmax(_triple_conditioning(ring))), axis=0)


def _plane_basis(ring: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    centroid = ring.mean(axis=0)
    u, _, vt = np.linalg.svd(ring - centroid, full_matrices=False)
    del u
    return centroid, vt[0], vt[1]


def _segments_cross(p, p2, q, q2) -> bool:
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = side(p, p2, q), side(p, p2, q2)
    d3, d4 = side(q, q2, p), side(q, q2, p2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def is_self_intersecting(ring: np.ndarray) -> bool:
    """Proper crossing of two non-adjacent edges, tested in the ring's own plane.

    A bow-tie is the one outline shape compas_timber accepts and should not: it yields a
    Brep with `is_solid=True` and a negative volume. Concavity is NOT tested here -- a
    reflex outline is normal on a hyperbolic surface and builds with an exactly correct
    solid volume.
    """
    ring = np.asarray(ring, dtype=float)
    n = len(ring)
    if n < 4:
        return False
    centroid, ex, ey = _plane_basis(ring)
    flat = np.column_stack([(ring - centroid) @ ex, (ring - centroid) @ ey])
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue                      # adjacent across the closing edge
            if _segments_cross(flat[i], flat[(i + 1) % n], flat[j], flat[(j + 1) % n]):
                return True
    return False


def min_edge_length(ring: np.ndarray) -> float:
    ring = np.asarray(ring, dtype=float)
    if len(ring) < 2:
        return 0.0
    return float(np.min(np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1)))


def coplanarity(ring: np.ndarray) -> float:
    """Worst distance from the ring's own best-fit plane. Frame-independent."""
    return planarise(ring)[1]


def is_valid_solid(brep) -> bool:
    """`is_valid and volume > 0`, NOT `is_solid`.

    `is_solid` returns True for a self-intersecting plate whose volume is negative, which
    is precisely the case this guard exists to catch.
    """
    return bool(getattr(brep, "is_valid", False)) and float(getattr(brep, "volume", 0.0)) > 0.0


def _closed_polyline(ring: np.ndarray) -> Polyline:
    pts = [list(map(float, p)) for p in ring]
    return Polyline(pts + [pts[0]])


def build_model(
    rings: Sequence[np.ndarray],
    thickness: float,
    unit: str = "MM",
    min_side: Optional[float] = None,
    normals: Optional[Sequence[np.ndarray]] = None,
):
    """Rings (already in model units) to `(model, rejections)`.

    `rejections` is a list of `(ring index, RejectionReason)`. The criteria are checked in
    a fixed order -- MIN_SIDE, NON_PLANAR, SELF_INTERSECTING, then the build itself -- so a
    ring that fails two of them is always attributed to the same one and the tally is
    stable between runs.

    `min_side` is `None` by default rather than a constant: the spec states it as
    `0.05 * spacing`, and a length that is only meaningful relative to spacing has no
    business being hard-coded in a function that does not know the spacing.
    """
    model = TimberModel(tolerance=Tolerance(unit=unit))
    rejections: List[Tuple[int, RejectionReason]] = []

    for index, ring in enumerate(rings):
        ring = np.asarray(ring, dtype=float)
        if min_side is not None and min_edge_length(ring) < min_side:
            rejections.append((index, RejectionReason.MIN_SIDE))
            continue
        if coplanarity(ring) > PLANARITY_BUDGET:
            rejections.append((index, RejectionReason.NON_PLANAR))
            continue
        if is_self_intersecting(ring):
            rejections.append((index, RejectionReason.SELF_INTERSECTING))
            continue

        vector = None
        if normals is not None:
            vector = Vector(*(-np.asarray(normals[index], dtype=float)))
        try:
            plate = CtPlate.from_outline_thickness(_closed_polyline(ring), thickness, vector=vector)
            if not is_valid_solid(plate.geometry):
                raise ValueError("the plate solid is invalid or has a non-positive volume")
        except Exception:                     # upstream raises several unrelated types here
            rejections.append((index, RejectionReason.BUILD_FAILED))
            continue
        model.add_element(plate)

    return model, rejections


def _spread(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"median": 0.0, "p90": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {
        "median": ordered[len(ordered) // 2],
        "p90": ordered[min(len(ordered) - 1, (9 * len(ordered)) // 10)],
        "max": ordered[-1],
    }


def build_timber_model(cfg, surface, agents, plates, spacing) -> TimberStage:
    """The `run.py` hook: interior plate rings in metres to a millimetre `TimberModel`.

    Boundary plates are already dropped -- that is normative order and happens upstream, so
    the count this stage accounts for is the INTERIOR plate count, not the plate count.
    """
    del surface                                # signature is the run.py hook's, not ours
    started = time.perf_counter()
    scale = 1000.0
    thickness_mm = float(cfg.thickness) * scale
    min_side_mm = 0.05 * float(spacing) * scale

    rings: List[np.ndarray] = []
    normals: List[np.ndarray] = []
    shifts: List[float] = []
    residuals: List[float] = []
    after: List[float] = []
    for plate in plates:
        raw = np.asarray(plate.ring, dtype=float) * scale
        flat, residual = planarise(raw)
        # RMS, not max: the max shift is EQUAL to the residual by construction (the worst
        # vertex is the one that defines both), so reporting it would be one number twice.
        # The RMS says how much of the ring moved, which the residual does not.
        shifts.append(float(np.sqrt(np.mean(np.sum((flat - raw) ** 2, axis=1)))))
        flat = rotate_to_sharpest_corner(flat)
        rings.append(flat)
        normals.append(np.asarray(agents.n[plate.agent_index], dtype=float))
        residuals.append(residual)
        after.append(coplanarity(flat))

    model, rejections = build_model(
        rings, thickness_mm, unit="MM", min_side=min_side_mm, normals=normals
    )
    elements = list(model.elements())

    by_reason: Dict[str, int] = {}
    for _, reason in rejections:
        by_reason[reason.name] = by_reason.get(reason.name, 0) + 1

    diagnostics = {
        "unit": "MM",
        "thickness_mm": thickness_mm,
        "min_side_mm": min_side_mm,
        "input_plate_count": len(plates),
        "element_count": len(elements),
        "rejected_count": len(rejections),
        "rejections_by_reason": by_reason,
        # which plate, by agent index, so a rejection can be looked at rather than counted
        "rejected_agents": [
            [int(plates[i].agent_index), reason.name] for i, reason in rejections
        ],
        # A4: what planarisation had to answer for, and what it cost
        "planarity_residual_mm": _spread(residuals),
        "planarisation_shift_rms_mm": _spread(shifts),
        "coplanarity_after_mm": _spread(after),
        "planarity_budget_mm": PLANARITY_BUDGET,
        "blank_length_mm": _spread([float(e.blank_length) for e in elements]),
        "wall_time_s": time.perf_counter() - started,
    }
    return TimberStage(model=model, diagnostics=diagnostics, rejections=rejections)
