# Architecture for Non-Trivial Add-ins

The basics (one `IExternalCommand` per button, transactions, collectors) stop scaling once an
add-in has many commands, WPF dialogs, shared services, and must run across Revit versions. This
is the production shape, drawn from the **Nice3point/RevitTemplates** + **RevitToolkit** stack
(the de-facto modern reference) and Autodesk's own desktop→cloud guidance.

## Pick a structure tier by complexity

| Tier | When | Shape |
|------|------|-------|
| Trivial | 1–3 commands, no UI | `App.cs` + `Commands/` (the `template/` in this skill) |
| Small UI | a modal dialog or two | + `ViewModels/` + `Views/` (MVVM) |
| Standard | shared services, DI | + a static `Host` (composition root) |
| Production | many features, multi-version, tested | multi-project: thin shell + feature modules + tests/installer |

Production multi-project layout:
```
source/
  RevitAddIn/         # thin shell: Application.cs (ribbon), Host.cs (DI root), Commands/, Configuration/
  ModalModule/        # a feature: Models/ Services/ ViewModels/ Views/
  ModelessModule/     # a feature: Messages/ Models/ Services/ ViewModels/ Views/
install/              # WiX/installer
build/                # NUKE/CI build automation
tests/                # in-process Revit tests + BenchmarkDotNet
```
Principles: **one class per command** (`Commands/`); **feature modules** are separate projects with
their own MVVM stack; the **shell** only starts the Host and builds the ribbon.

## Dependency Injection in a long-lived process

Revit is a single, long-lived process, so the DI container is a **process-wide singleton** held in a
static `Host`, created in `OnStartup` and disposed in `OnShutdown`.

Lightweight (`ServiceCollection`):
```csharp
public static class Host
{
    private static IServiceProvider? _provider;
    public static void Start()
    {
        var services = new ServiceCollection();
        services.AddTransient<MyViewModel>();
        services.AddTransient<MyView>();
        _provider = services.BuildServiceProvider();
    }
    public static T GetService<T>() where T : class => _provider!.GetRequiredService<T>();
}
```

