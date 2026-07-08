---
name: creating-revit-plugin
description: Use when building, scaffolding, or debugging an Autodesk Revit desktop add-in/plugin in C#/.NET — IExternalCommand, IExternalApplication, .addin manifest, ribbon buttons, transactions, FilteredElementCollector — especially for Revit 2027 (.NET 10) and 2025/2026 (.NET 8). Covers project/build setup, multi-version targeting, the ForgeTypeId/units and 64-bit ElementId migrations, the 2027 .NET 10 + add-in-isolation + Program Files install-path changes, ExternalEvent for modeless UI, deployment, and APS Design Automation. Triggers on "Revit add-in", "Revit plugin", "RevitAPI.dll", ".addin", "IExternalCommand".
---

# Create Revit Plugin

## Overview

Build Autodesk Revit desktop add-ins in C#/.NET. A Revit add-in is a compiled DLL that Revit loads at startup via a `.addin` manifest, exposing commands (`IExternalCommand`) and ribbon UI (`IExternalApplication`).

**Three rules carry most of the weight. Internalize these before writing any code:**

1. **Match the runtime to the Revit version.** Revit **2027 = .NET 10** (`net10.0-windows`); Revit **2025/2026 = .NET 8** (`net8.0-windows`); Revit **2021–2024 = .NET Framework 4.8** (`net48`). A DLL built for the wrong one **will not load**. Always x64. (Autodesk has also back-ported 2025/2026 to .NET 10 to track Microsoft's LTS — see the Revit 2027 note below.)
2. **Every model modification must be inside an open `Transaction`** — and the API is only callable on Revit's main thread inside a **valid API context** (a command, an event, or an `IExternalEventHandler.Execute`). Calling the API from a worker thread or directly from a modeless dialog throws.
3. **Never copy the Revit API DLLs to your output.** Reference `RevitAPI.dll`/`RevitAPIUI.dll` with `<Private>false</Private>` (or `CopyLocal=false`). Revit supplies them; shipping copies causes version-conflict load failures.

## When to Use

- "Create / scaffold a Revit add-in or plugin" → use the **`template/`** scaffold + `reference/project-setup-and-build.md`.
- "Add a ribbon button / command" → `reference/ui-and-interaction.md`.
- "Why won't my add-in load / build for Revit 2025?" → version-critical facts below + `reference/project-setup-and-build.md`.
- "Fast build–deploy–test loop from the terminal / Claude Code (no Visual Studio)" → `reference/project-setup-and-build.md` → **"Terminal-only build–deploy–test loop"** (`dotnet build` auto-deploys; RevitAddInManager hot-reloads commands without restarting Revit).
- "Verify a plugin's output against a live Revit model in a closed loop (build → run via MCP → read back → iterate)" → `reference/mcp-verified-dev-loop.md`.
- "Modify the model / read elements / set parameters" → `reference/revit-api-fundamentals.md` + units section in `reference/ui-and-interaction.md`.
- "Run Revit headless / in the cloud" → that's **APS Design Automation**, a different deployment of the same logic → `reference/resources-and-best-practices.md`.
- "Structure a *large* add-in / DI / MVVM / multi-version / async-from-UI / make logic reusable headless" → `reference/architecture.md`.
- "Make it production-grade: DLL conflicts, testing, logging, error handling, performance, settings, **worksharing**/central models, add-in **longevity/versioned data upgrades** across Revit releases" → `reference/robustness-and-testing.md`.
- "Let an AI agent drive Revit (MCP), or build a Revit MCP server" / "get better Revit code out of an AI agent" → `reference/ai-assisted-and-mcp.md`.

**Not for:** Dynamo scripts, generic APS web APIs (Viewer/Data Management), or AutoCAD/other-product add-ins.

## Version-Critical Facts (where stale training data breaks)

LLM training data predates these changes and will produce code that won't compile or load. Verify against these:

| Area | Old (≤ a given version) | Current (Revit 2025–2027) |
|------|--------------------------|----------------------------|
| Runtime | .NET Framework 4.8 (≤2024) | **.NET 8** (`net8.0-windows`) for 2025/2026; **.NET 10** (`net10.0-windows`) for **2027** |
| `ElementId` value | `id.IntegerValue` (Int32) | **`id.Value`** (Int64), since 2024 |
| Units / specs | `DisplayUnitType`, `UnitType` enums | **`ForgeTypeId`**: `UnitTypeId.*`, `SpecTypeId.*`, `GroupTypeId.*`, since 2022 |
| Unit conversion | `UnitUtils.Convert*(…, DisplayUnitType)` | `UnitUtils.ConvertToInternalUnits(v, UnitTypeId.Millimeters)` |
| Transaction mode | `TransactionMode.Automatic` | **`Manual`** (Automatic is obsolete); `ReadOnly` for query-only commands |
| `[Regeneration]` attr | `RegenerationOption.Automatic` | Removed long ago; attribute is legacy/optional, `Manual` only |

Internal units are **decimal feet** (lengths) and **radians** (angles) — always convert at the UI boundary.

### Revit 2027 (.NET 10) — what changed

Revit 2027 has shipped on **.NET 10** (final, not preview). Building add-ins for it requires the **.NET 10 SDK** and `TargetFramework` = `net10.0-windows`. Autodesk has also back-ported **Revit 2025/2026 to .NET 10** to track Microsoft's LTS (Microsoft ends .NET 8 support Nov 10, 2026), so don't hard-pin tooling assumptions to .NET 8. Most managed add-ins recompile cleanly; native/dependency-heavy ones may need attention. Three 2027-specific changes that break stale guidance:

1. **Machine-wide add-in install path moved (security change).** All-users manifests are no longer scanned under `%ProgramData%\Autodesk\Revit\Addins\<year>\` — they now live under **`%ProgramFiles%\Autodesk\Revit\Addins\<year>\`** (writing there needs admin rights). `Application.AllUsersAddinsLocation` returns the new path. The **per-user** location — `%AppData%\Autodesk\Revit\Addins\<year>\` — is **unchanged**; prefer it for dev/deploy to avoid the admin requirement.
2. **Explicit add-in isolation / dependency declarations.** New `.addin` manifest settings let an add-in declare how its assemblies are shared and what it depends on: `PublicAssemblies`, `Dependencies` (`dependsonclientid`, `dependsoncontext`), and `UseAllContextsForDependencyResolution`; backed by new API types `AddInDependencyBase`, `ClientIdDependency`, `ContextNameDependency`. This supersedes ad-hoc `AssemblyLoadContext` tricks for cross-add-in sharing. See `reference/robustness-and-testing.md`.
3. **Some APIs removed/changed.** Cloud regions: the hardcoded `CloudRegionUS`/`CloudRegionEMEA` are replaced by `ModelPathUtils.GetAllCloudRegions()`. Also removed: AXM import, several legacy rebar methods, and some `EnergyDataSettings` properties. Re-check these against the Revit 2027 SDK "What's New" when porting.

## Minimal Working Add-in

A command (`[Transaction(TransactionMode.Manual)]` is mandatory on every `IExternalCommand`):

```csharp
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace MyAddin
{
    [Transaction(TransactionMode.Manual)]
    public class HelloCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            using (Transaction t = new Transaction(doc, "Hello"))   // name shows in undo stack
            {
                t.Start();
                // ...model edits here...
                t.Commit();
            }
            TaskDialog.Show("Hello", "Hello, Revit!");
            return Result.Succeeded;   // or Failed (set `message`) / Cancelled
        }
    }
}
```

The `.addin` manifest (place in `%AppData%\Autodesk\Revit\Addins\<year>\` for the current user; for an all-users install use `%ProgramData%\…` on Revit ≤2026 but **`%ProgramFiles%\Autodesk\Revit\Addins\<year>\` on Revit 2027+** — see the Revit 2027 note above):

```xml
<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <AddIn Type="Application">                 <!-- "Application" for ribbon; "Command" for a bare command -->
    <Name>My Addin</Name>
    <Assembly>MyAddin.dll</Assembly>          <!-- relative to the .addin, or absolute path -->
    <AddInId>PUT-A-UNIQUE-GUID-HERE</AddInId> <!-- new GUID per add-in -->
    <FullClassName>MyAddin.App</FullClassName>
    <VendorId>YOURTAG</VendorId>
  </AddIn>
