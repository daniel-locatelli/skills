"""Two ways to look at a run, neither of which adds a dependency to the solver environment.

That constraint shapes the whole file. The solver environment needs numpy and scipy and
nothing else -- no PIL, no matplotlib, no viewer -- so this module writes FILES and lets
something else draw them.

  `--geometry-json`  the diagnostic drawing. Writes the schema that the .NET harness's
                     `hosts/dotnet/render.py` already consumes, so the same script draws
                     both hosts and the two sets of PNGs are directly comparable. Render it
                     with any interpreter that has PIL:

                         python run.py ... --geometry-json out.json --no-timber
                         python ..\dotnet\render.py out.json out.png

                     Four images: plan (K<0 shaded pink, fallback triangles amber, plates
                     green where convex and red where not), axonometric, and a catalogue of
                     every hyperbolic and every elliptic plate seen along its own normal.
                     The catalogue is the one that settles "do these look like bow-ties".

  `--mesh`           the actual compas_timber SOLIDS, tesselated and written as OBJ or STL
                     -- millimetres, and the built Breps rather than a re-plot of the numpy
                     rings, so it shows the thickness, the rejections and anything the
                     timber stage did that the geometry layer did not. Opens in Windows 3D
                     Viewer, Blender, Rhino, FreeCAD or any web viewer.

The geometry-JSON half imports nothing but numpy, so `--no-timber --geometry-json` is a
Level 1 picture that touches no COMPAS -- same rule as everywhere else in this host.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import numpy as np


def _kneg_grid(surface, length: float, n: int = 80) -> List[List[int]]:
    """Cells of an n x n grid over [-L/2, L/2]^2 where K < 0, for the plan view's shading.

    Only meaningful for a height field over the xy plane. On a sphere or a tube the xy
    plane is not a chart -- two points share an (x, y) -- so this returns empty rather than
    a picture of the near half pretending to be the whole.
    """
    if not hasattr(surface, "_f"):
        return []
    out = []
    for i in range(n):
        x = -0.5 * length + length * (i + 0.5) / n
        for j in range(n):
            y = -0.5 * length + length * (j + 0.5) / n
            if surface.gaussian_at(x, y) < 0.0:
                out.append([i, j])
    return out


def geometry_payload(cfg, surface, agents, plate_set, tris, length: Optional[float] = None):
    """The drawing schema `hosts/dotnet/render.py` reads. Metres, like everything upstream.

    Every plate is emitted, boundary ones included, and `boundary` says which. The drawing
    is where you WANT the dropped ring visible -- the whole question a plan view answers is
    what the boundary drop took, and a picture of the survivors alone cannot answer it.
    """
    if length is None:
        p = np.asarray(agents.p, dtype=float)
        # np.ptp(a), not a.ptp() -- numpy 2 removed the method
        length = float(max(np.ptp(p[:, 0]), np.ptp(p[:, 1]))) or 1.0

    fallback = plate_set.tri_is_fallback
    if fallback is None:
        fallback = np.zeros(len(tris), dtype=bool)

    payload: Dict[str, Any] = {
        "L": length,
        "surface": cfg.surface,
        "agents": [[float(c) for c in q] for q in agents.p],
        "kneg": _kneg_grid(surface, length),
        "tris": [
            [int(a), int(b), int(c), bool(fallback[t])]
            for t, (a, b, c) in enumerate(np.asarray(tris, dtype=int).reshape(-1, 3))
        ],
        "plates": [
            {
                "v": [[float(c) for c in v] for v in pl.ring],
                "convex": bool(pl.is_convex),
                "K": float(pl.k),
                "boundary": bool(pl.touches_boundary),
                "class": pl.curvature_class,
                "agent": int(pl.agent_index),
                "fallback_vertices": int(np.count_nonzero(pl.ring_is_fallback)),
            }
            for pl in plate_set.plates
        ],
    }
    return payload


def write_geometry_json(path, payload) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def export_mesh(model, path) -> Dict[str, Any]:
    """Tesselate every built solid into one mesh and write it. `.stl` or `.obj` by suffix.

    Millimetres, because that is the unit the model is in -- see timber.py. Most viewers do
    not carry units, so a 2.4 m plate arrives as 2400 of whatever the viewer calls a unit.
    """
    from compas.datastructures import Mesh

    path = str(path)
    joined = Mesh()
    faces = 0
    for element in model.elements():
        mesh = element.geometry.to_viewmesh()
        index = {
            key: joined.add_vertex(x=x, y=y, z=z)
            for key, (x, y, z) in zip(mesh.vertices(), mesh.vertices_attributes("xyz"))
        }
        for face in mesh.faces():
            joined.add_face([index[v] for v in mesh.face_vertices(face)])
            faces += 1

    if path.lower().endswith(".obj"):
        joined.to_obj(path)
    else:
        joined.to_stl(path)
    return {
        "path": path,
        "unit": "MM",
        "element_count": len(list(model.elements())),
        "vertex_count": joined.number_of_vertices(),
        "face_count": faces,
    }
