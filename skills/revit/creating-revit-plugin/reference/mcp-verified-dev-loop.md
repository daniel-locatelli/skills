# MCP-Verified Revit Closed-Loop Dev Workflow

A reusable, documented closed feedback loop for building a Revit add-in with Claude Code:
**build the plugin → run it against a live, open Revit 2027 via `revit-mcp` → read the result
back from the live model → assert against acceptance criteria → iterate on the code** — without
restarting Revit between iterations. On every iteration Claude has direct, ground-truth evidence of
how the implementation actually behaves in Revit.

This doc is the workflow only. The first plugin to run through it (a Basic Wall system-family **type
creator**) is designed separately in its own brainstorm → spec → plan cycle. See the design spec:
[`docs/superpowers/specs/2026-06-01-mcp-verified-revit-dev-loop-design.md`](../docs/superpowers/specs/2026-06-01-mcp-verified-revit-dev-loop-design.md).

**Load-bearing principle:** verification asserts against the **live model read back independently**,
never against whatever the plugin reports it did.

> ## ⚠️ First-run preflight (do this before attempting the loop)
>
> The verify loop needs the `revit-mcp` tools live **and executable** in this session. Confirm, in order:
> 1. **Revit is open with a document**, and the `revit-mcp` in-Revit half is installed and its service is running (§2).
> 2. **A `.mcp.json` exists at the project root** with the real `revit-mcp` server path (copy `template/.mcp.json`, §2).
> 3. **The `revit-mcp` tools are actually listed** in this session (`/mcp`). If they're absent, the loop cannot run.
> 4. **A tool call actually executes** — listed ≠ executable. Make one real call (e.g. `get_current_view_info`) and
>    confirm it returns model data, not an error. The `revit-mcp` server is **three separate deployables** (Node
>    server + `revit-mcp-plugin` host + `revit-mcp-commandset`); `connect to revit client failed` and
>    `Method 'X' not found` are **distinct** failures with distinct fixes. See the triage table + the
>    `commandRegistry.json` trap in [`ai-assisted-and-mcp.md`](ai-assisted-and-mcp.md) → "Deploying & triaging the
>    third-party `revit-mcp` family" before debugging.
>
> **Startup catch:** Claude Code connects MCP servers **only at session start**. If you just created or
> edited `.mcp.json`, the tools will **not** appear until you **restart the session** — a running session
> cannot bootstrap a new MCP connection. So: finish §2 setup *first*, then start the session that runs the loop.
>
> If the tools aren't available and you can't restart yet, you can still **brainstorm → spec → plan** the
> plugin (and even build it); only the **execute + verify** stage needs the live connection. Fall back to the
> Approach-2 path (§9) if `revit-mcp` is unavailable but Revit is open.

---

## 1. Overview & when to use this loop

Use this loop when a plugin's "did it work?" is a **readable model state** — e.g. a created
`WallType` whose `CompoundStructure` (layers, materials, widths, function) you can inspect. That data
is awkward to eyeball and ideal for automated read-back, so a closed verify loop pays for itself.

Three cooperating processes; **Revit never restarts during the loop**:

- **Claude Code** — editor + `dotnet build` + MCP client + loop driver.
- **Revit 2027** — open, with the model loaded, hosting the `revit-mcp` server (its handlers marshal
  into Revit's valid API context via `ExternalEvent`; the loop relies on the server for this).
- **Plugin DLL** — built to `bin\Debug\net10.0-windows\`, loaded **fresh each iteration**.

Position in the superpowers flow:

```
brainstorm → spec → (approve) → plan → (approve) → execute = build plugin
   → ┌─ VERIFY LOOP (bounded autonomous, cap 5) ───────────────────────────┐
     │ trigger via revit-mcp execute-C# → read live model back → assert     │
     │ vs acceptance criteria → if fail: diagnose → edit → dotnet build      │
     │ → re-trigger (fresh ALC, no restart) → repeat                         │
     │ stop on: all-pass | ambiguity/product decision | cap reached         │
     └─────────────────────────────────────────────────────────────────────┘
   → report (pass/fail table + diffs + audit log path)
```

**When to use this (Approach 1) vs. the manual RevitAddInManager loop:** use this MCP loop for
plugins whose correctness is a readable model state and that satisfy the **disposal contract**
(section 3). For plugins whose correctness isn't a readable model state (pure UI/ribbon behaviour),
or that can't meet the disposal contract (e.g. one that must register an `IUpdater`), use the manual
**RevitAddInManager** loop — see the Approach-2 fallback (section 9) and
[`project-setup-and-build.md`](project-setup-and-build.md) → "Terminal-only build–deploy–test loop".

---

## 2. Prerequisites & one-time setup

1. **Install the `revit-mcp` Revit-side half** into `%AppData%\Autodesk\Revit\Addins\<year>\`
   (per-user; the Addins-folder location is unchanged in Revit 2027). This is **two pieces, not one** —
   the `revit-mcp-plugin` host **and** the `revit-mcp-commandset` it loads from `…\Commands\` — and the
   command set must be **registered in `commandRegistry.json`** or every call returns `Method not found`.
   Start Revit, **open a document**, switch the service On, and confirm a real tool call **executes**
   (not just that tools are listed). See [`ai-assisted-and-mcp.md`](ai-assisted-and-mcp.md) → "Deploying &
   triaging the third-party `revit-mcp` family" for the three-piece layout, the error-string triage, and
   the build configs. **Version reality:** the writable community server runs on **Revit 2026 / .NET 8**
   today (no 2027/.NET 10 community build; 2027's built-in MCP is read-only) — so in practice this loop's
   live half runs in Revit 2026 even though the doc's examples show 2027/`net10.0-windows`.
2. **Register the MCP server with Claude Code.** Copy [`template/.mcp.json`](../template/.mcp.json) to
   your project root as `.mcp.json` and set the server entry's `args` path to your local `revit-mcp`
   MCP entry script. The path is intentionally a placeholder in the template
   (`REPLACE_WITH_PATH_TO/revit-mcp/build/index.js`) because the entry differs per install — find the
   built `index.js` (or equivalent) under your `revit-mcp` checkout's `build/`/`dist/` folder.
   Claude Code reads project `.mcp.json` on start.
3. **Verify the tools are listed.** In Claude Code, run `/mcp` (or inspect the tool listing) and
   confirm the `revit-mcp` tools appear — including an `execute`/`execute_csharp`-style tool that runs
   arbitrary C# in Revit's API context. **The exact tool name depends on the `revit-mcp` version —
   confirm it before relying on it.**

`template/.mcp.json` (placeholder path — set it per install):

```json
{
  "mcpServers": {
    "revit-mcp": {
      "command": "node",
      "args": ["REPLACE_WITH_PATH_TO/revit-mcp/build/index.js"],
      "env": {}
    }
  }
}
```

> The Revit 2027 **built-in** MCP server is a **read-only Tech Preview** (elements, parameters,
> geometry, views; no modifications; won't trigger a custom plugin; unclear it surfaces
> `CompoundStructure` layer detail) and is insufficient alone for wall-type verification. This
> workflow depends on third-party `revit-mcp`'s **arbitrary C# execution** inside Revit's API context.

---

## 3. The loop-verifiable-plugin convention

To be MCP-loop-verifiable a plugin must expose a **UI-free core entry point** separate from its thin
`IExternalCommand`/ribbon shell (the core/adapter split from
[`architecture.md`](architecture.md), made mandatory). The loop invokes the core directly.

```csharp
// Loop-callable boundary — ONLY shared types cross the ALC boundary (R1):
public static ElementId Create(Document doc, string specJson);

// Real typed implementation the overload delegates to:
public static ElementId Create(Document doc, WallTypeSpec spec);
```

- **Input:** `specJson` is the text of the user-supplied JSON spec file (the "external information the
  user points to"). The string overload deserializes it (`System.Text.Json`) into `WallTypeSpec` and
  calls the typed overload. **Only `Document`/`string`/`ElementId` cross the cross-ALC boundary** — the
  child ALC's `WallTypeSpec` would otherwise be a *different* type than the loop's, breaking type
  identity, so the typed `Create(Document, WallTypeSpec)` stays internal to the plugin.
- **Output:** the created/updated `WallType`'s `ElementId` (a shared type).
- **Transaction ownership:** `Create` opens and commits its **own** `Transaction`(s) for the model
  edits. It must **not** assume an outer transaction is open, and the loop must **not** open one around
  it (nested `Transaction`s are illegal). The loop wraps the call in a `TransactionGroup` **only**
  (section 4).
- **Idempotency:** look up the existing type by name; **duplicate-and-edit only when absent** (update
  otherwise). Less critical inside the loop since the loop rolls back every iteration (section 4), but
  required for real ribbon/command runs.
- **Disposal contract (the gate for Approach-1 eligibility):** `Create` and everything it touches must
  leave **zero surviving references** in Revit's memory after returning — no static event
  subscriptions, no retained WPF/UI objects, no callbacks/`IUpdater`s registered with Revit, no objects
  parked in static fields. A leaked reference both prevents the collectible ALC from unloading (memory
  growth) and can keep *old* code alive or pollute later reads. A plugin that cannot meet this contract
  uses the **Approach-2 fallback (section 9)** instead.

---

## 4. The `execute-C#` snippet template

This is the load-bearing artifact: one `execute-C#` call performs a full build–deploy–verify
iteration. It shadow-copies the freshly-built DLL to a unique temp path, loads it into a **collectible
`AssemblyLoadContext`**, calls the shared-types-only `Create(Document, string)` core inside a
rolled-back `TransactionGroup`, captures failures via the app `FailuresProcessing` event, and returns
a DTO built from an **independent** read of the live model.

### Step 1 — the `PluginLoadContext` helper

```csharp
using System.Reflection;
using System.Runtime.Loader;

// Loads the plugin + its PRIVATE deps fresh from the shadow folder, but returns null
// for framework + RevitAPI/RevitAPIUI so they bind to Revit's already-loaded copies
// in the Default context (shared type identity for Document/WallType/ElementId). [R2]
sealed class PluginLoadContext : AssemblyLoadContext
{
    private readonly AssemblyDependencyResolver _resolver;
    public PluginLoadContext(string pluginPath) : base(isCollectible: true)
        => _resolver = new AssemblyDependencyResolver(pluginPath);

    protected override Assembly Load(AssemblyName name)
    {
        string path = _resolver.ResolveAssemblyToPath(name);
        return path != null ? LoadFromAssemblyPath(path) : null; // null ⇒ delegate to Default
    }
}
```

### Step 2 — the main snippet

```csharp
// === revit-mcp execute-C# : one build–deploy–verify iteration ===
// Assumes the revit-mcp host exposes the active Document as `doc` and UIApplication as `uiapp`.
// Adapt the first lines if your revit-mcp variant provides the context differently.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Autodesk.Revit.DB;

// --- inputs the loop substitutes each iteration ---
string builtDll  = @"{{BUILT_DLL_PATH}}";    // bin\Debug\net10.0-windows\MyPlugin.dll
string specJson  = File.ReadAllText(@"{{SPEC_JSON_PATH}}");
string coreType  = "{{CORE_TYPE}}";          // e.g. MyPlugin.Core.WallTypeCreator
string auditPath = @"{{AUDIT_LOG_PATH}}";

var result   = new Dictionary<string, object>();
var warnings = new List<string>();
var errors   = new List<string>();

// Null-init everything the finally must clean up; the ENTIRE body is guarded so a throw
// in setup (dir create, copy, ALC ctor, subscribe) still yields an ok:false DTO and cleans up.
string shadow = null;
PluginLoadContext alc = null;
TransactionGroup tg = null;
EventHandler<Autodesk.Revit.DB.Events.FailuresProcessingEventArgs> onFailures = null;

try
{
    // 1+2: shadow-copy fresh build to a unique path, load into a collectible ALC
    shadow = Path.Combine(Path.GetTempPath(), "revitloop", Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(shadow);
    string shadowDll = Path.Combine(shadow, Path.GetFileName(builtDll));
    string srcDir = Path.GetDirectoryName(builtDll)
        ?? throw new ArgumentException($"no directory in {builtDll}");
    foreach (var f in Directory.GetFiles(srcDir))
        File.Copy(f, Path.Combine(shadow, Path.GetFileName(f)), true); // DLL + private deps + .deps.json

    alc = new PluginLoadContext(shadowDll);

    // R3: capture ALL failures during the plugin's own transactions via the app-level event.
    onFailures = (s, e) =>
    {
        var fa = e.GetFailuresAccessor();
        foreach (var fm in fa.GetFailureMessages())
        {
            string desc = fm.GetDescriptionText();
            if (fm.GetSeverity() == FailureSeverity.Warning) { warnings.Add(desc); }
            else { errors.Add($"[{fm.GetSeverity()}] {desc}"); }
        }
        fa.DeleteAllWarnings();                                  // resolve warnings only
        e.SetProcessingResult(FailureProcessingResult.Continue);
    };
    uiapp.Application.FailuresProcessing += onFailures;

    // Root assembly is loaded by explicit path; PluginLoadContext.Load only governs
    // resolution of this assembly's TRANSITIVE dependencies.
    Assembly asm  = alc.LoadFromAssemblyPath(shadowDll);
    Type creator  = asm.GetType(coreType, throwOnError: true);
    MethodInfo create = creator.GetMethod("Create", BindingFlags.Public | BindingFlags.Static,
        new[] { typeof(Document), typeof(string) })
        ?? throw new MissingMethodException(coreType, "static ElementId Create(Document, string)");

    tg = new TransactionGroup(doc, "loop-verify");
    tg.Start();

    var id = (ElementId)create.Invoke(null, new object[] { doc, specJson });

    // R4: INDEPENDENT read-back of the live model — do not trust the plugin's self-report.
    if (doc.GetElement(id) is WallType wt)
    {
        var cs = wt.GetCompoundStructure();
        result["typeName"]   = wt.Name;
        result["elementId"]  = id.Value;
        result["function"]   = wt.Function.ToString();
        result["totalWidth"] = cs?.GetWidth() ?? 0.0;
        result["layers"] = cs?.GetLayers().Select((L, i) => (object)new Dictionary<string, object>
        {
            ["index"]        = i,
            ["function"]     = L.Function.ToString(),
            ["materialId"]   = L.MaterialId?.Value ?? -1,            // -1 sentinel = no material set
            ["materialName"] = (doc.GetElement(L.MaterialId) as Material)?.Name, // null when layer has no material
            ["width"]        = L.Width
        }).ToList();
    }
    else { errors.Add($"No WallType resolved for id {id?.Value}"); }
}
catch (Exception ex) { errors.Add($"{ex.GetType().Name}: {ex.Message}"); }
finally
{
    if (onFailures != null) uiapp.Application.FailuresProcessing -= onFailures; // unsubscribe only if subscribed
    try { tg?.RollBack(); } catch { /* group not started */ }  // pristine model each iteration
    alc?.Unload();                                             // best-effort (R: leak, not block)
    for (int i = 0; i < 2; i++) { GC.Collect(); GC.WaitForPendingFinalizers(); } // 2-pass best-effort unload
    if (shadow != null) { try { Directory.Delete(shadow, true); } catch { } }
}

result["ok"]       = errors.Count == 0;
result["warnings"] = warnings;
result["errors"]   = errors;
string json = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
File.AppendAllText(auditPath, json + Environment.NewLine);    // audit trail (D6)
return json;                                                  // returned to Claude
```

### Step 3 — placeholders the loop substitutes

The loop substitutes these `{{PLACEHOLDERS}}` each iteration before sending the snippet:

| Placeholder | Meaning |
|---|---|
| `{{BUILT_DLL_PATH}}` | absolute path to the freshly-built plugin DLL (`bin\Debug\net10.0-windows\MyPlugin.dll`) |
| `{{SPEC_JSON_PATH}}` | absolute path to the user-supplied `WallTypeSpec` JSON file |
| `{{CORE_TYPE}}` | fully-qualified core type name, e.g. `MyPlugin.Core.WallTypeCreator` |
| `{{AUDIT_LOG_PATH}}` | absolute path to the on-disk audit log (section 8) |

> **Caveat:** the `uiapp`/`doc` context variables this snippet assumes depend on the `revit-mcp` host
> and **must be confirmed** for your version. If the host provides the context differently (e.g. only
> `uiapp`, or a different name), adapt the first lines accordingly — the rest of the snippet is
> host-agnostic.

---

## 5. Result DTO schema + verification-contract template

The snippet returns a stable-schema **result DTO**. The workflow provides the mechanism + template;
each plugin's own spec fills in the values.

```jsonc
{
  "ok": true,
  "elementId": 123456,
  "typeName": "EXT-200-Concrete",
  "function": "Exterior",          // WallType.Function
  "wrapping": { "atInserts": "...", "atEnds": "..." }, // EXTENSION POINT (not emitted by the core snippet)
  "totalWidth": 0.6562,            // internal units (decimal feet)
  "layers": [                       // ordered exterior→interior
    { "index": 0, "function": "Finish1", "materialId": 987, "materialName": "Concrete", "width": 0.0656 }
  ],
  "params": { "Type Mark": "W1" },  // EXTENSION POINT (not emitted by the core snippet)
  "warnings": [],                    // suppressed Revit warnings (severity Warning) — informational
  "errors": []                       // exceptions + captured Revit Errors; non-empty ⇒ ok:false
}
```

> **Core subset vs. extension points.** The block above is the **full contract schema**, but the
> section-4 reference snippet emits only the **core subset**: `ok`, `elementId`, `typeName`,
> `function`, `totalWidth`, `layers`, `warnings`, `errors`. The `wrapping` and `params` fields are
> **per-plugin verification-contract extension points** — a specific plugin's spec/snippet populates
> them (e.g. `wrapping` from the `WallType` wrapping params; `params` via `LookupParameter` for the
> named type parameters its contract requires). A reader should expect those two keys to be **absent**
> from the core snippet's output until a plugin adds them. (The section-8 audit example shows a plugin
> that has populated them.)

