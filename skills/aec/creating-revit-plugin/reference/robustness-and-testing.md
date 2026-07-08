# Robustness, Testing & Performance

The patterns that separate a hobby add-in from a production one. Code-level, .NET 8/.NET 10 / Revit 2025+ (Revit 2027 = .NET 10).

## 1. Dependency isolation / "DLL hell" — the #1 real-world problem

Revit loads **every** add-in into one process and, by default, the **same load context**
(`AssemblyLoadContext.Default`). If two add-ins ship different versions of a shared NuGet lib
(Newtonsoft.Json, CommunityToolkit.Mvvm, Microsoft.Extensions.*), **first-loaded-wins**: the second
add-in silently binds to the wrong version or throws `TypeLoadException` / `MissingMethodException` /
`FileLoadException`. (Classic: Revit itself loads `Microsoft.Extensions.Options 7.0`; your add-in
needs 8.0 → `TypeLoadException`.)

**Critical .NET 8 caveat:** pre-2025 add-ins (.NET Framework 4.8) could isolate in their own
`AppDomain`. **.NET 6+ removed AppDomain isolation** — `AppDomain.CreateDomain` throws
`PlatformNotSupportedException`. On Revit 2025/2026 (.NET 8) the only isolation primitive is
**`AssemblyLoadContext` (ALC)**. So true isolation is only achievable on 2025+.

Solutions, weakest → strongest:

