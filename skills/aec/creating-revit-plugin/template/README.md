# MyRevitAddin — starter Revit add-in (Revit 2027 / .NET 10)

A complete, buildable Revit desktop add-in scaffold. It registers a **My Addin** ribbon tab
with three example commands:

| Button | Command | Demonstrates |
|--------|---------|--------------|
| Hello Revit | `HelloCommand` | Minimal `IExternalCommand`, the object model, `TaskDialog`. |
| Count Elements | `CountElementsCommand` | `TransactionMode.ReadOnly`, `FilteredElementCollector`. |
| Create Levels | `CreateLevelsCommand` | `Transaction`, unit conversion (`UnitUtils`), idempotency, failure/cancel handling. |

## Use it

1. **Copy** the `MyRevitAddin/` folder (and the `.sln`) into your repo.
2. **Rename** to your add-in: the folder, `.csproj`, `.addin`, `AssemblyName`/`RootNamespace`
   in the `.csproj`, and the `namespace`/`FullClassName` references. (Search-replace `MyRevitAddin`.)
3. **Generate a new GUID** for `<AddInId>` in the `.addin` (PowerShell: `[guid]::NewGuid()`),
   and set `<VendorId>`/`<VendorDescription>`.
4. **Target version:** defaults to Revit 2027 (`net10.0-windows`; needs the **.NET 10 SDK**).
   For Revit 2025/2026 set `TargetFramework` to `net8.0-windows`, `RevitVersion` to `2026`, and
   the API package to `2026.0.0`. For 2024 or older switch to `net48`. Match the TFM to the target
   Revit exactly. For one project targeting many versions, see `../reference/project-setup-and-build.md`.

## Build, deploy, run

- **Build** (no Revit install needed to compile — the API comes from NuGet; the .NET 10 SDK must be installed):
  ```powershell
  dotnet build MyRevitAddin/MyRevitAddin.csproj -c Debug
  ```
- The post-build `DeployAddin` target copies `MyRevitAddin.addin` and the DLL into
  `%AppData%\Autodesk\Revit\Addins\2027\` (this per-user path is unchanged in 2027). Start Revit
  and the ribbon tab appears.
- **Terminal-only fast loop (no Visual Studio):** install
  [RevitAddInManager](https://github.com/chuongmep/RevitAddInManager) (v1.6.2+ supports Revit 2027),
  then iterate: edit → `dotnet build` → in Revit, **Add-Ins → Add-In Manager → Load** the built DLL
  and **Run** your command; press **F5** in Add-In Manager to reload after each rebuild — Revit stays
  open. Add-In Manager runs `IExternalCommand` classes only; for **ribbon/`OnStartup`** changes,
  rebuild and restart `Revit.exe`. Full details + the why-the-DLL-isn't-locked explanation:
  `../reference/project-setup-and-build.md` → "Terminal-only build–deploy–test loop".
- **Debug (breakpoints):** in Visual Studio press **F5** (the `Revit 2027` profile in
  `Properties/launchSettings.json` launches `Revit.exe` with the debugger attached), or attach any
  managed debugger (VS / VS Code) to a running `Revit.exe`. Not needed for the build-and-check loop.
- **MCP-verified closed loop:** copy `.mcp.json` to your project root (and set its `revit-mcp` entry
  path) to enable the build→run→read-back→iterate workflow that verifies the plugin against a live
  Revit model — see `../reference/mcp-verified-dev-loop.md`.

## Notes

- `RevitAPI.dll` / `RevitAPIUI.dll` are **not** copied to output (the NuGet package handles
  this). Never ship copies of them — it causes version-conflict load failures.
- Icons are optional: drop `icon16.png` / `icon32.png` into `Resources/` (see its README).
- For ribbon pulldowns, modeless WPF dialogs (`ExternalEvent`), selection filters, events,
  `IUpdater`, and the parameter/units API, see `../reference/ui-and-interaction.md`.
