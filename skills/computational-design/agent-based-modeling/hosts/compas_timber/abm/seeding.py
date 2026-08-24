"""Seeding (algorithm.md 1).

Two facts the reference exposes and this host preserves deliberately, because section 8 is
measured with them:

  - `count` is NOMINAL. The hex lattice is generated and then filtered by a 0.4.pitch
    margin, so a run realises fewer agents than asked for (131 for 150 on the egg-crate).
    Every per-agent statistic must be reported against the realised count.
  - the lattice pitch derives from PARAMETER-DOMAIN area while `spacing` derives from
    SURFACE area (plan 400 vs surface 479, ~12% apart), so the packing is seeded denser
    than its own target spacing and separation expands it. The fast convergence is partly
    a product of this mismatch. A host that "fixes" either will not reproduce section 8.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .surfaces import Surface, anisotropy


def auto_spacing(surface: Surface, count: int) -> float:
    """sqrt(A / (0.866 . count)) from SURFACE area (algorithm.md 6)."""
    return math.sqrt(surface.area() / (0.8660254 * max(1, count)))


def dominant_principal_angle(surface: Surface) -> float:
    """Anisotropy-weighted 12-fold circular mean of the principal direction, in raw uv.

    Returns radians in [-pi/12, pi/12] -- i.e. reduced mod 30 degrees. 12-fold, not 6-fold:
    where |k1| = |k2| the numerically larger principal direction swaps between E1 and E2
    from sample to sample, and in a 6-fold field E1 and E2 are opposite targets, so the
    reduction would fight itself. In the 12-fold field both principal directions are fixed
    points. On the egg-crate the answer is 15 degrees.

    The derivative stencil here is CLAMPED to the domain, deliberately unlike the unclamped
    one used for curvature (algorithm.md 1). Recovering a uv angle needs the first
    fundamental form: an orthonormal frame has already discarded E, F and G.
    """
    d = surface.domain
    sc = ss = 0.0
    hu, hv = 1e-4 * d.du, 1e-4 * d.dv
    for i in range(17):
        u = d.u0 + d.du * (i + 0.5) / 17.0
        for j in range(17):
            v = d.v0 + d.dv * (j + 0.5) / 17.0
            k1, k2, e1 = surface.principal_at(u, v)
            if float(np.linalg.norm(e1)) < 1e-14:
                continue
            w = anisotropy(k1, k2) * (abs(k1) + abs(k2))
            if w <= 0.0:
                continue
            up, um = min(u + hu, d.u1), max(u - hu, d.u0)
            vp, vm = min(v + hv, d.v1), max(v - hv, d.v0)
            pu = (surface.point_at(up, v) - surface.point_at(um, v)) / (up - um)
            pv = (surface.point_at(u, vp) - surface.point_at(u, vm)) / (vp - vm)
            e_, f_, g_ = float(pu @ pu), float(pu @ pv), float(pv @ pv)
            det = e_ * g_ - f_ * f_
            if det < 1e-18:
                continue
            r1, r2 = float(e1 @ pu), float(e1 @ pv)
            alpha = (g_ * r1 - f_ * r2) / det
            beta = (e_ * r2 - f_ * r1) / det
            theta = math.atan2(beta, alpha)
            sc += w * math.cos(12.0 * theta)
            ss += w * math.sin(12.0 * theta)
    if sc == 0.0 and ss == 0.0:
        return 0.0
    return math.atan2(ss, sc) / 12.0


def hex_seed(
    surface: Surface,
    count: int,
    hex_angle: Optional[float] = None,
    hex_jitter: float = 0.15,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Jittered hexagonal lattice in RAW uv. Open patches only.

    A uv lattice is meaningless across a seam or a pole; use `random_seed` there.
    `hex_angle` is in radians, None selects `dominant_principal_angle`.
    """
    rng = rng if rng is not None else np.random.default_rng(1)
    d = surface.domain
    pitch = math.sqrt(abs(d.du * d.dv) / (0.8660254 * max(1, count)))
    ang = dominant_principal_angle(surface) if hex_angle is None else float(hex_angle)
    b1 = np.array([pitch * math.cos(ang), pitch * math.sin(ang)])
    b2 = np.array(
        [pitch * math.cos(ang + math.pi / 3.0), pitch * math.sin(ang + math.pi / 3.0)]
    )
    centre = np.array(d.mid)
    margin = 0.4 * pitch
    span = int(math.ceil(max(abs(d.du), abs(d.dv)) / pitch)) + 2
    out = []
    for i in range(-span, span + 1):
        for j in range(-span, span + 1):
            p = centre + i * b1 + j * b2
            if (
                p[0] < d.u0 + margin
                or p[0] > d.u1 - margin
                or p[1] < d.v0 + margin
                or p[1] > d.v1 - margin
            ):
                continue                                    # tested on the UN-jittered point
            u = p[0] + rng.uniform(-0.5, 0.5) * pitch * hex_jitter
            v = p[1] + rng.uniform(-0.5, 0.5) * pitch * hex_jitter
            out.append((min(max(u, d.u0), d.u1), min(max(v, d.v0), d.v1)))
    return np.array(out, dtype=float).reshape(-1, 2)


def random_seed(
    surface: Surface,
    count: int,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Uniform per unit AREA by rejection sampling against |Su x Sv|.

    Not uniform in uv: poles and stretched patches would be over-sampled. The maximum area
    element is estimated on a 24x24 grid and the loop is guarded at count.1000 attempts.
    """
    rng = rng if rng is not None else np.random.default_rng(1)
    d = surface.domain
    jmax = 0.0
    for i in range(24):
        u = d.u0 + d.du * (i + 0.5) / 24.0
        for j in range(24):
            v = d.v0 + d.dv * (j + 0.5) / 24.0
            su, sv = surface.derivatives_at(u, v)
            jmax = max(jmax, float(np.linalg.norm(np.cross(su, sv))))
    if jmax <= 0.0:
        jmax = 1.0
    out = []
    attempts = 0
    guard = max(1, count) * 1000
    while len(out) < count and attempts < guard:
        attempts += 1
        u = d.u0 + rng.random() * d.du
        v = d.v0 + rng.random() * d.dv
        su, sv = surface.derivatives_at(u, v)
        if rng.random() * jmax <= float(np.linalg.norm(np.cross(su, sv))):
            out.append((u, v))
    return np.array(out, dtype=float).reshape(-1, 2)
