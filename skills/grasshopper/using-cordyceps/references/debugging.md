# Cordyceps: debugging and canvas-driving pitfalls

Measured findings for placing and wiring components, probing values, clusters, and
components whose UI is invisible to `gh_canvas`. Read when a call "succeeds" but nothing happened.

## Empirical gotchas

- **PowerShell callers: `ConvertTo-Json -AsArray`.** A one-element array serialises as a bare object without it,
  and `gh_script configure` then silently creates no param / `gh_wire connect` connects nothing.
- **Ambiguous component names** silently fail `gh_canvas add` (call succeeds, no component lands). Use `Category/Name` (e.g., `Curve/Circle`) or the GUID from `gh_canvas search`. The non-deprecated Boolean Toggle is `2e78987b-9dfb-42a2-8b76-3923ac8bd91a`; new C# Script is `b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`.
- **`gh_wire connect` takes `sourceId`/`targetId`/`targetParam`** — not `fromId`/`toId` (those fail with "Provide sourceId+targetId"). A failed wire is easy to miss: the component still solves on its defaults, so always check the wire call's own response, not just downstream outputs.
- **`Stop-Process` on Rhino skips Grasshopper's settings save.** Anything set via `Grasshopper.CentralSettings` mid-session (`CanvasObjectIcons`, `PreviewMeshEdges`, …) silently reverts. Re-apply such settings after every force-kill relaunch, or close Rhino gracefully when settings must stick.
- **`gh_canvas add` response shape** is `result.id`, NOT `result.component.id`.
- **`gh_inspect outputs` `preview` is sometimes empty** for non-primitive types even when data is flowing. See "Panel-as-probe" below.
- **Some components are not found by `Category/Name`** (`Surface/Primitive/Sphere` → "Unknown component type"); take the GUID from `gh_canvas search` (Sphere: `dabc854d-f50e-408a-b001-d043c7de151d`).
- **`$pid` is a read-only automatic variable in PowerShell** — don't use it as a loop variable in driver scripts.

### Panel-as-probe Pattern

When `outputs preview` is empty but you need to confirm a value, wire a sink Panel to the output. `gh_canvas info` on that panel returns `dataCount` — the cleanest "did data flow?" signal. For the values themselves, screenshot the canvas (`gh_document capture_canvas`) — the panel renders incoming data inline. Don't use `gh_canvas get` on the probe — that returns the panel's static editor text, not runtime wire data.

### Cluster editor

**Never use Grasshopper's native F5 / recompute button while a cluster editor is open** — it destroys cluster input hooks. Always use `gh_document(action='recompute')` and `gh_document(action='solver', enabled=true)`; both are cluster-safe.

### Custom component attributes (buttons, menus) bypass `gh_canvas`

Any component that overrides `CreateAttributes()` with custom GDI+ UI — embedded buttons, sliders, popups, right-click menus — is invisible to `gh_canvas`. There's no "click" action: `gh_canvas` only sees parameter values, not visual chrome painted by `GH_ComponentAttributes` subclasses.

Workaround: drive the component's public methods directly via `rhino_scene` with `-RunPythonScript`. The Python runtime inside Rhino can reach the live Grasshopper document and call anything the component exposes.

```powershell
CCall 'rhino_scene' @{
  action='script'
  cmd='-RunPythonScript (import Grasshopper as GH; doc = GH.Instances.ActiveCanvas.Document; [obj.RequestUpload() for obj in doc.Objects if hasattr(obj, "RequestUpload") and "Color Legend" in obj.Name])'
}
```

The pattern:
1. `Grasshopper.Instances.ActiveCanvas.Document` → the live `GH_Document`
2. Iterate `doc.Objects` to find components by name, nickname, GUID, or by `hasattr` for a known method
3. Call any public method on the component — `RequestUpload()`, `ExpireSolution(true)`, custom right-click menu handlers, etc.

The `-RunPythonScript ( … )` form lets you inline a one-liner from a single Cordyceps call without writing a temp `.py` file. Newlines and quotes are awkward inside the parentheses — keep the body compact, use list comprehensions or semicolons, and prefer `hasattr(obj, "MethodName")` over type checks (cleaner across plugins).

This is the universal escape hatch when a plugin's "interactive" UX (an upload button, a "bake all" button, a custom canvas widget) has no wire-level equivalent. If the component author exposed the action as a public method, you can trigger it; if they hid it inside a private event handler, you're stuck — file an issue asking for a programmatic surface.