`ok` is `false` when `errors[]` is non-empty: a caught exception, a captured Revit **Error**-severity
failure, or a validation failure (section 6) all populate `errors[]`. Suppressed **Warning**-severity
failures go to `warnings[]` and are informational — they do not by themselves fail the iteration.

**Verification-contract template.** Each plugin's spec fills in this table; Claude builds the pass/fail
table by comparing the live-read DTO field against each row:

| criterion | expected (from spec) | tolerance | source |
|---|---|---|---|
| `typeName` | `EXT-200-Concrete` | exact | `WallType.Name` |
| `function` | `Exterior` | exact | `WallType.Function` |
| `layers[0].width` | `0.0656` ft (20 mm) | `1e-6` ft (round-trip) | `CompoundStructureLayer.Width` |
| `layers[0].materialName` | `Concrete` | exact | `Material.Name` via `MaterialId` |
| `totalWidth` | `0.6562` ft | per-criterion (derived/clamped) | `CompoundStructure.GetWidth()` |
| `params["Type Mark"]` | `W1` | exact | named type parameter |

---

## 6. Units & tolerance

Lengths are reported in **internal units (decimal feet)**; the spec's millimetre inputs are converted
at the boundary. Comparison tolerance is **per-criterion and configurable, not a single global value,
and is grounded in queryable Revit constants rather than an arbitrary number.**

