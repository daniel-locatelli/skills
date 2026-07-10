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

Even with `claude mcp add`, the ToolSearch index can be captured at session start and not refresh when Cordyceps comes online later. Direct JSON-RPC fallback:

```powershell
function CCall($name, $args_) {
  $payload = @{
    jsonrpc='2.0'; id=[int](Get-Random -Maximum 99999)
    method='tools/call'; params=@{ name=$name; arguments=$args_ }
  } | ConvertTo-Json -Depth 12 -Compress
  (Invoke-RestMethod -Uri 'http://127.0.0.1:26929/mcp' -Method POST `
    -Headers @{'Content-Type'='application/json'; 'Accept'='application/json,text/event-stream'} `
    -Body $payload -TimeoutSec 30).result.content[0].text
}

CCall 'gh_canvas' @{ action='help' }
```

Resources work the same way — use `method='resources/list'` then `method='resources/read'` with `params=@{uri='gh://docs/getting-started'}` to read embedded guides over HTTP.

## Pitfalls Cordyceps Doesn't Document

### C# Script source is the *body*, not a class

The GH 8 C# Script (`b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`) wraps your source in `public class Script_Instance { public void RunScript(…) { … } }` itself. Pass **only** the body. Wrapping your own class around it compiles silently but produces `<null>` outputs with no compile error and no runtime message — the hardest possible failure mode to diagnose. Declared inputs and outputs are available as variables of those names.

✅ Correct source (using directives, then bare body):
```csharp
using System;
using System.Collections.Generic;
using Rhino.Geometry;

var curves = new List<Curve>();
curves.Add(new LineCurve(new Point3d(0,0,0), new Point3d(10,0,0)));
result = curves;   // 'result' is a declared output
```

❌ Wrong (silent `<null>`):
```csharp
public class Script_Instance {
  public void RunScript(string a, string b, ref object joined) {
    joined = a + " " + b;
  }
}
```

The legacy script (`a9a8ebd2-…`) auto-imported common namespaces; the new one does not.

### Other empirical gotchas

- **Ambiguous component names** silently fail `gh_canvas add` (call succeeds, no component lands). Use `Category/Name` (e.g., `Curve/Circle`) or the GUID from `gh_canvas search`. The non-deprecated Boolean Toggle is `2e78987b-9dfb-42a2-8b76-3923ac8bd91a`; new C# Script is `b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`.
- **`gh_script configure` reports output types as "Generic Data"** in its response, even though it correctly applies the type hint to the live component (since v1.4.4). Trust the declared type, not the response label.
- **`gh_script configure` resets all wires.** Use `gh_script set` for code-only updates — it preserves wires for parameters whose names didn't change, and returns `lostConnections` for any that did, which is directly consumable by `gh_wire connect`.
- **`gh_canvas add` response shape** is `result.id`, NOT `result.component.id`.
- **`gh_inspect outputs` `preview` is sometimes empty** for non-primitive types even when data is flowing. See "Panel-as-probe" below.
- **`object` is rejected as a C# Script input type.** Use a concrete type from the upstream Type System guide.

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
- Wrapping C# Script source in a `Script_Instance` class → silent `<null>` output.
- Skipping `gh://docs/*` and guessing instead → reinventing what the embedded docs already cover.
- Leaving `Upload`/`Login`/trigger toggles `true` between unrelated edits → re-fires on every recompute.
- Reading component `outputs` to confirm a destructive side effect → check the side-effect target instead.
- Pressing F5 inside a cluster editor → nukes cluster inputs.
- Trying to "click" a custom GDI+ button on a component via `gh_canvas` → unreachable; use `rhino_scene` + `-RunPythonScript` to call the component's public method instead.