Full host (`HostApplicationBuilder` — adds logging/config/hosted services). **Use `DisableDefaults = true`**
(Revit has no env/CLI args; the legacy `Host.CreateDefaultBuilder` pulls in console/lifetime defaults you don't want):
```csharp
var builder = new HostApplicationBuilder(new HostApplicationBuilderSettings {
    ContentRootPath = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location),
    DisableDefaults = true
});
builder.Logging.ClearProviders();
builder.AddSerilogLoggingProvider();
builder.Services.AddSingleton<IMessenger>(StrongReferenceMessenger.Default);
builder.Services.AddSingleton<ElementMetadataExtractionService>(); // stateless service
builder.Services.AddScoped<MyModelessViewModel>();                  // per-window
_host = builder.Build();
await _host.StartAsync();   // OnShutdownAsync -> _host.StopAsync()
```

**Scoping is the load-bearing part.** Because the process never restarts, a single global scope leaks
state across every dialog. Tie a **DI scope to each window's lifetime**:
```csharp
public static T CreateScope<T>() where T : FrameworkElement
{
    var scope = _host!.Services.GetRequiredService<IServiceScopeFactory>().CreateScope();
    var element = scope.ServiceProvider.GetRequiredService<T>();
    if (element is Window w) w.Closed += (_, _) => scope.Dispose();
    else element.Unloaded += (_, _) => scope.Dispose();
    return element;
}
```
Rule of thumb: **stateless services → `Singleton`** (live the whole session); **ViewModels/Views → `Scoped`**
resolved via `CreateScope<T>()`; avoid `Transient` for anything holding `IDisposable` Revit objects.

## MVVM for WPF dialogs (CommunityToolkit.Mvvm)

Standardize on **CommunityToolkit.Mvvm** source generators (`ObservableObject`, `[ObservableProperty]`,
`[RelayCommand]`). Resolve ViewModels from DI; inject services via the constructor; set the View's
`DataContext` to the injected VM. For a **modal** dialog the command already runs in Revit's API
context, so a `[RelayCommand]` may call the API directly (open a transaction). For **modeless**, it
must not — marshal through an ExternalEvent (below).

> `[ObservableProperty]` on a **partial property** needs CommunityToolkit.Mvvm 8.4+ / C# 13. Older
> versions use the field form `[ObservableProperty] private string _x;`.

## Async ExternalEvent — `await` a Revit API action from UI code

A modeless window runs on the WPF thread, outside Revit's API context, so every API call must be
marshalled through an `ExternalEvent`. The modern pattern lets you `await` that round-trip and get a
return value back on the UI thread.

**RevitToolkit's `[ExternalEvent]` source generator** is the cleanest — write a plain method taking
`UIApplication`; it generates the event + `RaiseAsync()`:
```csharp
public sealed partial class MyViewModel(ElementMetadataExtractionService svc) : ObservableObject
{
    [RelayCommand]                                   // runs on UI thread
    private async Task DeleteAsync()
    {
        var deletedId = await DeleteElementAsyncEvent.RaiseAsync();   // awaits Revit
        TaskDialog.Show("Deleted", $"ID: {deletedId}");
    }

    [ExternalEvent]                                  // runs in Revit API context
    private ElementId DeleteElement(UIApplication app)
    {
        var doc = app.ActiveUIDocument.Document;
        var r = app.ActiveUIDocument.Selection.PickObject(ObjectType.Element);
        using var t = new Transaction(doc, "Delete element");
        t.Start(); doc.Delete(r.ElementId); t.Commit();
        return r.ElementId;
    }
}
```
`[ExternalEvent(AllowDirectInvocation = true)]` lets the same handler also run synchronously inline
when already in API mode — so one VM serves both modal and modeless windows. None of these libraries
introduce real threads; they queue onto Revit's event loop.

**Library options (name the one you use):**
- **RevitToolkit** (`Nice3point.Revit.Toolkit`) — the `[ExternalEvent]` generator + `ExternalEvent`/
  `AsyncExternalEvent`/`AsyncRequestExternalEvent<T,TResult>` types. Most integrated.
- **`ricaun.Revit.UI.Tasks`** (RevitTask) — `await revitTask.Run(uiapp => {...}, cancellationToken)`; supports cancellation + return values.
- **`Revit.Async`** (Kennan Chan) — `await RevitTask.RunAsync(uiapp => {...})`; oldest, simplest drop-in.

## Reusable code patterns (framework-agnostic)

These work without any toolkit and cut the most repetitive Revit boilerplate. (From AU "Advanced
Revit Code Refactoring", David Echols.)

**`UsingTransaction` extension on `Document`** — wrap the start/commit/rollback/dispose boilerplate
once; every edit becomes a one-liner with guaranteed safety:
```csharp
public static TransactionStatus UsingTransaction(this Document doc, Action<Transaction> action,
                                                 string name = "Edit")
{
    using var t = new Transaction(doc, name);
    try { if (t.Start() != TransactionStatus.Started) return t.GetStatus(); action(t); return t.Commit(); }
    catch { t.RollBack(); throw; }
}
// usage:
doc.UsingTransaction(t => wall.WallType = newType, "Change wall type");
```

**Divorce document changes from the transaction structure.** Encapsulate *what* changes (small,
reusable operations on `Document`) separately from *how* it's wrapped — because the transaction
context differs by caller: a command runs in manual mode (you open the transaction), an event may have
**no** transaction (or forbid one), and an `IUpdater` is **already inside** one (use a `SubTransaction`).
Writing the change once and invoking it from each context (the `UsingTransaction(Action)` wrapper
above is exactly this) lets the same logic serve commands, events, and updaters. (AU "In It for the
Long Haul", Joel Spahn.)

**Extension methods on API classes** to build a domain vocabulary and attach reusable behavior to
read-only API types (`Document`, `ViewSheet`, `BasicFileInfo`, `Transaction`). E.g.
`basicInfo.IsOpenedAsCentral(path)` used in a `DocumentOpening` handler to enforce a workflow.

**Command base-class hierarchy** — funnel every command through an abstract base that does the
cross-cutting work once (exception handling, command-data init, wrap in a `TransactionGroup`,
pre/post hooks), then specialize: *Base → by availability (Project doc / Family doc / no doc, licensed
/ unlicensed) → by kind → concrete command*. This is the hand-rolled version of RevitToolkit's
`ExternalCommand` base class, and pairs naturally with the Command+Factory pattern below.

**Command + Factory + Singleton — decouple the dialog/UI from the API logic.** The thin
`IExternalCommand` only collects user input (a dialog), then hands off to a command object that does
the Revit work; a process-wide `CommandFactory` singleton registers/executes/unregisters it. No
thread-locking needed — only one command runs in the Revit UI at a time. This is the same separation
as the core/adapter split below, and the same shape an MCP tool handler takes (see
`ai-assisted-and-mcp.md`):
```csharp
public Result Execute(ExternalCommandData data, ref string msg, ElementSet els)
{
    using var dlg = new PrintPdfForm(doc);
    if (dlg.ShowDialog() != DialogResult.OK) return Result.Cancelled;
    CommandFactory.Instance.Execute("Print PDF", new object[] { doc, dlg.SelectedSheets });
    return Result.Succeeded;
}
```

**Adapter** to wrap verbose element-creation APIs in a clean `Create(...)` one-liner (e.g.
`HaDetailLine.Create(start, end, view)` hiding `Line.CreateBound` + `doc.Create.NewDetailCurve`).

## Separate business logic from the Revit API (desktop **and** headless)

Layer as **Revit-agnostic core + thin Revit adapters**, exploiting the `RevitAPI.dll` (DB) vs
`RevitAPIUI.dll` (UI) split:
- **Core** — its own project, pure .NET, ideally no Revit references at all (operate on your own
  POCO/DTO models). Unit-testable without Revit.
- **DB adapter** — an `IExternalDBApplication` (RevitToolkit `ExternalDBApplication`). This is the
  **only** entry point that runs in **APS Design Automation** (headless: no `RevitAPIUI.dll`, no
  `TaskDialog`, no `UIApplication`, no `Selection`, no ribbon).
- **UI adapter** — the desktop `IExternalApplication` shell (ribbon, dialogs) that calls the same core.

Rules for cloud compatibility: keep transactions in the adapter, computation in the core; drive
everything from `Document`/`Application` + input parameters, never interactive picks. Build the DB
add-in against the Revit-version-matched `RevitAPI.dll` (2025/2026 engines are .NET 8; 2027 is .NET 10). Porting
desktop→cloud is a **re-architecture, not a recompile**: decouple the headless AppBundle from an
orchestration/UI tier, parallelize independent jobs, and stream long-job status. See
`resources-and-best-practices.md` for the APS Design Automation specifics.

### Making the core MCP-loop-verifiable

The same split makes a plugin verifiable in a closed build→run→read-back→iterate loop against a live
Revit. To qualify, expose a UI-free, **shared-types-only** entry point —
`static ElementId Create(Document doc, string specJson)` — that deserializes the spec and delegates to
the typed core method (only `Document`/`string`/`ElementId` cross the cross-ALC boundary). The core
**owns its own `Transaction`s** (it must not assume an outer transaction, since the loop wraps the call
in a `TransactionGroup` only), and it honors a **disposal contract**: no surviving references in Revit
after it returns (no static event subscriptions, retained UI objects, registered `IUpdater`s, or
statics) so the collectible load context can unload. See `mcp-verified-dev-loop.md`.

## RevitToolkit features worth knowing

`Nice3point.Revit.Toolkit` (NuGet per Revit version, reference as `$(RevitVersion).*`):
- **Base classes** — `ExternalCommand`/`AsyncExternalCommand`, `ExternalApplication`/`AsyncExternalApplication`,
  `ExternalDBApplication` (headless). Override `Execute()` instead of implementing the full interface;
  they wire **automatic dependency resolution** (no `FileNotFoundException` for plugin-folder DLLs).
- **`RevitContext`** (UI ambient context, any thread): `UiApplication`, `ActiveDocument`, `ActiveView`,
  `IsRevitInApiMode`, `BeginDialogSuppressionScope(...)` (auto-answer `TaskDialog`s during batch ops).
- **`RevitApiContext`** (DB): `Application`, `BeginFailureSuppressionScope(resolveErrors:)`.
- **`ResolveHelper`** — `BeginAssemblyResolveScope<T>()` for scoped assembly resolution (see the
  dependency-isolation section in `robustness-and-testing.md`).
- **Fluent ribbon** (`Nice3point.Revit.Extensions.UI`): `panel.AddPushButton<TCommand>("Text").SetLargeImage(...)`
  — strongly-typed, no manual `PushButtonData`/assembly-path strings.
- **`Nice3point.Revit.Sdk`** — MSBuild SDK that auto-patches the `.addin` manifest and handles
  multi-version targeting (see `project-setup-and-build.md`).

> **When to reach for this stack vs. the bare `template/`:** the skill's `template/` is intentionally
> dependency-free for learning and small tools. For a real product with DI, MVVM, multi-version, CI,
> and tests, start from `dotnet new install Nice3point.Revit.Templates` → `dotnet new revit-addin`.

## Sources
- Nice3point/RevitTemplates (samples: SingleProjectDIApplication, SingleProjectHostingApplication, MultiProjectSolution) — github.com/Nice3point/RevitTemplates; RevitToolkit — github.com/Nice3point/RevitToolkit.
- ricaun.Revit.UI.Tasks (RevitTask) — github.com/ricaun-io/ricaun.Revit.UI.Tasks; ricaun.Revit.DI — github.com/ricaun-io/ricaun.Revit.DI; Revit.Async — github.com/KennanChan/Revit.Async.
- APS Design Automation for Revit (UI/logic split, `IExternalDBApplication`) — aps.autodesk.com/en/docs/design-automation/v3; AU "Moving from Add-Ins to Design Automation" (2025).
