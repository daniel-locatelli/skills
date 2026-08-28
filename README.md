# Skills

**Small, composable, model-agnostic skills for coding agents — AEC development (Revit, Grasshopper, BTLx), web quality auditing, and contributing on GitHub or GitLab.**

This is the single home for all my public agent skills. The largest group is AEC: AEC workflows are shifting from clicking through software to instructing agents, and skills are how the expertise travels. This repo is the practical end of that shift.

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

### Computational design (host-agnostic strategies)

- **[agent-based-modeling](./skills/computational-design/agent-based-modeling/SKILL.md)** — Agent-based tessellation of doubly-curved surfaces (ICD Stuttgart plate-shell lineage): a normative specification with a plain-C# core (`ISurfaceHost` + solver + tangent-plane-intersection plates) that any host wraps in six methods, and three worked host recipes — Grasshopper via Cordyceps, a console harness you tune in, and a Python/COMPAS host that carries plates through to `compas_timber` solids and BTLx. Covers the convergence pitfalls that cost a day, why bow-tie plates appear on saddles (Dupin indicatrix, not Voronoi), why a developable cylinder is the prettiest and most worthless test surface, a four-class rule for reading any acceptance number before you assert it, and a bibliography with DOIs.

### Timber

- **[working-with-btlx](./skills/timber/working-with-btlx/SKILL.md)** — Work with BTLx, the design2machine timber-CNC exchange format: a parameter reference generated from the XSD for every processing (JackRafterCut, Drilling, Lap, Tenon, FreeContour, ...), reference sides and `ReferencePlaneID`, schema version history and validation, plus the XSD→markdown generator. Makes the agent check the spec before answering a parameter, range, default, or version question.

### Web

- **[optimizing-web-performance](./skills/web/optimizing-web-performance/SKILL.md)** — The Lighthouse loop for a deployed site: audit production, summarize with `scripts/lh-summary.mjs`, fix the two or three things that move the score (Astro island directives, interaction-boundary splitting, idle-deferred heavy chunks, contrast), verify with a *comparable* measurement, ship.
- **[auditing-website-quality](./skills/web/auditing-website-quality/SKILL.md)** — Hub for an in-depth site audit: runs each dimension's sub-skill, aggregates their findings (one shared JSON contract) into a dated scorecard in `docs/audits/` with fixes ranked by severity ÷ effort, and stops for approval before touching code. Ships `scripts/aggregate.mjs` + `templates/scorecard.md`.
- **[auditing-agent-readiness](./skills/web/auditing-agent-readiness/SKILL.md)** — Is the site discoverable and usable by AI agents? Zero-dependency checker for `llms.txt` (per locale), `.md` variants and `Accept: text/markdown` negotiation, robots AI rules and AI-UA blocking, `.well-known/{api-catalog,mcp.json,agent-skills}`, a live MCP `initialize`/`tools/list` handshake, and DNS-AID SVCB — plus the judgment calls the script can't make (what counts as declined by design).

- **[auditing-security-headers](./skills/web/auditing-security-headers/SKILL.md)** — Security posture of a deployed site: CSP quality (unsafe-inline/eval, wildcards, report-only), HSTS, nosniff, clickjacking, Referrer-/Permissions-Policy, cookie flags, mixed content, SRI, exposed `.env`/`.git`, http→https, security.txt — plus repo-side `pnpm audit` triage and secrets-scan guidance.
- **[auditing-seo-and-social](./skills/web/auditing-seo-and-social/SKILL.md)** — The SEO checks Lighthouse doesn't do: sitemap↔canonical↔og:url agreement, OG/Twitter card completeness and og:image resolvability, JSON-LD validity, hreflang (locales, x-default, alternates), noindex-in-sitemap, internal link rot, redirect chains, soft-404s — locale-aware.
- **[auditing-content-integrity](./skills/web/auditing-content-integrity/SKILL.md)** — Audits the content *repo tree*, not a URL: locale parity of markdown/MDX collections (missing, orphaned, or placeholder-copy translations), frontmatter field and invariant-value drift, house style (em dashes, h1-in-body, empty alt), and freshness of generated exports like `llms.txt`.

### Git

- **[preparing-pull-request](./skills/git/preparing-pull-request/SKILL.md)** — Run before opening a pull request (or filing an issue) on a repository you don't own (GitHub via `gh`, GitLab via `glab`): re-verify against fresh main, trace the defect's origin through blame → commit → PR → issue (leftover, reintroduction, or deliberate?), sweep the upstream tracker for duplicates and in-flight PRs touching the same files, and test every claim the PR body will make (including the red-then-green regression test). Stops before committing; the PR itself still needs your go.

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
  timber/
    working-with-btlx/            SKILL.md + references/ + scripts/generate_reference.py
  web/
    optimizing-web-performance/   SKILL.md + scripts/lh-summary.mjs
    auditing-website-quality/     SKILL.md + scripts/aggregate.mjs + templates/scorecard.md
    auditing-agent-readiness/     SKILL.md + scripts/check-agent-readiness.mjs (+ node:test fixtures)
    auditing-security-headers/    SKILL.md + scripts/check-headers.mjs (+ node:test fixtures)
    auditing-seo-and-social/      SKILL.md + scripts/check-seo.mjs (+ node:test fixtures)
    auditing-content-integrity/   SKILL.md + scripts/check-content.mjs (+ fixture trees)
  git/
    preparing-pull-request/       SKILL.md
```

The category folder is the host application or platform, so a skill whose name doesn't mention the platform (an MCP-driven testing skill, say) is still unambiguous from its path.

## Versioning & license

Semver on the repo (see `CHANGELOG.md`); MAJOR bumps track breaking changes in the covered host applications (Rhino/Revit major versions). MIT licensed — see `LICENSE`.

## Contributing

    git config core.hooksPath .githooks

Required. This repo is public; the hook refuses commits containing private
infrastructure identifiers. Private skills live in a separate private repo.

## Who's behind this

I'm [Daniel Locatelli](https://daniellocatelli.com) — PhD researcher at Gramazio Kohler Research (ETH Zurich) and software developer. These skills come out of daily practice building AEC tooling: every pinned fact here is something an agent got wrong for me first.
