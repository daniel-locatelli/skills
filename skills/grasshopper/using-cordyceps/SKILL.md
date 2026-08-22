---
name: using-cordyceps
description: Use when driving Grasshopper or Rhino through the Cordyceps MCP server — placing/wiring components on the GH canvas, configuring C# or Python script components, reading solver outputs, baking/rendering/capturing scenes, or restarting the server after Rhino was closed. Triggers on mentions of Cordyceps, gh_canvas/gh_wire/gh_script/gh_inspect/rhino_render/rhino_scene tool names, bootstrap.gh, or any "automate Grasshopper" / "control Rhino from Claude" task.
---

# Using Cordyceps

Cordyceps is an MCP server hosted **inside** a running Grasshopper instance (it ships as a `.gha` plugin). It exposes 7 tools with 110+ actions at `http://127.0.0.1:26929/mcp` (port configurable on the component).

**Source of truth:** https://github.com/brookstalley/cordyceps — features and APIs evolve quickly. This skill captures the *Claude Code–specific* operating ritual; for tool semantics, **read the embedded docs Cordyceps ships** (see below).

## Install (one-time, per machine)

Either install via Rhino's package manager (Yak: `cordyceps`, v1.4+), or download `Cordyceps.gha` from the repo's `releases/` folder and place it in Grasshopper's Components Folder (*File → Special Folders → Components Folder*). **On Windows, right-click the `.gha` → Properties → Unblock**, or Rhino will refuse to load it.

Drop the **Cordyceps** component on the canvas (`Params → Util → Cordyceps`). It has two inputs:
- **Port** — default 26929
- **DebugLevel** — 0 (default), or 1+ to print request/response traffic to Rhino's command history (invaluable when something silently fails)

Once placed, register the server with Claude Code so its tools surface in ToolSearch:

```
claude mcp add --transport http cordyceps http://127.0.0.1:26929/mcp
```

## Bring It Online

**Don't** call `Rhino.exe bootstrap.gh` directly — that path triggers a "Recover your data" prompt the next time Rhino closes dirty, and once that prompt is up nothing can dismiss it (chicken-and-egg).

Use the launcher in this skill folder:

```powershell
pwsh "$env:USERPROFILE\.claude\skills\using-cordyceps\launch-cordyceps.ps1"
```

It sweeps stale autosaves under `%APPDATA%\Grasshopper\AutoSave\`, copies `bootstrap.gh` to `$env:TEMP\cordyceps-<random>.gh`, opens that disposable copy with Rhino, and polls until the MCP endpoint responds. Unique filename per session means the autosave can never re-attach to the canonical bootstrap. Cold start ≈ 20s.

## Read the Embedded Docs First

Cordyceps publishes its own knowledge base as MCP resources. The server's `initialize` response literally instructs **"READ FIRST: gh://docs/getting-started"**. Always start with `resources/list`, then `resources/read` for whatever matches your task:

| Resource | When to read |
|---|---|
| `gh://docs/getting-started` | First contact — tool listing, core workflow |
| `gh://docs/common-errors` | Hit an error message |
| `gh://docs/data-trees` | Working with lists, branches, N×M operations |
| `gh://docs/type-system` | Wiring across geometry types, Goo conversions |
| `gh://docs/canvas-layout` | Placing components without overlap |
| `gh://docs/component-patterns` | Standard recipes (arrays, transforms, conditionals) |
| `gh://docs/rendering` | Bake → materials → camera → capture pipeline |
| `gh://docs/geometry-orientation` | Cylinders, cones, anything Z-axis-driven |
| `gh://docs/best-practices` | Solver discipline, naming, debugging |
| `gh://patterns/*` | Concrete examples: `linear-array`, `grid-array` |
| `gh://component/{name}` | Per-component I/O documentation |

These guides are version-locked to the installed Cordyceps — always preferred over anything in this skill.

## Tool Surface (7 tools)

