"""Per-object shape statistics in metres, and the form label the agent reads.

Form comes from the principal extents e1 >= e2 >= e3 of the mesh vertices:
linear when e1/e2 >= RATIO (named by the long axis), plate when e2/e3 >= RATIO
(named by the plate's own orientation: a slab is plate-horizontal, a wall
plate-vertical), else bulky.
"""
import numpy as np

RATIO = 4.0
FLOOR = 1e-3        # m; a flat mesh has e3 = 0
VERTICAL = 0.966    # |z| of a unit axis >= cos 15 deg
HORIZONTAL = 0.259  # |z| <= sin 15 deg


def points(mesh, scale):
    return np.array([[v.X, v.Y, v.Z] for v in mesh.Vertices], dtype=float) * scale


def direction(axis):
    z = abs(axis[2])
    if z >= VERTICAL:
        return "vertical"
    if z <= HORIZONTAL:
        return "horizontal"
    return "sloped"


def stats(pts):
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centred = pts - pts.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    proj = centred @ vt.T
    ext = proj.max(axis=0) - proj.min(axis=0)
    order = np.argsort(-ext)
    ext, axes = list(ext[order]), vt[order]
    while len(ext) < 3:
        ext.append(0.0)
    e1, e2, e3 = ext
    if e1 / max(e2, FLOOR) >= RATIO:
        form = "linear-" + direction(axes[0])
    elif e2 / max(e3, FLOOR) >= RATIO:
        normal = direction(axes[2]) if len(axes) == 3 else "vertical"
        form = "plate-" + {"vertical": "horizontal", "horizontal": "vertical"}.get(normal, "sloped")
    else:
        form = "bulky"
    return {
        "size": [round(float(x), 4) for x in hi - lo],
        "slenderness": round(e1 / max(e3, FLOOR), 2),
        "form": form,
        "zMin": round(float(lo[2]), 4),
        "zMax": round(float(hi[2]), 4),
        "bbox": (lo, hi),
    }


def summary(values):
    a = np.asarray(values, dtype=float)
    return {"min": round(float(a.min()), 4), "median": round(float(np.median(a)), 4),
            "max": round(float(a.max()), 4)}
