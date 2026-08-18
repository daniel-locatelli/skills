---
name: auditing-website-quality
description: Use when asked for a full website quality audit, a site health check or scorecard, "what should we fix on this site", or a client-facing review of a deployed site covering performance, accessibility, SEO, security headers, agent readiness, and content/i18n integrity.
---

# Auditing website quality (hub)

Sweep every dimension with its sub-skill, aggregate into **one dated
scorecard in the repo**, rank fixes by severity ÷ effort, then **stop and ask**
before changing anything.

## Dimensions and sub-skills

| Dimension | Sub-skill | Produces |
|---|---|---|
| Performance / a11y / SEO / BP (Lighthouse) | `optimizing-web-performance` | `lh-summary.mjs` → hand-write `performance.json` (blocker: a CWV metric score < 0.5; major: a category < 90; minor: any other audit < 0.9) |
| Agent readiness | `auditing-agent-readiness` | `check-agent-readiness.mjs --json` |
| Security & headers | `auditing-security-headers` (planned) | `check-headers.mjs --json` |
| SEO & social depth | `auditing-seo-and-social` (planned) | `check-seo.mjs --json` |
| Content & i18n integrity | `auditing-content-integrity` (planned) | `check-content.mjs --json` |

If a planned sub-skill's folder does not exist yet, skip it and list the gap
in the scorecard Summary — do not improvise the dimension inline.

## Procedure

1. Confirm target URL, locales, repo path (or none), Lighthouse form factor
   (mobile default). `S` = session scratchpad.
2. Run each available sub-skill; save `$S/<dimension>.json` in the findings
   contract `{ dimension, score, findings[{ id, severity, title, evidence,
   url|file, fix, effort, autoFixable }] }`. Sub-skills **report only** here;
   their fix steps wait.
3. Aggregate:
   ```bash
   node ~/.claude/skills/auditing-website-quality/scripts/aggregate.mjs \
     --site https://example.com --commit $(git rev-parse --short HEAD) \
     --out docs/audits/$(date +%F)-website-quality.md $S/*.json
   ```
   No repo → write to the cwd and say so.
4. Fill the scorecard's **Summary** slot (3–5 lines): biggest lever, quick
   wins, anything declined by design, dimensions skipped.
5. Show the top-10 table and **wait for approval**. Then fix in ranked order,
   one commit per finding group, re-run the affected sub-skill, and append a
   `## Re-check <date>` section with the new score table to the same file.

## Rules

- No fix before the scorecard file exists and the user has approved.
- Rank = severity weight (blocker 25, major 10, minor 3) ÷ effort (S 1, M 2,
  L 4); the script does this — do not reorder by taste.
- Deliberately declined items stay in the appendix as `info` with the reason.
- Fix catalogues live in Addy Osmani's `web-quality-skills`
  (`/plugin marketplace add addyosmani/web-quality-skills`); this hub only
  orchestrates.

## Common mistakes

- Running only Lighthouse and calling it an audit.
- Fixing the first thing you see; the scorecard comes first.
- Scorecard in chat only, not in `docs/audits/` (loses the re-check).
- Letting a sub-skill fix while the sweep is still running.