Each tool dispatches via `action='…'`. Always call `action='help'` once per unfamiliar tool — it returns the full action list with parameters and examples.

| Tool | Domain | Action highlights |
|---|---|---|
| `gh_canvas` | Components + values + groups + baking | `add` `delete` `move` `rename` `find` `search` `list` `info` `bounds` `validate` `bake` `get` `set` `config` `enable` `preview` `zoomable` `group_*` |
| `gh_wire` | Connections | `connect` `disconnect` `list` `clear` `validate` |
| `gh_document` | Document lifecycle + capture | `info` `save` `clear` `solver` `recompute` `undo` `redo` `snapshot` `revert` `snapshots` `capture_canvas` `capture_viewport` `capture_region` `capture_views` |
| `gh_script` | C#/Python script components | `get` `set` `configure` `info` |
| `gh_inspect` | Debugging | `status` `outputs` `trace` `disconnected` `geometry` `log` `reports` `categories` `docs` |
| `rhino_scene` | Baked objects + layers | `objects` `select` `deselect` `set_layer` `set_name` `set_color` `bbox` `layer_*` `hide` `show` `delete` `script` |
| `rhino_render` | Display, camera, materials, environments, render | `display` `camera` (presets: `top`/`front`/`iso_nw`/…) `zoom` `modes` `render` `settings` `ground` `sun` `skylight` `view_save` `view_load` `view_list` `light_add` `light_list` `light_set` `light_delete` `material_*` `env_*` |

## When ToolSearch Can't Surface the Tools

Even with `claude mcp add`, the ToolSearch index can be captured at session start and not refresh when Cordyceps
comes online later. Use the module that ships with this skill rather than pasting a helper into every call:

```powershell
Import-Module "$env:USERPROFILE\.claude\skills\using-cordyceps\cordyceps.psm1"

CCall gh_canvas @{ action='help' }              # alias of Invoke-Cordyceps; returns a PARSED object
if (-not (Test-Cordyceps)) { throw 'server down' }
Read-CordycepsDoc gh://docs/rendering           # embedded guides over HTTP
Assert-CordycepsScript 'import Grasshopper; Grasshopper.CentralSettings.PreviewMeshEdges = False'
```

`Set-CordycepsPort 26930` if the component is not on the default port. `Invoke-Cordyceps` returns the parsed
result, so test `.success` directly instead of re-parsing text.

**Always drive Rhino Python through `Assert-CordycepsScript`, never raw.** It appends a witness write and confirms
the file landed, because `rhino_scene script` reports `success:true` whatever the script did (see Pitfalls).

## Token Discipline

Cordyceps work burns context through **tool output volume**, not through instructions — a single verbose echo can
cost as much as this whole skill file, and it costs that *per run*. Three rules:

1. **Driver scripts print summaries, not payloads.** Wiring 17 connections returns a JSON blob naming every
   endpoint; the only information in it is `17/17 ok`. Print the count, and dump raw JSON **only for failures**:
   ```powershell
   Write-Host "wires: $($w.succeeded)/$($w.total) ok"
   if ($w.failed) { $w.results | Where-Object { -not $_.success } | ConvertTo-Json -Depth 5 }
   ```
2. **Size captures to their purpose.** Verifying a layout or a colour needs ~600px; render full size only for the
   deliverable. A 1200x1200 PNG read back to answer "did the plates come out red?" is a thumbnail's worth of
   information at ten times the price. Never re-read an image already in context.
3. **Isolate bulk canvas construction in a subagent** when it is mechanical. The verbose tool output dies in the
   subagent's context and only the summary returns. This is the structural fix for volume — more effective than
   trimming instructions, and it does not trade away judgment the way a cheaper model does.

## Pitfalls Cordyceps Doesn't Document

### C# Script source: body-only *or* full file — but never `using` after a type

