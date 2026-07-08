# GH_Component Lifecycle and GH_AssemblyInfo

## Overview

Every compiled Grasshopper plugin requires exactly two classes:

- **`GH_Component` subclass** — the logic unit the author writes; one subclass per component. Grasshopper instantiates it, calls its lifecycle methods, and draws it on the canvas.
- **`GH_AssemblyInfo` subclass** — the plugin's identity card; exactly one per `.gha` assembly. Grasshopper reads it at load time to register the assembly, display it in the plugin manager, and uniquely identify it across installations.

Both classes are required. Omitting `GH_AssemblyInfo` causes Grasshopper to silently ignore the assembly or fail at load. You may put both classes in a single `.cs` file or in separate files — convention is separate files (e.g. `MidPointComponent.cs` and `CurveUtilsInfo.cs`).

---

## The Five Required Overrides for GH_Component

Verified against the Grasshopper SDK guide at `developer.rhino3d.com/guides/grasshopper/simple-component/`.

### 1. Constructor

The constructor calls the five-argument base class constructor: `(name, nickname, description, category, subCategory)`. All five are strings. The constructor must be `public` with no parameters of its own.

```csharp
public MidPointComponent()
    : base(
        "MidPoint",          // component name — shown in tooltips
        "MPt",               // nickname — drawn on the canvas node
        "Returns the midpoint of a curve by normalised arc-length (t = 0.5).",
        "CurveUtils",        // tab category in the GH ribbon
        "Analyse")           // sub-category within the tab
{
}
```

Parameter order: `name`, `nickname`, `description`, `category`, `subCategory`. Getting the order wrong compiles successfully but produces a component with scrambled labels — this is a silent mistake.

### 2. RegisterInputParams

```csharp
protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
{
    pManager.AddCurveParameter("Curve", "C", "Input curve", GH_ParamAccess.item);
}
```

Each `Add*Parameter` call appends one input slot. The index of the slot is the order of registration (0, 1, 2, …). Use this index in `DA.GetData` inside `SolveInstance`.

### 3. RegisterOutputParams

```csharp
protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager pManager)
{
    pManager.AddPointParameter("Point", "P", "Midpoint of the curve", GH_ParamAccess.item);
}
```

Same indexing rule as inputs — `DA.SetData(0, ...)` writes to the first registered output.

### 4. SolveInstance

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    Curve curve = null;
    if (!DA.GetData(0, ref curve)) return;

    Point3d midpoint = curve.PointAtNormalizedLength(0.5);
    DA.SetData(0, midpoint);
}
```

`DA.GetData` returns `false` when the input is missing or invalid and has already set a component warning. Always return immediately on `false`; do not attempt to use the output value.

Note on `Curve curve = null`: this compiles correctly under the default Rhino.Templates csproj, which does **not** enable `<Nullable>enable</Nullable>`. If you add nullable annotations (`Curve? curve`) you will get warning CS8632 unless you add `<Nullable>enable</Nullable>` explicitly to the csproj — the template does not add it for you. See the scaffolding rule below.

### 5. ComponentGuid

```csharp
public override Guid ComponentGuid =>
    new Guid("D4F7A193-3BE1-4C0E-8B52-96A1E7F02C34"); // EXAMPLE ONLY — regenerate for your plugin
