# Web quality audit skills — design

Date: 2026-08-18. Status: approved in principle (brainstorming Q&A, 2026-08-18); this
document is the written form.

## Goal

A hub + sub-skill family that lets a coding agent run an in-depth quality audit
of a deployed website, produce a dated markdown scorecard with prioritised
fixes, and (on approval) act on them. Reusable for client sites, not only
daniellocatelli.com.

## Scope change to this repo

`daniel-locatelli/skills` becomes the **single home for all of Daniel's public
skills**, not only AEC. Category folders stay "the host/platform the skill
targets": `revit/`, `grasshopper/`, and now `web/`. README, marketplace and
plugin manifests are widened accordingly; the AEC pitch stays as one section.

## Dimensions

| Dimension | Sub-skill | Coverage |
|---|---|---|
| Lighthouse perf / a11y / SEO / BP | `optimizing-web-performance` (existing, moved in unchanged) | Lighthouse loop, `lh-summary.mjs` |
| Agent readiness | `auditing-agent-readiness` | `llms.txt` per locale, `.md` variants + `Accept: text/markdown` negotiation, robots AI-crawler rules, sitemap, `/.well-known/{mcp.json,api-catalog,agent-skills}`, MCP `initialize` + `tools/list`, DNS-AID SVCB lookup, isitagentready.com re-check |
| Security & headers | `auditing-security-headers` | CSP/HSTS/XFO/XCTO/Referrer-Policy/Permissions-Policy, cookies, TLS, `pnpm audit`, secrets scan, Mozilla Observatory / securityheaders.com |
| SEO & social depth | `auditing-seo-and-social` | JSON-LD validity, OG/Twitter cards, hreflang <-> locales, canonical <-> sitemap, broken links, redirect chains |
| Content & i18n integrity | `auditing-content-integrity` | locale parity of content files, structural fields in sync, no em dashes, headings start at h2, alt text, knowledge-pipeline freshness |
| Hub | `auditing-website-quality` | runs all of the above, aggregates, writes scorecard, ranks fixes, acts on approval |

## Layout

```
skills/web/
  auditing-website-quality/     SKILL.md, scripts/aggregate.mjs, templates/scorecard.md
  optimizing-web-performance/   (moved in unchanged)
  auditing-agent-readiness/     SKILL.md, scripts/check-agent-readiness.mjs, fixtures/
  auditing-security-headers/    SKILL.md, scripts/check-headers.mjs, fixtures/
  auditing-seo-and-social/      SKILL.md, scripts/check-seo.mjs, fixtures/
  auditing-content-integrity/   SKILL.md, scripts/check-content.mjs, fixtures/
```

Each sub-skill is usable alone; the hub only orchestrates. Generic core with
clearly marked **"If Astro"** / **"If Cloudflare"** notes.

## Approach: hybrid

- **Scripts** for machine-checkable items (HTTP probes, header parsing, JSON
  validation, file parity). Node ESM (`.mjs`), zero deps beyond Node 20+
  built-ins (`fetch`, `dns/promises`, `node:test`), runnable with
  `node <skill>/scripts/<check>.mjs <url|path> [--json]`.
- **Guidance tables** in SKILL.md for judgment items (is this CSP too loose for
  this app? is declining an isitagentready item justified?).

## Findings contract (all scripts, `--json`)

```json
{
  "dimension": "agent-readiness",
  "score": 0-100,
  "findings": [{
    "id": "ar.llms-txt.missing-locale",
    "severity": "blocker|major|minor|info",
    "title": "…",
    "evidence": "…",
    "url": "https://…" | "file": "src/…",
    "fix": "…",
    "effort": "S|M|L",
    "autoFixable": true|false
  }]
}
```

Score = 100 minus weighted deductions (blocker 25, major 10, minor 3, info 0),
floored at 0. Hub ranks fixes by `severityWeight / effortWeight`
(S=1, M=2, L=4), ties by dimension order above.

## Hub output

`docs/audits/YYYY-MM-DD-website-quality.md` in the audited repo (or the cwd
when no repo), from `templates/scorecard.md`: header (site, date, commit),
per-dimension score table, ranked fix list (top 10 + full appendix), then
"Proposed next actions" awaiting approval. The hub **stops** after writing the
scorecard and asks; it does not fix without approval.

## Testing

- Each script: `node --test` fixture tests, one good + one broken fixture
  (recorded responses / sample trees), no network in tests.
- Each SKILL.md: writing-skills RED/GREEN — baseline subagent without the skill
  vs with it, on the same task; document rationalizations/gaps.
- Hub validated end-to-end on daniellocatelli.com and one unrelated public
  site.

## Rollout order

1. Repo rescope + move perf skill (this session).
2. Hub + `auditing-agent-readiness`.
3. `auditing-security-headers`.
4. `auditing-seo-and-social`.
5. `auditing-content-integrity`.

Each step: implement, test, register in `.claude-plugin/plugin.json`, junction
into `~/.claude/skills/`, `refresh-index.ps1`, changelog, commit.

## Constraints

- SKILL.md < ~500 words; description = "Use when…" triggers only.
- Cross-reference Addy Osmani's `web-quality-skills` for fix catalogues; do not
  duplicate.
- Windows-friendly (pnpm, PowerShell paths); Lighthouse CLI non-zero exit
  after valid JSON is expected.
