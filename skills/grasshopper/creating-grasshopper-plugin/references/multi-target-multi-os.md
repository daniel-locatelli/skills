# Multi-Target and Multi-OS Plugins

## What Multi-Targeting Is

A single `.csproj` that compiles for more than one .NET target framework and/or operating system, producing separate outputs that Rhino and Grasshopper load based on the runtime environment. This is how one codebase supports Rhino 7, Rhino 8, Windows, and Mac simultaneously.

**Canonical developer guide:**
- Moving to .NET Core: `https://developer.rhino3d.com/guides/rhinocommon/moving-to-dotnet-core/`
- Multi-targeted Yak packages: `https://developer.rhino3d.com/guides/yak/creating-a-multi-targeted-rhino-plugin-package/`

---

## Rhino Version to TFM Mapping

| Rhino | Windows (legacy) | Windows (.NET Core) | Mac |
|---|---|---|---|
| Rhino 7 | `net48` | N/A | N/A |
| Rhino 8 (pre-8.20) | `net48` | `net7.0-windows` / `net7.0` | `net7.0` |
| Rhino 8 (8.20+) | `net48` | `net8.0-windows` / `net8.0` | `net8.0` |

Key rules:
- Mac runs **only** .NET Core (`net7.0` or `net8.0`). It does not support `net48` or `-windows` TFMs.
- The `-windows` TFM suffix enables WinForms/WPF APIs. Without it, those APIs are unavailable at compile time.
- Rhino 8 on Windows can load **either** `net48` or .NET Core assemblies. It prefers .NET Core when both are present.
- The `net48` target remains valuable even for Rhino 8-only plugins: it is required by Rhino.Inside Revit (which hosts Rhino inside the .NET Framework Revit process).

---

## Choosing Your Target Frameworks

### Rhino 8 only, no WinForms (simplest)

```xml
<TargetFrameworks>net8.0;net48</TargetFrameworks>
```

The `net8.0` output works on both Windows and Mac. The `net48` output is the Windows legacy fallback.

### Rhino 8 only, with WinForms on Windows

```xml
<TargetFrameworks>net8.0-windows;net8.0;net48</TargetFrameworks>
```

Three targets: `net8.0-windows` for Windows with WinForms, `net8.0` for Mac (compiles against WinForms reference assemblies that Rhino provides at runtime), `net48` for Windows legacy.

### Rhino 7 + 8, no WinForms

```xml
<TargetFrameworks>net8.0;net48</TargetFrameworks>
```

Same as Rhino 8-only — Rhino 7 uses the `net48` output, Rhino 8 uses the `net8.0` output.

### Rhino 7 + 8, with WinForms

```xml
<TargetFrameworks>net8.0-windows;net8.0;net48</TargetFrameworks>
```

---

## Essential csproj Properties

```xml
<PropertyGroup>
  <TargetFrameworks>net8.0-windows;net8.0;net48</TargetFrameworks>
  <TargetExt>.gha</TargetExt>
  <EnableDynamicLoading>true</EnableDynamicLoading>
  <EnableWindowsTargeting>true</EnableWindowsTargeting>
  <NoWarn>NU1701;NETSDK1086</NoWarn>
</PropertyGroup>
```

| Property | Why |
|---|---|
| `EnableDynamicLoading` | Required for Grasshopper to load the `.gha` as a plugin at runtime. |
| `EnableWindowsTargeting` | Allows building the `-windows` TFM on non-Windows machines (Mac/Linux CI). |
| `NU1701` | Suppresses warnings about net48-targeted NuGet packages restored for .NET Core. The Grasshopper NuGet ships net48 libs; this warning is expected. |
| `NETSDK1086` | Suppresses warnings about Windows-specific TFMs. |

---

## Conditional WinForms

WinForms is only available on Windows targets. Use MSBuild conditions — not preprocessor directives — to enable it:

```xml
<PropertyGroup Condition="$(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4'))">
  <UseWindowsForms>true</UseWindowsForms>
</PropertyGroup>
```

This activates WinForms for `net8.0-windows` (explicitly Windows) and `net48` (implicitly Windows).

### Mac: compile-time WinForms references

Rhino on Mac provides its own `System.Windows.Forms.dll` at runtime. To compile WinForms code for the plain `net8.0` target (Mac), pull in compile-only reference assemblies:

```xml
<ItemGroup Condition="!($(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4')))">
  <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net48"
                    Version="1.0.3"
                    ExcludeAssets="all"
                    GeneratePathProperty="true" />
  <Reference Include="$(PkgMicrosoft_NETFramework_ReferenceAssemblies_net48)\build\.NETFramework\v4.8\System.Windows.Forms.dll"
             Private="False" />
  <PackageReference Include="System.Drawing.Common"
                    Version="8.0.0"
                    ExcludeAssets="runtime" />
</ItemGroup>
```

This provides the types at compile time. At runtime, Rhino on Mac supplies the actual implementations. The `Private="False"` and `ExcludeAssets="runtime"` ensure nothing is copied to output — Rhino provides these assemblies.

For Rhino 8.11+, a simpler alternative exists:

```xml
<FrameworkReference Include="Microsoft.WindowsDesktop.App.WindowsForms" />
```

---

## NuGet Package References

### Grasshopper and RhinoCommon

Always exclude runtime assets — Rhino provides these assemblies:

```xml
<ItemGroup>
  <PackageReference Include="Grasshopper" Version="8.*" ExcludeAssets="runtime" />
</ItemGroup>
```

For plugins that must also support Rhino 7, use conditional references with different SDK versions:

```xml
<ItemGroup Condition="$(TargetFramework.StartsWith('net4'))">
  <PackageReference Include="Grasshopper" Version="7.0.20314.3001" ExcludeAssets="runtime" />
</ItemGroup>

<ItemGroup Condition="!$(TargetFramework.StartsWith('net4'))">
  <PackageReference Include="Grasshopper" Version="8.0.23304.9001" ExcludeAssets="runtime" />
</ItemGroup>
```

### Framework polyfills for net48

.NET Framework 4.8 lacks many modern APIs. Add polyfill packages conditionally:

```xml
<ItemGroup Condition="'$(TargetFramework)' == 'net48'">
  <PackageReference Include="System.Text.Json" Version="10.0.3" />
  <PackageReference Include="System.Net.Http" Version="4.*" />
</ItemGroup>
```

On .NET 8, these are built-in and must not be added as packages.

---

## Core / Shared Library Projects

If your plugin has a separate core library (business logic, API clients), that library does not need the `-windows` TFM:

```xml
<!-- Core.csproj -->
<TargetFrameworks>net8.0;net48</TargetFrameworks>
```

Only the `.gha` project — which references Grasshopper UI types — needs the three-target split. The core library targets the platform-neutral TFMs.

---

## Preprocessor Directives

The .NET SDK auto-defines symbols for each TFM. Use the `_OR_GREATER` variants to write forward-compatible branches:

| TFM | Auto-Defined Symbols |
|---|---|
| `net48` | `NET48`, `NETFRAMEWORK`, `NET48_OR_GREATER` |
| `net8.0` | `NET8_0`, `NET`, `NETCOREAPP`, `NET8_0_OR_GREATER` |
| `net8.0-windows` | `NET8_0_WINDOWS`, `NET8_0`, `WINDOWS`, `NET8_0_OR_GREATER` |

Example:

```csharp
#if NETFRAMEWORK
    // Rhino 7 / .NET Framework code path
#elif NET8_0_OR_GREATER
    // Rhino 8 / .NET 8 code path
#endif
```

**Prefer MSBuild conditions over preprocessor directives.** Platform branching in the csproj (conditional `PropertyGroup` and `ItemGroup`) keeps the C# code unified. Reserve `#if` for cases where the actual code logic must diverge — not for selecting references or packages.

---

## Build Output Structure

A multi-target build produces separate output directories:

```
bin\Release\net48\            → Rhino 7 Windows / Rhino 8 legacy
bin\Release\net8.0\           → Rhino 8 Mac / Rhino 8 Windows (cross-platform)
bin\Release\net8.0-windows\   → Rhino 8 Windows (with WinForms)
```

Each directory contains a complete set of the `.gha` and its dependencies. For local deploy, copy the correct directory for your Rhino version. See `[[local-deploy.md]]`.

---

## Yak Packaging for Multi-Target

A multi-target `.yak` package uses framework subdirectories with a single `manifest.yml` at the root:

```
my-plugin-1.0.0-rh8-any.yak
  manifest.yml
  net48/
    MyPlugin.gha
    SomeDependency.dll
  net8.0/
    MyPlugin.gha
    SomeDependency.dll
```

### Building the package

1. Create a staging directory with the framework subdirectories and `manifest.yml`.
2. Run `yak build` from that staging directory.