```

**This GUID must be unique across all Grasshopper plugins on the user's machine.** Grasshopper uses it to rewire saved `.gh` files back to the correct component after reloading. Two components sharing a GUID will conflict silently or fail to reload. See "Common failures" for examples of what *not* to do.

How to generate a real GUID:

- PowerShell: `[System.Guid]::NewGuid().ToString("D")`
- C# REPL / `dotnet-script`: `Console.WriteLine(Guid.NewGuid());`
- Online generator: `guidgenerator.com` or `uuidgenerator.net`
- Visual Studio: **Tools → Create GUID**

Copy the result and paste it into the string literal. Do not type a GUID by hand.

---

## Complete Minimal Example

```csharp
using System;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace CurveUtils
{
    public class MidPointComponent : GH_Component
    {
        public MidPointComponent()
            : base("MidPoint", "MPt",
                   "Returns the midpoint of a curve by normalised arc-length (t = 0.5).",
                   "CurveUtils", "Analyse")
        {
        }

        protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
        {
            pManager.AddCurveParameter("Curve", "C", "Input curve", GH_ParamAccess.item);
        }

        protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager pManager)
        {
            pManager.AddPointParameter("Point", "P", "Midpoint of the curve", GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess DA)
        {
            Curve curve = null;
            if (!DA.GetData(0, ref curve)) return;

            Point3d midpoint = curve.PointAtNormalizedLength(0.5);
            DA.SetData(0, midpoint);
        }

        public override Guid ComponentGuid =>
            new Guid("D4F7A193-3BE1-4C0E-8B52-96A1E7F02C34"); // EXAMPLE ONLY — regenerate for your plugin
    }
}
```

---

## GH_AssemblyInfo Minimum

Verified against the Grasshopper SDK API reference at `mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_AssemblyInfo.htm`.

`GH_AssemblyInfo` is an abstract class. You must subclass it exactly once per assembly. The minimum set of members to override:

```csharp
using System;
using System.Drawing;
using Grasshopper.Kernel;

namespace CurveUtils
{
    public class CurveUtilsInfo : GH_AssemblyInfo
    {
        public override string Name => "CurveUtils";

        public override string Description => "Curve analysis utilities for Grasshopper.";

        public override Bitmap Icon => null; // see [[icons.md]] for generation and loading

        public override string AuthorName => "Your Name";

        public override string AuthorContact => "you@example.com";

        public override string AssemblyVersion => "1.0.0";

        // Id is computed from Name by default; override it with a stable GUID
        // to ensure Grasshopper can always uniquely identify this assembly.
        public override Guid Id =>
            new Guid("8C3A1F07-D924-4B67-A05E-72F8C3D6B14A"); // EXAMPLE ONLY — regenerate for your plugin
    }
}
```

### Properties that matter

| Property | Purpose |
|---|---|
| `Name` | Shown in Grasshopper's plugin manager |
| `Description` | Tooltip in the plugin manager |
| `Icon` | 24×24 bitmap shown in the plugin manager; `null` is acceptable for development — see `[[icons.md]]` |
| `AuthorName` | Displayed in the plugin manager |
| `AuthorContact` | Displayed in the plugin manager |
| `AssemblyVersion` | Version string shown in the plugin manager |
| `Id` | A stable, unique GUID for this assembly — see below |

### Why `Id` must be freshly generated — and what "freshly generated" actually means

`Id` defaults to a hash of `Name`. Overriding it with a stable, unique `Guid` is recommended because:

1. Two differently-named plugins that happen to collide on the hash would still conflict.
2. If you rename the plugin later, the `Id` hash changes and Grasshopper loses the association with saved files.

**Freshly generated means: produced by a GUID generator at the time you create the plugin, not typed from memory, not incremented from a sample, not copied from documentation.**

A real random GUID looks like this (the hex digits have no pattern): `8C3A1F07-D924-4B67-A05E-72F8C3D6B14A`

Patterned GUIDs that *look* generated but are not:

```
b2c3d4e5-f6a7-8901-bcde-f12345678902   ← sequential hex digits — NOT random
a1b2c3d4-e5f6-7890-abcd-ef1234567890   ← ascending pairs — NOT random
00000000-0000-0000-0000-000000000000   ← all zeros — invalid
```

These patterns indicate the GUID was hand-typed. Grasshopper may still load the plugin, but if another developer copies the same sample and ships a plugin with the same patterned GUID, both plugins will conflict on any machine that has them installed.

Use one of the generation methods listed in the ComponentGuid section above. Paste the result directly.

---

## Project Scaffolding Rule

**Always scaffold with the official template. Never hand-roll a csproj.**

```powershell
# Install the template package (once per machine)
dotnet new install Rhino.Templates

# Scaffold a new Grasshopper plugin project
dotnet new grasshopper -n CurveUtils
cd CurveUtils
```

The template produces a working csproj immediately. Hand-rolling a csproj is error-prone and wastes time. The template-produced csproj includes all the correct properties and package references.

### Important properties in the template-produced csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net7.0-windows</TargetFramework>
    <TargetExt>.gha</TargetExt>
    <!-- <Nullable>enable</Nullable> is NOT present — see note below -->
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Grasshopper" Version="..." />
    <PackageReference Include="RhinoCommon" Version="..." />
  </ItemGroup>
</Project>
```

