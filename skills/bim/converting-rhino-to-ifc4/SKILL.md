---
name: converting-rhino-to-ifc4
description: Use when turning a Rhino .3dm (non-BIM geometry — breps, extrusions, meshes on layers) into an IFC file, deciding which IFC class (IfcWall, IfcSlab, IfcColumn, ...) Rhino layers or blocks should become, or delivering IFC4 / IFC4X3 from a Rhino model for Revit, ArchiCAD, Solibri or a web viewer — without Rhino running.
---

# Converting Rhino to IFC4

A Rhino model has layers and geometry, not building elements. **You** decide
what each layer is; `scripts/rhino2ifc.py` measures the geometry and writes
the IFC. Offline: Python + `rhino3dm` + `ifcopenshell` + `numpy`, no Rhino.

Once, if an import fails, make a venv; `$PY` below is its python
(`.venv/Scripts/python` on Windows, `.venv/bin/python` elsewhere):

    python -m venv .venv
    $PY -m pip install -r <skillRoot>/requirements.txt

Every command prints JSON, errors included. Exit `0` ok, `1` internal error
(a bug: report the command and file), `2` input error (the JSON names the
entry and the fix), `3` objects without a cached mesh, `4` validation failed.

## Workflow

1. **Inventory**

       $PY <skillRoot>/scripts/rhino2ifc.py inventory model.3dm -o inventory.json

   One record per **key** — a layer path, or `block:<definition name>` for a
   block. Per key: count, geometry types, colour, bbox, `forms`, and
   min/median/max of size, slenderness, `zMin`, `zMax` (metres). Counts and
   statistics are per object; a block instance counts once, all its parts
   measured together. A layer that mixes shapes is split into clusters
   `<layer>#<n>`, one per main form; rarer forms join cluster 1 and show in
   its `forms`. `keys` lists the clusters, and `parentKeys` maps each mixed
   layer to its clusters. Points, curves and text (also inside blocks) are
   counted under `nonGeometric` and never converted.

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
   - A mixed layer (`parentKeys`): map **either** the layer's own key (all
     its objects, one class — e.g. the whole facade as one merged `IfcWall`)
     **or** every one of its `#n` clusters. Not both, not some.
   - `schema`: `IFC4` (default; best supported by Revit, ArchiCAD, viewers) or
     `IFC4X3_ADD2` only when asked.
   - `merge: true` = one element per key (a facade of 18,000 pieces); false =
     one element per Rhino object or block instance (all its parts).
   - `class`: a physical `IfcElement` subtype; openings, projections and
     virtual elements are refused.
   - `predefinedType` is optional; `USERDEFINED` needs `objectType`.
   - `confidence`: `high` = name and geometry agree; `medium` = one supports
     the class, the other is neutral; `low` = they conflict, or neither helps.
   - **Geometry outweighs the name** when they disagree. When neither
     convinces, `IfcBuildingElementProxy` with `low` is the honest answer —
     never invent a class to look complete.

3. **Review on doubt** — show the user a table (key, count, form, class,
   confidence, rationale), skip rows included. Ask only about `medium` and
   `low` rows; `high` rows pass, and skip rows are not asked about unless the
   name is ambiguous. Update the mapping with the answers.

4. **Convert**

       $PY <skillRoot>/scripts/rhino2ifc.py convert model.3dm mapping.json -o model.ifc

   Options, only when the user wants them:
   - `--storeys` — levels from the bottoms of the objects mapped to `IfcSlab`
     `FLOOR` (merged ones too; 0.3 m tolerance). Each element goes to the
     storey where its bottom is: a
     three-storey column sits in the storey it starts in. When stepped or
     sunken slabs fool detection: `--storeys 0,3.2,6.4` (metres).
   - `--georef EPSG:2056,2600000,1200000,400[,rot_deg]` — map conversion of
     the model origin (code, easting, northing, height, x-axis rotation).
   - `--north <layer>` — true north from the first line on that layer.

   Refused mapping → exit 2 with every problem listed; fix them all, rerun.

5. **Validate**, then report what the output says — not what you expect:

       $PY <skillRoot>/scripts/rhino2ifc.py validate model.ifc

   Schema errors (entity and attribute types, cardinality — not the
   schema's WHERE rules), elements per class, elements without geometry,
   owner / person / organization counts, header author.

## What the IFC contains

IfcProject → IfcSite → IfcBuilding (→ IfcBuildingStorey with `--storeys`), metres.
`IfcGeographicElement` sits in the site, everything else in the building.
Bodies are `IfcPolygonalFaceSet` from the cached meshes, coloured from the
Rhino display colour. Every element carries `Pset_RhinoSource`: `LayerPath`
(`;`-joined when a merged element spans layers), `ObjectIds` (Rhino GUIDs;
first 50 plus `ObjectCount` when merged),
`Confidence`, `Rationale` — so any element can be found in the .3dm again.
Header author and organization are empty; no IfcOwnerHistory.

Blocks are one key `block:<name>` per definition (the outermost, for nested
blocks), exploded to world geometry; `LayerPath` is the instance's layer.

## Not covered

NURBS (`IfcAdvancedBrep`) bodies, openings and voids, materials, spaces and
zones, blocks as `IfcMappedItem`. Say so when the user needs one of them.