Yak detects the multi-target layout and produces a single `.yak` with distribution tag `rh8_0-any`. For platform-specific packages:

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" build --platform win
& "C:\Program Files\Rhino 8\System\Yak.exe" build --platform mac
```

### Rhino 7 + 8 packaging

Produce **two separate `.yak` files**: one for Rhino 8 (multi-targeted with net48 + net8.0) and one for Rhino 7 (net48 only). Push them separately. Rhino 7's Package Manager only sees packages tagged `rh7*`; Rhino 8's only sees `rh8*`.

See `[[yak-packaging.md]]` for manifest fields, versioning, and push workflow.

---

## Plugin GUID

Use a **single GUID** across all targets. Grasshopper identifies plugins by GUID, not by filename or framework. All three outputs (net48, net8.0, net8.0-windows) share the same `GH_AssemblyInfo.Id` and `ComponentGuid` values.

Do not generate separate GUIDs per target — Grasshopper would treat them as different plugins, causing duplicate entries in the palette if multiple targets are loaded.

---

## Gotchas

### System.Drawing.Common on Mac

Since .NET 6, `System.Drawing.Common` is Windows-only by default. On Mac, McNeel provides its own implementation at runtime. For compilation, use the reference-assembly workaround in the "Conditional WinForms" section above. Do not set `System.Drawing.EnableUnixSupport` — Rhino handles this internally.

### AnyCPU required for Mac

Mac requires `AnyCPU` platform target (Apple Silicon / Intel Universal Binary support). Do not use `x64` or `x86` platform targets. The default SDK project setting is already `AnyCPU`.

### C# language version on net48

.NET Framework 4.8 defaults to C# 7.3. You can set `<LangVersion>10.0</LangVersion>` for syntactic features (file-scoped namespaces, pattern matching), but runtime-dependent features (default interface implementations, `Span<T>`-based APIs) remain unavailable on net48.

### Rhino.Inside Revit

Plugins that must work inside Rhino.Inside Revit **must** include a `net48` target. Revit runs on .NET Framework; the .NET Core targets will not load in that host.

### Transitive targets from RhinoCommon NuGet

RhinoCommon's MSBuild `.targets` files are non-transitive (placed in the NuGet `/build` folder). If you have a library project that references RhinoCommon, and your `.gha` project references that library, the targets may not flow through. Fixed in Rhino 8 SR22+ with `buildTransitive` support. For earlier versions, use `GeneratePathProperty="true"` as a workaround.

### EnableWindowsTargeting on CI

If your CI runs on Linux or Mac, the `-windows` TFM will fail to build without `<EnableWindowsTargeting>true</EnableWindowsTargeting>`. Add this unconditionally — it is harmless on Windows.

---

## Complete Example csproj

A Rhino 8 plugin targeting Windows + Mac with WinForms support:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFrameworks>net8.0-windows;net8.0;net48</TargetFrameworks>
    <TargetExt>.gha</TargetExt>
    <EnableDynamicLoading>true</EnableDynamicLoading>
    <EnableWindowsTargeting>true</EnableWindowsTargeting>
    <NoWarn>NU1701;NETSDK1086</NoWarn>
    <Version>1.0.0</Version>
  </PropertyGroup>

  <!-- WinForms on Windows targets only -->
  <PropertyGroup Condition="$(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4'))">
    <UseWindowsForms>true</UseWindowsForms>
  </PropertyGroup>

  <!-- Mac: compile-time WinForms references (Rhino provides runtime impl) -->
  <ItemGroup Condition="!($(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4')))">
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net48"
                      Version="1.0.3" ExcludeAssets="all" GeneratePathProperty="true" />
    <Reference Include="$(PkgMicrosoft_NETFramework_ReferenceAssemblies_net48)\build\.NETFramework\v4.8\System.Windows.Forms.dll"
               Private="False" />
    <PackageReference Include="System.Drawing.Common" Version="8.0.0" ExcludeAssets="runtime" />
  </ItemGroup>

  <!-- Grasshopper SDK — excluded from runtime (Rhino provides it) -->
  <ItemGroup>
    <PackageReference Include="Grasshopper" Version="8.*" ExcludeAssets="runtime" />
  </ItemGroup>
</Project>
```

---

## Cross-links

See also:
- `[[local-deploy.md]]` for deploying multi-target outputs to the correct Libraries subfolder.
- `[[yak-packaging.md]]` for single-target packaging; the "Yak Packaging for Multi-Target" section above extends it.
- `[[component-lifecycle.md]]` for `GH_AssemblyInfo`, GUID, and assembly metadata shared across targets.
