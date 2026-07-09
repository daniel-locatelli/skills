# Project Setup, Build, Debug & Deploy

## Target Framework per Revit Version (non-negotiable)

The framework is dictated by the Revit version. Always x64.

| Revit version | Runtime | TargetFramework (TFM) |
|---------------|---------|------------------------|
| 2021 – 2024 | .NET Framework 4.8 | `net48` |
| 2025 – 2026 | .NET 8 (desktop) | `net8.0-windows` |
| **2027** | **.NET 10 (desktop, LTS)** | **`net10.0-windows`** |

A `net48` DLL will not load in Revit 2025+, a `net8.0` DLL will not load in ≤2024, and Revit 2027 needs `net10.0-windows` (build with the **.NET 10 SDK**). There is no shim — match the TFM to the target Revit exactly. Autodesk has also **back-ported Revit 2025/2026 to .NET 10** (Microsoft ends .NET 8 support Nov 10, 2026), so a 2025/2026 install may itself be running on .NET 10; your add-in's TFM still follows the table above (a `net8.0-windows` add-in keeps loading on a .NET 10 Revit).

### Revit 2027 deployment & manifest changes

- **All-users install path moved (security).** Revit 2027 no longer scans `%ProgramData%\Autodesk\Revit\Addins\<year>\`. Machine-wide manifests now go under **`%ProgramFiles%\Autodesk\Revit\Addins\<year>\`** (writing there requires admin). `Application.AllUsersAddinsLocation` returns the new path. The **per-user** path `%AppData%\Autodesk\Revit\Addins\<year>\` is **unchanged** — use it for dev deploy.
- **Add-in isolation / dependency manifest settings.** New `.addin` elements let you declare assembly sharing and inter-add-in dependencies: `PublicAssemblies`, `Dependencies` (`dependsonclientid`, `dependsoncontext`), `UseAllContextsForDependencyResolution`; API types `AddInDependencyBase`, `ClientIdDependency`, `ContextNameDependency`. Prefer these over hand-rolled `AssemblyLoadContext` sharing — see `robustness-and-testing.md`.
- **Removed/changed APIs.** Cloud regions: use `ModelPathUtils.GetAllCloudRegions()` instead of `CloudRegionUS`/`CloudRegionEMEA`. AXM import, some legacy rebar methods, and a few `EnergyDataSettings` properties were removed — check the Revit 2027 SDK "What's New" when porting.

## Single-version SDK-style .csproj (Revit 2026 / .NET 8 shown; 2027 swap below)

This mirrors a real production project. Clean, minimal, buildable. **For Revit 2027**, change `<TargetFramework>` to `net10.0-windows` and the API package to `2027.0.*` (everything else is identical; build with the .NET 10 SDK) — this is exactly what the `template/` scaffold ships as its default:

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net8.0-windows</TargetFramework>
    <PlatformTarget>x64</PlatformTarget>
    <UseWPF>true</UseWPF>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RootNamespace>MyAddin</RootNamespace>
    <!-- Quiet the WPF transitive-version warning under .NET 8 (alternative to FrameworkReference below) -->
    <NoWarn>1701;1702;MSB3277</NoWarn>
  </PropertyGroup>

  <!-- Reference the Revit API. EITHER NuGet (cross-machine) OR HintPath (local install). -->
  <ItemGroup>
    <PackageReference Include="Revit_All_Main_Versions_API_x64" Version="2026.0.0" />
  </ItemGroup>
  <!-- OR direct file references (note Private=false — DO NOT copy these to output):
  <ItemGroup>
    <Reference Include="RevitAPI">
      <HintPath>C:\Program Files\Autodesk\Revit 2026\RevitAPI.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="RevitAPIUI">
      <HintPath>C:\Program Files\Autodesk\Revit 2026\RevitAPIUI.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
  -->

  <!-- Ship the manifest next to the DLL -->
  <ItemGroup>
    <Content Include="MyAddin.addin"><CopyToOutputDirectory>Always</CopyToOutputDirectory></Content>
  </ItemGroup>

  <!-- Icons embedded in the DLL (load via embedded-resource stream; see ui-and-interaction.md) -->
  <ItemGroup>
    <EmbeddedResource Include="Resources\icon32.png" />
  </ItemGroup>

</Project>
```

