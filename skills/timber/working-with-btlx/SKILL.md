---
name: working-with-btlx
description: Use when working with BTLx or BTL files (.btlx, .btlz), the design2machine timber CNC exchange format, BTLx processings (JackRafterCut, Drilling, FreeContour, Lap, Tenon…), reference sides / ReferencePlaneID, BTLx schema versions or validation, or timber fabrication export in compas_timber — before answering any BTLx parameter, range, default, or version question.
---

# BTLx

XML exchange format for timber CNC machining (design2machine): parts +
parametric **processings**, each measured in the 2D space of one of the
part's six reference sides. Mental model: [references/btlx-concepts.md](references/btlx-concepts.md).

**Core rule: never answer a wire-contract question (parameter names, types,
ranges, defaults, required/optional) from memory.** Plausible-but-wrong
answers are the observed failure mode — signed ranges that are actually
unsigned, defaults on attributes that are required. Look it up:

| Question | Source |
|---|---|
| Parameter names / types / ranges / defaults | [references/processings-2.3.0.md](references/processings-2.3.0.md) (generated from the XSD) |
| Same, for the version compas_timber writes | [references/processings-2.0.0.md](references/processings-2.0.0.md) |
| What changed between versions; which Version to declare | [references/versions.md](references/versions.md) |
| Geometric meaning (what does StartX measure?), file structure, ref sides | [references/btlx-concepts.md](references/btlx-concepts.md); diagrams: manual PDF (archive below) |
| Worked examples of a processing in real XML | archive `examples_2.0/<processing>/` (.btlx + description PDF per processing) |

## Primary sources (archive)

Vendor files live **outside this skill** (no redistribution rights;
design2machine's website is the only official channel — no schema repo
exists). On Daniel's machines:

```
C:\repos\data-models-reverse-engineering\BTLx\
├─ schema_xsd\    BTLx_1_0_0 … BTLx_2_3_1.xsd   ← normative
├─ manual_pdf\    BTLx_2_1_0/2_2_0/2_3_0.pdf    ← graphical appendix (no 2.0.0 exists anywhere)
└─ examples_2.0\  per-processing .btlx + PDFs
```

If the archive is missing, download from design2machine.com/btlx/. The
compas_timber implementation (`src/compas_timber/fabrication/`,
`src/compas_timber/btlx/` reader) is a secondary source — it enforces spec
ranges in property setters but pins `Version="2.0.0"`.

## Recipes

- **Validate a file:** `python -c "import xmlschema; xmlschema.XMLSchema(r'<archive>\schema_xsd\BTLx_2_3_1.xsd').validate(r'file.btlx')"` — validate against the schema the file's `Version` attribute declares (each schema accepts exactly one value).
- **Check a parameter fast:** grep the processing name in the generated reference; the shared base attributes (`ProcessID`, `ReferencePlaneID`…) are in its "Shared base" section.
- **New schema version ships:** regenerate — `python scripts/generate_reference.py <new.xsd> -o references/processings-<ver>.md`; append the version row to versions.md from the XSD's header changelog comments.
- **Deep contour semantics** (FreeContour, DualContour, apertures): generated tables give structure only; read the manual PDF + `examples_2.0/contour-and-outline/`.