- **Round-trip lengths use a tight epsilon.** Layer widths and other API-set lengths round-trip at
  double precision, so set-then-get equality uses a **tight** epsilon (≈`1e-6` ft) — deliberately
  tight so a real discrepancy (e.g. 200 mm vs 198.5 mm) **fails**.
  **Do NOT use a coarse tolerance like 1/16″ (≈`0.0052` ft) for round-trip checks** — it would mask
  genuine errors.
- **Validity floors are queried at runtime, not hardcoded.** Use `CompoundStructure.MinimumLayerThickness`
  and `Application.ShortCurveTolerance` (≈`0.00256` ft). A spec requesting a layer **thinner than the
  minimum** is a **validation error (`ok:false`)**, surfaced **before** creation — *not* treated as a
  tolerance miss.
- **Derived/clamped quantities may use a looser, explicitly-stated tolerance.** Quantities Revit may
  derive or clamp (e.g. a summed `totalWidth`) may use a slightly looser, **documented** per-criterion
  tolerance — stated explicitly in the plugin's verification contract (section 5), never implicitly.

---

## 7. Bounded-iteration protocol

**Two independent counters** — a build error must not burn a live-test attempt:

- **Verify cap:** default **5** (overridable per run). Counts **only live Revit test iterations** —
  attempts that built successfully and ran the `execute-C#` call, then failed an assertion.
