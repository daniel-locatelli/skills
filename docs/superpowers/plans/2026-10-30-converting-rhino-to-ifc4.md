# converting-rhino-to-ifc4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `converting-rhino-to-ifc4` skill: an agent reads a per-layer inventory of a Rhino .3dm, classifies each layer (or shape cluster) into an IFC class, and a CLI writes and validates the IFC4 file.

**Architecture:** One CLI, `scripts/rhino2ifc.py` (`inventory`, `convert`, `validate`), over a small package `scripts/r2i/`: `model` reads the .3dm into world-space meshed items with rhino3dm (cached render meshes, blocks exploded), `shape` computes per-object statistics and a form label, `inventory` groups items into mapping keys and splits mixed layers into clusters, `mapping` validates the agent's `mapping.json` against the keys and the IFC schema, `writer` emits the IFC with ifcopenshell, `checks` validates it. The agent's judgement lives in `SKILL.md` and `reference/ifc-classes.md`.

**Tech Stack:** Python 3.10+, rhino3dm, ifcopenshell, numpy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-30-converting-rhino-to-ifc4-design.md`

**Provenance:** Every code block below was run as a prototype before this plan was written: 51 tests pass, and HIL.3dm (19,003 objects) gives inventory in 6 s, convert in 7 s, and a 12 MB IFC4 file that validates. Copy the code as written. If a step's result differs from the "Expected" line, stop and report; do not change the code to make it pass.

## Global Constraints

- Skill folder: `skills/bim/converting-rhino-to-ifc4/` in the new bucket `skills/bim/`.
- Default schema `IFC4`; `IFC4X3_ADD2` only when the mapping says so. The schema is chosen only in `mapping.json`.
- Offline: no Rhino, no RhinoCommon, no network. Dependencies: `rhino3dm>=8.35`, `ifcopenshell>=0.9`, `numpy>=2.0` (tested with rhino3dm 8.35.0, ifcopenshell 0.9.0.post1, numpy 2.5.4).
- Every CLI outcome is JSON on stdout. Exit codes: `0` ok, `2` input error, `3` objects without a cached mesh, `4` validation failed.
- The IFC header has empty author and organization, `originating_system` `rhino2ifc`, and no IfcOwnerHistory, IfcPerson or IfcOrganization.
- Lengths in the IFC are metres.
- Windows paths: commands are for Git Bash from the repo root `C:\repos\github\daniel-locatelli\skills`; the venv lives at `.venv/` (git-ignored).
- Commit only the paths each task names (`git commit <paths> -m ...`). Never `git add -A`, `git commit -a`, `git stash` or `git reset`. `skills/git/preparing-pull-request/SKILL.md` has an unrelated uncommitted change: leave it alone.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File Structure

```
skills/bim/README.md                              bucket README                        (Task 5)
skills/bim/converting-rhino-to-ifc4/
  SKILL.md                                        workflow + classification rules      (Task 5)
  requirements.txt                                dependencies                         (Task 1)
  reference/ifc-classes.md                        class signatures, name cues, traps   (Task 5)
  scripts/rhino2ifc.py                            CLI                                  (Tasks 2-4)
  scripts/r2i/__init__.py, errors.py              package, the one error type          (Task 1)
  scripts/r2i/model.py                            .3dm -> world-space meshed items     (Task 1)
  scripts/r2i/shape.py                            per-object statistics, form label    (Task 2)
  scripts/r2i/inventory.py                        keys, clusters, inventory.json       (Task 2)
  scripts/r2i/mapping.py                          mapping.json validation              (Task 3)
  scripts/r2i/writer.py                           IFC writer                           (Task 3)
  scripts/r2i/checks.py                           IFC validation report                (Task 4)
  tests/make_fixture.py                           builds the test .3dm                 (Task 1)
  tests/conftest.py                               run(), MAPPING, fixtures             (Task 1)
  tests/test_model.py, test_inventory.py, test_mapping.py, test_convert.py, test_validate.py
.gitignore                                        + .venv/                             (Task 1)
README.md, CHANGELOG.md, .claude-plugin/plugin.json, .claude-plugin/marketplace.json  (Task 5)
```

---

### Task 1: Package, model reader and test fixture

**Files:**
- Create: `skills/bim/converting-rhino-to-ifc4/requirements.txt`
- Create: `skills/bim/converting-rhino-to-ifc4/scripts/r2i/__init__.py`, `skills/bim/converting-rhino-to-ifc4/scripts/r2i/errors.py`, `skills/bim/converting-rhino-to-ifc4/scripts/r2i/model.py`
- Create: `skills/bim/converting-rhino-to-ifc4/tests/make_fixture.py`, `skills/bim/converting-rhino-to-ifc4/tests/conftest.py`
- Test: `skills/bim/converting-rhino-to-ifc4/tests/test_model.py`
- Modify: `.gitignore` (append `.venv/`)

**Interfaces:**
- Produces: `R2IError(code, message, fix=None, **extra)` with `.code`, `.to_json()`.
- Produces: `model.read(path) -> Model` with `.doc`, `.unit`, `.scale` (to metres), `.items: list[Item]`, `.non_geometric: {layer: {type: count}}`, `.layer_colours: {layer: (r, g, b)}`.
- Produces: `Item(key, kind, layer, object_id, name, geometry_type, colour, mesh)`; `kind` is `"layer"` or `"block"`; `mesh` is a world-space `rhino3dm.Mesh` in model units, or `None` when no cached mesh exists.
- Produces: `model.north(model, layer_path) -> (x, y)`; raises `R2IError` code 2 when the layer has no curve.
- Produces: `make_fixture.build(path, missing_mesh=False) -> path`; the `conftest` helpers `run(*args) -> (exit code, JSON)`, `write_mapping(tmp_path, entries=MAPPING, schema="IFC4") -> path`, `layer(inventory, key) -> record`, `MAPPING`, and the session fixture `model3dm`.

- [ ] **Step 1: Create the venv and requirements**

`skills/bim/converting-rhino-to-ifc4/requirements.txt`:

```text
rhino3dm>=8.35
ifcopenshell>=0.9
numpy>=2.0
pytest>=8
```

Append one line to `.gitignore`:

```text
.venv/
```

Run: `python -m venv .venv && .venv/Scripts/python -m pip install -q -r skills/bim/converting-rhino-to-ifc4/requirements.txt && .venv/Scripts/python -c "import rhino3dm, ifcopenshell, numpy; print(rhino3dm.__version__, ifcopenshell.version)"`
Expected: a version line such as `8.35.0 0.9.0.post1`.

- [ ] **Step 2: Write the fixture builder, conftest and failing tests**

`skills/bim/converting-rhino-to-ifc4/tests/make_fixture.py`:

```python
"""Build the test .3dm with rhino3dm (metres).

Layers: Existing::Stützen (3 columns, one named C1), Layer 01 (2 columns and
2 floor slabs: mixed), Terrain (one flat mesh), Furniture (an instance of
block Chair coloured by object, and an instance of block Set, which nests a
Chair 1 m along x), Notes (a line), North (a line pointing north-east).
missing_mesh=True adds layer Solids with a Brep box that has no cached mesh.
"""
import sys

import rhino3dm as r


def box(x, y, z, dx, dy, dz):
    m = r.Mesh()
    for X, Y, Z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        m.Vertices.Add(x + X * dx, y + Y * dy, z + Z * dz)
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        m.Faces.AddFace(*q)
    return m


def layer(f, name, colour, parent=None):
    lay = r.Layer()
    lay.Name = name
    lay.Color = colour + (255,)
    if parent is not None:
        lay.ParentLayerId = f.Layers.FindIndex(parent).Id
    return f.Layers.Add(lay)


def attrs(index, name="", colour=None, from_parent=False):
    a = r.ObjectAttributes()
    a.LayerIndex = index
    a.Name = name
    if colour:
        a.ColorSource = r.ObjectColorSource.ColorFromObject
        a.ObjectColor = colour + (255,)
    elif from_parent:
        a.ColorSource = r.ObjectColorSource.ColorFromParent
    return a


def build(path, missing_mesh=False):
    f = r.File3dm()
    f.Settings.ModelUnitSystem = r.UnitSystem.Meters
    existing = layer(f, "Existing", (128, 128, 128))
    stuetzen = layer(f, "Stützen", (255, 0, 0), parent=existing)
    for i, x in enumerate((0, 5, 10)):
        f.Objects.AddMesh(box(x, 0, 0, 0.4, 0.4, 3.0), attrs(stuetzen, "C1" if i == 0 else ""))
    mixed = layer(f, "Layer 01", (200, 200, 200))
    for x in (0, 5):
        f.Objects.AddMesh(box(x, 10, 0, 0.3, 0.3, 3.0), attrs(mixed))
    for z in (0.0, 3.0):
        f.Objects.AddMesh(box(0, 10, z, 8, 8, 0.25), attrs(mixed))
    terrain = layer(f, "Terrain", (120, 90, 60))
    ground = r.Mesh()
    for x, y in [(-10, -10), (20, -10), (20, 20), (-10, 20)]:
        ground.Vertices.Add(x, y, -0.5)
    ground.Faces.AddFace(0, 1, 2, 3)
    f.Objects.AddMesh(ground, attrs(terrain))
    parts = layer(f, "Furniture parts", (0, 0, 0))
    furniture = layer(f, "Furniture", (0, 255, 0))
    chair = f.InstanceDefinitions.Add("Chair", "", "", "", r.Point3d(0, 0, 0),
                                      (box(0, 0, 0, 0.5, 0.5, 0.5),),
                                      (attrs(parts, from_parent=True),))
    chair_id = f.InstanceDefinitions.FindIndex(chair).Id
    nested = f.InstanceDefinitions.Add(
        "Set", "", "", "", r.Point3d(0, 0, 0),
        (r.InstanceReference(chair_id, r.Transform.Translation(1, 0, 0)),),
        (attrs(parts, from_parent=True),))
    f.Objects.AddInstanceObject(r.InstanceReference(chair_id, r.Transform.Translation(2, 2, 0)),
                                attrs(furniture, colour=(0, 0, 255)))
    f.Objects.AddInstanceObject(
        r.InstanceReference(f.InstanceDefinitions.FindIndex(nested).Id,
                            r.Transform.Translation(10, 0, 0)), attrs(furniture))
    notes = layer(f, "Notes", (0, 0, 0))
    f.Objects.AddLine(r.Point3d(0, 0, 0), r.Point3d(5, 0, 0), attrs(notes))
    north = layer(f, "North", (0, 0, 0))
    f.Objects.AddLine(r.Point3d(0, 0, 0), r.Point3d(1, 1, 0), attrs(north))
    if missing_mesh:
        solids = layer(f, "Solids", (0, 0, 0))
        f.Objects.AddBrep(r.Brep.CreateFromBox(r.Box(r.BoundingBox(0, 0, 0, 1, 1, 1))),
                          attrs(solids))
    if not f.Write(str(path), 8):
        raise RuntimeError("could not write %s" % path)
    return path