1. **Version-pin / avoid the dependency** — match the version Revit ships, or don't take the dep.
   Cheap, brittle (breaks when another vendor disagrees; you don't control load order).
2. **Probe your plugin folder** (RevitToolkit `ResolveHelper`) — hooks `AssemblyResolve` to load deps
   from *your* folder. Fixes `FileNotFoundException`, but **not** version conflicts (still shared context).
   ```csharp
   using (ResolveHelper.BeginAssemblyResolveScope<MyViewModel>())  // nestable, auto-restores
       window.Show();
   ```
   Automatic when you inherit RevitToolkit base classes (`ExternalCommand`, etc.).
3. **Automatic ALC isolation (RevitToolkit ≥2025.0.1, Revit 2025+)** — inherit the toolkit's
   `ExternalCommand`/`ExternalApplication`/`ExternalDBApplication` base classes → each plugin's deps
   load into a **separate ALC**, conflicts vanish. Plain `IExternalCommand` gets **no** isolation.
4. **Explicit source-generated ALC (`Scotec.Revit.Isolation`, Revit 2025+)** — `[RevitCommandIsolation]` /
   `[RevitApplicationIsolation]` attributes generate a `*Factory` per add-in with its own ALC. The
   `.addin` must register the **generated `…Factory` class**, not yours; PushButtons reference the
   factory types too.
5. **Helper-assembly isolation (universal)** — hide the conflicting dep behind your own thin wrapper
   assembly, exposing only primitives across the boundary.
6. **Native add-in isolation manifest (Revit 2027+)** — 2027 makes isolation a first-class `.addin`
   feature instead of a code trick. Declare which assemblies are shared and what your add-in depends
   on via `PublicAssemblies`, `Dependencies` (`dependsonclientid`, `dependsoncontext`), and
   `UseAllContextsForDependencyResolution` (API types `AddInDependencyBase`, `ClientIdDependency`,
   `ContextNameDependency`). Revit then resolves each add-in's assemblies with the declared sharing
   rules — use this on 2027 in preference to hand-rolled ALC plumbing for cross-add-in scenarios.

**ALC trade-offs:** objects pass freely (no serialization, unlike old AppDomains), BUT **a type with
the same name in two ALCs is not the same type** — keep cross-ALC boundaries to primitives/DTOs;
adds factory indirection; harder debugging; 2025+ only.

> Practical recommendation: on **2027** declare isolation/dependencies in the `.addin` manifest (option
> 6). On 2025/2026 use ALC isolation (toolkit base classes or Scotec). On 2023/2024 most teams
> version-pin + ResolveHelper and accept the residual risk.

## 2. Testing

Two layers. The high-leverage move is keeping business logic in a **Revit-agnostic core** (a
`netstandard2.0`/plain library with **zero `RevitAPI.dll` references**, operating on DTOs) so it tests
with normal xUnit/NUnit on any CI runner — no Revit license, no live process. Only the thin Revit
adapter needs a live-Revit harness.

**Driving a real Revit — `ricaun.RevitTest`** (modern, multi-version): auto-launches Revit, runs
NUnit-style tests in-process against a live API, closes Revit — from `dotnet test`/VS/Rider. Detects
the Revit version from your test assembly's RevitAPI reference.
```xml
<PackageReference Include="NUnit" Version="3.13.3" />
<PackageReference Include="ricaun.RevitTest.TestAdapter" Version="*" />
<IsTestProject>true</IsTestProject>
```
```csharp
public class RevitTest
{
    private UIApplication uiapp;
    [OneTimeSetUp] public void Setup(UIApplication uiapp) => this.uiapp = uiapp;  // framework injects it
    [Test] public void HasVersion() => Assert.IsNotNull(uiapp.Application.VersionName);
}
```
`ricaun.RevitTest.DA` runs the same tests in APS Design Automation. Alternatives: RevitTestFramework/RTF
(Dynamo's, journal-driven), Geberit `Revit.TestRunner`, Nice3point's TUnit-based in-process harness.

## 3. Logging & diagnostics

**Why it matters:** in Design Automation (cloud) you can't attach a debugger — logs are your only
window into a failed run; same for unreachable user machines.

Revit has no built-in DI, so init a static `Log.Logger` once in `OnStartup`, writing to a **per-user
writable path** (never beside the DLL — that's often under Program Files):
```csharp
var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                          "MyVendor", "MyAddin", "logs");
Directory.CreateDirectory(logDir);
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information().Enrich.FromLogContext()
    .WriteTo.File(Path.Combine(logDir, "addin-.log"), rollingInterval: RollingInterval.Day,
                  retainedFileCountLimit: 14, shared: true)   // shared:true → multiple Revit instances
    .CreateLogger();
```
Call `Log.CloseAndFlush()` in `OnShutdown`. In Design Automation also write to **stdout** (the engine
captures it into the job report). Serilog is itself a common DLL-hell source — isolate or pin it.

**Journal files** (crash diagnosis): `…\AppData\Local\Autodesk\Revit\Autodesk Revit <version>\Journals`.
They record the command sequence, loaded add-ins + load order, and exceptions near failure — useful
for "which add-in loaded before mine" (DLL-hell) and reproducing the crashing action.

## 4. Global error handling (don't crash Revit)

Wrap every `Execute` in try/catch — an unhandled exception can destabilize Revit:
```csharp
try { DoWork(cd.Application); return Result.Succeeded; }
catch (Autodesk.Revit.Exceptions.OperationCanceledException) { return Result.Cancelled; }  // Esc, not an error
catch (Exception ex)
{
    Log.Error(ex, "Command {Cmd} failed", nameof(MyCommand));
    message = "Something went wrong. See log: " + logPath;   // Revit shows this
    return Result.Failed;
}
```
App-level last resort: subscribe to `AppDomain.CurrentDomain.UnhandledException` in `OnStartup` to log
fatal escapes. Note the modern CLR no longer routes corrupted-state exceptions — design to avoid
native crashes; don't rely on catching `AccessViolationException`.

**`IFailuresPreprocessor`** is Revit's *own* error channel (warnings/errors at commit), separate from
.NET exceptions — and **essential in Design Automation**, where a modal warning dialog would hang the
job forever (no user to click OK):
```csharp
public class WarningSwallower : IFailuresPreprocessor
{
    public FailureProcessingResult PreprocessFailures(FailuresAccessor fa)
    {
        foreach (var f in fa.GetFailureMessages())
            if (f.GetSeverity() == FailureSeverity.Warning) fa.DeleteWarning(f);
        return FailureProcessingResult.Continue;  // or ProceedWithRollBack to abort safely
    }
}
// var opts = t.GetFailureHandlingOptions(); opts.SetFailuresPreprocessor(new WarningSwallower());
// opts.SetClearAfterRollback(true); t.SetFailureHandlingOptions(opts);
```

## 5. Performance — concrete do/don't

**FilteredElementCollector:** quick filters read the lightweight element header and never expand the
element; slow filters (`ElementParameterFilter`, geometry/param reads) materialize each element.
- **DO** apply quick filters first to shrink the set; the shortcut methods (`OfClass`, `OfCategory`,
  `WhereElementIsNotElementType`/`…IsElementType`) are all quick filters.
- **DON'T** filter in LINQ until native filters are exhausted — doing it in .NET is a measured **~2×
  slower**. ("Filtering in .NET is guaranteed to double execution time and halve performance.")
- **DON'T** rebuild collectors in a loop; build once, reuse/cache.

**Transactions & regeneration:**
- **DON'T** open/commit a transaction inside a per-element loop — every `Commit()` triggers an
  automatic `doc.Regenerate()` and grows the undo stack. One transaction wrapping many edits is far
  faster. For huge ops (tens of thousands), chunk into a few transactions.
- **DON'T** call `doc.Regenerate()` manually unless you must read just-created geometry before commit
  — it's expensive; the commit regenerates for you.
- **DO** use `TransactionGroup.Assimilate()` to merge several transactions into one undo entry (and
  `RollBack()` the whole group atomically on failure).

**Parameters:** avoid name-based `LookupParameter`/`get_Parameter(name)` in tight loops; prefer
`BuiltInParameter` enums or cache the `Parameter`/`Definition`. Filter server-side with
`ElementParameterFilter` rather than reading-then-filtering in .NET.

## 6. Settings / state storage: ExtensibleStorage vs config files

Use **ExtensibleStorage (ES)** when data belongs to the *model* (per-element metadata, project
settings that must travel with the .rvt and sync via worksharing). Use a **user config file** (JSON in
`%APPDATA%`) for per-user/machine preferences (window positions, last folder) that must NOT live in
the model.

ES gotchas (production traps):
- A **Schema GUID is immutable** and is effectively the version marker. You **cannot change** a
  schema's fields/name/access under the same GUID once deployed.
- **#1 mistake — schema conflict:** reusing sample code's GUID while changing the field definition. If
  Revit already holds that GUID with a different definition → hard conflict. **Change the definition →
  mint a new GUID.**
- **Migration:** new GUID per version; dual-read (try old → upgrade → write only to new → delete old).
- **Worksharing hazard:** writing ES during `DocumentOpened`/`DocumentSaved` forces element
  **borrowing** and causes permission errors for other users — don't.
- Store project-wide settings on a single `DataStorage` element (look up existing first; don't dupe).
- ES is private to your add-in and is **not** exported to the APS/Autodesk Viewer (the pipeline
  doesn't load add-ins) — export a sidecar if the viewer needs it.
- **Worksharing-friendly ES layout:** don't pile all add-in data onto one global element (e.g.
  `ProjectInfo`) — that forces every user to check it out and collide. Use a dedicated `DataStorage`
  element, and split into **type-specific info elements** (e.g. wall / column / room) so users editing
  different aspects update their own data without editing conflicts. (See §7.)

## 7. Worksharing (multi-user / central models)

Most add-ins are written for the single-user case, but large projects are **workshared**: a central
model with many users editing local copies. An add-in that ignores this corrupts or fails on real
projects. (From AU "Facing the Elephant in the Room", Scott Conover, Autodesk.) Key disciplines:

**Editability / checkout.** Before modifying a workshared element you must be able to edit it
(no one else owns it). Two strategies:
- **Check out in advance:** `WorksharingUtils.CheckoutElements(doc, ids)`; inspect with
  `GetCheckoutStatus` / `GetModelUpdatesStatus` before editing.
- **Try-and-rollback:** attempt the edit inside a transaction with an `IFailuresPreprocessor` that
  rolls back on a worksharing/permission failure (so a locked element doesn't abort the whole command).

**Open the document the right way for your purpose** (never just open the central directly):
- **Editing** → create a new local from central: `WorksharingUtils.CreateNewLocal(centralPath, localPath)`,
  then open the local.
- **Read-only** → open **detached**: `OpenOptions` with `DetachFromCentralOption` (non-graphical for
  pure data reads; or copy-and-open-detached for a server model where no local is needed).
- **Performance** → open only the last-viewed worksets via a `WorksetConfiguration`.

**Operations need user confirmation — never silently:** `Document.SynchronizeWithCentral` (offer to
relinquish vs. keep worksets checked out) and reload-latest should both prompt the user first.

**Updaters can bypass checkout — with a catch.** An `IUpdater` can change elements even when checked
out elsewhere and without local checkout (useful for bulk system-driven changes), but **those changes
are lost if another user edited the elements before the next sync**. Register the updater as
**optional** so the model isn't flagged as requiring your add-in to open.

**New elements land in the active workset**; you can reassign an element's workset after creation.
Also recall (§6) the ES rule: don't write ExtensibleStorage during `DocumentOpened`/`Saved` — it forces
borrowing and breaks other users.

## 8. Add-in longevity & versioned upgrades

An add-in lives across many Revit releases and many documents — most of which don't use it. Design
for that from the start. (AU "In It for the Long Haul", Joel Spahn.)

- **Stamp the document with your add-in version** (in ExtensibleStorage) when it first adopts your
  add-in. This is what lets you detect and upgrade persisted data later.
- **Stay out of the way:** do *initial* validation/initialization **when the user first runs a command**
  — not every document wants your add-in. Do *subsequent* validation in the `DocumentOpened` event
  **only if the document already uses your add-in** (check the stamp). Don't impose updaters, shared
  parameters, or schema on documents that never opted in.
- **Validation/init tasks:** initialize/validate/upgrade your stored data, manage shared parameters,
  register updaters — gated on the version stamp.
- **Persistence choice:** **Shared Parameters** are user-visible and schedulable but limited to
  parameter "shapes"; **ExtensibleStorage** is hidden and not schedulable but supports flexible data
  structures (see §6). Pick by whether the user/schedules need to see the data.
- **Upgrade path** (ES): read old data with the old schema → convert → write with the new schema →
  optionally delete the old entity/schema. New GUID per schema version (§6). For shared parameters,
  add/remove parameters as the version requires.

## Sources
- DLL-hell / ALC: Nice3point RevitToolkit (github.com/Nice3point/RevitToolkit, release 2025.0.1); Scotec.Revit.Isolation (scotec.com blog "Innovative Revit Add-in Development Part 3", github.com/scotec-Software-Solutions-AB/scotec-revit); Autodesk forums & blog.autodesk.io.
- Testing: ricaun.RevitTest (github.com/ricaun-io/ricaun.RevitTest, ricaun.com/revittest); Geberit Revit.TestRunner.
- Logging/journals: Autodesk "How to read the journal file"; Serilog best practices.
- Performance & transactions: The Building Coder (jeremytammik.github.io/tbc — filter shortcuts, slow filtering, transaction groups).
- ExtensibleStorage: blog.autodesk.io ES best practices; archi-lab "What/why/how of Extensible Storage".
- Worksharing: AU "Facing the Elephant in the Room: Making Revit Add-ins That Cooperate with Worksharing" (Scott Conover, Autodesk, DV1888); `WorksharingUtils` / `OpenOptions` / `WorksetConfiguration` in the Revit API Developers Guide.
- Add-in longevity / versioned upgrades: AU "In It for the Long Haul: Tips for Serious Revit Add-In Developers" (Joel Spahn, Lighting Analysts, DV2918).