Key facts:

- `TargetFramework=net7.0-windows` — required for Rhino 8 compatibility. Do not use `net6.0`, `net8.0`, or a framework-only target like `net7.0`.
- `TargetExt=.gha` — changes the output extension from `.dll` to `.gha`. Without this, Grasshopper will not recognise the file as a plugin.
- `Grasshopper` and `RhinoCommon` NuGet packages — both must come from the McNeel feed; do not invent package names.

### Nullable annotations and CS8632

The Rhino.Templates output does **not** enable `<Nullable>enable</Nullable>` by default. This means:

- Code like `Curve curve = null;` compiles without warnings (correct for the default template).
- Code like `Curve? curve = null;` produces warning **CS8632** ("The annotation for nullable reference types should only be used in code within a `#nullable` annotations context") unless you explicitly add `<Nullable>enable</Nullable>` to your `<PropertyGroup>`.

If you want nullable annotations throughout the project, add `<Nullable>enable</Nullable>` yourself. Be aware this changes the semantics of all reference types in the project and will require updating the existing template-generated code. For most plugins, leaving nullable disabled and using the `if (!DA.GetData(...)) return;` pattern is simpler.

Template version note: the nullable setting may vary across Rhino.Templates releases. If in doubt, inspect your generated `.csproj` file directly after running `dotnet new grasshopper`. Do not assume.

---

## Post-Build Deploy

The Rhino.Templates post-build target automatically copies the compiled `.gha` to `%APPDATA%\Grasshopper\Libraries\` after each successful build. Rhino reads that directory at startup.

### What `dotnet build` actually outputs

A successful build prints something like:

```
Build succeeded.
    0 Warning(s)
    0 Error(s)

Time Elapsed 00:00:03.45
```

MSBuild does **not** print a `Copying ...` diagnostic line for the post-build copy. The copy runs silently. You will not see a line like:

```
Copying CurveUtils.gha → %APPDATA%\Grasshopper\Libraries\   ← this line does NOT appear
```

This fabricated line has appeared in AI-generated transcripts. It does not exist in actual MSBuild output.

### How to confirm the .gha was produced

After `dotnet build` exits 0, look in:

1. **Build output directory:** `bin\Debug\net7.0-windows\CurveUtils.gha` (or `bin\Release\...` for release builds). The `.gha` extension confirms `TargetExt` worked correctly.
2. **Deploy directory:** `%APPDATA%\Grasshopper\Libraries\CurveUtils.gha`. If the post-build target ran, this file's timestamp matches the build time.

If the file exists in `bin\` but not in `%APPDATA%\Grasshopper\Libraries\`, the post-build target did not run (permissions issue, or the target was removed from the csproj). You can copy manually until the issue is diagnosed.

---

## Common Failures

These failures are drawn directly from the RED baseline catalogue (`tests/baseline/curve-utils.md`, `[component-lifecycle]` findings). Each finding is paired with the corrected pattern.

---

### Failure 1: Patterned GUID in ComponentGuid (Sonnet)

**What the agent did** (`runs/2026-05-17-sonnet-4-6.md` lines 62–69):

```csharp
// Agent wrote this:
public override Guid ComponentGuid =>
    new Guid("b2c3d4e5-f6a7-8901-bcde-f12345678902");
