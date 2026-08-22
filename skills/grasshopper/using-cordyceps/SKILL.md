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

### Canvas API shapes to get right first time

- **Ambiguous component names** silently fail `gh_canvas add` (call succeeds, no component lands). Use `Category/Name` (e.g., `Curve/Circle`) or the GUID from `gh_canvas search`. The non-deprecated Boolean Toggle is `2e78987b-9dfb-42a2-8b76-3923ac8bd91a`; new C# Script is `b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`.
- **`gh_wire connect` takes `sourceId`/`targetId`/`targetParam`** — not `fromId`/`toId` (those fail with "Provide sourceId+targetId"). A failed wire is easy to miss: the component still solves on its defaults, so always check the wire call's own response, not just downstream outputs.
- **`gh_canvas add` response shape** is `result.id`, NOT `result.component.id`.
- **Some components are not found by `Category/Name`** (`Surface/Primitive/Sphere` → "Unknown component type"); take the GUID from `gh_canvas search` (Sphere: `dabc854d-f50e-408a-b001-d043c7de151d`).

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
the file landed, because `rhino_scene script` reports `success:true` whatever the script did (see `references/scripting.md`).

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

Measured on live Rhino sessions; each contradicts the obvious guess. Kept out of this file so a
plain build-and-wire session doesn't pay for them — **read the one that matches your task**:

| Reference | When to read |
|---|---|
| [references/scripting.md](references/scripting.md) | Before `gh_script set`/`configure` (C# or Python 3 source forms, silent `<null>` outputs, type hints) or any `rhino_scene script` / Rhino-Python call |
| [references/rendering.md](references/rendering.md) | Before baking, `gh_document capture_*`, `rhino_render camera`, or anything about preview colour and display modes |
| [references/debugging.md](references/debugging.md) | A value or side effect you expected is missing — probing data flow with a sink Panel, cluster-safe recompute, driving custom GDI+ component UI that `gh_canvas` cannot see |

## Common Mistakes

- Calling `Rhino.exe bootstrap.gh` directly → recovery-prompt risk.
- Appending helper code whose `using` lines land after a type declaration → silent `<null>` output (see `references/scripting.md`).
- Skipping `gh://docs/*` and guessing instead → reinventing what the embedded docs already cover.
- Leaving `Upload`/`Login`/trigger toggles `true` between unrelated edits → re-fires on every recompute.
- Reading component `outputs` to confirm a destructive side effect → check the side-effect target instead.
- Pressing F5 inside a cluster editor → nukes cluster inputs.
- Trying to "click" a custom GDI+ button on a component via `gh_canvas` → unreachable; use `rhino_scene` + `-RunPythonScript` to call the component's public method instead.
