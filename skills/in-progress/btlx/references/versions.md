# BTLx version history

> Hand-curated from the changelog comments each XSD carries in its header and
> from `generate_reference.py --list` runs over the archived schemas.
> Processing counts are regenerable: `python scripts/generate_reference.py <xsd> --list`.
> Schema dates are design2machine's published dates (schema.html).

BTLx succeeded the older BTL format (v10/v11, still documented at
design2machine.com/btlx/documentation/). The XSD headers carry entries back to
2016, before the first public 1.0 release.

| Version | Published | Processings | What changed (schema-level) |
|---|---|---|---|
| 1.0.0 | 2020-06-09 | 47 | First public BTLx schema. X3D `Shape` embedded per part (from BTL 1.1 work). |
| 2.0.0 | 2021-03-03 | 50 | + `JapaneseTenon`, `JapaneseMortise`, `FreeSurface` (NURBS patch). NURBS curve/patch definitions, contours with optional apertures, typed `UserAttribute` (String/Integer/Real). **The version compas_timber writes** (`Version="2.0.0"` hardcoded in `fabrication/btlx.py`). |
| 2.1.0 | 2022-06-29 | 53 | + `CrampContour`, `ScrewContour`, `InsulationArea`. `ProcessID` became **required**. `Drilling` `DepthLimited` default flipped to `yes`. `SawCut` machining limits renamed Front/Back → Start/End. Many parameters moved from bare `xs:double` to range-restricted types. |
| 2.2.0 | 2024-03-14 | 53 | No new processings; structural revision: contour structure simplified, outline now includes silhouette, **angle sequence changed for `Mortise`, `DovetailMortise`, `HouseMortise`** (wire-incompatible with 2.1 readers for those), `ScrewDiameter` moved from screw-contour segments to `Contour`, `RidgeValleyCut` angle parameters renamed, `ProcessingGroupType` made non-abstract. |
| 2.3.0 | 2025-03-11 | 54 | + `PatternContour`; new `Connector` element (joining, sits beside processings in `ProcessingGroup`), `ConnectorInfo` in `FreeContour`, `FaceLimited` attribute for `FreeContour` segments, `CrampWidth` for cramp contours, dynamic `ConnectorParameter`. |
| 2.3.1 | 2025-07-08 | 54 | One addition: `@MinDistanceToEnd` on `PatternContourAttributes`. |

## Availability notes (verified 2026-07-26)

- design2machine has **no schema/spec repository** — the GitHub org holds only
  the BtlViewer binary releases. The website is the only distribution channel;
  the local archive at `C:\repos\data-models-reverse-engineering\BTLx\` is the
  durable copy.
- PDF manuals are only published for **2.1.0 and later**. `BTLx_2_0_0.pdf`
  returns 300/not-found and has no Wayback Machine snapshot — for the version
  compas_timber actually pins, **the 2.0.0 XSD is the only surviving official
  record** (`schema_xsd/BTLx_2_0_0.xsd` in the archive).
- The PDF manual is versioned per minor line (the "BTLx 2.3" manual covers
  2.3.x; its history page lists per-build changes).

## Reading a version bump

The XSD header comments are the authoritative changelog — each schema lists
its own changes plus the inherited history. To diff two versions precisely:

```
python scripts/generate_reference.py old.xsd -o old.md
python scripts/generate_reference.py new.xsd -o new.md
diff old.md new.md
```

The root `Version` attribute is an **enum with exactly one value** per schema
(e.g. only `"2.3.0"` validates against `BTLx_2_3_0.xsd`) — a file declares the
schema it satisfies, and validators check against that schema alone. Writing
the oldest version whose feature set you use maximizes machine compatibility
(the reasoning behind compas_timber's deliberate 2.0.0 pin).
