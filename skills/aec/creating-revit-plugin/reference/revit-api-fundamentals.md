# Revit API Fundamentals

Reference assemblies: `RevitAPI.dll` (database, geometry, transactions) and `RevitAPIUI.dll` (UI, commands, ribbon). Namespaces: `Autodesk.Revit.DB`, `Autodesk.Revit.UI`, `Autodesk.Revit.Attributes`.

## Entry Points

### IExternalCommand — a single user-invoked action
One method; one ribbon button / menu item maps to one command class.

```csharp
Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements);
```
- `commandData` — gateway to the session (`Application`, `ActiveUIDocument`, `View`).
- `message` — set this when returning `Result.Failed`/`Cancelled`; Revit shows it to the user.
- `elements` — element set Revit highlights if the command fails.

**Mandatory attribute:** `[Transaction(TransactionMode.Manual)]` on the class. Without it the command fails to load.

Optional attributes: `[Regeneration(RegenerationOption.Manual)]` (legacy — `Automatic` was removed ~Revit 2014; usually omitted now), `[Journaling(JournalingMode.NoCommandData)]`.

### IExternalApplication — startup/shutdown, ribbon, events
Runs once when Revit starts. The place to build the ribbon and subscribe to events. **No active document exists at startup** — you receive a `UIControlledApplication`, not `UIApplication`, so you cannot touch a model here.

```csharp
Result OnStartup(UIControlledApplication application);
Result OnShutdown(UIControlledApplication application);
```
Attributes are **not** used on `IExternalApplication` classes.

## The .addin Manifest

Plain XML, `.addin` extension. Revit reads every `.addin` at startup from two locations (per-user overrides machine-wide):
- Machine-wide (all users):
  - Revit **≤ 2026**: `C:\ProgramData\Autodesk\Revit\Addins\<year>\`
  - Revit **2027+**: `C:\Program Files\Autodesk\Revit\Addins\<year>\` — moved for security; writing there needs admin. (`Application.AllUsersAddinsLocation` returns the version-correct path.)
- Per-user (unchanged across versions): `C:\Users\<user>\AppData\Roaming\Autodesk\Revit\Addins\<year>\` (e.g. `2027`)

**Required (both types):** `Assembly` (DLL path — absolute, or relative to the `.addin`), `FullClassName` (`Namespace.Class`), `AddInId` (unique GUID — also called ClientId, one per add-in). `VendorId` strongly recommended.

**`Type="Command"`** manifest (bare command, no ribbon):
```xml
<RevitAddIns>
  <AddIn Type="Command">
    <Assembly>MyAddin.dll</Assembly>
    <AddInId>76eb700a-2c85-4888-a78d-31429ecae9ed</AddInId>
    <FullClassName>MyAddin.HelloCommand</FullClassName>
    <Text>Hello Revit</Text>            <!-- button/menu label -->
    <VendorId>YOURTAG</VendorId>
  </AddIn>
</RevitAddIns>
```
Command-only optional fields: `Text`, `VisibilityMode`, `Discipline`, `AvailabilityClassName` (an `IExternalCommandAvailability` controlling enabled state), `LargeImage`, `TooltipImage`, `LanguageType`.

**`Type="Application"`** manifest (for ribbon-building add-ins — `Name` required, `Text` not used):
```xml
<RevitAddIns>
  <AddIn Type="Application">
    <Name>My Addin</Name>
    <Assembly>MyAddin.dll</Assembly>
    <AddInId>604b1052-f742-4951-8576-c261d1993107</AddInId>
    <FullClassName>MyAddin.App</FullClassName>
    <VendorId>YOURTAG</VendorId>
  </AddIn>
