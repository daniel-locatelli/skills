---
name: creating-grasshopper-plugin
description: Use for ANY task in a Grasshopper plugin (.gha) project — creating or editing components, changing icons, building, deploying or installing locally, scaffolding, multi-targeting .NET, packaging with Yak, or debugging load failures. If the repo produces a .gha, this skill applies.
---

# Creating a Grasshopper Plugin

## Overview

Build compiled Grasshopper plugins (`.gha`) for Rhino 8. Core principle: scaffold from `Rhino.Templates`, verify the build actually ran, print-debug with `RhinoApp.WriteLine`, hand off to Visual Studio for breakpoints.

## When to use / When NOT to use

- **Use:** compiled `.gha`, Rhino 7/8, .NET Framework 4.8 / .NET 7–8, Windows and Mac; `GH_Component` work; multi-target builds; Yak distribution; load-failure diagnosis.
- **NOT for:** scripted components (GHPython / C# script), `.rhp` plugins, Hops, interactive debugger control. Different skills, different tools.

## Workflow phases

1. **Scaffold** — `dotnet new install Rhino.Templates`; `dotnet new grasshopper`. *Verify:* csproj has `TargetFramework=net7.0-windows` and `TargetExt=.gha`.
2. **Minimal viable component** — one component, primitive in/primitive out. *Verify:* `dotnet build` exits 0.
3. **Deploy locally** — copy build output to `%APPDATA%\Grasshopper\Libraries\<PluginName>\`, restart Rhino. *Verify:* component appears in Grasshopper's palette. See `references/local-deploy.md`.
4. **Real geometry** — RhinoCommon `Curve`/`Brep`/`Mesh`; document units and tolerance. *Verify:* run a real curve through it in Rhino.
5. **Iterate** — data trees, exceptions, edge cases. Extract logic into static helpers. *Verify:* unit tests pass.
6. **Package** — `manifest.yml`, icon, version. *Verify:* `yak build` produces a `.yak`; `yak push` only when releasing.

## Edit cycle (every change)

The workflow phases above are milestones. This cycle runs on **every edit**:

1. `dotnet build` — must exit 0.
2. Copy full build output to `%APPDATA%\Grasshopper\Libraries\<PluginName>\`. See `references/local-deploy.md`.
3. Close and reopen Rhino (assemblies don't hot-reload).
4. Verify the change on the Grasshopper canvas.

Do not report work as complete until step 4. "Build succeeded" is compilation, not verification — the component must appear, wire correctly, and behave as expected.

## Decision point: scripted vs. compiled

If you catch yourself thinking "I'll just write a Python component" — stop. This skill is for compiled `.gha`; scripted components are a different surface.

## Reference index

| Symptom | File |
|---|---|
| Component shape, `GH_AssemblyInfo`, GUID, scaffolding | `references/component-lifecycle.md` |
| `Param_*` choice, `GH_ParamAccess`, `DA.GetData`/`SetData` | `references/params-and-registration.md` |
| Tree iteration, `GH_Structure`, paths, branches | `references/data-trees.md` |
| Hardcoded tolerance, unit conversions, planarity | `references/geometry-units-and-tolerance.md` |
| Parallel solver, main-thread APIs, `RhinoDoc.ActiveDoc`, manual async | `references/threading-and-the-main-thread.md` |
| `GH_PersistentParam`, custom attributes, GDI+ buttons, `Read`/`Write` | `references/persistence-and-attributes.md` |
| Icon design rules, Python generation, embedding in build | `references/icons.md` |
| Build+copy deploy loop, restart requirement, dependency pitfalls | `references/local-deploy.md` |
| Multi-target csproj, TFM mapping, Mac support, conditional WinForms | `references/multi-target-multi-os.md` |
| `manifest.yml`, icon, `yak build`/`push`, versioning | `references/yak-packaging.md` |

## Red flags / common mistakes

- *"I'll describe what I would have done."* — Fail fast; surface blocked criteria, don't self-certify a hypothetical.
- *"Cannot verify build, but solution is correct."* — Binary criteria (compile, scaffold) stay **unverified**, not ✓.
- *"`new Guid("a1b2c3d4-e5f6-...")` — freshly generated."* — Patterned GUIDs are not random. **Before** writing the file, run `[guid]::NewGuid()` (PowerShell) or `uuidgen` and paste into **both** `ComponentGuid` and `GH_AssemblyInfo.Id`.
- *"Here is the MSBuild log I expect."* — Don't invent tool output. Run the tool or say you didn't.
- *"Build succeeded, so it works."* — Compilation checks types. Deploy and test check behavior. Always complete the edit cycle.
- *"I'll just write a Python component."* — Wrong skill.

## Retrieval pointers

- `retrieval/search-discourse.md` — volatile, version-dependent, or template-output claims (consult **before** asserting from training).
- `retrieval/dev-guide-index.md` — stable canonical APIs and URL map for `developer.rhino3d.com`.
