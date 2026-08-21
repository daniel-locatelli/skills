---
name: auditing-content-integrity
description: Use when asked to audit a content repo's integrity — locale parity of markdown/MDX collections, untranslated or stale translations, frontmatter consistency, house-style rules (em dashes, heading levels, alt text), or freshness of generated exports like llms.txt.
---

# Auditing content & i18n integrity

This dimension audits the **repo tree**, not a URL. Input is the content root
(`<collections>/<locale>/<file>.md|mdx`, e.g. Astro's `src/content`). Broken
links and SEO metadata belong to `auditing-seo-and-social`; deployed-page
behavior to the other dimensions — don't fold them in.

## 1. Run the checker

```bash
node ~/.claude/skills/auditing-content-integrity/scripts/check-content.mjs \
  path/to/src/content --source en --locales pt,de \
  --exports public/llms.txt,public/pt/llms.txt --json > $S/content-integrity.json
```

Human-readable without `--json`. Locales autodetect from directory names when
omitted; `--exports` = generated artifacts checked for staleness (mtime vs
newest content file). Underscore-prefixed files are drafts — exempt. It
checks: missing translations, orphans, placeholder copies (body identical to
source), missing frontmatter fields, invariant-value drift (dates, links,
image paths), em dashes, h1-in-body, empty alt text, export freshness.

## 2. Judge what the script can't

| Check | Verdict rule |
|---|---|
| Translation quality | Identical body = flagged by script; *near*-identical or English prose in a pt/de file needs your read — spot-check one long file per locale |
| Stale translations | Script compares exports by mtime only; for per-file staleness use `git log -1 --format=%ci -- <en file> <pt file>` — translation older than a content-changing source commit = major |
| Deliberate gaps | Locale-specific entries (e.g. a German-only Impressum) are orphans by design — record as `info` with the reason, don't "fix" them |
| Field semantics | The script compares invariant *values*; whether `title`/`description` should differ (translated) or match (product names) is a judgment call — identical translatable fields across locales = untranslated → major |
| Alt-text quality | Present-but-useless alt ("image", filename) and untranslated alt in pt/de files: minor, listed per file |

## 3. Report

Findings contract: `{ dimension: "content-integrity", score, findings[{ id,
severity, title, evidence, file, fix, effort, autoFixable }] }` — findings use
`file` (repo-relative), not `url`; severity `blocker|major|minor|info`, effort
`S|M|L` — use these words, not high/medium/low. Standalone: ranked table plus
a per-locale coverage line ("pt 39/42, de 31/42"). Under the hub
(`auditing-website-quality`): hand over the JSON path and stop.

## If Astro / If Cloudflare

- **If Astro:** the schema source of truth is `src/content.config.ts` (Zod) —
  read it before judging frontmatter findings; required-field violations fail
  the build, so surviving gaps are in *optional* fields. `_` prefix also
  excludes entries from `getCollection` — parity exemption matches Astro.
- **If Cloudflare:** exports under `public/` deploy verbatim — a stale
  committed `llms.txt` ships stale; prefer generating it in the build.

## Common mistakes

- Auditing deployed URLs instead of the tree (wrong dimension).
- Flagging draft (`_`) files or deliberate locale-only entries as parity gaps.
- Trusting mtimes across fresh clones (git resets them — fall back to `git log`).
- Fixing style findings in the source locale but not the translations.
- Rewriting em dashes with hyphens; use commas, colons or parentheses.
