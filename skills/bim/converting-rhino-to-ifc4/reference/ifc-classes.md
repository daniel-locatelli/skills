# Classifying Rhino geometry into IFC classes

Read with `inventory.json`. A form is one of `linear-vertical`,
`linear-horizontal`, `linear-sloped` (long axis at least 4x the next),
`plate-horizontal`, `plate-vertical`, `plate-sloped` (thin: middle extent at
least 4x the smallest; named by the plate's own orientation), `bulky`.
A mixed layer's rarer forms join cluster 1 and show in its `forms`.

**Flat objects** (zero thickness: a mesh terrain, a surface drawn as a
plane) are `plate-*` with a huge slenderness by construction; the thickness
bands below do not apply to them — decide on extent, position and name.

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
| `IfcMember` (`MULLION`, `BRACE`, `RAFTER`, `PURLIN`, `STUD`) | `linear-*` of small section: mullions, bracing, timber. IFC4 has no `TRANSOM`: use `MULLION`, or `USERDEFINED` with `objectType` "Transom" | mullion, brace / Pfosten, Riegel, Sparren / montant / montante / montante |
| `IfcPlate` (`CURTAIN_PANEL`, `SHEET`) | thin `plate-*` panels, cladding, glazing panes | panel, glass / Paneel, Glas, Blech / panneau, verre / pannello, vetro / painel, vidro |
| `IfcStair` / `IfcStairFlight` | `bulky` or `linear-sloped`, rising in steps. `IfcStair` for a whole stair as one element; `IfcStairFlight` only when flights are modelled separately | stair / Treppe / escalier / scala / escada |
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
  `IfcCurtainWall` when the user wants it simple: map the layer's own key
  (from `parentKeys`) instead of its clusters. Ask which.
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