if __name__ == "__main__":
    build(sys.argv[1], missing_mesh="--missing-mesh" in sys.argv)
```

`skills/bim/converting-rhino-to-ifc4/tests/conftest.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE.parent / "scripts" / "rhino2ifc.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCRIPT.parent))

import make_fixture  # noqa: E402

MAPPING = [
    {"key": "Existing::Stützen", "class": "IfcColumn", "merge": False,
     "confidence": "high", "rationale": "vertical, slender; 'Stützen' = columns"},
    {"key": "Layer 01#1", "class": "IfcColumn", "merge": False,
     "confidence": "medium", "rationale": "linear-vertical"},
    {"key": "Layer 01#2", "class": "IfcSlab", "predefinedType": "floor", "merge": False,
     "confidence": "medium", "rationale": "plate-horizontal at two levels"},
    {"key": "Terrain", "class": "IfcGeographicElement", "predefinedType": "TERRAIN",
     "merge": True, "confidence": "high", "rationale": "flat mesh named Terrain"},
    {"key": "Chair", "class": "IfcFurniture", "merge": False,
     "confidence": "high", "rationale": "block named Chair"},
    {"key": "Set", "class": "IfcFurniture", "merge": False,
     "confidence": "medium", "rationale": "block nesting a chair"},
]


def run(*args):
    """Run the CLI; (exit code, parsed stdout JSON)."""
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout)


def write_mapping(tmp_path, entries=MAPPING, schema="IFC4"):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"schema": schema, "entries": entries}), encoding="utf-8")
    return path


def layer(inv, key):
    return next(rec for rec in inv["layers"] if rec["key"] == key)


@pytest.fixture(scope="session")
def model3dm(tmp_path_factory):
    return make_fixture.build(tmp_path_factory.mktemp("m") / "fixture.3dm")
```

`skills/bim/converting-rhino-to-ifc4/tests/test_model.py`:

```python
import pytest

import make_fixture
from r2i import model
from r2i.errors import R2IError


@pytest.fixture(scope="module")
def m(model3dm):
    return model.read(model3dm)


def items(m, key):
    return [it for it in m.items if it.key == key]


def test_units(m):
    assert (m.unit, m.scale) == ("Meters", 1.0)


def test_layer_items(m):
    cols = items(m, "Existing::Stützen")
    assert len(cols) == 3 and {it.kind for it in cols} == {"layer"}
    assert [it.name for it in cols] == ["C1", "", ""]
    assert cols[0].colour == (255, 0, 0)
    assert all(it.mesh is not None for it in cols)


def test_block_items_world_space_and_colour(m):
    chair, = items(m, "Chair")
    assert chair.kind == "block" and chair.layer == "Furniture"
    assert chair.colour == (0, 0, 255)  # by parent -> the instance's object colour
    xs = [v.X for v in chair.mesh.Vertices]
    assert min(xs) == 2.0
    nested, = items(m, "Set")
    assert min(v.X for v in nested.mesh.Vertices) == 11.0  # 10 (Set) + 1 (Chair in Set)
    assert nested.colour == (0, 255, 0)


def test_definition_geometry_not_listed_twice(m):
    assert len(m.items) == 3 + 4 + 1 + 2


def test_non_geometric(m):
    assert m.non_geometric == {"Notes": {"LineCurve": 1}, "North": {"LineCurve": 1}}


def test_missing_mesh_kept_as_none(tmp_path):
    m = model.read(make_fixture.build(tmp_path / "s.3dm", missing_mesh=True))
    solid, = items(m, "Solids")
    assert solid.mesh is None and solid.geometry_type == "Brep"


def test_north(m):
    assert model.north(m, "North") == pytest.approx((0.7071068, 0.7071068))
    with pytest.raises(R2IError) as exc:
        model.north(m, "Terrain")
    assert exc.value.code == 2


def test_unreadable_file(tmp_path):
    bad = tmp_path / "bad.3dm"
    bad.write_text("not a model")
    with pytest.raises(R2IError) as exc:
        model.read(bad)
    assert exc.value.code == 2
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_model.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'r2i'`.

- [ ] **Step 4: Implement the package and model reader**

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/__init__.py`:

```python
"""rhino2ifc internals: model (read .3dm), shape (per-object statistics),
inventory (keys and clusters), mapping (validate the agent's classes),
writer (IFC), checks (validate an IFC)."""
```

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/errors.py`:

```python
"""The one error type: an exit code, a message, the fix, and any extra JSON."""


