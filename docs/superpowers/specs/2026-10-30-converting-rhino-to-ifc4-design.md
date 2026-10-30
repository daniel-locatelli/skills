# Converting Rhino to IFC4 — design

Date: 2026-10-30
Skill: `skills/bim/converting-rhino-to-ifc4`

## Purpose

Turn a non-BIM Rhino model (.3dm: breps, extrusions, meshes on arbitrary
layers) into a clean IFC4 file. The agent, not a fixed keyword table, decides
which IFC class each part of the model is, from layer names and geometry.

Origin: the hand-written `infra/package/export_ifc.py` of
`agent-design-benchmark` (Rhino 8 ScriptEditor, keyword table, HIL.3dm). This
skill generalises it; it is independent of the benchmark.

## Decisions

| # | Decision |
|---|---|
| D1 | Classification unit is the **layer**; a layer with mixed geometry is split into shape clusters, each classified separately. Never per object. |
| D2 | Runs **offline**: Python + `rhino3dm` + `ifcopenshell` + `numpy`, no Rhino. Brep/extrusion geometry comes from the render meshes cached in the .3dm. Objects without a cached mesh stop the run (exit 3) with the fix: open and save normally in Rhino, or mesh via Cordyceps. |
| D3 | **Review on doubt**: the agent writes the mapping, shows it as a table, and asks the user only about medium/low-confidence entries before converting. |
| D4 | v1 always does: merge per layer when mapped, `Pset_RhinoSource` traceability, colours, anonymous header. Opt-in flags: `--storeys`, `--georef`, `--north`. |
| D5 | Default schema **IFC4 (ADD2_TC1)**; `IFC4X3_ADD2` as opt-in. The schema is chosen once, in `mapping.json`, because class validity depends on it. |

## Layout

```
skills/bim/README.md                    bucket README
skills/bim/converting-rhino-to-ifc4/
  SKILL.md                              workflow + classification rules
  scripts/rhino2ifc.py                  CLI: inventory, convert, validate
  scripts/r2i/                          model, shape, inventory, mapping, writer, checks, errors
  reference/ifc-classes.md              per-class signatures, name cues, traps
  tests/make_fixture.py                 generates the test .3dm
  tests/conftest.py, tests/test_*.py    pytest, one file per module
```

Registered in `.claude-plugin/plugin.json` and the top-level `README.md`;
`CHANGELOG.md` entry; plugin version bumped (minor).

Dependencies: Python 3.10+, `rhino3dm`, `ifcopenshell`, `numpy`. SKILL.md tells
the agent to install them into a venv when an import fails.

## Workflow (SKILL.md)

1. `rhino2ifc.py inventory <in.3dm> -o inventory.json`
2. Agent reads `inventory.json` and `reference/ifc-classes.md`, writes `mapping.json`.
3. Agent shows the mapping table; asks only about `medium`/`low` entries; updates the mapping.
4. `rhino2ifc.py convert <in.3dm> mapping.json -o out.ifc [--storeys [<z1>,<z2>,...]] [--georef EPSG:<code>,<E>,<N>,<H>[,<rot_deg>]] [--north <layer path>]`
5. `rhino2ifc.py validate out.ifc` — the agent reports its output, not assumptions.

## `inventory`

Output JSON:

- `units` (model unit and scale to metres), `extent` (bbox in metres), `objectCount`.
- `layers[]`, one per layer that holds objects (blocks: one entry per
  instance definition, `kind: "block"`, keyed `block:<definition name>`
  regardless of the layers of the instances or of the geometry inside the
  definition, so a layer and a block of one name stay two keys; instances are
  exploded to world geometry, nested instances recursively with composed
  transforms). Statistics, forms and counts are per object: a Rhino object,
  or a block instance with all its exploded parts as one vertex set:
  - `path`, `count`, `geometryTypes` ({type: count}), `colour`
  - `bbox` (union, metres)
  - per-object statistics as min / median / max: size (dx, dy, dz),
    slenderness (largest / smallest principal extent), `zMin`, `zMax`
  - `forms` ({form: count}). From the principal extents e1 >= e2 >= e3 of
    the mesh vertices: `linear-<dir>` when e1/e2 >= 4 (dir of the long axis),
    `plate-<dir>` when e2/e3 >= 4 (dir of the plate itself: a slab is
    `plate-horizontal`, a wall `plate-vertical`), else `bulky`; dir is
    `vertical` / `horizontal` / `sloped` at 15 degrees.
  - `missingMesh`: object ids without a usable mesh
  - `clusters[]` (only when the key is mixed: two or more forms each hold at
    least 10 % of its objects): one per such form, largest first, keyed
    `<key>#<n>`, with `form`, `count` and the same statistics; objects of rarer
    forms join cluster 1 (and show in its `forms`).