Two source forms are accepted by the GH 8 C# Script (`b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`), both via
`gh_script set` and `gh_script configure` (verified 2026-08-21, Cordyceps 1.4.x, Rhino 8):

1. **Body only** — using directives, then bare statements; declared inputs/outputs are variables.
2. **Full file** — `// #! csharp`, usings, `public class Script_Instance : GH_ScriptInstance { private void
   RunScript(<typed inputs>, ref object <outputs>) {...} }` **plus any helper classes / namespaces after it**.
   Cordyceps re-derives the component's inputs from the `RunScript` signature on every `set` (dropping a
   parameter from the signature silently removes the input and its wire).

The silent-`<null>` failure mode is real but its cause is a **compile error the component swallows**:
any `using` directive that appears *after* a type declaration (CS1529) — e.g. when you concatenate a second
file that starts with its own usings — compiles to nothing: `out` = `""`, every output a single null, runtime
level "Blank", no message. Strip the usings of appended files (or put them all at the top). A wrong body form
or a missing symbol, by contrast, *does* show its errors in `out`.

Bisect recipe when outputs are null and `out` is empty: `gh_script set` a probe that only does
`report = "probe"` with the same signature → works? then append your helper code in chunks until it breaks.

### Other empirical gotchas

- **`gh_canvas bake` needs a component, not a Param container.** `Params/Mesh`, `Params/Curve` etc. return
  "Component has no bakeable outputs"; route through a pass-through component (`Mesh Join`, `Flip Curve`) and bake that.
- **Viewport captures can be wireframe-only.** In a non-GPU / remote session both `gh_document capture_viewport`
  and Rhino's `-ViewCaptureToFile` returned wire-only grey images whatever the display mode (Shaded, Rendered,
  Arctic…) and GH previews were not drawn at all. Bake closed outlines to coloured layers for a legible capture;
  keep meshes for sessions with a real GPU.
- **PowerShell callers: `ConvertTo-Json -AsArray`.** A one-element array serialises as a bare object without it,
  and `gh_script configure` then silently creates no param / `gh_wire connect` connects nothing.