- **Build-fix budget:** **3 consecutive** `dotnet build` failures. A compile error → fix-and-rebuild
  **without** decrementing the verify cap; exceeding the budget stops the loop (likely a design issue,
  not a typo). A **successful build resets** this budget.

Other guards:

- **Stop-and-ask triggers:** spec ambiguous/contradictory; a criterion needs a product decision; a
  build failure implies a design change (vs. a typo); `revit-mcp`/Revit unreachable.
- **Memory ceiling:** if best-effort ALC unloads stall (a surviving reference) and the Revit process
  RSS grows past a configured ceiling across iterations, **stop and report** (recommend restarting
  Revit) rather than risk an OOM in the host. A stalled unload is itself only a logged memory-leak
  **warning**, not a loop failure — the next iteration loads a fresh ALC from a new unique path
  regardless. Correctness depends on the disposal contract (section 3), not on unload succeeding.
- **Each attempt logs:** pass/fail table + code diff + one-line rationale (to the conversation and the
  audit file).
- **On any cap/budget reached:** stop; report the closest attempt, the remaining failures, and a
  hypothesis. **Never silently loop past a limit.**

---

## 8. Audit-log format

Each iteration appends **one JSON object per line** to `{{AUDIT_LOG_PATH}}`: the result DTO (section 5)
plus the loop's bookkeeping — `attempt`, a `pass`/`fail` table, and a `codeDiffSummary`. This gives a
complete, replayable trail of every `execute-C#` call and its result (D6).