</RevitAddIns>
```

The object model from `commandData`: `Application` (`UIApplication`) → `ActiveUIDocument` (`UIDocument`, the UI/selection) → `.Document` (`Document`, the model database — all edits go here).

## Quick Reference

| Task | API |
|------|-----|
| Get the model | `commandData.Application.ActiveUIDocument.Document` |
| Query elements | `new FilteredElementCollector(doc).OfClass(typeof(Wall)).WhereElementIsNotElementType()` |
| By category | `.OfCategory(BuiltInCategory.OST_Walls)` |
| Resolve an id | `doc.GetElement(elementId)` |
| Modify model | wrap in `using (var t = new Transaction(doc, "name")) { t.Start(); …; t.Commit(); }` |
| Read/write param | `el.LookupParameter("X")` / `el.get_Parameter(BuiltInParameter.Y)`; `p.Set(v)` (needs transaction) |
| Build ribbon | `IExternalApplication.OnStartup` → `CreateRibbonTab` / `CreateRibbonPanel` / `PushButtonData` |
| Pick element | `uidoc.Selection.PickObject(ObjectType.Element)` (Esc throws `OperationCanceledException`) |
| Act from modeless UI | `ExternalEvent.Create(handler)` + `handler.Raise()` (never call API directly) |

## Scaffold a New Add-in

The `template/` directory is a complete, buildable Revit 2027 (.NET 10) add-in: SDK-style `.csproj`, `App.cs` ribbon, sample command, `.addin`, `launchSettings.json` (F5-into-Revit), embedded-icon loader, and `.gitignore`. To use it, see `template/README.md` — copy the folder, rename namespace/assembly, generate fresh GUIDs. To target 2025/2026 instead, switch the TFM to `net8.0-windows` and the API package to `2026.0.0` (one-line change, documented in the `.csproj`). For multi-version targeting (one project → many Revit versions), see `reference/project-setup-and-build.md`.

## Reference Files

- **`reference/revit-api-fundamentals.md`** — entry points, manifest details, object model, transactions (Transaction/SubTransaction/Group), FilteredElementCollector, Result.
- **`reference/project-setup-and-build.md`** — `.csproj` (single + multi-version), referencing the API (NuGet vs HintPath), `Private=false`, MSB3277/CA1416 fixes, debugging (attach to `Revit.exe`, Add-In Manager), post-build deploy, installers, SDK & RevitLookup.
- **`reference/ui-and-interaction.md`** — ribbon (buttons/icons/pulldowns), threading & valid API context, `ExternalEvent`/`IExternalEventHandler`, modal vs modeless WPF, events vs `IUpdater` (DMU), selection & `ISelectionFilter`, `IFailuresPreprocessor`, parameters & the ForgeTypeId/units system.
- **`reference/icons.md`** — *creating* ribbon icons: Revit/Autodesk design rules (flat, transparent, distinct), the verified Iconify→PNG generator (`resvg-py`, 32×32 + 16×16, optional simpler 16px glyph), wiring via `ImageUtils.Load`, and matching sizes to the ribbon layout.
- **`reference/resources-and-best-practices.md`** — APS vs desktop API vs Design Automation, official docs/SDK/tutorials, key tooling (Nice3point templates, RevitLookup, pyRevit, RevitAddinManager), production checklist, App Store submission.
- **`reference/architecture.md`** — scaling beyond the basics: project structure tiers, DI with per-window scopes, MVVM, the **async `[ExternalEvent]`** pattern (`await` a Revit action from UI code), and the **core/adapter split** so logic runs desktop *and* headless. The Nice3point RevitToolkit/Templates stack.
- **`reference/robustness-and-testing.md`** — DLL-hell & **AssemblyLoadContext isolation** (.NET 8/.NET 10) plus the **Revit 2027 native add-in-isolation manifest**, testing (`ricaun.RevitTest` + a Revit-agnostic core), Serilog logging & journal files, global error handling, **performance** (filter ordering, transaction batching), ExtensibleStorage schema versioning.
- **`reference/ai-assisted-and-mcp.md`** — driving Revit live via **MCP** (Revit 2027's built-in server; `revit-mcp` servers), how to architect a Revit MCP add-in (tool handlers marshalled through `ExternalEvent`), and getting better Revit code out of an AI agent.
- **`reference/mcp-verified-dev-loop.md`** — the MCP-verified closed-loop dev workflow: revit-mcp setup, the loop-verifiable-plugin convention, the execute-C# snippet (collectible ALC + TransactionGroup + independent read-back), the result-DTO + verification contract, the bounded-iteration protocol, and the RevitAddInManager fallback.

## Common Mistakes

- **DLL won't load** → wrong TFM for the target Revit: use `net48` (≤2024), `net8.0-windows` (2025/2026), or `net10.0-windows` (2027). A 2027 add-in needs the .NET 10 SDK to build.
- **Add-in not found by Revit 2027 (all-users install)** → you deployed to `%ProgramData%\…\Addins\`; 2027 scans `%ProgramFiles%\Autodesk\Revit\Addins\<year>\` instead. Use the per-user `%AppData%` path for dev.
- **"Modification of the document is forbidden"** → editing outside an open `Transaction`.
- **"Starting a transaction… outside of API context is not allowed"** → calling the API from a modeless dialog/worker thread; route through `ExternalEvent`.
- **Version-conflict / "assembly already loaded"** → you copied `RevitAPI.dll` to output; set `<Private>false</Private>`.
- **Compile errors on `IntegerValue` / `DisplayUnitType`** → use `ElementId.Value` and the `ForgeTypeId`/`UnitTypeId` APIs.
- **Icons don't show on .NET 8/.NET 10** → naive pack URIs often fail; load from an embedded-resource stream into a frozen `BitmapImage` (see `template/`/`reference/ui-and-interaction.md`).
- **`CreateRibbonTab` throws** → tab already exists; wrap in try/catch and reuse existing panels (`GetRibbonPanels`).
- **Cached `Element` goes stale** → store `ElementId`, re-fetch via `doc.GetElement(id)`; check `el.IsValidObject`.
- **Slow on big models** → opening a `Transaction` inside a per-element loop (each commit regenerates), or filtering in LINQ instead of `FilteredElementCollector` quick filters (~2× slower). Batch edits into one transaction; filter natively. See `reference/robustness-and-testing.md`.
- **Fails on real (workshared) projects** → modifying elements another user has checked out, opening the central directly, or syncing silently. Check out (or try-and-rollback), create a new local for editing / open detached for read-only, and confirm syncs. See `reference/robustness-and-testing.md` §7.

## Verify Before Claiming Done

Real verification needs Revit installed. At minimum: the project **builds** for the target framework; the `.addin` points to the built DLL with a unique `AddInId`; the command class is `public`, has `[Transaction(TransactionMode.Manual)]`, and implements `IExternalCommand`. Then load in Revit and confirm the ribbon button appears and the command runs. Use **RevitLookup** to inspect elements/parameters when results look wrong.
