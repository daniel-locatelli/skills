# Resources, Ecosystem & Production Best Practices

## APS vs Desktop API vs Design Automation (the most-confused distinction)

**Autodesk Platform Services (APS)**, formerly Forge, is Autodesk's cloud developer platform (Viewer, Data Management, Model Derivative, webhooks, Automation APIs). It is **not** the desktop Revit API. Three distinct things people conflate:

- **(a) Desktop Revit API** — a **.NET API running inside Revit** on a Windows workstation. Your add-in (compiled C#, this skill's focus) plugs into the ribbon and acts on the user's open document. Right choice for interactive tools shipped to users.
- **(b) APS Design Automation / Revit Automation API** — runs **Revit headless in Autodesk's cloud**, no desktop install or license needed. You package the same DB-API logic as an "AppBundle" and trigger "WorkItems" — to validate models, extract data, batch-modify, generate docs at scale. **No UI** in the cloud (no `TaskDialog`, no `UIApplication` interaction). Docs: `aps.autodesk.com/en/docs/design-automation/v3`.
- **(c) Other APS web APIs** — work with BIM data via web, no Revit at all.

**Practical path:** build & debug the engine logic as a desktop add-in first, then repackage for Design Automation for headless/cloud scale.

### Which API to use (decision matrix)
From the AU 2025 "Moving from Revit API Add-Ins to the Design Automation API" class (Rocha/Smith/Nseir, HDR + Autodesk):
- **Updating many models, or batch material/quantity takeoff that edits** → **Automation API** (the desktop Revit API has performance problems opening/editing many files).
- **Just *reading* data / quantity takeoffs** → **APS data APIs** (AEC Data Model, Model Properties, Model Derivative, Takeoff) — no Revit engine needed.
- **Trigger inside the Revit UI needing user input** → **desktop Revit API**.

Good Automation API fits: model analytics/dashboards, batch parameter/family edits, batch project
setup (titleblocks/views/sections), batch exports (PDF/Excel/NWC). Pair with a web UI (often React)
that triggers WorkItems — "one-click" headless runs over a set of models.

### Concrete Design Automation workflow (what's actually involved)
1. **Add-in shape:** implement **`IExternalDBApplication`** (not `IExternalCommand`/`IExternalApplication`)
   and add NuGet **`Autodesk.Forge.DesignAutomation.Revit`** (the "DesignAutomation Framework").
   Subscribe to `DesignAutomationBridge.DesignAutomationReadyEvent`; its handler reads input files and
   does the Revit work. Tech stack for the cloud side is .NET **or** JavaScript; there is no UI.
2. **Local debug trick (non-obvious, valuable):** trigger the DA event locally by calling
   `DesignAutomationBridge.SetDesignAutomationReady` from a separate debug add-in named
   `DesignAutomationHandler`, with a ribbon button; conditionally load it by working directory and point
   the main add-in's working dir at the same folder. Lets you debug the headless logic in Visual Studio
   with local input files (a `Result.rvt` is written to the working dir).
3. **AppBundle:** a `*.bundle` folder containing `PackageContents.xml` + a `Contents/` folder (with the
   `.addin` + DLLs), zipped — built as a PostBuild step.
4. **Cloud lifecycle (test in Postman):** create AppBundle → alias → upload → create **Activity**
   (run-time config / parameters) → alias → get signed S3 download URLs for inputs → signed upload URL
   for output → send **WorkItem** (the job) → poll status for `success` → complete upload → create file
   versions on ACC. Auth: **2-legged** (no user data) or **3-legged** (ACC/user-specific data).
   Sample repo: github.com/nseirs/revit-automation-update-titleblocks.

Porting desktop→cloud is a **re-architecture, not a recompile** (see the core/adapter split in
`architecture.md`): decouple the headless AppBundle from an orchestration/UI tier, parallelize
independent jobs, stream long-job status, and respect platform limits (no desktop install; a Revit
Cloud Worksharing model must be downloaded **detached** then `Document.SaveAsCloudModel()`). Manage
Activities/AppBundles per Revit version. `IFailuresPreprocessor` is mandatory (a modal warning would
hang the job forever).

## Key official resources

| Resource | URL |
|----------|-----|
| Revit API Developers Guide (2027) | help.autodesk.com/view/RVT/2027/ENU/?guid=Revit_API_Revit_API_Developers_Guide_html (2026 guide still at /RVT/2026/ENU) |
| Migrating Revit to .NET 10 — What's New in 2027 | help.autodesk.com/view/RVT/2027/ENU/?guid=GUID-8D7A4715-EAF8-4BD1-BE78-061F900D0BCE |
| Revit 2027 SDK: .NET 10 migration & API changes | blog.autodesk.io/revit-2027-sdk-net-10-api-changes-and-additions/ |
| "Using the Autodesk Revit API" (getting started) | same guide, Getting Started chapter |
| My First Revit Plug-in (official tutorial) | autodesk.com support article "My First Revit Plug-in" (updated for 2025/2026) |
| APS Revit API overview | aps.autodesk.com/developer/overview/revit-api |
| Design Automation v3 docs | aps.autodesk.com/en/docs/design-automation/v3 |
| revitapidocs.com | revitapidocs.com (e.g. /2027/) — community searchable class browser; mirror rvtdocs.com |
| Revit SDK | Revit Developer Centre / APS (per version); samples: github.com/jeremytammik/RevitSdkSamples |
| Autodesk Developer Network (ADN) | paid program: priority API support, pre-release access, App Store help |

## Ecosystem tooling

| Tool | What it is |
|------|------------|
| **Nice3point/RevitTemplates** | `dotnet new` templates scaffolding modern add-ins (MVVM, DI, logging, multi-version 2020–2027; the SDK maps 2027→`net10.0-windows`). github.com/Nice3point/RevitTemplates |
| **Nice3point/RevitToolkit** | Companion lib: automatic dependency resolution (avoids `FileNotFoundException`), API helpers, context/options classes. |
| **RevitLookup** | Interactive element/parameter snoop tool — essential debugging companion. github.com/lookup-foundation/RevitLookup |
| **pyRevit** | Open-source IronPython/CPython RAD scripting env wrapping the Revit API; rapid in-Revit tooling. github.com/pyrevitlabs/pyRevit |
| **RevitAddInManager** | Load/reload add-in DLLs without restarting Revit. github.com/chuongmep/RevitAddInManager |
| **ricaun.RevitTest / AppLoader** | Multi-version NUnit testing that drives Revit; hot-reload commands. github.com/ricaun-io |

## Learning content
- **The Building Coder** (Jeremy Tammik) — the canonical Revit API blog (2,080+ posts). Now at `blog.autodesk.io/category/thebuildingcoder/`; index `jeremytammik.github.io/tbc/a/`; samples `github.com/jeremytammik/the_building_coder_samples`.
- **Autodesk Platform Services YouTube** — `@autodeskplatformservices` (APS/Design Automation tutorials).
- **Autodesk University** — `autodesk.com/autodesk-university/search?query="Revit API"` (100+ classes). Notable: "Get Started with Revit API Using Python" (2024), "Moving from Add-Ins to Design Automation" (2025).
- **Revit API forum** — forums.autodesk.com (Revit API Forum).

## Production best-practices checklist
- **Transactions:** every model edit inside a `Transaction`/`TransactionGroup`; tight, well-named; commit on success, roll back on failure. Make commands **idempotent** (check-then-create by stable key; re-running must not duplicate elements).
- **Don't block the UI thread:** the API is single-threaded and context-bound. Marshal work back via `IExternalEventHandler`/`ExternalEvent` (or `Idling`); never call the API from a worker thread.
- **Graceful failure:** wrap commands in try/catch, return `Result.Failed`/`Cancelled`, handle warnings via `IFailuresPreprocessor`. An unhandled exception that crashes/slows Revit is an explicit App Store rejection reason.
- **Version compatibility:** API is version-pinned; reference the matching `RevitAPI.dll`; multi-target for back-compat (see project-setup-and-build.md).
- **Settings/data storage:** use **ExtensibleStorage** for data that belongs *to the model* (travels with the file; needs schema GUID + versioning; beware cross-session schema conflicts; don't migrate schemas during `DocumentOpened`/`Saved` — triggers worksharing borrow issues). Use config files / user settings for *machine/user* preferences.
- **Logging:** structured logging (e.g. Serilog) to a writable per-user path — essential since you can't attach a debugger in cloud/Design Automation runs.
- **Localization:** externalize UI strings.
- **Signing & distribution:** Authenticode-sign; package as `.bundle` with `PackageContents.xml`; silent install (no manual file copying).

## Autodesk App Store submission (high level)
- Submit via **Publisher Center** (`aps.autodesk.com/app-store/publisher-center`, Revit guidelines under `/revit`).
- Review: suitability check, then ~2–3 working days of testing.
- Must: target a supported Revit version, run on any supported Windows, **work immediately after install** (no manual copying/registration), not crash or slow Revit, not collect private data without consent.
- Distribution package = code-signed `.bundle`/`PackageContents.xml`.

## Sources
APS overview & Design Automation v3 docs; Revit API Developers Guide 2027 (+ "Migrating Revit to .NET 10" / 2027 SDK blog); My First Revit Plug-in; revitapidocs.com; Nice3point RevitTemplates/RevitToolkit; RevitLookup; pyRevit; RevitAddInManager; ricaun-io; The Building Coder (blog.autodesk.io); Autodesk University class catalog; App Store Publisher Center & Product Guidelines; ExtensibleStorage best-practices (blog.autodesk.io, help.autodesk.com).
