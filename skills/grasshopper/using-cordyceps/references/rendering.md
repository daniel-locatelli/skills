# Cordyceps: rendering and capture pitfalls

Measured findings for baking, previews, camera, materials and viewport/canvas capture.
Read before `gh_canvas bake`, `gh_document capture_*`, or `rhino_render`.

- **`gh_canvas bake` needs a component, not a Param container.** `Params/Mesh`, `Params/Curve` etc. return
  "Component has no bakeable outputs"; route through a pass-through component (`Mesh Join`, `Flip Curve`) and bake that.
- **Viewport captures can be wireframe-only.** In a non-GPU / remote session both `gh_document capture_viewport`
  and Rhino's `-ViewCaptureToFile` returned wire-only grey images whatever the display mode (Shaded, Rendered,
  Arctic…) and GH previews were not drawn at all. Bake closed outlines to coloured layers for a legible capture;
  keep meshes for sessions with a real GPU.
- **Colour Swatch cannot be set** (`gh_canvas set` → "Cannot set value on GH_ColourSwatch", stays white). Drive a Custom Preview material from a Panel holding `R,G,B` wired into a `Params/Colour` parameter instead.
- **Shaded viewport captures show GH's default dull-red preview** of every surface/mesh output, which z-fights with geometry lying on it. Before `capture_viewport`, disable previews per component (`gh_canvas preview enabled=false`, keep only your Custom Previews) and, for clean fills, `rhino_scene script cmd='-RunPythonScript (import Grasshopper; Grasshopper.CentralSettings.PreviewMeshEdges = False)'`.
- **`gh_document capture_viewport` can only capture the viewport that is currently visible.** Any other viewport fails with
  "Failed to capture viewport" whatever it is named — in a maximised layout that is every viewport but one. Drive the active
  viewport and capture with **no `view` argument**. Related: `rhino_render camera` **renames the viewport to match the
  preset** (`preset='top'` on `Perspective` leaves a second viewport called "Top"; `preset='iso_sw'` renames it back), so
  capture-by-name is ambiguous as well as unreliable.
- **"Grasshopper display error — System.Drawing.Common: Parameter is not valid" on opening the GH window** of a Rhino that was launched hours earlier by the launcher (its canvas captures returned "black image" all along) is a stale-window artefact, not a definition problem: close that Rhino, relaunch, rebuild the canvas.
