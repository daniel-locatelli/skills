---
name: auditing-seo-and-social
description: Use when asked to audit a site's SEO depth, social-sharing cards, structured data, hreflang/i18n signals, canonicals, sitemaps, or broken links — the checks Lighthouse's SEO category does not cover.
---

# Auditing SEO & social depth

Lighthouse SEO verifies ~14 mechanical basics; this dimension covers what it
doesn't: structured data, share cards, hreflang correctness, canonical ↔
sitemap agreement, link rot, soft-404s. Machine checks first, judgment second,
one findings JSON out. Performance and security headers belong to their own
dimensions — hand them off, don't fold them in.

## 1. Run the checker

```bash
node ~/.claude/skills/auditing-seo-and-social/scripts/check-seo.mjs \
  https://example.com --locales pt,de --json > $S/seo-and-social.json
```

Human-readable without `--json`. `--locales` = non-default locale prefixes
(hreflang checks only run when set). It discovers pages via robots.txt/sitemap,
samples the homepage + `--max-pages` (default 5) sitemap URLs, and checks:
titles (uniqueness, locale-aware), descriptions, canonicals (self + in
sitemap), OG/Twitter completeness, og:image resolvability, og:url↔canonical,
JSON-LD validity, noindex-in-sitemap, hreflang (locales, x-default, alternates
resolve), internal link rot + redirect chains, soft-404s. Needs network;
sequential-ish, so a big site takes a couple of minutes.

## 2. Judge what the script can't

| Check | Verdict rule |
|---|---|
| JSON-LD content | Portfolio: `Person` + `WebSite` on home, `CreativeWork` per project; fields must match visible content; `inLanguage` per locale |
| Locale metadata | Same description/OG text across locales = untranslated → major; same homepage *title* across locales is fine |
| hreflang reciprocity | Script checks presence + 200s; spot-check one pair points back at each other |
| og:image quality | Fetch it and look: 1200×630, legible as thumbnail, per-page images beat one generic fallback |
| Scraper reachability | If shares look broken despite good tags, test `curl -A facebookexternalhit/1.1` (WAF challenges block scrapers) and re-scrape in the FB/LinkedIn debuggers |
| Search Console | Only the owner can read index coverage / hreflang acceptance — report as "user verifies", never assume |

## 3. Report

Findings contract: `{ dimension: "seo-and-social", score, findings[{ id,
severity, title, evidence, url, fix, effort, autoFixable }] }`, severity
`blocker|major|minor|info`, effort `S|M|L` — use these words, not
high/medium/low. Standalone: ranked table, `info` last, and name what was NOT
checked (Search Console, social caches). Under the hub
(`auditing-website-quality`): hand over the JSON path and stop.

## If Astro / If Cloudflare

- **If Astro:** head tags live in the shared layout — most findings collapse
  into one component fix; sitemap from `@astrojs/sitemap` (set `site` in
  config); hreflang from the i18n routing config.
- **If Cloudflare:** check the `<project>.pages.dev` twin isn't indexed
  (canonical/noindex it); Bot Fight Mode can block social scrapers; redirect
  rules (`_redirects`) are where chains come from.

## Common mistakes

- Re-running Lighthouse SEO and calling it depth.
- Flagging shared homepage titles across locales as duplicates.
- Trusting JSON-LD by eye instead of parsing it (the script parses; you judge content).
- Reporting "no structured data" as major — it is `info`/opportunity unless rich results were promised.
- Skipping the sitemap↔canonical↔og:url triangle; they must agree exactly.