class R2IError(Exception):
    """Exit codes: 2 input, 3 objects without a cached mesh, 4 validation failed."""

    def __init__(self, code, message, fix=None, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.extra = extra

    def to_json(self):
        out = {"code": self.code, "message": self.message}
        if self.fix:
            out["fix"] = self.fix
        out.update(self.extra)
        return out
```

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/model.py`:

```python
"""Read a .3dm with rhino3dm into world-space items, one per meshable object.

rhino3dm cannot tessellate: Brep and Extrusion geometry comes from the render
meshes Rhino cached in the file. An item whose mesh is missing keeps
`mesh=None`; callers decide whether that stops the run.
"""
from dataclasses import dataclass, field

import rhino3dm as r

from .errors import R2IError

UNIT_TO_M = {
    "Microns": 1e-6, "Millimeters": 1e-3, "Centimeters": 1e-2, "Decimeters": 0.1,
    "Meters": 1.0, "Kilometers": 1e3, "Inches": 0.0254, "Feet": 0.3048,
    "Yards": 0.9144, "Miles": 1609.344,
}
MESHABLE = (r.Mesh, r.Brep, r.Extrusion, r.Surface, r.SubD)
MAX_NESTING = 32


@dataclass
class Item:
    key: str            # layer path, or the outermost block definition name
    kind: str           # "layer" | "block"
    layer: str          # layer path of the top-level object (the instance, for blocks)
    object_id: str      # Rhino GUID of the top-level object
    name: str           # Rhino object name ("" when unset)
    geometry_type: str  # rhino3dm class name of the meshed geometry
    colour: tuple       # (r, g, b), 0-255
    mesh: object        # rhino3dm.Mesh in world coordinates, model units; None = no cached mesh


@dataclass
class Model:
    doc: object                 # rhino3dm.File3dm
    unit: str
    scale: float                # model unit -> metres
    items: list = field(default_factory=list)
    non_geometric: dict = field(default_factory=dict)  # layer path -> {type: count}
    layer_colours: dict = field(default_factory=dict)  # layer path -> (r, g, b)


def mesh_of(geom):
    """The cached mesh of a meshable geometry, or None."""
    if isinstance(geom, r.Mesh):
        return geom
    if isinstance(geom, r.Brep):
        out = r.Mesh()
        for face in geom.Faces:
            m = face.GetMesh(r.MeshType.Render)
            if m is None:
                m = face.GetMesh(r.MeshType.Any)
            if m is None:
                return None
            out.Append(m)
        return out
    if isinstance(geom, r.Extrusion):
        m = geom.GetMesh(r.MeshType.Render)
        return m if m is not None else geom.GetMesh(r.MeshType.Any)
    return None  # Surface, SubD: rhino3dm exposes no cached mesh


def colour_of(attrs, layer_colour, parent_colour):
    src = attrs.ColorSource
    if src == r.ObjectColorSource.ColorFromObject:
        return tuple(attrs.ObjectColor[:3])
    if src == r.ObjectColorSource.ColorFromParent and parent_colour is not None:
        return parent_colour
    return layer_colour


def read(path):
    doc = r.File3dm.Read(str(path))
    if doc is None:
        raise R2IError(2, "cannot read %s" % path, "check the path; it must be a Rhino .3dm file")
    unit = doc.Settings.ModelUnitSystem.name
    if unit not in UNIT_TO_M:
        raise R2IError(2, "unsupported model unit %s" % unit,
                       "set a metric or imperial unit in Rhino (Document Properties > Units)")
    model = Model(doc=doc, unit=unit, scale=UNIT_TO_M[unit])
    layers = {layer.Index: layer for layer in doc.Layers}
    for layer in layers.values():
        model.layer_colours[layer.FullPath] = tuple(layer.Color[:3])
    defs = {d.Id: d for d in doc.InstanceDefinitions}

    for obj in doc.Objects:
        attrs = obj.Attributes
        if attrs.IsInstanceDefinitionObject:
            continue
        path = layers[attrs.LayerIndex].FullPath
        colour = colour_of(attrs, model.layer_colours[path], None)
        geom = obj.Geometry
        top = dict(layer=path, object_id=str(attrs.Id), name=attrs.Name or "")
        if isinstance(geom, r.InstanceReference):
            idef = defs[geom.ParentIdefId]
            _explode(model, layers, defs, idef, geom.Xform, colour,
                     dict(top, key=idef.Name, kind="block"), 0)
        elif isinstance(geom, MESHABLE):
            model.items.append(Item(key=path, kind="layer", geometry_type=type(geom).__name__,
                                    colour=colour, mesh=mesh_of(geom), **top))
        else:
            counts = model.non_geometric.setdefault(path, {})
            name = type(geom).__name__
            counts[name] = counts.get(name, 0) + 1
    return model


def _explode(model, layers, defs, idef, xform, parent_colour, top, depth):
    if depth > MAX_NESTING:
        raise R2IError(2, "block %s nests deeper than %d" % (top["key"], MAX_NESTING),
                       "explode the block in Rhino")
    for oid in idef.GetObjectIds():
        obj = model.doc.Objects.FindId(oid)
        if obj is None:
            continue
        attrs = obj.Attributes
        colour = colour_of(attrs, model.layer_colours[layers[attrs.LayerIndex].FullPath],
                           parent_colour)
        geom = obj.Geometry
        if isinstance(geom, r.InstanceReference):
            _explode(model, layers, defs, defs[geom.ParentIdefId],
                     r.Transform.Multiply(xform, geom.Xform), colour, top, depth + 1)
        elif isinstance(geom, MESHABLE):
            mesh = mesh_of(geom)
            if mesh is not None:
                mesh = mesh.Duplicate()
                mesh.Transform(xform)
            model.items.append(Item(geometry_type=type(geom).__name__, colour=colour,
                                    mesh=mesh, **top))


def north(model, layer_path):
    """(x, y) unit vector of the first curve on layer_path, start -> end."""
    for obj in model.doc.Objects:
        layer = model.doc.Layers.FindIndex(obj.Attributes.LayerIndex)
        geom = obj.Geometry
        if layer.FullPath == layer_path and isinstance(geom, r.Curve):
            a, b = geom.PointAtStart, geom.PointAtEnd
            dx, dy = b.X - a.X, b.Y - a.Y
            n = (dx * dx + dy * dy) ** 0.5
            if n > 0:
                return (round(dx / n, 9), round(dy / n, 9))
    raise R2IError(2, "no curve on layer %r for --north" % layer_path,
                   "draw one line pointing north on that layer, or drop --north")
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_model.py -q`
Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
git add skills/bim/converting-rhino-to-ifc4/requirements.txt skills/bim/converting-rhino-to-ifc4/scripts/r2i skills/bim/converting-rhino-to-ifc4/tests
git commit .gitignore skills/bim/converting-rhino-to-ifc4/requirements.txt skills/bim/converting-rhino-to-ifc4/scripts/r2i skills/bim/converting-rhino-to-ifc4/tests -m "feat(bim): rhino2ifc model reader and test fixture

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Shape statistics, inventory and the `inventory` command

**Files:**
- Create: `skills/bim/converting-rhino-to-ifc4/scripts/r2i/shape.py`, `skills/bim/converting-rhino-to-ifc4/scripts/r2i/inventory.py`, `skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py`
- Test: `skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py`

**Interfaces:**
- Consumes: `model.read`, `Item`, `R2IError` (Task 1).
- Produces: `shape.stats(points) -> {"size": [dx, dy, dz], "slenderness", "form", "zMin", "zMax", "bbox": (lo, hi)}`; `shape.points(mesh, scale) -> ndarray (n, 3)` in metres; `shape.summary(values) -> {"min", "median", "max"}`.
- Produces: `inventory.build(model) -> (doc, groups)`. `doc` is the inventory.json document (`units`, `objectCount`, `extent`, `keys`, `layers`, `nonGeometric`, and `error` when meshes are missing). `groups` is `{mapping key: [(Item, stats or None)]}`.
- Produces: `rhino2ifc.py inventory <in.3dm> [-o out.json]`: prints the document, or with `-o` writes it and prints `{"ok", "output", "keys", "objectCount"[, "error"]}`; exit 3 when meshes are missing.

- [ ] **Step 1: Write the failing tests**

`skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py`:

```python
import pytest

import make_fixture
from conftest import layer, run


@pytest.fixture(scope="module")
def inv(model3dm):
    code, doc = run("inventory", model3dm)
    assert code == 0, doc
    return doc


def test_keys_and_units(inv):
    assert inv["keys"] == ["Chair", "Existing::Stützen", "Layer 01#1", "Layer 01#2",
                           "Set", "Terrain"]
    assert inv["units"] == {"model": "Meters", "toMetres": 1.0}
    assert inv["objectCount"] == 10


def test_forms_and_statistics(inv):
    st = layer(inv, "Existing::Stützen")
    assert st["forms"] == {"linear-vertical": 3}
    assert st["size"]["dz"]["median"] == 3.0
    assert st["slenderness"]["median"] == 7.5
    assert layer(inv, "Terrain")["forms"] == {"plate-horizontal": 1}


def test_mixed_layer_split_into_clusters(inv):
    clusters = layer(inv, "Layer 01")["clusters"]
    assert [(c["key"], c["form"], c["count"]) for c in clusters] == [
        ("Layer 01#1", "linear-vertical", 2), ("Layer 01#2", "plate-horizontal", 2)]
    assert clusters[1]["zMin"] == {"min": 0.0, "median": 1.5, "max": 3.0}


def test_blocks_in_world_space(inv):
    assert layer(inv, "Chair")["kind"] == "block"
    assert layer(inv, "Chair")["bbox"]["min"] == [2.0, 2.0, 0.0]
    assert layer(inv, "Set")["bbox"]["min"] == [11.0, 0.0, 0.0]


def test_non_geometric_listed_not_keyed(inv):
    assert inv["nonGeometric"] == {"Notes": {"LineCurve": 1}, "North": {"LineCurve": 1}}
    assert "Notes" not in inv["keys"]


def test_output_file(model3dm, tmp_path):
    out = tmp_path / "inventory.json"
    code, summary = run("inventory", model3dm, "-o", out)
    assert code == 0 and summary["ok"] and summary["keys"] == 6
    assert out.read_text(encoding="utf-8").count("Stützen") >= 1


def test_missing_mesh_exit_3(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    code, doc = run("inventory", path)
    assert code == 3
    miss = doc["error"]["missingMesh"]
    assert miss[0]["key"] == "Solids" and miss[0]["geometryType"] == "Brep"
    assert "save it normally" in doc["error"]["fix"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py -q`
Expected: every test fails or errors; `run()` raises `JSONDecodeError` because `rhino2ifc.py` does not exist yet.

- [ ] **Step 3: Implement shape and inventory**

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/shape.py`:

```python
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
```

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/inventory.py`:

```python
"""Group items into mapping keys and summarise each key for the agent.

A key is a layer path or a block definition name. A key is mixed when two or
more forms each hold at least MIXED_SHARE of its meshed objects; it is then
split into clusters `<key>#1..n`, one per such form (largest first, ties by
form name), and objects of rarer forms join cluster 1. The agent maps the
cluster keys, never the mixed key itself.
"""
from collections import Counter

import numpy as np

from . import shape

MIXED_SHARE = 0.1


def resolve(model):
    """(records, groups): records for inventory.json; groups maps every
    mapping key to its [(item, stats)] (stats None when the mesh is missing)."""
    by_key = {}
    for item in model.items:
        by_key.setdefault(item.key, []).append(item)

    records, groups = [], {}
    for key, items in by_key.items():
        rows = [(it, shape.stats(shape.points(it.mesh, model.scale)) if it.mesh is not None else None)
                for it in items]
        meshed = [(it, st) for it, st in rows if st is not None]
        record = {
            "key": key,
            "kind": items[0].kind,
            "layer": items[0].layer if items[0].kind == "layer" else None,
            "count": len({it.object_id for it in items}),
            "geometryTypes": dict(Counter(it.geometry_type for it in items)),
            "colour": list(model.layer_colours.get(key, items[0].colour)),
            "missingMesh": [{"key": key, "objectId": it.object_id, "geometryType": it.geometry_type}
                            for it, st in rows if st is None],
        }
        record.update(_describe(meshed))
        forms = Counter(st["form"] for _, st in meshed)
        main = sorted((f for f, n in forms.items() if n >= MIXED_SHARE * len(meshed)),
                      key=lambda f: (-forms[f], f))
        if len(main) >= 2:
            record["clusters"] = []
            members = {f: [] for f in main}
            for it, st in meshed:
                members[st["form"] if st["form"] in members else main[0]].append((it, st))
            for i, f in enumerate(main, 1):
                ckey = "%s#%d" % (key, i)
                groups[ckey] = members[f]
                record["clusters"].append(dict({"key": ckey, "form": f,
                                                "count": len(members[f])}, **_describe(members[f])))
            groups.setdefault(key + "#1", []).extend((it, st) for it, st in rows if st is None)
        else:
            groups[key] = rows
        records.append(record)
    return records, groups


def _describe(rows):
    if not rows:
        return {}
    stats = [st for _, st in rows]
    lo = np.min([st["bbox"][0] for st in stats], axis=0)
    hi = np.max([st["bbox"][1] for st in stats], axis=0)
    return {
        "bbox": {"min": [round(float(x), 3) for x in lo], "max": [round(float(x), 3) for x in hi]},
        "forms": dict(Counter(st["form"] for st in stats)),
        "size": {axis: shape.summary([st["size"][i] for st in stats])
                 for i, axis in enumerate(("dx", "dy", "dz"))},
        "slenderness": shape.summary([st["slenderness"] for st in stats]),
        "zMin": shape.summary([st["zMin"] for st in stats]),
        "zMax": shape.summary([st["zMax"] for st in stats]),
    }


def build(model):
    """The inventory.json document and the groups convert needs."""
    records, groups = resolve(model)
    missing = [m for rec in records for m in rec["missingMesh"]]
    all_stats = [st for rows in groups.values() for _, st in rows if st is not None]
    doc = {
        "units": {"model": model.unit, "toMetres": model.scale},
        "objectCount": len({it.object_id for it in model.items}),
        "extent": _describe([(None, st) for st in all_stats]).get("bbox"),
        "keys": sorted(groups),
        "layers": records,
        "nonGeometric": model.non_geometric,
    }
    if missing:
        doc["error"] = {"code": 3, "missingMesh": missing,
                        "fix": "open the .3dm in Rhino and save it normally (not Save Small), "
                               "or mesh those objects via Cordyceps, then rerun inventory"}
    return doc, groups
```

- [ ] **Step 4: Write the CLI with the `inventory` command**

`skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py` (Tasks 3 and 4 replace this file with longer versions):

```python
#!/usr/bin/env python3
"""Rhino .3dm -> IFC4 (or IFC4X3_ADD2), classified by an agent.

  rhino2ifc.py inventory <in.3dm> [-o inventory.json]
  rhino2ifc.py convert <in.3dm> <mapping.json> -o <out.ifc>
               [--storeys [z1,z2,...]] [--georef EPSG:<code>,<E>,<N>,<H>[,<rot_deg>]]
               [--north <layer path>]
  rhino2ifc.py validate <file.ifc>