- `keys`: the keys the mapping must cover (clusters, not mixed keys).
- `parentKeys`: `{mixed key: [its cluster keys]}`. The mapping covers a mixed
  key either by the mixed key itself (all its objects, one class) or by all
  of its clusters — not both, not a partial set.
- `nonGeometric`: per layer, counts of points, curves, text and other
  non-meshable objects — including those inside block definitions (counted on
  the instance's layer) and block-definition objects the file cannot resolve
  (`unresolved block object`). Not keys; never converted.

**Mesh source** (rhino3dm cannot tessellate): Mesh → itself; Brep → each
`BrepFace.GetMesh(MeshType.Render)`, falling back to `MeshType.Any`, joined
into one mesh; Extrusion → `GetMesh(Render)` then `Any`. A Brep with any face
lacking a mesh, an Extrusion without one, SubD or other surface types
without a cached mesh, and any mesh with no vertices or faces (a Brep with
zero faces included) go to `missingMesh`. An object on a layer index or a
block instance of a definition the file does not have → exit 2.

Exit 3 if any `missingMesh` is non-empty. The JSON is still the full
inventory, plus `"error": {"code": 3, "missingMesh": [{"key", "objectId",
"geometryType"}], "fix": "..."}`.

## `mapping.json`

```json
{
  "schema": "IFC4",
  "entries": [
    {"key": "Existing::Stützen", "class": "IfcColumn", "predefinedType": null,
     "merge": false, "confidence": "high", "rationale": "vertical, slender 7:1, 'Stützen' = columns"},
    {"key": "Layer 01#2", "class": "IfcSlab", "predefinedType": "FLOOR",
     "merge": false, "confidence": "medium", "rationale": "horizontal thin plates at 3 levels"},
    {"key": "North", "skip": true, "rationale": "north arrow"}
  ]
}
```

`key` is a layer path, a cluster id, a mixed key from `parentKeys`, or
`block:<definition name>`. Every inventory key must be covered exactly once
(classified or `skip`, directly or through its mixed key); `convert` refuses
otherwise. The file must be an object with an `entries` list of objects whose
`key` and `class` are strings; any other shape is refused (exit 2) with every
problem listed. `schema` is `IFC4` or `IFC4X3_ADD2` and is the only place
the schema is chosen. `predefinedType` is normalised to upper case;
`USERDEFINED` requires an `objectType` string (written to `ObjectType`).

## `convert`

- **Validation before writing** (exit 2, naming the entry): unknown key, missing
  key, a mixed key mapped together with any of its clusters, class not a
  concrete `IfcElement` subtype in the chosen schema (feature and virtual
  elements — openings, projections, `IfcVirtualElement` — refused), invalid
  `predefinedType` for the class. A classified (not skipped) key holding
  objects without a mesh → exit 3, nothing written.
- **Spatial structure**: IfcProject → IfcSite → IfcBuilding; SI units in
  metres (scaled from model units); Body and Reference contexts. Elements of
  class `IfcGeographicElement` are contained in the Site, all others in the
  Building.
- **`--storeys`**: levels = bottom elevations of the Rhino objects (block
  instances) mapped to `IfcSlab` FLOOR, merged or not, clustered with 0.3 m
  tolerance; IfcBuildingStorey per level, aggregated under the Building, its
  placement at z = level relative to the Building (element placements stay in
  world coordinates); each element contained in the storey whose band
  `[level, next level)` holds its `zMin` (below the lowest level → lowest
  storey). A multi-storey column or wall therefore sits in the storey where it
  starts; SKILL.md states this. Storeys found are printed in the result JSON.
  `--storeys <z1>,<z2>,...` (metres, duplicates dropped) gives the levels
  explicitly and skips detection — the fix when stepped or sunken slabs fool the 0.3 m clustering.
  Without the flag no storeys are created.
- **Geometry**: each object → IfcPolygonalFaceSet (triangles and quads, `Closed`
  from the mesh) in a Body / Tessellation representation, coordinates in metres.
- **Elements**: `merge: false` → one element per Rhino object or block
  instance (all its parts' meshes as items); `merge: true` → one element per
  key with all meshes as items. `Name` = layer leaf name (or cluster id /
  block definition name), or the Rhino object name when set and not merged.
- **`Pset_RhinoSource`** on every element: `LayerPath` (the distinct layer
  paths of its objects, `;`-joined), `ObjectIds`
  (`;`-separated GUIDs; when merged and more than 50 objects: the first 50 and
  `ObjectCount`), `Confidence`, `Rationale`.
- **Blocks**: `Pset_RhinoSource.LayerPath` is the instance's layer; for a merged
  key whose rows span several layers, the distinct layer paths joined with `;`
  (as in the Pset bullet above). Geometry
  inside a definition whose colour is "by parent" takes the instance's colour.
- **Colours**: the render material first (object material when "by object",
  the parent instance's when "by parent", else the layer's `RenderMaterialIndex`;
  models like HIL keep every layer's display colour black), its diffuse colour
  and transparency; with no valid material, the display colour (object colour
  when "by object", else layer colour). → IfcSurfaceStyle with
  IfcSurfaceStyleShading (`Transparency` only when > 0); one style per distinct
  (colour, transparency), assigned via IfcStyledItem.
- **Header**: author, organization, authorization empty; `originating_system`
  `rhino2ifc`; no IfcOwnerHistory.
- **`--georef`**: IfcProjectedCRS (`EPSG:<code>`) + IfcMapConversion (Eastings,
  Northings, OrthogonalHeight; XAxisAbscissa/Ordinate from the optional
  rotation; Scale 1.0).
- **`--north <layer>`**: TrueNorth of the model context from the first line on
  that layer (start → end), as in `export_ifc.py`.

Result JSON: output path, schema, element count per class, storeys, skipped
keys. An `-o` path that cannot be written → exit 2.

## `validate`

`ifcopenshell.validate` against the file's schema (entity and attribute
types, cardinality; not the schema's WHERE rules), plus: element count per
class, elements without a representation, IfcOwnerHistory / IfcPerson /
IfcOrganization count, header author/organization. Exit 4 if schema
validation fails or any element lacks geometry.

## `reference/ifc-classes.md`

For each class common in non-BIM models — IfcWall, IfcSlab (FLOOR / ROOF /
LANDING), IfcRoof, IfcColumn, IfcBeam, IfcMember, IfcPlate, IfcStair /
IfcStairFlight, IfcRailing, IfcWindow, IfcDoor, IfcCovering, IfcCurtainWall,
IfcFooting, IfcPile, IfcGeographicElement, IfcFurnishingElement,
IfcBuildingElementProxy (and IfcSpace / IfcSpatialZone as non-elements, out of
v1 conversion):

- geometric signature (direction, slenderness, thickness, typical dimensions)
- name cues in EN / DE / FR / IT / PT
- traps (rooftop structures are not IfcRoof; a facade of thousands of panels is
  one merged IfcWall or IfcCurtainWall, not IfcPlate; "glass" may be windows
  or curtain wall; neighbouring context buildings are proxies on the site)

Rules stated in SKILL.md: geometry outweighs the name when they disagree;
IfcBuildingElementProxy with `low` confidence is the honest answer when
neither convinces; no class is invented to look complete.

## Errors

JSON on stdout for every outcome, usage errors included. Exit codes: `0` ok,
`1` internal error (any unexpected exception: `{"code": 1, "message":
"<Type>: <msg>", "fix": "internal error; report it with the command and
file"}`), `2` input error (arguments, file, mapping, class, predefined type,
unwritable output), `3` objects without mesh, `4` validation failed. Every
error names the layer/key/object and the fix.

## Testing

- `tests/make_fixture.py` builds a small .3dm with rhino3dm: a German-named
  column layer (`Stützen`), a meaningless `Layer 01` mixing columns and slabs
  at two levels, a block, a mesh terrain, a curve-only layer, and one brep
  without a cached mesh (in a second fixture variant). `build_extra`: a layer
  and a block both named Chair (the block: four legs, a seat and a line, three
  instances on two layers), a floor-slab layer at three levels, a mixed
  facade layer, 55 small objects on one layer, and optionally an empty mesh.
  `build_broken`: a block definition with an unresolved object, optionally an
  instance of a missing definition.
- pytest covers: inventory statistics and cluster split; block keys
  `block:<name>` and layer/block name collision; per-instance block statistics;
  parent-key vs clusters either-or rule; mapping validation
  (missing key, unknown class, bad predefined type, lower-case predefined
  type accepted, USERDEFINED without `objectType` refused); nested block
  transforms; convert produces files
  that pass `ifcopenshell.validate` for IFC4 and IFC4X3_ADD2; storey detection,
  incl. merged floor slabs; `Pset_RhinoSource`; ObjectCount for merged keys
  over 50 objects; colours; empty header and no IfcOwnerHistory; exit 3 on
  missing mesh, empty meshes as missing; JSON on every exit (argparse errors,
  malformed mapping, unwritable output, internal error exit 1).
- Acceptance (by hand, not CI — 119 MB file on Drive):
  `C:\Users\nunesd\My Drive\Demonstrator\HIL.3dm`. The agent's mapping should
  match the benchmark's choices — Stützen → IfcColumn, Treppen → IfcStair,
  Dachaufbauten → IfcBuildingElementProxy, Facade → merged IfcWall,
  Terrain → IfcGeographicElement TERRAIN — and the IFC must validate and open
  in a viewer.

## Out of scope (v1)

Blocks as IfcMappedItem; IfcSpace / IfcSpatialZone output; materials and
property sets beyond `Pset_RhinoSource`; NURBS (AdvancedBrep) geometry;
openings / voids; running inside Rhino.
