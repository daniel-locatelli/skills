# BTLx concepts — the mental model

> Hand-distilled (own words) from the design2machine manual (BTLx 2.3,
> 2025-07-08 — page refs below), the XSD, and the compas_timber
> implementation. The manual's diagrams are the authority for exact geometry;
> page numbers point there. Wire-level parameter facts belong to the
> generated `processings-*.md` files, not here.

## What BTLx is

An XML exchange format for timber machining: a **parametric description of
wooden parts and the machining operations (processings) on them**, carrying
no machine-specific data. A CAM system imports it and translates to a
concrete machine. The XSD is the normative schema; the PDF manual is its
*graphical appendix* (the geometry drawings the schema can't express).

- Units, schema-wide: **millimeters, degrees, kilograms** (XSD header).
- All indices on the wire are **1-based**.
- `.btlx` = the XML file. `.btlz` = a standard **zip containing exactly one
  BTLx file** (nothing else) — a compression wrapper, not a container format
  (manual p. 2).

## File structure

```
BTLx  @Version (enum, exactly one value per schema) @Language (ISO 639-1)
├─ FileHistory?          InitialExportProgram?, EditingProgram*
└─ Project               @Name …
   ├─ UserAttributes?    typed key/values (String | Integer | Real)
   ├─ Rawparts?          stock for nesting — mostly NOT part of the building
   │                     project; manufacturing concern (manual p. 7)
   └─ Parts → Part*      the building components
      ├─ geometry attrs  Length/Width/Height + order/count data
      ├─ Transformations placement(s) in project coordinates; if @Count > 1
      │                  there must be Count transformations, each own GUID
      ├─ Processings?    the machining list (+ ProcessingGroup nesting;
      │                  Connector since 2.3.0)
      └─ Shape?          optional explicit X3D mesh of the processed part —
                         faces coplanar, counterclockwise, closed volume,
                         coordinates relative to the part's ReferencePoint
                         (manual p. 8)
```

There is **no joint/connection layer**: a lap joint is two independent Lap
processings on two independent parts (the 2.3.0 `Connector` element is the
first step beyond that). Design intent does not survive the trip —
fabrication truth, design amnesia.

## Part coordinates, reference sides, reference edges

- Each part has a local frame: `ReferencePoint` + `XVector`/`YVector`
  (manual p. 5). X runs along the **length**; the cross-section spans
  width × height. The frame sits on a corner of the **blank** (the stock
  volume before machining — in compas_timber terms, extensions are already
  baked into Length).
- **RS1–RS6, the six reference sides**: the four longitudinal faces (RS1–RS4,
  wrapping around the cross-section) then the two end faces (RS5 = start,
  RS6 = end). **RE1–RE4** are the four reference edges of the cross-section.
  The exact circumferential order and each side's own X/Y axes are defined
  by drawing — manual p. 5 is the authority; do not reason them out.
- Every processing measures its parameters (`StartX`, `StartY`,
  `StartDepth`, angles) **in the 2D parametric space of one reference
  side**, viewed orthogonally to that side (manual p. 6).

## ReferencePlaneID (on every processing, required)

- `1`–`6` → the global reference sides above.
- `≥100` → a **user-defined ReferencePlane** declared on the part (its own
  ReferencePoint + X/YVector, relative to the part frame `PartRef`,
  manual p. 6).
- No default. XSD constrains only `≥1` — the 1–6/100+ split is manual-level
  convention.

## Processing shared machinery

Every processing carries the base attributes (exact table: generated
reference, "Shared base"): `Name`, `ProcessID` (required), `Process`
(yes/no), `ProcessingQuality` (automatic | visible | fast), `Recess`
(how leftover material is handled — automatic vs manual, manual p. 4),
`Priority`, `Comment`, plus per-processing `UserAttributes`.

Camber rule: **all processings are defined on the part without camber**
(manual p. 7) — cambered parts machine the straight geometry.

## Correspondence: compas_timber

| BTLx | compas_timber |
|---|---|
| ReferencePlaneID 1–6 | `ref_side_index` 0–5 — writer adds 1 (`fabrication/btlx.py`), reader subtracts 1; everything between stays 0-based |
| Part = blank | `Beam.blank` / `ref_frame` on a blank corner (`elements/base.py` cites the BTLx PDF) |
| `@Version` | hardcoded `"2.0.0"` — deliberate "oldest schema you satisfy" pin (see `versions.md`) |
| Processing | `BTLxProcessing` subclass; `PROCESSING_NAME` must match the spec's element name exactly |
| Part/Project `UserAttributes` | not exported today |

## Traps (each observed in baseline testing)

- Ranges are **not symmetric by default**: `StartY`/`StartDepth` are often
  `WidthType` (0…50000, unsigned) while `StartX` is `LengthPosType`
  (±100000). Never quote a range from memory — read the generated table.
- Required attributes (`Orientation`, `ReferencePlaneID`, `ToolPosition`,
  `ProcessID`) have **no defaults**; optional elements do.
- `.btlz` holds one file only.
- A schema's `Version` attribute accepts exactly one value — files declare
  the one schema they satisfy.