One-object example (one line in the log; pretty-printed here for readability):

```jsonc
{
  "attempt": 2,
  "ok": false,
  "elementId": 123456,
  "typeName": "EXT-200-Concrete",
  "function": "Exterior",
  "wrapping": { "atInserts": "Both", "atEnds": "Exterior" },
  "totalWidth": 0.6398,
  "layers": [
    { "index": 0, "function": "Finish1", "materialId": 987, "materialName": "Concrete", "width": 0.0656 },
    { "index": 1, "function": "Structure", "materialId": 654, "materialName": "Concrete, Cast-in-Place", "width": 0.5742 }
  ],
  "params": { "Type Mark": "W1" },
  "warnings": [],
  "errors": [],
  "pass": [
    { "criterion": "typeName", "expected": "EXT-200-Concrete", "actual": "EXT-200-Concrete", "result": "pass" },
    { "criterion": "totalWidth", "expected": 0.6562, "actual": 0.6398, "tolerance": 1e-6, "result": "fail" }
  ],
  "codeDiffSummary": "Set structure layer width from 175mm to 200mm; totalWidth still short — check finish layer."
}
```

---

## 9. Approach-2 fallback (RevitAddInManager + revit-mcp read)

If collectible-ALC hot-reload misbehaves **or** a plugin can't meet the disposal contract (section 3),
drop to **Approach 2** without redesigning the verify half:

1. Reload + run the real `IExternalCommand` via **RevitAddInManager** (an add-in that reloads a
   freshly-built command DLL into the running Revit and lets you invoke it — see
   [`project-setup-and-build.md`](project-setup-and-build.md) → "Terminal-only build–deploy–test loop").
2. **Read back with the same `revit-mcp` read step** used in Approach 1 (sections 4–5 unchanged): query
   the live model for the created element and build the same result DTO.

Verification — the assert-against-the-live-model half (section 5's DTO + the section 6 tolerances) — is
**identical**. Only the *trigger* mechanism changes (RevitAddInManager instead of the collectible ALC),
so the verification contract and the bounded-iteration protocol carry over unchanged.

---

## 10. Worked example

The **Basic Wall system-family type creator** is the first passenger of this loop and is designed in a
later, separate cycle. Its own spec defines the concrete `WallTypeSpec` schema (layer/material
resolution, duplicate-by-name idempotency details, error handling) and its acceptance criteria —
i.e. the values that fill the verification-contract template (section 5). A link to that worked example
will be added here once its spec exists.

---

## 11. Sources

- Design spec: [`docs/superpowers/specs/2026-06-01-mcp-verified-revit-dev-loop-design.md`](../docs/superpowers/specs/2026-06-01-mcp-verified-revit-dev-loop-design.md)
- `revit-mcp` (third-party MCP server with arbitrary C# execution): `mcp-servers-for-revit/revit-mcp`
- Revit 2027 built-in MCP server (read-only Tech Preview): Autodesk Revit 2027 MCP documentation
- .NET collectible assembly loading: `AssemblyLoadContext` (`isCollectible: true`) and
  `AssemblyDependencyResolver` — .NET runtime documentation
- Related skill references: [`architecture.md`](architecture.md) (core/adapter split),
  [`project-setup-and-build.md`](project-setup-and-build.md) (terminal build–deploy–test loop),
  [`ai-assisted-and-mcp.md`](ai-assisted-and-mcp.md) (MCP landscape)