```

Five lines later the same agent wrote: "The GUID must be freshly generated — never copied from a sample."

**Why it failed:** The GUID `b2c3d4e5-f6a7-8901-bcde-f12345678902` is a sequential run of hex bytes (`b2`, `c3`, `d4`, `e5` …). No real UUID generator produces this. The agent composed it mentally, which defeats the purpose of a GUID. The self-contradictory assertion ("freshly generated") that immediately followed shows the agent was reasoning about GUIDs correctly in prose but ignoring its own advice in code.

**Corrected approach:** Generate using `[System.Guid]::NewGuid().ToString("D")` in PowerShell or the Visual Studio **Tools → Create GUID** menu. Paste the result verbatim. Do not type hex digits by hand.

---

### Failure 2: Fabricated MSBuild "Copying" output line (Sonnet)

**What the agent did** (`runs/2026-05-17-sonnet-4-6.md` lines 83–87):

```
CurveUtils -> bin\Release\net7.0-windows\CurveUtils.gha
Copying CurveUtils.gha → %APPDATA%\Grasshopper\Libraries\
```

The agent presented this as the expected output of `dotnet build`.

**Why it failed:** MSBuild does not emit a `Copying ...` message for post-build copy targets. The agent fabricated console output it had never observed. A developer following this output would waste time searching for a log line that will never appear.

**Corrected approach:** After `dotnet build` succeeds, verify the deploy by checking the file system directly (see "Post-Build Deploy" section above). Do not predict or reproduce build output from training data.

---

### Failure 3: Patterned GUID in GH_AssemblyInfo (Opus)

**What the agent did** (`runs/2026-05-17-opus-4-5.md` lines 76–77):

```csharp
// Agent wrote this:
public override Guid Id =>
    new Guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890");
```

And two lines later (line 109): "The GUID must be freshly generated (not all-zeros, not copied from samples)."

**Why it failed:** `a1b2c3d4-e5f6-7890-abcd-ef1234567890` is an ascending sequence of hex nibbles. Same failure mode as Sonnet: mentally composed, not generated. Same self-contradiction.

**Corrected approach:** Same as Failure 1. Generate, paste, do not type.

---

### Failure 4: Fabricating template file contents from training data (Opus)

**What the agent did** (`runs/2026-05-17-opus-4-5.md` lines 88–106):

The agent wrote out the complete contents of `CurveUtilsInfo.cs` — including an invented GUID `d8e9f0a1-b2c3-4d5e-6f7a-8b9c0d1e2f3a`, invented property values, and a comment "The template creates a `CurveUtilsInfo.cs` file" — without having run `dotnet new grasshopper`. The agent hallucinated the template's output from training-data patterns.

**Why it failed:** The agent asserted facts about what the template generates (exact file names, property values, GUIDs) without executing the template. This is particularly dangerous because:

1. Template output changes across Rhino.Templates versions.
2. The invented GUID was again patterned (ascending nibble pairs).
3. Any agent reading this transcript would learn the wrong template behavior.

**Corrected approach:** Always run `dotnet new grasshopper` and inspect the actual output. Do not predict template-generated file contents from training data. If you cannot run the template, explicitly state that you are providing a skeleton that must be reconciled against actual template output.

---

### Failure 5: Fabricated MSBuild "Copying" output line (Opus)

**What the agent did** (`runs/2026-05-17-opus-4-5.md` lines 119–123):

```
CurveUtils -> bin\Release\net7.0-windows\CurveUtils.gha
Copying CurveUtils.gha → %APPDATA%\Grasshopper\Libraries\
```

Same fabrication as Failure 2, independent agent, same transcript form.

**Why it failed:** Both Sonnet and Opus independently produced this non-existent output line. This suggests it is a training-data artifact — possibly from a forum post or documentation draft that described the intent of the post-build target in prose that was then mistakenly learned as console output. Neither agent ran `dotnet build`.

**Corrected approach:** Same as Failure 2. Never reproduce build output from memory. Verify by running the build.

---

### What these failures have in common

All five failures share the same root cause: **asserting volatile, generated, or runtime-observable facts from training-data memory instead of generating or observing them.** GUIDs must be generated. Build output must be observed. Template file contents must be produced by the template. When any of these is impossible in the current environment (e.g. sandbox restrictions), state that explicitly and hand off to the user — do not substitute a hypothetical.

---

## Cross-links

See also:
- `[[params-and-registration.md]]` for input/output param type selection, `GH_ParamAccess` modes, and the `DA.GetData` nullability contract.
- `[[icons.md]]` for icon design rules, programmatic generation with Python/Pillow, `IconLoader` utility, and embedding icons as assembly resources.
- `[[yak-packaging.md]]` for distribution: `manifest.yml`, package icon, `yak build` / `yak push`, and version semantics.
- `[[dev-guide-index.md]]` for the Grasshopper SDK API URL (`mcneel.github.io/grasshopper-api-docs`) and RhinoCommon API URL — use these to verify any signature before asserting it.