JSON on stdout for every outcome. Exit 0 ok, 2 input error, 3 objects
without a cached mesh, 4 validation failed.
"""
import argparse
import json
import sys

from r2i import inventory, model
from r2i.errors import R2IError


def emit(doc):
    print(json.dumps(doc, ensure_ascii=False, indent=2))


def cmd_inventory(args):
    doc, _ = inventory.build(model.read(args.model))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        emit({"ok": "error" not in doc, "output": args.output, "keys": len(doc["keys"]),
              "objectCount": doc["objectCount"], **({"error": doc["error"]} if "error" in doc else {})})
    else:
        emit(doc)
    return 3 if "error" in doc else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="rhino2ifc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inventory")
    s.add_argument("model")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_inventory)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except R2IError as exc:
        emit({"ok": False, "error": exc.to_json()})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_model.py skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py -q`
Expected: `15 passed`.

- [ ] **Step 6: Commit**

```bash
git add skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py
git commit skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_inventory.py -m "feat(bim): rhino2ifc inventory: per-key statistics, forms, clusters

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Mapping validation, IFC writer and the `convert` command

**Files:**
- Create: `skills/bim/converting-rhino-to-ifc4/scripts/r2i/mapping.py`, `skills/bim/converting-rhino-to-ifc4/scripts/r2i/writer.py`
- Modify: `skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py` (replace the whole file)
- Test: `skills/bim/converting-rhino-to-ifc4/tests/test_mapping.py`, `skills/bim/converting-rhino-to-ifc4/tests/test_convert.py`

**Interfaces:**
- Consumes: `inventory.build` and its `groups` (Task 2), `model.north` (Task 1).
- Produces: `mapping.load(path, keys) -> {"schema", "entries": {key: entry}}`. An entry is `{"key", "skip", "rationale"}` when skipped, else `{"key", "skip": False, "class" (canonical name), "predefinedType" (upper case or None), "objectType", "merge", "confidence", "rationale"}`. Raises `R2IError` code 2 with `problems=[...]`.
- Produces: `mapping.element_class(schema, name) -> (name, declaration) | None` and `mapping.predefined_types(declaration) -> set | None` (Task 5 uses both to check the reference).
- Produces: `writer.convert(model, groups, mapping, out_path, storeys=None|"auto"|[float], georef=None|(epsg, E, N, H, rot), north_layer=None) -> {"ok", "output", "schema", "elements": {class: n}, "storeys": [m], "skipped": [key]}`. Raises `R2IError` code 3 when a classified key holds objects without a mesh, or code 2 when `--storeys` finds no floor slabs.
- Produces: `rhino2ifc.py convert <in.3dm> <mapping.json> -o <out.ifc> [--storeys [z,...]] [--georef EPSG:c,E,N,H[,rot]] [--north <layer>]`.

- [ ] **Step 1: Write the failing tests**

`skills/bim/converting-rhino-to-ifc4/tests/test_mapping.py`:

```python
import pytest

from conftest import MAPPING, run, write_mapping


@pytest.mark.parametrize("change, expected", [
    (lambda m: m[:-1], "Set: missing"),
    (lambda m: m + [dict(m[0])], "key listed twice"),
    (lambda m: [dict(m[0], **{"class": "IfcWal"})] + m[1:], "not a concrete IfcElement"),
    (lambda m: [dict(m[0], **{"class": "IfcBuildingStorey"})] + m[1:], "not a concrete IfcElement"),
    (lambda m: m[:2] + [dict(m[2], predefinedType="CEILING")] + m[3:], "not in"),
    (lambda m: m[:2] + [dict(m[2], predefinedType="USERDEFINED")] + m[3:], "needs objectType"),
    (lambda m: [dict(m[0], **{"class": "IfcFurniture", "predefinedType": "X"})] + m[1:], "not in"),
    (lambda m: [dict(m[0], confidence="sure")] + m[1:], "confidence must be"),
    (lambda m: [dict(m[0], rationale="")] + m[1:], "rationale missing"),
    (lambda m: m + [{"key": "Nope", "skip": True, "rationale": "x"}], "not an inventory key"),
])
def test_problems_exit_2(model3dm, tmp_path, change, expected):
    code, doc = run("convert", model3dm, write_mapping(tmp_path, change(MAPPING)),
                    "-o", tmp_path / "x.ifc")
    assert code == 2
    assert any(expected in p for p in doc["error"]["problems"]), doc
    assert not (tmp_path / "x.ifc").exists()


def test_userdefined_with_object_type_accepted(model3dm, tmp_path):
    entries = MAPPING[:2] + [dict(MAPPING[2], predefinedType="userdefined",
                                  objectType="Podium")] + MAPPING[3:]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0, doc


def test_skip_accepted(model3dm, tmp_path):
    entries = MAPPING[:-1] + [{"key": "Set", "skip": True, "rationale": "not needed"}]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0 and doc["skipped"] == ["Set"]


def test_bad_schema(model3dm, tmp_path):
    code, doc = run("convert", model3dm, write_mapping(tmp_path, schema="IFC2X3"),
                    "-o", tmp_path / "x.ifc")
    assert code == 2 and "schema" in doc["error"]["message"]


def test_unreadable_mapping(model3dm, tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text("{not json", encoding="utf-8")
    code, doc = run("convert", model3dm, bad, "-o", tmp_path / "x.ifc")
    assert code == 2 and "cannot read mapping" in doc["error"]["message"]
```

`skills/bim/converting-rhino-to-ifc4/tests/test_convert.py`:

```python
import ifcopenshell
import pytest

import make_fixture
from conftest import MAPPING, run, write_mapping


@pytest.fixture(scope="module")
def ifc(model3dm, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ifc")
    out = tmp / "out.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp), "-o", out, "--storeys",
                    "--north", "North", "--georef", "EPSG:2056,2600000,1200000,400")
    assert code == 0, doc
    return ifcopenshell.open(str(out)), doc


def pset(element):
    for rel in element.IsDefinedBy:
        ps = rel.RelatingPropertyDefinition
        if ps.Name == "Pset_RhinoSource":
            return {p.Name: p.NominalValue.wrappedValue for p in ps.HasProperties}
    return None


@pytest.mark.parametrize("schema", ["IFC4", "IFC4X3_ADD2"])
def test_element_counts_per_schema(model3dm, tmp_path, schema):
    out = tmp_path / "out.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp_path, schema=schema), "-o", out)
    assert code == 0, doc
    assert doc["schema"] == schema
    assert doc["elements"] == {"IfcColumn": 5, "IfcSlab": 2, "IfcGeographicElement": 1,
                               "IfcFurniture": 2}
    assert ifcopenshell.open(str(out)).schema_identifier == schema


def test_names_and_pset(ifc):
    f, _ = ifc
    columns = f.by_type("IfcColumn")
    assert sorted(c.Name for c in columns) == ["C1", "Layer 01#1", "Layer 01#1",
                                               "Stützen", "Stützen"]
    ps = pset(next(c for c in columns if c.Name == "C1"))
    assert ps["LayerPath"] == "Existing::Stützen"
    assert ps["Confidence"] == "high" and "columns" in ps["Rationale"]
    assert len(ps["ObjectIds"]) == 36


def test_merged_element_and_tessellation(ifc):
    f, _ = ifc
    terrain, = f.by_type("IfcGeographicElement")
    assert terrain.PredefinedType == "TERRAIN"
    body = terrain.Representation.Representations[0]
    assert body.RepresentationType == "Tessellation"
    assert body.Items[0].is_a("IfcPolygonalFaceSet")


def test_predefined_type_upper_cased(ifc):
    f, _ = ifc
    assert {s.PredefinedType for s in f.by_type("IfcSlab")} == {"FLOOR"}


def test_terrain_on_site(ifc):
    f, _ = ifc
    terrain, = f.by_type("IfcGeographicElement")
    assert terrain.ContainedInStructure[0].RelatingStructure.is_a("IfcSite")


def test_storeys_detected(ifc):
    f, doc = ifc
    assert doc["storeys"] == [0.0, 3.0]
    storeys = {s.Name: s for s in f.by_type("IfcBuildingStorey")}
    upper = [e.Name for r in storeys["Level 1"].ContainsElements for e in r.RelatedElements]
    assert upper == ["Layer 01#2"]


def test_storeys_explicit(model3dm, tmp_path):
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", tmp_path / "x.ifc",
                    "--storeys", "3,0,6")
    assert code == 0 and doc["storeys"] == [0.0, 3.0, 6.0]


def test_storeys_without_floor_slabs(model3dm, tmp_path):
    entries = MAPPING[:2] + [dict(MAPPING[2], predefinedType="ROOF")] + MAPPING[3:]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o",
                    tmp_path / "x.ifc", "--storeys")
    assert code == 2 and "--storeys 0,3.2" in doc["error"]["fix"]


def test_no_storeys_by_default(model3dm, tmp_path):
    out = tmp_path / "x.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", out)
    assert code == 0 and doc["storeys"] == []
    assert ifcopenshell.open(str(out)).by_type("IfcBuildingStorey") == ()


def test_colours(ifc):
    f, _ = ifc
    colours = {(round(c.Red, 3), round(c.Green, 3), round(c.Blue, 3))
               for c in f.by_type("IfcColourRgb")}
    assert (1.0, 0.0, 0.0) in colours   # Stützen layer colour
    assert (0.0, 0.0, 1.0) in colours   # Chair part "by parent" takes the instance's object colour
    assert (0.0, 1.0, 0.0) in colours   # Set instance: Furniture layer colour


def test_anonymous_header(ifc):
    f, _ = ifc
    assert f.by_type("IfcOwnerHistory") == () and f.by_type("IfcPerson") == ()
    assert f.header.file_name.author == ("",)
    assert f.header.file_name.originating_system == "rhino2ifc"


def test_georef_and_north(ifc):
    f, _ = ifc
    conv, = f.by_type("IfcMapConversion")
    assert conv.TargetCRS.Name == "EPSG:2056" and conv.Eastings == 2600000.0
    assert conv.XAxisAbscissa == 1.0 and conv.XAxisOrdinate == 0.0
    north = f.by_type("IfcGeometricRepresentationContext")[0].TrueNorth.DirectionRatios
    assert north == pytest.approx((0.7071068, 0.7071068))


@pytest.mark.parametrize("value", ["2056,1,2,3", "EPSG:2056,1,2", "EPSG:x,1,2,3"])
def test_bad_georef(model3dm, tmp_path, value):
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", tmp_path / "x.ifc",
                    "--georef", value)
    assert code == 2 and "--georef" in doc["error"]["message"]


def test_missing_mesh_exit_3(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    entries = MAPPING + [{"key": "Solids", "class": "IfcWall", "merge": False,
                          "confidence": "low", "rationale": "box"}]
    code, doc = run("convert", path, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 3 and doc["error"]["missingMesh"][0]["key"] == "Solids"


def test_missing_mesh_skipped_key_converts(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    entries = MAPPING + [{"key": "Solids", "skip": True, "rationale": "no mesh"}]
    code, doc = run("convert", path, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0, doc
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_mapping.py skills/bim/converting-rhino-to-ifc4/tests/test_convert.py -q`
Expected: failures; argparse rejects `convert` (exit 2, and stdout is not JSON), so `run()` raises `JSONDecodeError`.

- [ ] **Step 3: Implement mapping validation**

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/mapping.py`:

```python
"""Load and check the agent's mapping.json against the inventory keys and the schema.