- **Ambiguous component names** silently fail `gh_canvas add` (call succeeds, no component lands). Use `Category/Name` (e.g., `Curve/Circle`) or the GUID from `gh_canvas search`. The non-deprecated Boolean Toggle is `2e78987b-9dfb-42a2-8b76-3923ac8bd91a`; new C# Script is `b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`.
- **`gh_wire connect` takes `sourceId`/`targetId`/`targetParam`** — not `fromId`/`toId` (those fail with "Provide sourceId+targetId"). A failed wire is easy to miss: the component still solves on its defaults, so always check the wire call's own response, not just downstream outputs.
- **`Stop-Process` on Rhino skips Grasshopper's settings save.** Anything set via `Grasshopper.CentralSettings` mid-session (`CanvasObjectIcons`, `PreviewMeshEdges`, …) silently reverts. Re-apply such settings after every force-kill relaunch, or close Rhino gracefully when settings must stick.
- **`gh_script configure` reports output types as "Generic Data"** in its response, even though it correctly applies the type hint to the live component (since v1.4.4). Trust the declared type, not the response label.
- **`gh_script configure` resets all wires.** Use `gh_script set` for code-only updates — it preserves wires for parameters whose names didn't change, and returns `lostConnections` for any that did, which is directly consumable by `gh_wire connect`.
- **`gh_canvas add` response shape** is `result.id`, NOT `result.component.id`.
- **`gh_inspect outputs` `preview` is sometimes empty** for non-primitive types even when data is flowing. See "Panel-as-probe" below.
- **`object` is rejected as a C# Script input type.** Use a concrete type from the upstream Type System guide.
- **Python 3 Script output type hints are item-access only, and a stale hint survives reconfigure.** Returning a list from a `Brep`-hinted output fails with `type conversion failed from PyObject to Brep`; `access: "list"` in `gh_script configure` is not honored. Worse, once a typed hint is set it sticks to the param — reconfiguring to hint-free does not clear it (even outputting `[]` keeps failing). Only deleting and re-adding the component clears it. Reliable shape: one item per typed output.
- **Custom Preview rejects untyped script outputs.** A hint-free (Generic Data) output wraps values in `GH_ObjectWrapper`, and Custom Preview fails with `Data conversion failed from Goo to Geometry` even when the wrapped value is a `Rhino.Geometry.Brep`. Give the script output a concrete geometry type hint (see previous bullet: one item per output) — then previews collect it fine; multiple wires into one `G` input merge as usual.
- **Colour Swatch cannot be set** (`gh_canvas set` → "Cannot set value on GH_ColourSwatch", stays white). Drive a Custom Preview material from a Panel holding `R,G,B` wired into a `Params/Colour` parameter instead.
- **Shaded viewport captures show GH's default dull-red preview** of every surface/mesh output, which z-fights with geometry lying on it. Before `capture_viewport`, disable previews per component (`gh_canvas preview enabled=false`, keep only your Custom Previews) and, for clean fills, `rhino_scene script cmd='-RunPythonScript (import Grasshopper; Grasshopper.CentralSettings.PreviewMeshEdges = False)'`.
- **Some components are not found by `Category/Name`** (`Surface/Primitive/Sphere` → "Unknown component type"); take the GUID from `gh_canvas search` (Sphere: `dabc854d-f50e-408a-b001-d043c7de151d`).
- **`$pid` is a read-only automatic variable in PowerShell** — don't use it as a loop variable in driver scripts.
- **`rhino_scene script` returns `success:true` no matter what the script did.** It only queues the command string; it
  never sees the outcome. A *failing* `-_RunPythonScript` therefore parks a **modal error dialog** in Rhino — blocking the
  UI until a human dismisses it — while your tool call looks clean. (Cost: a `RhinoView.Visible` typo, an invisible modal,
  and a user who had to close it by hand.) Never read `success:true` as evidence the script ran: have the script write a
  witness file and test for it. Both forms work when the script is correct — inline `( … )` and `"<file.py>"`, and the call is **synchronous** (measured: a script sleeping 4s blocked the HTTP call for 4.2s), so on success the effect has already landed when the call returns — no polling needed. `Assert-CordycepsScript` in `cordyceps.psm1` wraps all of this.
- **`gh_document capture_viewport` can only capture the viewport that is currently visible.** Any other viewport fails with
  "Failed to capture viewport" whatever it is named — in a maximised layout that is every viewport but one. Drive the active
  viewport and capture with **no `view` argument**. Related: `rhino_render camera` **renames the viewport to match the
  preset** (`preset='top'` on `Perspective` leaves a second viewport called "Top"; `preset='iso_sw'` renames it back), so
  capture-by-name is ambiguous as well as unreliable.
- **"Grasshopper display error — System.Drawing.Common: Parameter is not valid" on opening the GH window** of a Rhino that was launched hours earlier by the launcher (its canvas captures returned "black image" all along) is a stale-window artefact, not a definition problem: close that Rhino, relaunch, rebuild the canvas.

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

## Common Mistakes

- Calling `Rhino.exe bootstrap.gh` directly → recovery-prompt risk.
- Appending helper code whose `using` lines land after a type declaration → silent `<null>` output (see above).
- Skipping `gh://docs/*` and guessing instead → reinventing what the embedded docs already cover.
- Leaving `Upload`/`Login`/trigger toggles `true` between unrelated edits → re-fires on every recompute.
- Reading component `outputs` to confirm a destructive side effect → check the side-effect target instead.
- Pressing F5 inside a cluster editor → nukes cluster inputs.
- Trying to "click" a custom GDI+ button on a component via `gh_canvas` → unreachable; use `rhino_scene` + `-RunPythonScript` to call the component's public method instead.
