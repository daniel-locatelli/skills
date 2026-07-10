# Skills for AEC Development

Agent skills for building AEC (Architecture, Engineering, Construction) software — Revit add-ins, Grasshopper plugins, and whatever comes next.

The idea follows [mattpocock/skills](https://github.com/mattpocock/skills): one repo of small, composable, model-agnostic skills that any coding agent can install. These are **discipline + curated reference + retrieval recipes**, not knowledge dumps — the live truth stays in the vendor docs and forums; the skills teach the agent how to get there fast and what to do once there.

They exist because LLM training data goes stale exactly where AEC APIs move fastest: runtime migrations (.NET Framework → .NET 8 → .NET 10), breaking API changes (`ElementId` Int32 → Int64, `ForgeTypeId` units), and deploy/load mechanics that produce silent failures. Each skill pins the version-critical facts and enforces a verified build–deploy–test loop.

## Quickstart

Two install channels; pick whichever fits your setup.

### Claude Code — plugin marketplace

No Node required — the marketplace is built into Claude Code. Register this repo as a marketplace, then install the plugin:

```
/plugin marketplace add daniel-locatelli/skills
/plugin install daniel-locatelli-skills@daniel-locatelli
```

Updates arrive through the `/plugin` menu (or enable auto-update for the marketplace). Installs all skills as one plugin.

### Any agent — skills.sh installer

Cross-agent — Claude Code, the Claude Code VS Code extension, Cursor, Codex, and more. Requires Node (which those harnesses already run on). Pick the skills and agents you want:

```bash
npx skills@latest add daniel-locatelli/skills
```

Update installed skills whenever this repo changes:

```bash
npx skills@latest update
```

The installer records each skill's source and content hash in `skills-lock.json`, so `update` only re-pulls skills whose canonical version here has changed.

Or clone and link a single skill folder into `~/.claude/skills/<skill-name>` (user-level) or a project's `.claude/skills/` (project-level).

## Reference

All skills are **model-invoked**: the agent reaches for them automatically when the task fits (you can also invoke them directly). Skills are grouped by the host application they target.

### Revit

- **[creating-revit-plugin](./skills/revit/creating-revit-plugin/SKILL.md)** — Build, scaffold, and debug Autodesk Revit desktop add-ins in C#/.NET, current for Revit 2027 (.NET 10) and 2025/2026 (.NET 8). Transactions and the valid-API-context rule, ribbon UI, `ExternalEvent` for modeless dialogs, multi-version targeting, MCP-verified dev loops, and APS Design Automation. Ships a complete buildable Revit 2027 scaffold in `template/`.

### Grasshopper

- **[creating-grasshopper-plugin](./skills/grasshopper/creating-grasshopper-plugin/SKILL.md)** — Build compiled Grasshopper plugins (`.gha`) for Rhino 8 in C#. Scaffolding from `Rhino.Templates`, `GH_Component` authoring, data trees, local deploy, Yak packaging, load-failure diagnosis — with an edit cycle that treats "build succeeded" as compilation, not verification.
- **[using-cordyceps](./skills/grasshopper/using-cordyceps/SKILL.md)** — Drive a running Grasshopper/Rhino session through the [Cordyceps](https://github.com/brookstalley/cordyceps) MCP server: place and wire canvas components, configure C#/Python script components, read solver outputs, bake and render scenes. Covers the safe-launch ritual, JSON-RPC fallback when ToolSearch can't surface the tools, and empirical gotchas Cordyceps doesn't document.

## Layout

```
skills/
  revit/
    creating-revit-plugin/        SKILL.md + reference/ + template/ (buildable scaffold)
  grasshopper/
    creating-grasshopper-plugin/  SKILL.md + references/ + retrieval/
    using-cordyceps/              SKILL.md + launch-cordyceps.ps1 + bootstrap.gh
```

The category folder is the host application, so a skill whose name doesn't mention the platform (an MCP-driven testing skill, say) is still unambiguous from its path.

Every skill is a folder with a `SKILL.md` entry point; supporting reference files sit next to it and are loaded on demand.

## Versioning

Semver on the repo (see `CHANGELOG.md`). MAJOR bumps track breaking changes in the covered host applications (Rhino/Revit major versions).

## License

MIT — see `LICENSE`.