### Referencing the API: NuGet vs HintPath
- **HintPath** to the install folder (`C:\Program Files\Autodesk\Revit <version>\`) — simplest, but path is machine-specific.
- **NuGet** — `Revit_All_Main_Versions_API_x64` / `Revit.RevitApi.x64`, or the **Nice3point** packages (`Nice3point.Revit.Api.RevitAPI`, `…RevitAPIUI`) which support wildcard versions like `Version="$(RevitVersion).*"`. These set CopyLocal=false automatically and don't depend on a local install path.
- **Either way: `RevitAPI.dll`/`RevitAPIUI.dll` must NOT be copied to output** (`<Private>false</Private>`). Revit provides them; a stray copy causes "API_Error: Assembly version conflicts" (visible in Revit's journal file).

### MSB3277 / CA1416 (.NET 8 / .NET 10)
- **MSB3277** (conflicting WindowsBase/PresentationCore) → add `<FrameworkReference Include="Microsoft.WindowsDesktop.App" />`, or simply `<NoWarn>...;MSB3277</NoWarn>` as above. (Same fix applies on `net10.0-windows`.)
- **CA1416** ("platform-specific") → add `[assembly: System.Runtime.Versioning.SupportedOSPlatform("windows")]`.

## Multi-version targeting (one project → many Revit versions)

Two common approaches:

**A. Per-version build configurations + wildcard NuGet + `#if` guards.** Define configs like `Release R24;Release R25;Release R26`, parse `$(RevitVersion)` from the config name, map TFM and emit symbols (`REVIT2025`, `REVIT2025_OR_GREATER`):
```xml
<PropertyGroup Condition="$(RevitVersion) &lt; 2025"><TargetFramework>net48</TargetFramework></PropertyGroup>
<PropertyGroup Condition="$(RevitVersion) &gt;= 2025 And $(RevitVersion) &lt; 2027"><TargetFramework>net8.0-windows</TargetFramework></PropertyGroup>
<PropertyGroup Condition="$(RevitVersion) &gt;= 2027"><TargetFramework>net10.0-windows</TargetFramework></PropertyGroup>
<PropertyGroup><DefineConstants>$(DefineConstants);REVIT$(RevitVersion)</DefineConstants></PropertyGroup>
<ItemGroup>
  <PackageReference Include="Nice3point.Revit.Api.RevitAPI"   Version="$(RevitVersion).*" />
  <PackageReference Include="Nice3point.Revit.Api.RevitAPIUI" Version="$(RevitVersion).*" />
</ItemGroup>
```
```csharp
#if REVIT2025_OR_GREATER
    long id = element.Id.Value;            // .NET 8 / 64-bit id path
#else
    int id = element.Id.IntegerValue;      // legacy path
#endif
```

**B. The Nice3point.Revit.Sdk** encapsulates all of (A) in one line — it maps TFMs (2021-2024=`net48`, 2025-2026=`net8.0-windows`, 2027+=`net10.0-windows`), emits the `REVIT####_OR_GREATER` symbols, resolves API NuGet versions, and can auto-deploy and launch Revit:
```xml
<Project Sdk="Nice3point.Revit.Sdk/<latest>">
  <PropertyGroup>
    <Configurations>Debug R24;Debug R25;Debug R26;Debug R27;Release R24;Release R25;Release R26;Release R27</Configurations>
    <PublishAddin>true</PublishAddin>   <!-- auto-copy .addin + DLL to Addins folder -->
    <LaunchRevit>true</LaunchRevit>     <!-- F5 launches Revit -->
  </PropertyGroup>
</Project>
```

## Terminal-only build–deploy–test loop (no Visual Studio)

A full edit→build→run cycle driven from Claude Code + the shell, no IDE required. `dotnet` builds, the post-build `DeployAddin` target deploys, and **RevitAddInManager** provides the fast reload that F5-in-Visual-Studio used to.

**One-time setup**
- Install the **.NET 10 SDK** (Revit 2027 / `net10.0-windows`).
- Install **RevitAddInManager** (github.com/chuongmep/RevitAddInManager): its installer drops the add-in into `%AppData%\Autodesk\Revit\Addins\<year>\`; **v1.6.2 (May 2026) supports Revit 2027**. It then appears in Revit under **Add-Ins → Add-In Manager**.

**Inner loop — command logic, Revit stays open:**
1. Edit in Claude Code.
2. `dotnet build MyRevitAddin\MyRevitAddin.csproj -c Debug` → produces `bin\Debug\net10.0-windows\MyRevitAddin.dll`.
3. In Revit: **Add-Ins → Add-In Manager → Load** that DLL, select your `IExternalCommand`, **Run**. After each rebuild press **F5** in Add-In Manager to reload the fresh DLL.

Why `dotnet build` doesn't fail while Revit is open: Add-In Manager loads the command assembly **into memory** instead of holding your build output locked, so the rebuild can overwrite the DLL freely. (By contrast, if Revit loaded your add-in normally via its `.addin` at startup, that deployed copy is locked and rebuilding to it throws a file-in-use error — exactly the problem Add-In Manager exists to solve.)

> **Limitation — Add-In Manager runs `IExternalCommand` only.** It does **not** execute `IExternalApplication.OnStartup`, so it won't build or refresh your ribbon. During iteration, invoke the command class directly through Add-In Manager and treat the ribbon as a production-install concern.

**Outer loop — ribbon / `OnStartup` / `.addin` changes, needs a restart:**
1. `dotnet build` (the `DeployAddin` target copies the `.addin` + DLL to `%AppData%\Autodesk\Revit\Addins\<year>\`).
2. Close Revit if it's open (the startup-loaded DLL is locked), then launch:
   ```powershell
   & "C:\Program Files\Autodesk\Revit 2027\Revit.exe"
   ```
3. Your ribbon tab/buttons appear; exercise them.

**Notes**
- **.NET Hot Reload** (which Add-In Manager leverages) applies method-*body* edits without even a reload; new types or changed signatures still need the F5 reload.
- `dotnet watch` adds nothing here — Revit can't pick up changes without the reload/restart step, so a plain `dotnet build` is what you want.
- This loop needs **no debugger**. For breakpoints, attach a managed debugger to `Revit.exe` (see Debugging below) — works from VS Code (`netcoredbg`/`vsdbg`) as well as Visual Studio.

## Debugging (breakpoints)

- **F5 into Revit:** add `Properties\launchSettings.json` with a profile that launches `Revit.exe`:
  ```json
  { "profiles": { "Revit": { "commandName": "Executable",
      "executablePath": "C:\\Program Files\\Autodesk\\Revit 2027\\Revit.exe" } } }
  ```
  Build first (post-build copies the `.addin`/DLL), then F5 starts Revit and attaches the debugger.
- **Attach to a running Revit:** Debug → Attach to Process → `Revit.exe`, attach to **Managed code only** (attaching native too can prevent clean detach).
- **Reload a command without restarting Revit:** use **RevitAddInManager** (the maintained revival of the Revit SDK's *AddInManager* sample) — it loads/reloads an `IExternalCommand` DLL while Revit stays open. See the terminal-only loop above for the full cycle. (Note: this is **not** Autodesk's built-in *Revit Add-Ins Manager*, which only enables/disables add-ons and applies on next launch.)

## Deploy / Install

**Dev deploy via post-build copy** (MSBuild target appended to the `.csproj`):
```xml
<Target Name="DeployAddin" AfterTargets="Build">
  <PropertyGroup>
    <!-- Per-user path; unchanged in 2027. Set to your target Revit year. -->
    <AddinDir>$(AppData)\Autodesk\Revit\Addins\2027</AddinDir>
  </PropertyGroup>
  <MakeDir Directories="$(AddinDir)" />
  <Copy SourceFiles="$(TargetPath)" DestinationFolder="$(AddinDir)\$(AssemblyName)" />
  <Copy SourceFiles="$(TargetDir)$(AssemblyName).addin" DestinationFolder="$(AddinDir)" />
</Target>
```
(Point the `.addin`'s `<Assembly>` at the copied DLL, or use a relative path.) Classic .NET Framework projects often use an `xcopy` post-build event instead.

**Bundle format (recommended for the App Store / multi-version):** a `*.bundle` folder with `PackageContents.xml`, deployed under `%ProgramData%\Autodesk\ApplicationPlugins\`. One bundle can auto-load the right DLL per Revit version. (This `ApplicationPlugins` bundle path is distinct from the per-version `Addins\<year>` manifest folder, whose **all-users** location moved to `%ProgramFiles%` in Revit 2027 — see the 2027 deployment note above.)

**Installers:** WiX (max control, signs MSI + bundle), Inno Setup (simple), or Advanced Installer (GUI). **Autodesk App Store** requires the package be **Authenticode code-signed** and pass validation.

## SDK & Inspection Tools

- **Revit SDK** — not bundled; download per version from the Revit Developer Centre / APS. Contains `RevitAPI.chm` docs and 100+ C# sample projects (mirrored at github.com/jeremytammik/RevitSdkSamples).
- **RevitLookup** (github.com/lookup-foundation/RevitLookup) — essential interactive snoop tool for elements/parameters/database; supports Revit 2026/2027; install via MSI/WinGet. Sister tool **RevitDBExplorer** also edits.

## Common Build Gotchas
- **API/runtime mismatch** — `net48` DLL in 2025+ (or `net8.0` in ≤2024) silently fails to load.
- **Copied API DLLs** — `Private=false` always; otherwise version-conflict load errors.
- **MSB3277** under .NET 8 → `FrameworkReference Microsoft.WindowsDesktop.App` or `NoWarn`.
- **Dependency "DLL hell"** — Revit loads all add-ins into one process; if two add-ins reference different versions of a shared lib (classic: Newtonsoft.Json), the first loaded wins. .NET 6+ removed AppDomain isolation — isolate dependencies in a helper assembly or use `AssemblyLoadContext`; RevitToolkit also helps resolve this.
- **"Assembly already loaded" / file-in-use on rebuild** during dev — Revit locks a DLL it loaded at startup; either close Revit before rebuilding, or load/reload the command via **RevitAddInManager** (see the terminal-only loop) so your build output is never locked.

## Sources
- Autodesk: Migrating From .NET 4.8 to .NET 8 (help.autodesk.com, Revit 2025 Dev Guide); blog.autodesk.io "Migrating from .NET 4.8 to .NET Core 8".
- blog.autodesk.io "Revit 2027 SDK: .NET 10 Migration and Key API Changes" (TFM, Program Files install path, add-in isolation/dependency manifest, cloud-region + removed APIs).
- Autodesk Help: "Migrating Revit to .NET 10 (What's New in 2027)", help.autodesk.com/view/RVT/2027/ENU.
- APS blog: "Call for preview testing — Revit 2026/2025 migration to .NET 10" (the now-shipped back-port).
- Nice3point/RevitTemplates wiki (Multiple Revit Versions, MsBuild Sdk); NuGet `Revit_All_Main_Versions_API_x64`, `Nice3point.Revit.Api.*`.
- Real reference project: HM `02-2-digital-interfaces-revit` (DokwoodRevit) — `net8.0-windows`, NoWarn MSB3277, post-build xcopy of `.addin` to `…\Addins\2026`.
