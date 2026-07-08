# Skills for AEC Development

Agent skills for building AEC (Architecture, Engineering, Construction) software — Revit add-ins, Grasshopper plugins, and whatever comes next.

The idea follows [mattpocock/skills](https://github.com/mattpocock/skills): one repo of small, composable, model-agnostic skills that any coding agent can install. These are **discipline + curated reference + retrieval recipes**, not knowledge dumps — the live truth stays in the vendor docs and forums; the skills teach the agent how to get there fast and what to do once there.

They exist because LLM training data goes stale exactly where AEC APIs move fastest: runtime migrations (.NET Framework → .NET 8 → .NET 10), breaking API changes (`ElementId` Int32 → Int64, `ForgeTypeId` units), and deploy/load mechanics that produce silent failures. Each skill pins the version-critical facts and enforces a verified build–deploy–test loop.

## Quickstart

Install with the [skills.sh](https://skills.sh) installer and pick the skills and agents you want:

```bash
npx skills@latest add daniel-locatelli/skills
```

Or install as a Claude Code plugin:

```
/plugin install https://github.com/daniel-locatelli/skills
```

Or clone and link a single skill folder into `~/.claude/skills/<skill-name>` (user-level) or a project's `.claude/skills/` (project-level).

## Reference

Both skills are **model-invoked**: the agent reaches for them automatically when the task fits (you can also invoke them directly).

### AEC

- **[creating-revit-plugin](./skills/aec/creating-revit-plugin/SKILL.md)** — Build, scaffold, and debug Autodesk Revit desktop add-ins in C#/.NET, current for Revit 2027 (.NET 10) and 2025/2026 (.NET 8). Transactions and the valid-API-context rule, ribbon UI, `ExternalEvent` for modeless dialogs, multi-version targeting, MCP-verified dev loops, and APS Design Automation. Ships a complete buildable Revit 2027 scaffold in `template/`.
- **[creating-grasshopper-plugin](./skills/aec/creating-grasshopper-plugin/SKILL.md)** — Build compiled Grasshopper plugins (`.gha`) for Rhino 8 in C#. Scaffolding from `Rhino.Templates`, `GH_Component` authoring, data trees, local deploy, Yak packaging, load-failure diagnosis — with an edit cycle that treats "build succeeded" as compilation, not verification.

## Layout

```
skills/
  aec/
    creating-revit-plugin/        SKILL.md + reference/ + template/ (buildable scaffold)
    creating-grasshopper-plugin/  SKILL.md + references/ + retrieval/
```

Every skill is a folder with a `SKILL.md` entry point; supporting reference files sit next to it and are loaded on demand.

## Versioning

Semver on the repo (see `CHANGELOG.md`). MAJOR bumps track breaking changes in the covered host applications (Rhino/Revit major versions).

## License

MIT — see `LICENSE`.
