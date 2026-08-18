# AEC Skills

**Teach your coding agent Revit and Grasshopper — the versions that actually ship.**

AEC workflows are shifting from clicking through software to instructing agents, and skills are how the expertise travels. This repo is the practical end of that shift: small, composable, model-agnostic skills that make any coding agent competent at real AEC development today.

<!-- hero: screenshot/GIF slot — e.g. an agent wiring a Grasshopper canvas live via cordyceps, or a freshly built Revit 2027 add-in on the ribbon -->

## The problem

Ask an agent for a Revit add-in in 2026 and it will confidently write Revit 2019 code. It targets .NET Framework for a .NET 10 host, casts `ElementId` to Int32, hardcodes unit conversions that `ForgeTypeId` replaced, and declares victory at "build succeeded" — for a plugin that silently fails to load. LLM training data goes stale exactly where AEC APIs move fastest: runtime migrations, breaking API changes, and deploy/load mechanics that fail without an error message.

These skills pin the version-critical facts and enforce a verified build–deploy–test loop. They are **discipline + curated reference + retrieval recipes**, not knowledge dumps — the live truth stays in the vendor docs and forums; the skills teach the agent how to get there fast and what to do once there.

## What's inside

All skills are **model-invoked**: the agent reaches for them automatically when the task fits (you can also invoke them directly).

### Revit

- **[creating-revit-plugin](./skills/revit/creating-revit-plugin/SKILL.md)** — Build, scaffold, and debug Revit desktop add-ins in C#/.NET, current for Revit 2027 (.NET 10) and 2025/2026 (.NET 8). Transactions and the valid-API-context rule, ribbon UI, `ExternalEvent` for modeless dialogs, multi-version targeting, MCP-verified dev loops, and APS Design Automation. Ships a complete buildable Revit 2027 scaffold in `template/`.

### Grasshopper

- **[creating-grasshopper-plugin](./skills/grasshopper/creating-grasshopper-plugin/SKILL.md)** — Build compiled Grasshopper plugins (`.gha`) for Rhino 8 in C#. Scaffolding from `Rhino.Templates`, `GH_Component` authoring, data trees, local deploy, Yak packaging, load-failure diagnosis — with an edit cycle that treats "build succeeded" as compilation, not verification.
- **[using-cordyceps](./skills/grasshopper/using-cordyceps/SKILL.md)** — Give your agent a running Rhino it can drive. Through the [Cordyceps](https://github.com/brookstalley/cordyceps) MCP server it places and wires canvas components, configures C#/Python script components, reads solver outputs, and bakes and renders scenes. Covers the safe-launch ritual, a JSON-RPC fallback when ToolSearch can't surface the tools, and empirical gotchas Cordyceps doesn't document.

## Install

### Claude Code

The plugin marketplace is built in — no Node required. Register this repo, then install:

```
/plugin marketplace add daniel-locatelli/skills
/plugin install daniel-locatelli-skills@daniel-locatelli
```

Updates arrive through the `/plugin` menu (or enable auto-update for the marketplace).

### Any other agent

Cursor, Codex, GitHub Copilot, Continue, Cline, Roo Code, Windsurf, Zed, Gemini CLI, Warp — [70+ agents](https://skills.sh) via the skills.sh installer (requires Node):

```bash
npx skills@latest add daniel-locatelli/skills
```

Target a specific agent with `--agent <id>`, several with a comma-separated list, or all with `--agent '*'`; omit it to auto-detect the harness you're in. Later, `npx skills@latest update` re-pulls only the skills whose canonical version here has changed (tracked in `skills-lock.json`).

Or clone and link a single skill folder into `~/.claude/skills/<skill-name>` (user-level) or a project's `.claude/skills/` (project-level).

## How the skills are built

Every skill is a folder with a `SKILL.md` entry point; supporting reference files sit next to it and load on demand, so the agent only pays for what the task needs.

```
skills/
  revit/
    creating-revit-plugin/        SKILL.md + reference/ + template/ (buildable scaffold)
  grasshopper/
    creating-grasshopper-plugin/  SKILL.md + references/ + retrieval/
    using-cordyceps/              SKILL.md + launch-cordyceps.ps1 + bootstrap.gh
```

The category folder is the host application, so a skill whose name doesn't mention the platform (an MCP-driven testing skill, say) is still unambiguous from its path.

## Versioning & license

Semver on the repo (see `CHANGELOG.md`); MAJOR bumps track breaking changes in the covered host applications (Rhino/Revit major versions). MIT licensed — see `LICENSE`.

## Who's behind this

I'm [Daniel Locatelli](https://daniellocatelli.com) — PhD researcher at Gramazio Kohler Research (ETH Zurich) and software developer. These skills come out of daily practice building AEC tooling: every pinned fact here is something an agent got wrong for me first.
