# Changelog

## 1.7.0 — 2026-08-21

Completes the web-quality-audit family: `auditing-security-headers` (check-headers.mjs — CSP quality, HSTS, cookie flags, mixed content, SRI, exposed dotfiles, http→https, security.txt, plus pnpm-audit/secrets guidance), `auditing-seo-and-social` (check-seo.mjs — sitemap-driven sampling for canonicals, OG/Twitter cards, JSON-LD, hreflang, link rot, soft-404s, locale-aware) and `auditing-content-integrity` (check-content.mjs — repo-tree audit for locale parity, placeholder translations, frontmatter drift, house style, export freshness). All zero-dep `node:test`-covered scripts emitting the shared findings contract; every SKILL.md RED/GREEN-verified and every checker validated on live sites / the real portfolio tree. The hub's dimension table now lists all five sub-skills as shipped. Also syncs `marketplace.json` (stale at 1.4.0) with the plugin version.

## 1.6.0 — 2026-08-19

New `skills/git/` category with `preparing-pull-request` (moved in from a private `pre-pr-ritual` skill and generalised): the pre-PR discipline for repositories you don't own, on GitHub (`gh`) or GitLab (`glab`). Re-verify against fresh main, trace the defect's origin (blame → commit → PR → issue: leftover, reintroduction, or deliberate), sweep the upstream tracker for duplicates and in-flight PRs on the same files, test every claim the PR body will make (red-then-green regression test), then stop for the user's go.

## 1.5.0 — 2026-08-19

Promotes `working-with-btlx` (formerly `btlx`, in `in-progress/`) to a new `skills/timber/` category: the design2machine BTLx timber-CNC exchange format, with a parameter reference generated from the XSD per processing, reference sides / `ReferencePlaneID`, schema version history and validation, and the XSD→markdown generator. Renamed to match the task-naming pattern of the other skills.

## 1.4.0 — 2026-08-18

Ships the first two skills of the web-quality-audit family under `skills/web/`: `auditing-website-quality` (hub: sub-skill sweep → shared findings contract → dated scorecard with severity÷effort ranking → approval gate; `scripts/aggregate.mjs`, `templates/scorecard.md`) and `auditing-agent-readiness` (zero-dep checker for llms.txt per locale, `.md` variants + `Accept: text/markdown`, robots AI rules + AI-UA blocking, `.well-known` api-catalog / mcp.json / agent-skills, live MCP handshake, DNS-AID; `node:test` fixtures). `optimizing-web-performance` gains an "Under the hub" note. Remaining sub-skills (security-headers, seo-and-social, content-integrity) are planned in the spec.

## 1.3.0 — 2026-08-18

Repo rescope: `daniel-locatelli/skills` is now the single home for all public skills, not only AEC. New `skills/web/` category with `optimizing-web-performance` (Lighthouse loop + `lh-summary.mjs`, moved in from `~/.claude/skills`). Design spec for the upcoming `auditing-website-quality` hub + sub-skills in `docs/superpowers/specs/`.

## 1.2.0 — 2026-07-10

Added `using-cordyceps` under `skills/grasshopper/`, migrated from its standalone repo. Unlike `creating-grasshopper-plugin` (which builds compiled `.gha` plugins), this skill drives a *running* Grasshopper/Rhino session through the [Cordyceps](https://github.com/brookstalley/cordyceps) MCP server — placing and wiring canvas components, configuring C#/Python script components, baking, rendering, and the safe-launch ritual that avoids Grasshopper's data-recovery prompt. Ships `launch-cordyceps.ps1` and a canonical `bootstrap.gh`.

## 1.1.0 — 2026-07-09

Categories are now the host application, not the discipline: `skills/aec/` split into `skills/revit/` and `skills/grasshopper/`. The path now says which platform a skill targets even when its name doesn't — making room for upcoming skills like the MCP-driven test loops for Grasshopper and Revit. Skill names and content are unchanged; installs by skill name are unaffected.

## 1.0.0 — 2026-07-08

Initial consolidated release. Skills migrated from their standalone GitLab repos:

- `creating-revit-plugin` (renamed from `create-revit-plugin` to match the gerund naming of the other skills) — from [gitlab.com/daniellocatelli/creating-revit-plugin](https://gitlab.com/daniellocatelli/creating-revit-plugin). Covers Revit 2027 (.NET 10) and 2025/2026 (.NET 8); includes a buildable Revit 2027 scaffold in `template/`.
- `creating-grasshopper-plugin` — from [gitlab.com/daniellocatelli/creating-grasshopper-plugin](https://gitlab.com/daniellocatelli/creating-grasshopper-plugin) (was v1.0.0 there). Compiled `.gha` for Rhino 8.