</RevitAddIns>
```
Generate a fresh GUID per add-in (`[guid]::NewGuid()` in PowerShell, or VS Tools → Create GUID).

## Object Model

```
ExternalCommandData.Application  -> UIApplication   (UI app: ribbon, active doc, dialogs)
UIApplication.ActiveUIDocument   -> UIDocument      (UI of open project: selection, views, prompts)
UIDocument.Document              -> Document        (the model database — elements, params, edits)
UIApplication.Application        -> Application     (app-level, no UI: version, options, open/create docs)
```
**Rule of thumb:** `UI`-prefixed types handle the user interface; non-UI types (`Application`, `Document`) are the data layer. All model edits go through `Document`.

Standard command preamble:
```csharp
UIApplication uiapp = commandData.Application;
UIDocument   uidoc  = uiapp.ActiveUIDocument;
Document     doc    = uidoc.Document;
```

## Transactions

Every change to the model **must** be inside an open `Transaction`; Revit throws otherwise. Transactions are atomic, named (shown in the undo stack), and undoable.

- **`Transaction`** — the unit of change. `Start()` → edits → `Commit()` (or `RollBack()`). Use a `using` block. Commit auto-regenerates the model.
- **`SubTransaction`** — nested inside an open `Transaction`; commit/rollback a sub-section. Not named, can't exist standalone.
- **`TransactionGroup`** — wraps multiple `Transaction`s; `Assimilate()` merges them into one undo entry, `RollBack()` discards all.

```csharp
using (Transaction t = new Transaction(doc, "Create Wall"))
{
    t.Start();
    Wall.Create(doc, line, levelId, false);
    t.Commit();
}
```

**`TransactionMode`** (set via the `[Transaction(...)]` attribute):
- `Manual` — **standard.** You manage transactions explicitly. Revit wraps the command in an outer group that rolls back if you return `Result.Failed`.
- `ReadOnly` — query-only; starting a transaction or writing throws. Use for report/inspect commands.
- `Automatic` — **obsolete**, avoid.

Need to suppress/handle warnings raised during a transaction? See `IFailuresPreprocessor` in `ui-and-interaction.md`.

## Element Retrieval — FilteredElementCollector

The efficient way to query the model. Build on a `Document` (optionally scoped to a view), chain filters, then materialize.

Quick filters (apply these first — fast): `.OfClass(typeof(Wall))`, `.OfCategory(BuiltInCategory.OST_Walls)` (category enum names are `OST_`-prefixed), `.WhereElementIsNotElementType()` (instances only), `.WhereElementIsElementType()` (the type/symbol records).

Slow filters: `.WherePasses(new ElementParameterFilter(...))`, logical/geometric filters.

Terminators: `.ToElements()`, `.ToElementIds()`, `.FirstElement()`, or iterate (it's `IEnumerable<Element>`). Don't enumerate the same collector twice — create a new one.

```csharp
var walls = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Walls)
    .WhereElementIsNotElementType()
    .Cast<Wall>()
    .ToList();

// scoped to a view:
new FilteredElementCollector(doc, view.Id).OfCategory(BuiltInCategory.OST_Doors);
```

`ElementId` is a lightweight handle. Resolve with `doc.GetElement(id)`. **Since Revit 2024 `ElementId` is 64-bit — use `id.Value` (long), not the deprecated `id.IntegerValue`.**

**An `ElementId` is meaningless without the `Document` it belongs to** — the same id value exists in every document, including **linked models**. Always track which document an id came from (expand to `Element` and use `Element.Document` when you need to be sure); to find something that may live in a link, query each linked document. Also: collector results depend on context — **phase status, design options, the active view, and pinned/grouped/hidden state** all affect what you see, and **"not visible in a view" does not mean "does not exist."** (AU "In It for the Long Haul", Joel Spahn.)

Idempotent "get-or-create" is the standard pattern for re-runnable commands:
```csharp
Material? mat = new FilteredElementCollector(doc).OfClass(typeof(Material)).Cast<Material>()
    .FirstOrDefault(m => m.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
ElementId matId = mat?.Id ?? Material.Create(doc, name);   // inside a transaction
```

## Result Enum

Returned from `Execute` (and `OnStartup`/`OnShutdown`):
- `Result.Succeeded` — completed; changes committed.
- `Result.Failed` — failed; set `message`. Revit rolls back its auto-group.
- `Result.Cancelled` — user aborted (e.g. cancelled a pick); clean no-op, also rolled back.

## Sources
- Revit API Developers Guide (help.autodesk.com/view/RVT/2027/ENU) — Add-In Integration, Transactions, Filtered Element Collector. (2027 "What's New": .NET 10, Program Files add-in path, add-in isolation.)
- The Building Coder (blog.autodesk.io / jeremytammik.github.io/tbc) — manifest, transaction modes, 64-bit ids.
- revitapidocs.com — class/member reference and per-version "API Changes" pages.