Every problem is collected, so one run tells the agent everything to fix.
"""
import json

import ifcopenshell
import ifcopenshell.ifcopenshell_wrapper as w

from .errors import R2IError

SCHEMAS = ("IFC4", "IFC4X3_ADD2")
CONFIDENCE = ("high", "medium", "low")


def element_class(schema, name):
    """(canonical name, declaration) if name is a concrete IfcElement subtype, else None."""
    try:
        decl = ifcopenshell.schema_by_name(schema).declaration_by_name(name)
    except RuntimeError:
        return None
    if not isinstance(decl, w.entity) or decl.is_abstract():
        return None
    sup = decl
    while sup is not None:
        if sup.name() == "IfcElement":
            return decl.name(), decl
        sup = sup.supertype()
    return None


def predefined_types(decl):
    """Allowed PredefinedType values, or None when the class has no such attribute."""
    for attr in decl.all_attributes():
        if attr.name() == "PredefinedType":
            return set(attr.type_of_attribute().declared_type().enumeration_items())
    return None


def load(path, keys):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise R2IError(2, "cannot read mapping %s: %s" % (path, exc), "write valid JSON")
    problems = []
    schema = data.get("schema", "IFC4")
    if schema not in SCHEMAS:
        raise R2IError(2, "schema %r is not one of %s" % (schema, ", ".join(SCHEMAS)),
                       'set "schema" to "IFC4" (default) or "IFC4X3_ADD2"')
    entries, seen = {}, set()
    for i, raw in enumerate(data.get("entries", [])):
        key = raw.get("key")
        where = "entry %d (%s)" % (i, key)
        if key in seen:
            problems.append("%s: key listed twice" % where)
            continue
        seen.add(key)
        if key not in keys:
            problems.append("%s: not an inventory key" % where)
            continue
        entry = _check(schema, raw, where, problems)
        if entry:
            entries[key] = entry
    for key in sorted(set(keys) - seen):
        problems.append("%s: missing; classify it or add {\"key\": %r, \"skip\": true, "
                        "\"rationale\": ...}" % (key, key))
    if problems:
        raise R2IError(2, "mapping has %d problem(s)" % len(problems),
                       "fix each entry and rerun convert", problems=problems)
    return {"schema": schema, "entries": entries}


def _check(schema, raw, where, problems):
    if not isinstance(raw.get("rationale"), str) or not raw["rationale"].strip():
        problems.append("%s: rationale missing" % where)
    if raw.get("skip"):
        return {"key": raw["key"], "skip": True, "rationale": raw.get("rationale", "")}
    found = element_class(schema, raw.get("class") or "")
    if not found:
        problems.append("%s: %r is not a concrete IfcElement subtype in %s"
                        % (where, raw.get("class"), schema))
        return None
    name, decl = found
    if raw.get("confidence") not in CONFIDENCE:
        problems.append("%s: confidence must be one of %s" % (where, ", ".join(CONFIDENCE)))
    ptype = raw.get("predefinedType")
    ptype = ptype.upper() if isinstance(ptype, str) else None
    allowed = predefined_types(decl)
    if ptype and allowed is None:
        problems.append("%s: %s has no PredefinedType" % (where, name))
    elif ptype and ptype not in allowed:
        problems.append("%s: PredefinedType %s not in %s" % (where, ptype, sorted(allowed)))
    if ptype == "USERDEFINED" and not raw.get("objectType"):
        problems.append("%s: USERDEFINED needs objectType" % where)
    return {"key": raw["key"], "skip": False, "class": name, "predefinedType": ptype,
            "objectType": raw.get("objectType"), "merge": bool(raw.get("merge", False)),
            "confidence": raw.get("confidence"), "rationale": raw.get("rationale", "")}
```

- [ ] **Step 4: Implement the writer**

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/writer.py`:

```python
"""Write the IFC: Project > Site > Building [> Storeys], one element per object
(or per key when merged), tessellated bodies, colours, Pset_RhinoSource."""
import math

import ifcopenshell
import ifcopenshell.guid

from . import model as rmodel
from .errors import R2IError

STOREY_TOLERANCE = 0.3   # m: floor slab bottoms closer than this share a level
MAX_IDS = 50             # object GUIDs listed in Pset_RhinoSource of a merged element


class Writer:
    def __init__(self, schema, north=None, georef=None):
        f = ifcopenshell.file(schema=schema)
        self.f = f
        name = f.header.file_name
        name.author = ("",)
        name.organization = ("",)
        name.authorization = ""
        name.originating_system = "rhino2ifc"
        name.preprocessor_version = ""
        units = f.create_entity("IfcUnitAssignment", Units=[
            f.create_entity("IfcSIUnit", UnitType=u, Name=n) for u, n in (
                ("LENGTHUNIT", "METRE"), ("AREAUNIT", "SQUARE_METRE"),
                ("VOLUMEUNIT", "CUBIC_METRE"), ("PLANEANGLEUNIT", "RADIAN"))])
        self.ctx = f.create_entity(
            "IfcGeometricRepresentationContext", ContextType="Model",
            CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=self.axis(),
            TrueNorth=f.create_entity("IfcDirection", DirectionRatios=north) if north else None)
        self.body = f.create_entity(
            "IfcGeometricRepresentationSubContext", ContextIdentifier="Body",
            ContextType="Model", ParentContext=self.ctx, TargetView="MODEL_VIEW")
        self.project = self.root("IfcProject", "Project", RepresentationContexts=[self.ctx],
                                 UnitsInContext=units)
        if georef:
            epsg, e, n, h, rot = georef
            crs = f.create_entity("IfcProjectedCRS", Name="EPSG:%d" % epsg)
            f.create_entity("IfcMapConversion", SourceCRS=self.ctx, TargetCRS=crs,
                            Eastings=e, Northings=n, OrthogonalHeight=h,
                            XAxisAbscissa=math.cos(math.radians(rot)),
                            XAxisOrdinate=math.sin(math.radians(rot)), Scale=1.0)
        self.site = self.root("IfcSite", "Site", ObjectPlacement=self.placement())
        self.building = self.root("IfcBuilding", "Building", ObjectPlacement=self.placement())
        self.aggregate(self.project, [self.site])
        self.aggregate(self.site, [self.building])
        self.styles = {}

    def root(self, cls, name, **kw):
        return self.f.create_entity(cls, GlobalId=ifcopenshell.guid.new(), Name=name, **kw)

    def axis(self, xyz=(0.0, 0.0, 0.0)):
        pt = self.f.create_entity("IfcCartesianPoint", Coordinates=xyz)
        return self.f.create_entity("IfcAxis2Placement3D", Location=pt)

    def placement(self):
        return self.f.create_entity("IfcLocalPlacement", RelativePlacement=self.axis())

    def aggregate(self, whole, parts):
        self.root("IfcRelAggregates", None, RelatingObject=whole, RelatedObjects=parts)

    def style(self, colour):
        if colour not in self.styles:
            rgb = self.f.create_entity("IfcColourRgb", None, *(c / 255.0 for c in colour))
            shading = self.f.create_entity("IfcSurfaceStyleShading", SurfaceColour=rgb)
            self.styles[colour] = self.f.create_entity(
                "IfcSurfaceStyle", Side="BOTH", Styles=[shading])
        return self.styles[colour]

    def shape(self, items, scale):
        faces_sets = []
        for item in items:
            mesh = item.mesh
            coords = self.f.create_entity("IfcCartesianPointList3D", CoordList=[
                (round(v.X * scale, 6), round(v.Y * scale, 6), round(v.Z * scale, 6))
                for v in mesh.Vertices])
            faces = []
            for face in mesh.Faces:
                idx = face[:3] if face[2] == face[3] else face
                faces.append(self.f.create_entity(
                    "IfcIndexedPolygonalFace", CoordIndex=[i + 1 for i in idx]))
            fs = self.f.create_entity("IfcPolygonalFaceSet", Coordinates=coords,
                                      Closed=bool(mesh.IsClosed), Faces=faces)
            self.f.create_entity("IfcStyledItem", Item=fs, Styles=[self.style(item.colour)])
            faces_sets.append(fs)
        rep = self.f.create_entity(
            "IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body",
            RepresentationType="Tessellation", Items=faces_sets)
        return self.f.create_entity("IfcProductDefinitionShape", Representations=[rep])

    def pset(self, element, values):
        props = []
        for name, value in values:
            kind = "IfcInteger" if isinstance(value, int) else "IfcText"
            props.append(self.f.create_entity(
                "IfcPropertySingleValue", Name=name,
                NominalValue=self.f.create_entity(kind, value)))
        ps = self.root("IfcPropertySet", "Pset_RhinoSource", HasProperties=props)
        self.root("IfcRelDefinesByProperties", None, RelatedObjects=[element],
                  RelatingPropertyDefinition=ps)


def elements_of(entry, rows):
    """[(name, [(item, stats)])]: one per key when merged, else one per Rhino object."""
    leaf = entry["key"].split("::")[-1]
    if entry["merge"]:
        return [(leaf, rows)]
    by_object = {}
    for it, st in rows:
        by_object.setdefault(it.object_id, []).append((it, st))
    return [(rs[0][0].name or leaf, rs) for rs in by_object.values()]


def detect_levels(planned):
    zs = sorted(min(st["zMin"] for _, st in rows) for entry, _, rows in planned
                if entry["class"] == "IfcSlab" and entry["predefinedType"] == "FLOOR")
    if not zs:
        raise R2IError(2, "--storeys found no IfcSlab FLOOR elements",
                       "give the levels: --storeys 0,3.2,6.4 (metres)")
    levels = [zs[0]]
    for z in zs[1:]:
        if z - levels[-1] > STOREY_TOLERANCE:
            levels.append(z)
    return levels


def convert(model, groups, mapping, out_path, storeys=None, georef=None, north_layer=None):
    """storeys: None (no storeys), "auto", or a list of levels in metres."""
    planned, skipped = [], []
    for key, entry in sorted(mapping["entries"].items()):
        if entry["skip"]:
            skipped.append(key)
            continue
        rows = groups[key]
        missing = [{"key": key, "objectId": it.object_id, "geometryType": it.geometry_type}
                   for it, st in rows if st is None]
        if missing:
            raise R2IError(3, "objects without a cached mesh", missingMesh=missing,
                           fix="save the .3dm normally in Rhino (not Save Small), "
                               "or skip that key")
        for name, erows in elements_of(entry, rows):
            planned.append((entry, name, erows))

    north = rmodel.north(model, north_layer) if north_layer else None
    w = Writer(mapping["schema"], north=north, georef=georef)
    levels = None
    if storeys == "auto":
        levels = detect_levels(planned)
    elif storeys:
        levels = sorted(storeys)
    containers = {}
    storey_objs = []
    if levels:
        for i, z in enumerate(levels):
            storey_objs.append(w.root("IfcBuildingStorey", "Level %d" % i,
                                      ObjectPlacement=w.placement(), Elevation=z))
        w.aggregate(w.building, storey_objs)

    counts = {}
    for entry, name, rows in planned:
        kw = {}
        if entry["predefinedType"]:
            kw["PredefinedType"] = entry["predefinedType"]
        if entry["objectType"]:
            kw["ObjectType"] = entry["objectType"]
        element = w.root(entry["class"], name, ObjectPlacement=w.placement(),
                         Representation=w.shape([it for it, _ in rows], model.scale), **kw)
        ids = list(dict.fromkeys(it.object_id for it, _ in rows))
        values = [("LayerPath", rows[0][0].layer),
                  ("ObjectIds", ";".join(ids[:MAX_IDS]))]
        if len(ids) > MAX_IDS:
            values.append(("ObjectCount", len(ids)))
        values += [("Confidence", entry["confidence"]), ("Rationale", entry["rationale"])]
        w.pset(element, values)
        if entry["class"] == "IfcGeographicElement":
            container = w.site
        elif levels:
            z = min(st["zMin"] for _, st in rows)
            idx = max([i for i, lv in enumerate(levels) if lv <= z + 1e-6] or [0])
            container = storey_objs[idx]
        else:
            container = w.building
        containers.setdefault(container, []).append(element)
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1
    for container, elements in containers.items():
        w.root("IfcRelContainedInSpatialStructure", None,
               RelatingStructure=container, RelatedElements=elements)
    w.f.write(str(out_path))
    return {"ok": True, "output": str(out_path), "schema": mapping["schema"],
            "elements": counts, "storeys": levels or [], "skipped": skipped}
```

- [ ] **Step 5: Replace the CLI with the version that adds `convert`**

`skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py`:

```python
#!/usr/bin/env python3
"""Rhino .3dm -> IFC4 (or IFC4X3_ADD2), classified by an agent.

  rhino2ifc.py inventory <in.3dm> [-o inventory.json]
  rhino2ifc.py convert <in.3dm> <mapping.json> -o <out.ifc>
               [--storeys [z1,z2,...]] [--georef EPSG:<code>,<E>,<N>,<H>[,<rot_deg>]]
               [--north <layer path>]
  rhino2ifc.py validate <file.ifc>

