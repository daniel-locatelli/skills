---
name: auditing-agent-readiness
description: Use when asked whether a website is agent-ready, AI-crawler friendly, or discoverable/usable by LLM agents — llms.txt, markdown variants, robots AI rules, .well-known (mcp.json, api-catalog, agent-skills), MCP handshake, DNS-AID — or when re-checking an isitagentready.com score.
---

# Auditing agent readiness

Agent readiness = an agent can **find** the site (robots, sitemap, DNS-AID,
`.well-known`), **read** it cheaply (llms.txt per locale, `.md` variants,
`Accept: text/markdown`), and **act** on it (MCP, Agent Skills). Machine checks
first, judgment second, one findings JSON out. Feeds, JSON-LD, TTFB belong to
the SEO / performance dimensions — do not fold them in here.

## 1. Run the checker

```bash
node ~/.claude/skills/auditing-agent-readiness/scripts/check-agent-readiness.mjs \
  https://example.com --locales pt,de --json > $S/agent-readiness.json
```

Human-readable without `--json`. `--locales` = the site's non-default locale
prefixes. Needs network; DNS-AID goes through Cloudflare DoH. It probes: root
headers, AI user-agent blocking (403 / challenge page), robots.txt AI rules +
`Sitemap:`, sitemap, `/llms.txt` (+ per locale, + `llms-full.txt`), `.md`
variants and `Accept: text/markdown` on three sampled pages, `api-catalog`,
`mcp.json` + live JSON-RPC `initialize` / `tools/list`, agent-skills index
(digests, resolvable SKILL.md), `_mcp._agents` SVCB.

## 2. Judge what the script can't

| Check | Verdict rule |
|---|---|
| llms.txt content | H1 + one-line blockquote + H2 sections linking canonical URLs; each locale's file links that locale's pages |
| Blocked AI crawlers (robots or WAF) | A finding only if the owner wants AI visibility; a deliberate block becomes `info` with the reason recorded |
| MCP present | Read-only sites: `list_*` + `get_page` + `search` is enough; every tool needs `inputSchema.type: object` |
| Auth / OAuth discovery, protected-resource metadata, A2A agent card, WebMCP | **Not gaps** for a site with nothing to log in to, no agent-to-agent service, no in-page actions. Record as "declined by design" so re-audits do not resurface them |
| isitagentready.com | Re-run for the external number; expect the API/auth category to stay open on read-only sites |

## 3. Report

Findings contract: `{ dimension, score, findings[{ id, severity, title,
evidence, url, fix, effort, autoFixable }] }` with severity
`blocker|major|minor|info` and effort `S|M|L` — use these words, not
high/medium/low. Standalone: paste the findings
as a ranked table into the answer, `info` last. Under the hub
(`auditing-website-quality`): hand over the JSON path and stop.

## If Astro / If Cloudflare

- **If Astro:** llms.txt and `.md` variants are static endpoints built from the
  content collection; agent-skills index + digests from a build script.
- **If Cloudflare:** headers in `public/_headers` (`Link: rel=sitemap`,
  `X-Robots-Tag`, `Content-Type` for `.txt`/`.md`); `Accept: text/markdown`
  needs a zone Snippet/Worker rewrite because prerendered assets do not
  negotiate; AI-crawler blocking usually comes from AI Crawl Control / Bot
  Fight Mode, not robots.txt.

## Common mistakes

- Reporting the isitagentready checklist verbatim (auth items on a brochure site).
- Checking `/llms.txt` only in the default locale.
- Trusting `mcp.json` without a live `initialize` + `tools/list`.
- Scoring "no MCP" as a blocker; it is `info` unless the owner asked for one.
- Padding the audit with SEO/perf checks instead of handing those dimensions off.
