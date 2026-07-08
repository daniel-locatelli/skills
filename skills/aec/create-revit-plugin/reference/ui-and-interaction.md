# UI, Interaction & Advanced Patterns

## Ribbon UI (from IExternalApplication.OnStartup)

Build the ribbon in `OnStartup` (you receive a `UIControlledApplication`). You cannot build a ribbon from inside an `IExternalCommand`.

```csharp
public Result OnStartup(UIControlledApplication app)
{
    const string tab = "My Tools";
    try { app.CreateRibbonTab(tab); } catch { /* already exists */ }

    // Reuse the panel if it already exists (idempotent across reloads)
    RibbonPanel panel = app.GetRibbonPanels(tab).FirstOrDefault(p => p.Name == "Utilities")
                        ?? app.CreateRibbonPanel(tab, "Utilities");

    string asm = Assembly.GetExecutingAssembly().Location;
    var data = new PushButtonData(
        "cmdDoThing",                 // internal name (unique within panel)
        "Do\nThing",                  // visible label (\n wraps text)
        asm,                          // AssemblyName  -> path to this DLL
        "MyAddin.Commands.DoThing");  // ClassName -> fully-qualified IExternalCommand

    var btn = (PushButton)panel.AddItem(data);
    btn.ToolTip = "Does the thing.";
    btn.LongDescription = "Extended tooltip shown on hover-hold.";
    btn.LargeImage = ImageUtils.Load(Assembly.GetExecutingAssembly(), "icon32.png"); // 32x32
    btn.Image      = ImageUtils.Load(Assembly.GetExecutingAssembly(), "icon16.png"); // 16x16
    return Result.Succeeded;
}
```

**Button ⇄ command link:** `PushButtonData`'s last two args — **AssemblyName** (DLL path) and **ClassName** (fully-qualified type) — tell Revit which `IExternalCommand.Execute` to invoke. The command class must be `public`, implement `IExternalCommand`, and carry `[Transaction(TransactionMode.Manual)]`.

Other item types via `panel.AddItem` / `panel.AddStackedItems`: `PulldownButtonData` (menu → `.AddPushButton(...)`), `SplitButtonData`, `ComboBoxData`, `TextBoxData`, `RadioButtonGroupData`, `SeparatorItem`.

### Icons in .NET 8 — load from embedded resource stream
> To *create* the PNGs themselves (Revit ribbon design rules + a verified Iconify→PNG generation pipeline), see `[[icons.md]]`. This subsection covers only *loading* them.