JSON on stdout for every outcome. Exit 0 ok, 2 input error, 3 objects
without a cached mesh, 4 validation failed.
"""
import argparse
import json
import sys

from r2i import inventory, mapping, model, writer
from r2i.errors import R2IError


def emit(doc):
    print(json.dumps(doc, ensure_ascii=False, indent=2))


def parse_levels(text):
    if text == "auto":
        return "auto"
    try:
        return [float(x) for x in text.split(",")]
    except ValueError:
        raise R2IError(2, "--storeys %r is not a list of numbers" % text,
                       "use --storeys alone, or --storeys 0,3.2,6.4")


def parse_georef(text):
    try:
        crs, *nums = text.split(",")
        if not crs.upper().startswith("EPSG:") or len(nums) not in (3, 4):
            raise ValueError
        vals = [float(x) for x in nums] + ([0.0] if len(nums) == 3 else [])
        return (int(crs[5:]), *vals)
    except ValueError:
        raise R2IError(2, "--georef %r is malformed" % text,
                       "use EPSG:<code>,<E>,<N>,<H>[,<rotation deg>], e.g. EPSG:2056,2600000,1200000,400")


def cmd_inventory(args):
    doc, _ = inventory.build(model.read(args.model))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        emit({"ok": "error" not in doc, "output": args.output, "keys": len(doc["keys"]),
              "objectCount": doc["objectCount"], **({"error": doc["error"]} if "error" in doc else {})})
    else:
        emit(doc)
    return 3 if "error" in doc else 0


def cmd_convert(args):
    m = model.read(args.model)
    _, groups = inventory.build(m)
    mp = mapping.load(args.mapping, set(groups))
    storeys = parse_levels(args.storeys) if args.storeys else None
    georef = parse_georef(args.georef) if args.georef else None
    emit(writer.convert(m, groups, mp, args.output, storeys=storeys, georef=georef,
                        north_layer=args.north))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="rhino2ifc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inventory")
    s.add_argument("model")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_inventory)
    s = sub.add_parser("convert")
    s.add_argument("model")
    s.add_argument("mapping")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--storeys", nargs="?", const="auto")
    s.add_argument("--georef")
    s.add_argument("--north")
    s.set_defaults(fn=cmd_convert)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except R2IError as exc:
        emit({"ok": False, "error": exc.to_json()})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests -q`
Expected: `47 passed` (8 model + 7 inventory + 14 mapping + 18 convert).

- [ ] **Step 7: Commit**

```bash
git add skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_mapping.py skills/bim/converting-rhino-to-ifc4/tests/test_convert.py
git commit skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_mapping.py skills/bim/converting-rhino-to-ifc4/tests/test_convert.py -m "feat(bim): rhino2ifc convert: mapping validation, IFC4 writer, storeys, georef, colours, Pset_RhinoSource

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: The `validate` command

**Files:**
- Create: `skills/bim/converting-rhino-to-ifc4/scripts/r2i/checks.py`
- Modify: `skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py` (replace the whole file)
- Test: `skills/bim/converting-rhino-to-ifc4/tests/test_validate.py`

**Interfaces:**
- Consumes: the IFC files `convert` writes (Task 3).
- Produces: `checks.validate(path) -> {"ok", "schema" (full identifier, e.g. "IFC4X3_ADD2"), "elements", "schemaErrors" (first 20), "schemaErrorCount", "withoutGeometry", "identity", "header"}`. `ok` is false on any schema error or any element without a representation. Raises `R2IError` code 2 for an unreadable file.
- Produces: `rhino2ifc.py validate <file.ifc>`; exit 4 when not `ok`.

- [ ] **Step 1: Write the failing tests**

`skills/bim/converting-rhino-to-ifc4/tests/test_validate.py`:

```python
import ifcopenshell
import ifcopenshell.guid

from conftest import run, write_mapping


def test_valid_file(model3dm, tmp_path):
    out = tmp_path / "out.ifc"
    assert run("convert", model3dm, write_mapping(tmp_path), "-o", out)[0] == 0
    code, report = run("validate", out)
    assert code == 0, report
    assert report["ok"] and report["schema"] == "IFC4"
    assert report["schemaErrorCount"] == 0 and report["withoutGeometry"] == []
    assert report["identity"] == {"IfcOwnerHistory": 0, "IfcPerson": 0, "IfcOrganization": 0}
    assert report["header"] == {"author": [""], "organization": [""]}
    assert report["elements"]["IfcColumn"] == 5


def test_element_without_geometry_exit_4(tmp_path):
    f = ifcopenshell.file(schema="IFC4")
    f.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="bare")
    path = tmp_path / "bare.ifc"
    f.write(str(path))
    code, report = run("validate", path)
    assert code == 4 and not report["ok"] and len(report["withoutGeometry"]) == 1


def test_schema_error_exit_4(tmp_path):
    f = ifcopenshell.file(schema="IFC4")
    f.create_entity("IfcWall", GlobalId="not-a-guid", Name="bad")
    path = tmp_path / "bad.ifc"
    f.write(str(path))
    code, report = run("validate", path)
    assert code == 4 and report["schemaErrorCount"] >= 1


def test_unreadable_file_exit_2(tmp_path):
    code, doc = run("validate", tmp_path / "nope.ifc")
    assert code == 2 and "cannot open" in doc["error"]["message"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests/test_validate.py -q`
Expected: 4 failures (`JSONDecodeError`; argparse does not know `validate`).

- [ ] **Step 3: Implement checks**

`skills/bim/converting-rhino-to-ifc4/scripts/r2i/checks.py`:

```python
"""Validate a written IFC and report what is in it."""
from collections import Counter

import ifcopenshell
import ifcopenshell.validate

from .errors import R2IError


def validate(path):
    try:
        f = ifcopenshell.open(str(path))
    except Exception as exc:  # ifcopenshell raises several types for unreadable files
        raise R2IError(2, "cannot open %s: %s" % (path, exc), "check the path")
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, logger)
    errors = [s["message"] for s in logger.statements if s.get("level") == "error"]
    elements = f.by_type("IfcElement")
    no_geometry = [e.GlobalId for e in elements if not e.Representation]
    header = f.header.file_name
    result = {
        "ok": not errors and not no_geometry,
        "schema": f.schema_identifier,
        "elements": dict(Counter(e.is_a() for e in elements)),
        "schemaErrors": errors[:20],
        "schemaErrorCount": len(errors),
        "withoutGeometry": no_geometry,
        "identity": {t: len(f.by_type(t)) for t in ("IfcOwnerHistory", "IfcPerson",
                                                     "IfcOrganization")},
        "header": {"author": list(header.author), "organization": list(header.organization)},
    }
    return result
```

Note: use `f.schema_identifier`, not `f.schema`. `f.schema` returns `IFC4X3` for an `IFC4X3_ADD2` file, which the prototype caught.

- [ ] **Step 4: Replace the CLI with the final version**

`skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py`:

```python
#!/usr/bin/env python3
"""Rhino .3dm -> IFC4 (or IFC4X3_ADD2), classified by an agent.

  rhino2ifc.py inventory <in.3dm> [-o inventory.json]
  rhino2ifc.py convert <in.3dm> <mapping.json> -o <out.ifc>
               [--storeys [z1,z2,...]] [--georef EPSG:<code>,<E>,<N>,<H>[,<rot_deg>]]
               [--north <layer path>]
  rhino2ifc.py validate <file.ifc>

