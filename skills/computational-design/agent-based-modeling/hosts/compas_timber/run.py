"""CLI harness for the compas_timber ABM host.

Reports diagnostics, not a verdict. Three things it is deliberate about, each because the
opposite bit someone:

  - The alignment mean is NEVER printed bare. `alignment 0.00 over 0 pairs` and
    `alignment 0.00 over 566 pairs` mean opposite things -- an absent population versus a
    measured zero -- and only the pair count separates them.
  - The identities of algorithm.md 8(c) live in their own `identities` block, labelled.
    Euler's formula and the valence defect sum are satisfied by a jittered seed with zero
    iterations; they are worth reporting and worth never reading as evidence.
  - Give each run its own `--json` path. Parallel runs sharing one clobber each other; this
    already bit the .NET harness (hosts/dotnet/README.md).

Model unit is the METRE here and everywhere upstream of timber.py; the conversion to
millimetre happens once, at that boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

from abm.metrics import alignment_mean, euler, side_ratio_by_class, valence_tally
from abm.plates import build_plates, triangulate
from abm.solver import Parameters, Solver
from abm.surfaces import MongeSurface, SphereSurface, TubeSurface


def build_config(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="run.py", description=__doc__)
    ap.add_argument("--surface", choices=("sphere", "monge", "tube"), default="monge")
    ap.add_argument("--agents", type=int, default=150, help="NOMINAL count; realised differs")
    ap.add_argument("--seed", choices=("hex", "random"), default="hex")
    ap.add_argument("--hex-angle", default="auto", help="'auto' (12-fold mean) or degrees")
    ap.add_argument("--alignment-weight", type=float, default=0.3)
    ap.add_argument("--thickness", type=float, default=0.04, help="metres; used by the timber stage")
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument("--rng-seed", type=int, default=1)
    ap.add_argument("--btlx", default=None)
    ap.add_argument("--json", dest="json_path", default=None)
    ap.add_argument("--geometry-json", default=None,
                    help="drawing schema for hosts/dotnet/render.py; render with SYSTEM python")
    ap.add_argument("--mesh", default=None,
                    help=".stl or .obj of the built compas_timber solids, in MILLIMETRES")
    ap.add_argument("--monge-h", type=float, default=3.0)
    ap.add_argument("--monge-periods", type=float, default=2.0)
    ap.add_argument("--monge-length", type=float, default=20.0)
    ap.add_argument("--projection", choices=("closest", "vertical"), default="closest")
    ap.add_argument("--radius", type=float, default=10.0, help="sphere radius")
    ap.add_argument("--tube-radius", type=float, default=5.0)
    ap.add_argument("--tube-height", type=float, default=20.0)
    ap.add_argument("--tube-barrel", type=float, default=0.0,
                    help="0 = a DEVELOPABLE right cylinder; see TubeSurface's docstring")
    ap.add_argument("--no-timber", action="store_true", help="stop after Level 1 geometry")
    return ap.parse_args(argv)


def _surface(cfg):
    if cfg.surface == "sphere":
        return SphereSurface(radius=cfg.radius)
    if cfg.surface == "tube":
        return TubeSurface(
            radius=cfg.tube_radius, height=cfg.tube_height, barrel=cfg.tube_barrel
        )
    return MongeSurface(
        h=cfg.monge_h,
        periods=cfg.monge_periods,
        length=cfg.monge_length,
        projection=cfg.projection,
    )


def _hex_angle(value: str) -> Optional[float]:
    if str(value).strip().lower() == "auto":
        return None
    return float(np.radians(float(value)))


def _planarity(plates, agents) -> Dict[str, float]:
    """Distribution of each ring's worst deviation from its agent's tangent plane.

    Non-zero wherever a TPI guard fired, and reported in units of
    spacing so it is comparable across models and scales. This is the number the timber
    stage's planarisation has to answer for.
    """
    worst = []
    for plate in plates:
        n = agents.n[plate.agent_index]
        d = np.abs((plate.ring - agents.p[plate.agent_index]) @ n)
        worst.append(float(np.max(d)) if len(d) else 0.0)
    if not worst:
        return {"median": 0.0, "p90": 0.0, "max": 0.0}
    worst.sort()
    return {
        "median": worst[len(worst) // 2],
        "p90": worst[min(len(worst) - 1, (9 * len(worst)) // 10)],
        "max": worst[-1],
    }


def _neighbour_distance_std(p: np.ndarray, neighbours) -> float:
    """Spread of the realised neighbour distances, over ordered pairs.

    Compared against the seed's jitter spread, this is the half of the do-nothing detector
    that `maxDisplacement` cannot supply: a solver that iterates but moves nothing leaves
    the distances as scattered as the seed left them, whatever its displacement trace says.
    """
    d = [
        float(np.linalg.norm(p[int(j)] - p[i]))
        for i in range(len(p))
        for j in np.asarray(neighbours[i], dtype=int).reshape(-1)
    ]
    return float(np.std(d)) if d else 0.0


def run(cfg) -> Dict[str, Any]:
    started = time.perf_counter()
    surface = _surface(cfg)
    params = Parameters(
        count=cfg.agents,
        iterations=cfg.iterations,
        alignment_weight=cfg.alignment_weight,
        hex_angle=_hex_angle(cfg.hex_angle),
        layout=cfg.seed,
        rng_seed=cfg.rng_seed,
    )
    result = Solver(surface, params).run()
    agents = result.agents
    tris = triangulate(surface, agents, result.spacing)
    plate_set = build_plates(surface, agents, tris, result.spacing, params.band_fraction)
    interior = [pl for pl in plate_set.plates if not pl.touches_boundary]

    mean, pairs = alignment_mean(
        agents.p, agents.n, agents.e1, agents.anis, result.neighbours, result.spacing
    )

    stats_by_class = side_ratio_by_class(plate_set.plates)
    side_ratio: Dict[str, Any] = {}
    convex_by_class: Dict[str, int] = {}
    concave_by_class: Dict[str, int] = {}
    # every class is present even when empty: "the hyperbolic median on a sphere is
    # undefined" is a fact worth being able to read, and a missing key reads as an error
    for cls in ("elliptic", "hyperbolic", "parabolic"):
        stats = stats_by_class.get(cls)
        members = [pl for pl in interior if pl.curvature_class == cls]
        side_ratio[cls] = {
            "count": stats.count if stats else 0,
            "median": stats.median if stats else None,
            "p10": stats.p10 if stats else None,
            "mean": stats.mean if stats else None,
            "min": stats.minimum if stats else None,
        }
        convex_by_class[cls] = sum(1 for pl in members if pl.is_convex)
        concave_by_class[cls] = sum(1 for pl in members if not pl.is_convex)

    valence = valence_tally(interior)
    rejections = dict(plate_set.rejections)
    rejections["boundary_drop"] = len(plate_set.plates) - len(interior)

    payload: Dict[str, Any] = {
        "surface": cfg.surface,
        "projection": cfg.projection if cfg.surface == "monge" else None,
        "layout": cfg.seed,
        "rng_seed": cfg.rng_seed,
        "hex_angle": cfg.hex_angle,
        "alignment_weight": cfg.alignment_weight,
        "nominal_count": cfg.agents,
        "realised_count": len(agents.p),
        "spacing": result.spacing,
        "iterations": result.iterations_run,
        "converged": result.converged,
        "max_disp_first": result.max_disp_history[0] if result.max_disp_history else 0.0,
        "max_disp_last": result.max_disp_history[-1] if result.max_disp_history else 0.0,
        # the do-nothing detector's second half (spec Level 1.4): a solver that ran but did
        # nothing leaves the neighbour distances as scattered as the seed's jitter left them
        "neighbour_distance_std": _neighbour_distance_std(agents.p, result.neighbours),
        "seed_jitter_spread": result.seed_jitter_spread,
        "plate_count": len(plate_set.plates),
        "interior_plate_count": len(interior),
        "valence_tally": {str(k): v for k, v in valence.items()},
        "hexagon_share": (valence.get(6, 0) / len(interior)) if interior else 0.0,
        "side_ratio": side_ratio,
        "convex_by_class": convex_by_class,
        "concave_by_class": concave_by_class,
        "concave_total": sum(concave_by_class.values()),
        "alignment_mean": mean,
        "alignment_pairs": pairs,
        "tpi_fallback_count": plate_set.fallback_count,
        "tpi_fallback_share": (
            plate_set.fallback_count / plate_set.triangle_count if plate_set.triangle_count else 0.0
        ),
        "planarity_residual": _planarity(interior, agents),
        "rejections": rejections,
        # 8(c): satisfied by a jittered seed with zero iterations. Report, never assert.
        "identities": {
            "euler": euler(agents, tris),
            "valence_defect_sum": sum((6 - k) * v for k, v in valence.items()),
            "triangle_count": plate_set.triangle_count,
        },
        "wall_time_s": None,
        "timber": None,
    }

    if cfg.geometry_json:
        from viz import geometry_payload, write_geometry_json
        write_geometry_json(
            cfg.geometry_json,
            geometry_payload(
                cfg, surface, agents, plate_set, tris,
                length=cfg.monge_length if cfg.surface == "monge" else None,
            ),
        )
        payload["geometry_json"] = str(cfg.geometry_json)

    if not cfg.no_timber:
        stage = _timber_stage(cfg, surface, agents, interior, result.spacing)
        # the model itself is not JSON-serialisable and does not go in the payload; the
        # BTLx stage takes it from here
        payload["timber"] = stage.diagnostics
        payload["timber_model"] = stage.model
        if cfg.mesh:
            from viz import export_mesh
            # BEFORE the BTLx stage, which clears every element's cached geometry to get
            # past the <Shape> writer crash (see btlx.export_btlx). Tesselating afterwards
            # would rebuild all 85 solids for nothing.
            payload["mesh"] = export_mesh(stage.model, cfg.mesh)
        if cfg.btlx:
            payload["btlx"] = _btlx_stage(cfg, stage.model)

    payload["wall_time_s"] = time.perf_counter() - started
    if cfg.json_path:
        with open(cfg.json_path, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in payload.items() if k != "timber_model"}, fh, indent=2)
    return payload


def _timber_stage(cfg, surface, agents, plates, spacing):
    """The Level 2/3 stages, kept behind one call so Level 1 never imports COMPAS.

    That separation is the point of the whole file layout: a geometry regression must not be
    maskable by a fabrication-library failure, so `--no-timber` has to be a path that
    touches no COMPAS code at all.
    """
    try:
        from timber import build_timber_model
    except ImportError as exc:                     # pragma: no cover
        raise SystemExit(
            "the timber stage is unavailable; "
            f"pass --no-timber to stop after Level 1 geometry [{exc}]"
        )
    return build_timber_model(cfg, surface, agents, plates, spacing)


def _btlx_stage(cfg, model) -> Dict[str, Any]:
    """Write the BTLx and, where the archive and the validator venv are present, validate.

    `validated` is a THREE-valued field on purpose. "0 errors" and "not checked" must never
    look the same, and they would if a missing schema quietly reported a clean file.
    """
    from btlx import declared_version, export_btlx, read_back, validate_btlx, validator_available

    export_btlx(model, cfg.btlx)
    out: Dict[str, Any] = {
        "path": str(cfg.btlx),
        "declared_version": declared_version(cfg.btlx),
        "validated": None,
        "errors": None,
    }
    if validator_available():
        errors = validate_btlx(cfg.btlx)
        out["validated"] = True
        out["errors"] = errors
    back = read_back(cfg.btlx)
    out["read_back"] = {
        "part_count": back["part_count"],
        "thicknesses": sorted(set(round(t, 6) for t in back["thicknesses"])),
        "contour_counts": sorted(set(back["contour_counts"])),
        "element_number_collisions": len(back["element_numbers"]) - len(set(back["element_numbers"])),
    }
    return out


def report(payload: Dict[str, Any]) -> str:
    lines = [
        f"surface {payload['surface']} ({payload['layout']} seed, rng {payload['rng_seed']})",
        f"agents {payload['realised_count']} realised of {payload['nominal_count']} nominal, "
        f"spacing {payload['spacing']:.4f}",
        f"solver {payload['iterations']} iterations, "
        f"{'converged' if payload['converged'] else 'NOT converged'}, "
        f"maxDisp {payload['max_disp_first']:.4g} -> {payload['max_disp_last']:.4g} "
        f"({payload['max_disp_first'] / payload['max_disp_last']:.0f}x)",
        f"plates {payload['plate_count']}, interior {payload['interior_plate_count']}, "
        f"hexagons {payload['hexagon_share']:.1%}",
        f"TPI fallbacks {payload['tpi_fallback_count']} of "
        f"{payload['identities']['triangle_count']} triangles "
        f"({payload['tpi_fallback_share']:.1%})",
    ]
    for cls, d in sorted(payload["side_ratio"].items()):
        if not d["count"]:
            lines.append(f"  {cls:<10} n=0    (class empty -- its median is UNDEFINED, not 0)")
            continue
        lines.append(
            f"  {cls:<10} n={d['count']:<4} side ratio median {d['median']:.2f} "
            f"p10 {d['p10']:.2f}   convex {payload['convex_by_class'][cls]}/{d['count']}"
        )
    lines.append(
        f"alignment {payload['alignment_mean']:.2f} over {payload['alignment_pairs']} pairs"
    )
    pr = payload["planarity_residual"]
    lines.append(
        f"planarity residual median {pr['median']:.4g}, p90 {pr['p90']:.4g}, max {pr['max']:.4g} "
        "(metres; non-zero wherever a TPI guard fired)"
    )
    lines.append(
        f"neighbour distance std {payload['neighbour_distance_std']:.4f} against a seed "
        f"jitter spread of {payload['seed_jitter_spread']:.4f}"
    )
    lines.append(
        "rejections " + ", ".join(f"{k}={v}" for k, v in sorted(payload["rejections"].items()))
    )
    ident = payload["identities"]
    lines.append(
        f"identities (NOT evidence -- a jittered seed with zero iterations passes these): "
        f"Euler {ident['euler']}, valence defect sum {ident['valence_defect_sum']}, "
        f"triangles {ident['triangle_count']}"
    )
    tb = payload.get("timber")
    if tb is None:
        lines.append("timber stage not run (--no-timber)")
    else:
        lines.append(
            f"timber {tb['element_count']} elements of {tb['input_plate_count']} interior "
            f"plates, {tb['rejected_count']} rejected"
            + (
                " (" + ", ".join(f"{k}={v}" for k, v in sorted(tb["rejections_by_reason"].items())) + ")"
                if tb["rejections_by_reason"]
                else ""
            )
            + f", thickness {tb['thickness_mm']:.1f} mm, min side {tb['min_side_mm']:.1f} mm"
        )
        lines.append(
            f"  planarisation residual median {tb['planarity_residual_mm']['median']:.1f} mm, "
            f"max {tb['planarity_residual_mm']['max']:.1f} mm -> coplanar to "
            f"{tb['coplanarity_after_mm']['max']:.2g} mm "
            f"(budget {tb['planarity_budget_mm']:.2g})"
        )
    bx = payload.get("btlx")
    if bx is not None:
        verdict = (
            f"{len(bx['errors'])} schema errors" if bx["validated"]
            else "NOT VALIDATED (no validator venv or no schema archive -- not the same as clean)"
        )
        rb = bx["read_back"]
        lines.append(
            f"btlx {bx['path']} v{bx['declared_version']}, {verdict}; read back "
            f"{rb['part_count']} parts, thickness {rb['thicknesses']} mm, "
            f"contours per part {rb['contour_counts']} (the reader duplicates them), "
            f"{rb['element_number_collisions']} ElementNumber collisions"
        )
    if payload.get("geometry_json"):
        lines.append(
            f"geometry {payload['geometry_json']} -- draw it with the SYSTEM python: "
            f"python ..\\dotnet\\render.py {payload['geometry_json']} out.png"
        )
    mesh = payload.get("mesh")
    if mesh:
        lines.append(
            f"mesh {mesh['path']} -- {mesh['element_count']} solids, {mesh['face_count']} faces, "
            f"{mesh['unit']} (viewers carry no units: a 2.4 m plate reads as 2400)"
        )
    lines.append(f"wall time {payload['wall_time_s']:.2f} s")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    cfg = build_config(argv)
    print(report(run(cfg)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