Naive pack URIs (`pack://application:,,,/…`) frequently fail to render in .NET 8 add-ins. Robust approach (set the PNG's Build Action to `EmbeddedResource`):
```csharp
public static class ImageUtils
{
    public static BitmapImage? Load(Assembly asm, string endsWith)
    {
        var name = asm.GetManifestResourceNames()
            .FirstOrDefault(n => n.EndsWith(endsWith, StringComparison.OrdinalIgnoreCase));
        if (name == null) return null;
        using var s = asm.GetManifestResourceStream(name);
        var img = new BitmapImage();
        img.BeginInit();
        img.CacheOption = BitmapCacheOption.OnLoad;   // read fully before stream closes
        img.StreamSource = s;
        img.EndInit();
        img.Freeze();                                  // thread-safe + faster
        return img;
    }
}
```

## Threading & the "valid API context" rule (critical)

Revit API calls — anything that opens a `Transaction` or modifies the model — are only legal **on Revit's main thread, inside a callback Revit invoked**: `IExternalCommand.Execute`, an event handler, `IUpdater.Execute`, or `IExternalEventHandler.Execute`.

- A **modal** dialog (`ShowDialog()`) blocks on the command thread, so the command's API context is still valid after it returns — you can call the API directly.
- A **modeless** dialog (`Show()`) returns immediately; its later button clicks run **outside** any API context. Calling the API there throws *"Starting a transaction from an external application running outside of API context is not allowed."* → marshal back via `ExternalEvent`.
- **Never** call the API from a background/worker thread.

## ExternalEvent + IExternalEventHandler (the modeless bridge)

Create the `ExternalEvent` in a valid context (`OnStartup` or a command — not inside the dialog). The dialog calls `Raise()`; Revit later calls `Execute(uiapp)` on the main thread in a valid context.

```csharp
public class RequestHandler : IExternalEventHandler
{
    public double TargetHeightMm { get; set; }   // pass data from dialog via fields/properties

    public void Execute(UIApplication app)        // valid API context here
    {
        var uidoc = app.ActiveUIDocument;
        var doc = uidoc.Document;
        double ft = UnitUtils.ConvertToInternalUnits(TargetHeightMm, UnitTypeId.Millimeters);
        using var t = new Transaction(doc, "Set Height");
        t.Start();
        foreach (var id in uidoc.Selection.GetElementIds())
            doc.GetElement(id).get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)?.Set(ft);
        t.Commit();
    }
    public string GetName() => "My Modeless Handler";
}
```
Wiring:
```csharp
var handler = new RequestHandler();
ExternalEvent ev = ExternalEvent.Create(handler);   // in valid context
new MyWpfWindow(ev, handler).Show();                 // modeless
// inside the window's click handler:  _handler.TargetHeightMm = 3000; _ev.Raise();
```
`Raise()` is asynchronous and may be coalesced if raised repeatedly. For many actions, use one handler with a **request enum** dispatched inside `Execute` (Building Coder recommendation) rather than many handler classes. Use **modal** for "configure then run once"; **modeless** for a persistent tool palette.

## Events vs Dynamic Model Update (IUpdater)

**Application/Document events** — subscribe in `OnStartup`, unsubscribe in `OnShutdown`:
```csharp
app.ControlledApplication.DocumentOpened  += OnDocOpened;
app.ControlledApplication.DocumentChanged += OnDocChanged;   // READ-ONLY context
```
`DocumentChanged` gives `GetAddedElementIds()/GetModifiedElementIds()/GetDeletedElementIds()` for reactive notification, but **you cannot open a transaction inside it** — use it for logging, external sync, or scheduling follow-up work.

**`IUpdater` (DMU)** — use when you must **modify the model in reaction to a change, within the same transaction**. Revit calls `Execute` *inside the user's transaction*, so your edits join their undo step. **Do not open a transaction inside `Execute`** — you're already in one.
```csharp
var upd = new MyUpdater(app.ActiveAddInId);
UpdaterRegistry.RegisterUpdater(upd);
UpdaterRegistry.AddTrigger(upd.GetUpdaterId(),
    new ElementCategoryFilter(BuiltInCategory.OST_Walls), Element.GetChangeTypeAny());
```
**Rule of thumb:** need to *change the document* on a change → `IUpdater`. Only *observe/notify/sync* → events.

## Selection

```csharp
Selection sel = uidoc.Selection;
Reference r = sel.PickObject(ObjectType.Element, "Select an element");   // single
Element e = doc.GetElement(r);
IList<Reference> rs = sel.PickObjects(ObjectType.Element, new WallFilter(), "Select walls"); // multi
ICollection<ElementId> ids = sel.GetElementIds();   // current selection
```
`ObjectType`: `Element`, `Face`, `Edge`, `PointOnElement`, `LinkedElement`. **Esc throws `Autodesk.Revit.Exceptions.OperationCanceledException`** — catch it and return `Result.Cancelled`.
```csharp
public class WallFilter : ISelectionFilter
{
    public bool AllowElement(Element e) => e is Wall;
    public bool AllowReference(Reference r, XYZ p) => false;
}
```

## Failure handling (IFailuresPreprocessor)

Suppress/auto-resolve warnings raised during a transaction so dialogs don't interrupt the user:
```csharp
public class WarningSwallower : IFailuresPreprocessor
{
    public FailureProcessingResult PreprocessFailures(FailuresAccessor fa)
    {
        foreach (var f in fa.GetFailureMessages())
            if (f.GetSeverity() == FailureSeverity.Warning) fa.DeleteWarning(f);
        return FailureProcessingResult.Continue;
    }
}
// attach:
var opts = t.GetFailureHandlingOptions();
opts.SetFailuresPreprocessor(new WarningSwallower());
t.SetFailureHandlingOptions(opts);
```
`DeleteWarning` works only on **warnings**; errors must be resolved or the transaction rolls back. Return `FailureProcessingResult.Continue`.

## Parameters & Units (ForgeTypeId system, Revit 2022+)

**Read/write:**
```csharp
Parameter p = el.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM);  // by built-in
// or: el.LookupParameter("Comments");                                     // by name
if (p != null && !p.IsReadOnly) p.Set(value);   // Set needs an open transaction
double internalVal = p.AsDouble();               // lengths are in INTERNAL units = decimal feet
```

**Enums replaced by `ForgeTypeId` classes** (old code won't compile):
- `DisplayUnitType` → **`UnitTypeId`** (`UnitTypeId.Millimeters`, `.Meters`, …)
- `UnitType`/spec → **`SpecTypeId`** (`SpecTypeId.Length`, …)
- `BuiltInParameterGroup` → **`GroupTypeId`**
- `Parameter.ParameterType` → **`Parameter.GetDataType()`** (returns a `ForgeTypeId`)

**Unit conversion** (always convert at the UI boundary — Revit stores decimal feet / radians):
```csharp
double mm = UnitUtils.ConvertFromInternalUnits(internalVal, UnitTypeId.Millimeters);  // out
double ft = UnitUtils.ConvertToInternalUnits(userMm,       UnitTypeId.Millimeters);   // in
// document's display unit for length:
doc.GetUnits().GetFormatOptions(SpecTypeId.Length).GetUnitTypeId();
```
(Common shortcut seen in code: `feet = mm / 304.8`. Prefer `UnitUtils` for correctness/clarity.)

**Shared parameters:** `app.OpenSharedParameterFile()` → `Definition` from a `DefinitionGroup` → bind via `doc.ParameterBindings.Insert(def, new InstanceBinding(categorySet), GroupTypeId.X)`.

## Pitfalls
- **No transaction** → `Set`, `doc.Create.*`, `doc.Delete`, `doc.Regenerate()` throw "Modification of the document is forbidden".
- **Read-only contexts:** `DocumentChanged`, `[Transaction(ReadOnly)]` commands, during regeneration — no transactions. `IUpdater.Execute` is already transactional.
- **Stale geometry/params** after edits → call `doc.Regenerate()` inside the transaction (commit also regenerates).
- **Stale `Element` refs** → store `ElementId`, re-fetch via `doc.GetElement(id)`; check `el.IsValidObject`.
- **64-bit ids (2024+)** → `ElementId.Value`, not `IntegerValue`.

## Sources
- Revit API Developers Guide (help.autodesk.com) — Failures, Dynamic Model Update, Units, Selection.
- The Building Coder — Valid API Context, External Events, ForgeTypeId / "What's New 2022".
- revitapidocs.com — PickObjects/ISelectionFilter, UnitUtils ForgeTypeId overloads, API Changes 2024/2025.
- Real reference project: HM DokwoodRevit — embedded-resource `BitmapImage` loader with `Freeze()`, idempotent ribbon panel reuse, `mm/304.8` unit conversion, get-or-create material.
