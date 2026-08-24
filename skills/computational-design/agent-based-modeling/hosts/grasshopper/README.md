# Grasshopper host recipe (Rhino 8, C# Script, driven through Cordyceps)

Files
- `AbmHexPlates.cs` — the adapter: `RhinoSurfaceHost : Abm.ISurfaceHost, Abm.IPrincipalCurvatureHost` (5 methods +
  `Topology` from `IsClosed`/`IsSingular` + exact principal curvatures from `CurvatureAt`) and the `RunScript` that maps
  inputs/outputs. The build script appends `../../core/AbmCore.cs` **without its `using` lines** (a `using` after a type
  declaration is CS1529 and the GH 8 script component swallows that error silently: empty `out`, all outputs null).
- `TestSurface.cs` — `z = h cos(w x) cos(w y)`, `w = periods·π/L`, NURBS through an n×n grid.
- `build-canvas.ps1 [-Clear] [-Sphere]` — builds sliders/toggles, both scripts (or Rhino's Sphere primitive with `-Sphere`),
  wires, a report panel, two Custom Previews (green convex / red concave plate meshes; colours via Panel "R,G,B" → Colour
  param, because a Colour Swatch cannot be set through Cordyceps) and bakeable pass-throughs; writes `canvas-ids.json`.
- `capture.ps1 [-Suffix -sphere]` — hides every GH preview except the two coloured ones, bakes plate outlines per class to
  layers `abm-convex` / `abm-concave`, switches PreviewMeshEdges off and captures `captures/perspective<suffix>.png` +
  `captures/top<suffix>.png` in Shaded mode.

Inputs: `srf, count, iterations, spacing (0 = auto), wSeparation, wCohesion, wCentroid, wAlignment, speed, hexLayout,
hexAngle (< 0 = auto), keepBoundary, seed`. Outputs: `plates` (closed polylines), `meshes` (planar meshes, one per
plate), `agents`, `normals`, `e1` (principal direction × anisotropy), `gauss`, `isConvex`, `kClass` (0 elliptic, 1 parabolic
band, 2 hyperbolic), `report` (multi-line: convergence, sides histogram, tallies, side ratios, topology/Euler line).

Run (Rhino open with the Cordyceps component on a canvas, port 26929):

```powershell
pwsh build-canvas.ps1 -Clear            # egg-crate test surface; prints the report
pwsh capture.ps1                        # captures/top.png, perspective.png
pwsh build-canvas.ps1 -Clear -Sphere    # closed surface (seam + poles)
pwsh capture.ps1 -Suffix -sphere        # captures/top-sphere.png, perspective-sphere.png
```

Done-test (2026-08-22, on a live Rhino):
- Egg-crate `L=20 h=3 periods=2 n=24, count=150 hexLayout=true hexAngle=auto wAlignment=0.3`, spacing auto = 1.92,
  seedAngle = 15°: `converged=True` in 67 iterations (maxDisp 0.0019); 85 interior plates (34 boundary plates dropped),
  tpiFallbacks=72, edgeFlips=4; `sides=[5:4 6:81]`;
  **elliptic K>0: convex=15 concave=0 — hyperbolic K<0: convex=0 concave=38**; parabolic band: convex=16 concave=16;
  side ratio median / p10 elliptic 0.61 / 0.33 (n=15), **hyperbolic 0.41 / 0.33 (n=38)** (was 0.02 with the uv-aligned
  lattice: kites and arrowheads instead of bow-ties); alignment mean cos(12φ) = 0.64 over 566 pairs; `open patch`.
  `captures/top.png`: green hexagons on the dome and valleys, red symmetric butterflies in the four saddle quadrants.
- Sphere `R=10, count=150, iterations=1000`: `converged=True` in 601 iterations (maxDisp 0.003); 150 plates of 150 agents,
  0 boundary plates, tpiFallbacks=0, edgeFlips=0, `sides=[5:13 6:136 7:1]`, all convex, side ratio elliptic 0.62 / 0.44
  (n=150), Euler V−E+F = 2 and pentagons−heptagons = 12 — the tessellation closes over seam and poles
  (`captures/perspective-sphere.png`). The alignment mean reads `0.00 over 0 pairs`: a sphere is umbilic everywhere, so no
  pair clears the anisotropy gate. Absent population, not a failed metric — see §8 of `references/algorithm.md` on the two
  metrics' nearly disjoint populations.

The side-ratio figures come from `Abm.Metrics` in the core rather than from a copy in this adapter, so the numbers this
recipe prints and the numbers the console harness prints are produced by the same code.

Compile-checking the adapter without Rhino running
Cheap way to catch a syntax or signature error before spending a Rhino session: assemble the same source
`build-canvas.ps1` sends (adapter + `../../core/AbmCore.cs` with its `using` lines stripped, in that order) into one
file and build it against the installed Rhino assemblies:

```sh
cp AbmHexPlates.cs "$T/Combined.cs"
grep -v '^[[:space:]]*using [A-Za-z.]*;[[:space:]]*$' ../../core/AbmCore.cs >> "$T/Combined.cs"
# net7.0 csproj referencing RhinoCommon.dll, Grasshopper.dll, GH_IO.dll from "C:\Program Files\Rhino 8"
dotnet build "$T/check.csproj"
```

The **expected** and only acceptable diagnostic is `CS0534: 'Script_Instance' does not implement inherited abstract
member 'GH_ScriptInstance.InvokeRunScript(...)'` — Grasshopper generates that override itself. Any other error is real.
This proves the code compiles; it does **not** prove the definition runs, so the done-test numbers above still need a
live Rhino.

Known host limits
- `Params/Mesh` containers are not bakeable through `gh_canvas bake` ("no bakeable outputs"); bake a component (`Mesh Join`,
  `Flip Curve`) instead.
- `gh_canvas set` on a Colour Swatch fails ("Cannot set value on GH_ColourSwatch") — hence Panel → Colour param.
- Grasshopper's default preview (dull red) of the surface and of the script's `meshes` output hides the plates in a shaded
  capture (z-fighting, since plates lie on tangent planes); `capture.ps1` turns those previews off.
- `gh_script set` re-derives the inputs from the `RunScript` signature — removing a parameter from the signature silently
  drops the input and its wire; after changing the signature rebuild with `-Clear`.
- A sphere needs ~600 iterations; the `iterations` slider defaults to 1000.
- **`gh_document capture_viewport` only captures the viewport that is currently visible.** Any other viewport fails with
  "Failed to capture viewport" whatever its name. Verified: with `Perspective` maximised (`maximized=True`, the other three
  `False`), capturing `Top` and `Front` by name both failed while `Perspective` succeeded. `capture.ps1` therefore never
  captures by name — it drives the active viewport and captures with no `view` argument.
- `rhino_render camera` **renames the viewport to match the preset** (`preset='top'` on `Perspective` leaves a viewport
  called "Top"; `preset='iso_sw'` renames it back). Independent of the capture rule above, but it makes capture-by-name
  ambiguous, which is a second reason not to rely on it.
- **A failing `-_RunPythonScript` opens a modal dialog and Cordyceps reports `success:true` anyway.** `rhino_scene script`
  only queues the command string; it never sees the outcome. So a script with a bug (e.g. `RhinoView.Visible`, which does not
  exist) silently parks a modal error dialog in Rhino that blocks the UI until a human dismisses it, while the tool call looks
  clean. Do not treat `success:true` from `rhino_scene script` as evidence the script ran — have the script write a file and
  check for it. This matters for unattended runs: `capture.ps1` sets `Grasshopper.CentralSettings.PreviewMeshEdges = False`
  through this path, so a future edit that breaks that line would hang the session behind an invisible-to-the-tool dialog.