JSON on stdout for every outcome. Exit 0 ok, 2 input error, 3 objects
without a cached mesh, 4 validation failed.
"""
import argparse
import json
import sys

from r2i import checks, inventory, mapping, model, writer
from r2i.errors import R2IError


def emit(doc):
    print(json.dumps(doc, ensure_ascii=False, indent=2))


def parse_levels(text):
    if text == "auto":
        return "auto"
    try:
        return [float(x) for x in text.split(",")]
    except ValueError:
        raise R2IError(2, "--storeys %r is not a list of numbers" % text,
                       "use --storeys alone, or --storeys 0,3.2,6.4")


def parse_georef(text):
    try:
        crs, *nums = text.split(",")
        if not crs.upper().startswith("EPSG:") or len(nums) not in (3, 4):
            raise ValueError
        vals = [float(x) for x in nums] + ([0.0] if len(nums) == 3 else [])
        return (int(crs[5:]), *vals)
    except ValueError:
        raise R2IError(2, "--georef %r is malformed" % text,
                       "use EPSG:<code>,<E>,<N>,<H>[,<rotation deg>], e.g. EPSG:2056,2600000,1200000,400")


def cmd_inventory(args):
    doc, _ = inventory.build(model.read(args.model))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        emit({"ok": "error" not in doc, "output": args.output, "keys": len(doc["keys"]),
              "objectCount": doc["objectCount"], **({"error": doc["error"]} if "error" in doc else {})})
    else:
        emit(doc)
    return 3 if "error" in doc else 0


def cmd_convert(args):
    m = model.read(args.model)
    _, groups = inventory.build(m)
    mp = mapping.load(args.mapping, set(groups))
    storeys = parse_levels(args.storeys) if args.storeys else None
    georef = parse_georef(args.georef) if args.georef else None
    emit(writer.convert(m, groups, mp, args.output, storeys=storeys, georef=georef,
                        north_layer=args.north))
    return 0


def cmd_validate(args):
    result = checks.validate(args.ifc)
    emit(result)
    return 0 if result["ok"] else 4


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="rhino2ifc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inventory")
    s.add_argument("model")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_inventory)
    s = sub.add_parser("convert")
    s.add_argument("model")
    s.add_argument("mapping")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--storeys", nargs="?", const="auto")
    s.add_argument("--georef")
    s.add_argument("--north")
    s.set_defaults(fn=cmd_convert)
    s = sub.add_parser("validate")
    s.add_argument("ifc")
    s.set_defaults(fn=cmd_validate)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except R2IError as exc:
        emit({"ok": False, "error": exc.to_json()})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests -q`
Expected: `51 passed`.

- [ ] **Step 6: Commit**

```bash
git add skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_validate.py
git commit skills/bim/converting-rhino-to-ifc4/scripts skills/bim/converting-rhino-to-ifc4/tests/test_validate.py -m "feat(bim): rhino2ifc validate: schema check, geometry and identity report

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: SKILL.md, class reference and registration

**Files:**
- Create: `skills/bim/converting-rhino-to-ifc4/SKILL.md`, `skills/bim/converting-rhino-to-ifc4/reference/ifc-classes.md`, `skills/bim/README.md`
- Modify: `README.md` (What's inside section and the tree under "How the skills are built"), `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: the CLI (Tasks 2-4), and `mapping.element_class` / `mapping.predefined_types` for the reference check.

- [ ] **Step 1: Write SKILL.md**

`skills/bim/converting-rhino-to-ifc4/SKILL.md`:

````markdown
---
name: converting-rhino-to-ifc4
description: Use when turning a Rhino .3dm (non-BIM geometry — breps, extrusions, meshes on layers) into an IFC file, deciding which IFC class (IfcWall, IfcSlab, IfcColumn, ...) Rhino layers or blocks should become, or delivering IFC4 / IFC4X3 from a Rhino model for Revit, ArchiCAD, Solibri or a web viewer — without Rhino running.
---

# Converting Rhino to IFC4

A Rhino model has layers and geometry, not building elements. **You** decide
what each layer is; `scripts/rhino2ifc.py` measures the geometry and writes
the IFC. Offline: Python + `rhino3dm` + `ifcopenshell` + `numpy`, no Rhino.

    python -m venv .venv && .venv/Scripts/pip install -r <skillRoot>/requirements.txt   # once, if an import fails

Every command prints JSON. Exit `0` ok, `2` input error (the JSON names the
entry and the fix), `3` objects without a cached mesh, `4` validation failed.

## Workflow

1. **Inventory**

       python <skillRoot>/scripts/rhino2ifc.py inventory model.3dm -o inventory.json

   One record per **key** — a layer path, a block definition name, or a
   cluster `<layer>#<n>` when a layer mixes shapes. Per key: count, geometry
   types, colour, bbox, `forms`, and min/median/max of size, slenderness,
   `zMin`, `zMax` (metres). `keys` lists exactly what the mapping must cover.
   Points, curves and text are listed under `nonGeometric` and never converted.

   **Exit 3** = Brep/Extrusion/SubD objects without a cached render mesh
   (file saved with *Save Small*, or never shaded). Fix: open the .3dm in
   Rhino, switch a viewport to Shaded, save normally — or mesh through
   Cordyceps if Rhino is already driven by it. Never drop those objects
   silently.

2. **Classify** — read `inventory.json` and
   [reference/ifc-classes.md](reference/ifc-classes.md), write `mapping.json`:

   ```json
   {"schema": "IFC4", "entries": [
     {"key": "Existing::Stützen", "class": "IfcColumn", "merge": false,
      "confidence": "high", "rationale": "54 linear-vertical, 8 m; Stützen = columns"},
     {"key": "Facade#2", "class": "IfcPlate", "predefinedType": "CURTAIN_PANEL", "merge": true,
      "confidence": "medium", "rationale": "6090 plate-vertical panels on the facade"},
     {"key": "North", "skip": true, "rationale": "north arrow"}]}
   ```

   - Every key exactly once: classified, or `"skip": true`.
   - `schema`: `IFC4` (default; best supported by Revit, ArchiCAD, viewers) or
     `IFC4X3_ADD2` only when asked.
   - `merge: true` = one element per key (a facade of 18,000 pieces); false =
     one element per Rhino object or block instance.
   - `predefinedType` is optional; `USERDEFINED` needs `objectType`.
   - **Geometry outweighs the name** when they disagree. When neither
     convinces, `IfcBuildingElementProxy` with `low` is the honest answer —
     never invent a class to look complete.

3. **Review on doubt** — show the user a table (key, count, form, class,
   confidence, rationale). Ask only about `medium` and `low` rows; `high`
   rows pass. Update the mapping with the answers.

4. **Convert**

       python <skillRoot>/scripts/rhino2ifc.py convert model.3dm mapping.json -o model.ifc

   Options, only when the user wants them:
   - `--storeys` — levels from the bottoms of `IfcSlab` `FLOOR` elements (0.3 m
     tolerance). Each element goes to the storey where its bottom is: a
     three-storey column sits in the storey it starts in. When stepped or
     sunken slabs fool detection: `--storeys 0,3.2,6.4` (metres).
   - `--georef EPSG:2056,2600000,1200000,400[,rot_deg]` — map conversion of
     the model origin (code, easting, northing, height, x-axis rotation).
   - `--north <layer>` — true north from the first line on that layer.

   Refused mapping → exit 2 with every problem listed; fix them all, rerun.

5. **Validate**, then report what the output says — not what you expect:

       python <skillRoot>/scripts/rhino2ifc.py validate model.ifc

   Schema errors, elements per class, elements without geometry, owner /
   person / organization counts, header author.

## What the IFC contains

IfcProject → IfcSite → IfcBuilding (→ IfcBuildingStorey with `--storeys`), metres.
`IfcGeographicElement` sits in the site, everything else in the building.
Bodies are `IfcPolygonalFaceSet` from the cached meshes, coloured from the
Rhino display colour. Every element carries `Pset_RhinoSource`: `LayerPath`,
`ObjectIds` (Rhino GUIDs; first 50 plus `ObjectCount` when merged),
`Confidence`, `Rationale` — so any element can be found in the .3dm again.
Header author and organization are empty; no IfcOwnerHistory.

Blocks are one key per definition (the outermost, for nested blocks),
exploded to world geometry; `LayerPath` is the instance's layer.

## Not covered

NURBS (`IfcAdvancedBrep`) bodies, openings and voids, materials, spaces and
zones, blocks as `IfcMappedItem`. Say so when the user needs one of them.
````

- [ ] **Step 2: Write the class reference**

`skills/bim/converting-rhino-to-ifc4/reference/ifc-classes.md`:

```markdown
# Classifying Rhino geometry into IFC classes

Read with `inventory.json`. A form is one of `linear-vertical`,
`linear-horizontal`, `linear-sloped` (long axis at least 4x the next),
`plate-horizontal`, `plate-vertical`, `plate-sloped` (thin: middle extent at
least 4x the smallest; named by the plate's own orientation), `bulky`.

**Geometry outweighs the name.** A layer called "Walls" full of
`plate-horizontal` objects is slabs or a mistake — ask. When neither geometry
nor name convinces, use `IfcBuildingElementProxy` with confidence `low`.

## Classes

Name cues: EN / DE / FR / IT / PT. All classes exist in IFC4 and IFC4X3_ADD2.

| Class (PredefinedType) | Geometric signature | Name cues |
|---|---|---|
| `IfcWall` | `plate-vertical`, 0.1–0.6 m thick, storey-high or more | wall / Wand, Mauer / mur / muro, parete / parede |
| `IfcCurtainWall` | a whole glazed facade as one merged element | curtain wall / Vorhangfassade, Pfosten-Riegel / mur-rideau / facciata continua / fachada cortina |
| `IfcSlab` (`FLOOR`, `ROOF`, `LANDING`, `BASESLAB`) | `plate-horizontal`, 0.15–0.5 m thick, large in plan | slab, floor / Decke, Boden, Platte / dalle, plancher / solaio / laje |
| `IfcRoof` | an assembly; prefer `IfcSlab` `ROOF` for single roof plates | roof / Dach / toit / tetto / telhado |
| `IfcColumn` | `linear-vertical`, slenderness > 5, about a storey high | column / Stütze, Säule / poteau, colonne / pilastro, colonna / pilar |
| `IfcBeam` | `linear-horizontal`, structural depth | beam / Träger, Balken / poutre / trave / viga |
| `IfcMember` (`MULLION`, `BRACE`, `RAFTER`, `PURLIN`, `STUD`) | `linear-*` of small section: mullions, bracing, timber | mullion, brace / Pfosten, Riegel, Sparren / montant / montante / montante |
| `IfcPlate` (`CURTAIN_PANEL`, `SHEET`) | thin `plate-*` panels, cladding, glazing panes | panel, glass / Paneel, Glas, Blech / panneau, verre / pannello, vetro / painel, vidro |
| `IfcStair` / `IfcStairFlight` | `bulky` or `linear-sloped`, rising in steps | stair / Treppe / escalier / scala / escada |
| `IfcRamp` | `plate-sloped` walkway | ramp / Rampe / rampe / rampa / rampa |
| `IfcRailing` | `linear-horizontal` about 1 m above a floor edge | railing / Geländer / garde-corps / parapetto / guarda-corpo |
| `IfcWindow` | `plate-vertical` within a wall, glass size | window / Fenster / fenêtre / finestra / janela |
| `IfcDoor` | `plate-vertical`, about 1 x 2.1 m, starting at a floor | door / Tür / porte / porta / porta |
| `IfcCovering` (`CLADDING`, `CEILING`, `FLOORING`, `ROOFING`) | thin layer on another element | cladding / Verkleidung, Bekleidung / bardage / rivestimento / revestimento |
| `IfcFooting` | `bulky` or `plate-horizontal` below ground (`zMin` < 0) | footing, foundation / Fundament / fondation / fondazione / fundação |
| `IfcPile` | `linear-vertical` below ground | pile / Pfahl / pieu / palo / estaca |
| `IfcGeographicElement` (`TERRAIN`) | large, irregular, `plate-horizontal` or many strips; merge | terrain, site, topo / Gelände, Terrain / terrain / terreno / terreno |
| `IfcFurniture` | `bulky`, small, on a floor; often blocks | furniture, chair, table / Möbel / mobilier / arredo / mobília |
| `IfcBuildingElementProxy` | anything else; rooftop plant, context, unknown | — |

## Traps

- **Rooftop structures are not `IfcRoof`.** Plant rooms, stair cores, HVAC
  on a roof (Dachaufbauten, superstructures) → `IfcBuildingElementProxy`.
- **Facade of thousands of pieces.** Merge. One mixed layer often splits into
  clusters: `linear-*` → `IfcMember` `MULLION`, `plate-vertical` → `IfcPlate`
  `CURTAIN_PANEL` — or the whole facade as one merged `IfcWall` /
  `IfcCurtainWall` when the user wants it simple. Ask which.
- **"Glass" / "Glas"** is windows (holes in walls), curtain-wall panels, or
  balustrade glazing — position decides.
- **Context buildings** (neighbours drawn as massing) are not the project's
  elements: proxies, or skip when the user does not want them.
- **Construction and design aids** — limit volumes, zones, envelopes, grids,
  section boxes, north arrows, dimension geometry → `skip` (spaces and zones
  are out of v1).
- **Thin flat slabs at roof level** may be roof slabs (`IfcSlab` `ROOF`) or a
  roof covering (`IfcCovering` `ROOFING`) — thickness decides (> 0.1 m slab).
- **German compound names** carry the class in the last part: Außenwand →
  wall, Geschossdecke → slab, Stahlstütze → column.
- **Numbered layers** (`Layer 01`, `Default`) carry no meaning; the clusters
  and their forms are all you have — expect `medium` or `low`.
```

- [ ] **Step 3: Check that every class and PredefinedType in the reference exists in both schemas**

Run:

```bash
cd skills/bim/converting-rhino-to-ifc4/scripts && ../../../../.venv/Scripts/python -c "
import re
from r2i.mapping import element_class, predefined_types
text = open('../reference/ifc-classes.md', encoding='utf-8').read()
rows = re.findall(r'^\| \x60(Ifc\w+)\x60(?: / \x60(Ifc\w+)\x60)?(?: \(([^)]*)\))?', text, re.M)
bad = []
for schema in ('IFC4', 'IFC4X3_ADD2'):
    for a, b, types in rows:
        for cls in filter(None, (a, b)):
            found = element_class(schema, cls)
            if not found:
                bad.append((schema, cls)); continue
            allowed = predefined_types(found[1]) or set()
            bad += [(schema, cls, t) for t in re.findall(r'\x60(\w+)\x60', types) if t not in allowed]
print('rows', len(rows), 'bad', bad)"; cd - >/dev/null
```

Expected: `rows 19 bad []`.

- [ ] **Step 4: Bucket README**

`skills/bim/README.md`:

```markdown
# BIM skills

Skills that turn design geometry into building information. `converting-rhino-to-ifc4`
classifies the layers of a non-BIM Rhino model into IFC classes (the agent decides,
from layer names and measured shape) and writes IFC4 offline with rhino3dm and
ifcopenshell. Tests: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests -v`
(`pip install -r skills/bim/converting-rhino-to-ifc4/requirements.txt` first).
```

- [ ] **Step 5: Register the skill**

In `.claude-plugin/plugin.json`: set `"version": "1.10.0"`, append `"./skills/bim/converting-rhino-to-ifc4"` as the last entry of `"skills"`, and change the description's ending from `Zotero library automation via the local API.` to `Zotero library automation via the local API, Rhino-to-IFC4 conversion.`

In `.claude-plugin/marketplace.json`: set `"version": "1.10.0"` (line 11).

In `README.md`, insert this section after the `### Zotero` section and before `## Install`:

```markdown
### BIM

- **[converting-rhino-to-ifc4](./skills/bim/converting-rhino-to-ifc4/SKILL.md)** — Turn a non-BIM Rhino model into IFC4 with the agent deciding the classes. `rhino2ifc.py inventory` measures every layer offline (rhino3dm, no Rhino): counts, sizes, and a form label per object (`linear-vertical`, `plate-horizontal`, ...), splitting mixed layers into clusters. The agent maps each key to an IFC class with a confidence and a reason, asks the user only about the doubtful ones, and `convert` writes IfcPolygonalFaceSet bodies with colours, optional storeys and georeference, and a `Pset_RhinoSource` that traces every element back to its Rhino layer and GUIDs. `validate` reports schema errors before anyone opens the file.
```

In the `README.md` tree under "How the skills are built", add after the `zotero/` lines:

```text
  bim/
    converting-rhino-to-ifc4/     SKILL.md + scripts/rhino2ifc.py + reference/ifc-classes.md (+ pytest fixture builder)
```

- [ ] **Step 6: CHANGELOG entry**

Insert above `## 1.9.0 — 2026-09-05` in `CHANGELOG.md`:

```markdown
## 1.10.0 — 2026-10-30

New `skills/bim/` category with `converting-rhino-to-ifc4`: a non-BIM Rhino .3dm to IFC4 (or IFC4X3_ADD2), with the agent, not a keyword table, deciding the classes. `scripts/rhino2ifc.py` runs offline on rhino3dm + ifcopenshell. `inventory` summarises each layer and block (counts, sizes, slenderness, elevations, and a form label from the principal extents: linear, plate or bulky, and their orientation) and splits a layer that mixes forms into clusters. The agent writes `mapping.json` with a class, confidence and rationale per key, and asks the user only about medium- and low-confidence ones. `convert` refuses invalid classes or PredefinedTypes per schema before writing, merges big layers, explodes nested blocks to world space, and writes colours, optional storeys (detected from floor slabs, or given), LV95/EPSG georeference, true north, an anonymous header and a `Pset_RhinoSource` of layer path and Rhino GUIDs per element. `validate` runs the schema check. Objects without a cached render mesh stop the run (exit 3) instead of vanishing. Generalised from the hand-written export of the HIL pilot model, which serves as the acceptance case (19,003 objects: 6 s inventory, 7 s convert).
```

- [ ] **Step 7: Verify**

Run: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests -q && .venv/Scripts/python -c "import json; d=json.load(open('.claude-plugin/plugin.json')); print(d['version'], d['skills'][-1]); print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"`
Expected: `51 passed`, then `1.10.0 ./skills/bim/converting-rhino-to-ifc4`, then `1.10.0`. (If marketplace.json has another shape, read it and confirm by eye that its version reads 1.10.0.)

- [ ] **Step 8: Commit**

```bash
git add skills/bim/converting-rhino-to-ifc4/SKILL.md skills/bim/converting-rhino-to-ifc4/reference skills/bim/README.md
git commit skills/bim/converting-rhino-to-ifc4/SKILL.md skills/bim/converting-rhino-to-ifc4/reference skills/bim/README.md README.md CHANGELOG.md .claude-plugin/plugin.json .claude-plugin/marketplace.json -m "feat(bim): converting-rhino-to-ifc4 skill: SKILL.md, class reference, registration (1.10.0)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Acceptance on HIL.3dm (by hand, not CI)

The 119 MB model lives on Google Drive and is not committed. This task produces no commit. It checks that an agent following SKILL.md reaches the classes chosen in the benchmark export (`agent-design-benchmark/infra/package/export_ifc.py`).

**Files:** outputs only, outside the repo. First set `OUT` to the session's scratchpad directory (or any empty folder), e.g. `OUT="$(mktemp -d)"`.

- [ ] **Step 1: Inventory**

Run: `.venv/Scripts/python skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py inventory "C:/Users/nunesd/My Drive/Demonstrator/HIL.3dm" -o "$OUT/hil-inventory.json"`
Expected: `"ok": true`, `"keys": 11`, `"objectCount": 18948` (19,003 minus 54 support points and the north line, which are listed under `nonGeometric`).

- [ ] **Step 2: Classify as the skill says**

Read only `SKILL.md`, `reference/ifc-classes.md` and `hil-inventory.json`. Do not look at the benchmark script or at this list first. Write `$OUT/hil-mapping.json`, then compare it with:

| Key | Expected class |
|---|---|
| `Existing::Stützen` | `IfcColumn` |
| `Existing::Treppen` | `IfcStair` |
| `Existing::Dachaufbauten` | `IfcBuildingElementProxy` (not `IfcRoof`) |
| `Existing::Facade#1..3` | merged; `IfcWall` / `IfcCurtainWall`, or `IfcMember` + `IfcPlate` per cluster |
| `Existing::Terrain#1..2` | `IfcGeographicElement` `TERRAIN`, merged |
| `Envelope`, `Wall zone` | `skip` (design limits) |
| `Existing::Rooftop` | open: `IfcSlab` `ROOF` or `IfcCovering` `ROOFING`; expect a medium-confidence question |

Report every disagreement, and which line of SKILL.md or the reference led there. A disagreement is a finding about the skill text, not something to fix in the mapping.

- [ ] **Step 3: Convert and validate**

Run: `.venv/Scripts/python skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py convert "C:/Users/nunesd/My Drive/Demonstrator/HIL.3dm" "$OUT/hil-mapping.json" -o "$OUT/hil.ifc" --north North && .venv/Scripts/python skills/bim/converting-rhino-to-ifc4/scripts/rhino2ifc.py validate "$OUT/hil.ifc"`
Expected: `"ok": true` from both; `IfcColumn` 54, `IfcStair` 5, `IfcBuildingElementProxy` 7; `schemaErrorCount` 0; `withoutGeometry` []; identity counts all 0. The file is about 12 MB.

- [ ] **Step 4: Viewer check (by the user)**

Ask the user to open `$OUT/hil.ifc` in a viewer (e.g. the ifc-lite build from the benchmark, BIMcollab Zoom or Solibri) and confirm the building sits on the terrain with its colours. Report the outcome as the user states it.
