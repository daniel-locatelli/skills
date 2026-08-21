# Remaining Sub-Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the last three sub-skills of the web-quality-audit family — `auditing-security-headers`, `auditing-seo-and-social`, `auditing-content-integrity` — per rollout steps 3–5 of `docs/superpowers/specs/2026-08-18-web-quality-audit-skills-design.md`, and release the batch as 1.5.0.

**Architecture:** Same as the shipped sub-skills: each is a folder with `SKILL.md` + a zero-dependency Node ESM check script emitting the shared findings contract. The two URL-based scripts take an injectable `fetch`; the content script audits a **repo tree** and its fixtures are committed directory trees, not HTTP tables. Skill prose RED→GREEN with subagents (baselines already dispatched); scripts test-first with `node:test`.

**Tech Stack:** Node ≥ 20 (`fetch`, `node:fs/promises`, `node:test`), ESM `.mjs`, zero npm deps, Windows-friendly.

## Global Constraints

- Findings contract: `{ dimension, score 0-100, findings: [{ id, severity: blocker|major|minor|info, title, evidence, url|file, fix, effort: S|M|L, autoFixable }] }`. Score = 100 − (blocker×25 + major×10 + minor×3), floored at 0.
- Dimension strings must match `aggregate.mjs` `DIMENSION_ORDER` exactly: `security-headers`, `seo-and-social`, `content-integrity`. Id namespaces: `sec.*`, `seo.*`, `ci.*`.
- Every network/fs failure becomes a finding (`*.unchecked`, info) — never a crash.
- CLI main-guard (Windows-safe): `if (process.argv[1] && /check-<name>\.mjs$/.test(process.argv[1]))`.
- Tests: copy `makeFakeFetch` from `check-agent-readiness.test.mjs` (adapt keys per skill). Good fixture scores 100 with only info findings; broken fixture asserts specific ids. Run: `node --test skills/web/<skill>/scripts/*.test.mjs` (files, not dirs).
- SKILL.md < ~500 words; description = "Use when…" triggers only; If Astro / If Cloudflare markers; "Under the hub: hand over the JSON path and stop"; Common mistakes. RED baseline gaps drive the content; GREEN re-run must pass.
- Real-site validation per script: daniellocatelli.com + 2 unrelated public sites (content script: portfolio repo tree + a synthetic broken tree); hand-verify every non-info finding.
- Release once at the end: plugin.json + marketplace.json → 1.5.0, README, CHANGELOG, hub SKILL.md "(planned)" rows flipped, junctions, refresh-index, commit, push.

---

## File structure

```
skills/web/
  auditing-security-headers/
    SKILL.md
    scripts/
      check-headers.mjs            # audit(baseUrl, {fetch, pages}) + score + CLI
      check-headers.test.mjs
      fixtures/{good-site,broken-site}.mjs
  auditing-seo-and-social/
    SKILL.md
    scripts/
      check-seo.mjs                # audit(baseUrl, {fetch, locales, maxPages}) + score + CLI
      check-seo.test.mjs
      fixtures/{good-site,broken-site}.mjs
  auditing-content-integrity/
    SKILL.md
    scripts/
      check-content.mjs            # audit(contentDir, {sourceLocale, locales, exports}) + score + CLI
      check-content.test.mjs
      fixtures/good-tree/...       # committed sample content trees
      fixtures/broken-tree/...
```

---

### Task 1: `auditing-security-headers`

**Files:** create the four files under `skills/web/auditing-security-headers/scripts/` plus `SKILL.md`.

**Interfaces:**
- Produces: `export async function audit(baseUrl, { fetch, pages = [] } = {})` → contract object with `dimension: "security-headers"`; `export function score(findings)` (same formula, copy). Fixture keys: `"GET /"`, `"GET /path"`, and `"GET http /"` for the plaintext-HTTP probe (fake fetch keys http: URLs as `GET http <pathname>`); responses may carry `location` header for redirect checks (script fetches with `redirect: "manual"`).

**Checks (id / severity / effort / autoFixable / rule):**

| id | sev | eff | auto | rule |
|---|---|---|---|---|
| `sec.tls.http-not-redirected` | blocker | S | false | `GET http://host/` (manual redirect) not 301/302/307/308 → https |
| `sec.tls.http-unchecked` | info | S | false | http probe threw |
| `sec.csp.missing` | major | M | false | no `content-security-policy` (report-only alone → `sec.csp.report-only` minor) |
| `sec.csp.unsafe-inline` | major | M | false | effective script-src (or default-src fallback) has `'unsafe-inline'` without nonce-/sha256- source |
| `sec.csp.unsafe-eval` | major | M | false | effective script-src has `'unsafe-eval'` |
| `sec.csp.wildcard` | major | S | false | effective script-src has `*` or `http:` |
| `sec.hsts.missing` | major | S | true | no `strict-transport-security` |
| `sec.hsts.short-max-age` | minor | S | true | max-age < 15552000 (180 d) |
| `sec.xcto.missing` | minor | S | true | no `x-content-type-options: nosniff` |
| `sec.xfo.missing` | minor | S | true | neither `x-frame-options` nor CSP `frame-ancestors` |
| `sec.referrer-policy.missing` | minor | S | true | header absent |
| `sec.permissions-policy.missing` | info | S | true | header absent |
| `sec.headers.deprecated` | info | S | true | `x-xss-protection` or `expect-ct` present |
| `sec.server.verbose` | minor | S | false | `server`/`x-powered-by` value contains a digit (version disclosure) |
| `sec.cookies.flags` | major/minor | M | false | any `set-cookie` (root + pages): missing `Secure` → major; only missing `HttpOnly`/`SameSite` → minor; evidence names cookie + missing flags |
| `sec.mixed-content` | major | M | false | homepage HTML has `src=`/`href=` `http://` in script/link/img/iframe |
| `sec.sri.missing` | minor | S | true | cross-origin `<script src>`/stylesheet `<link>` without `integrity` |
| `sec.unchecked` | info | S | false | root fetch threw |

Non-script scope stays in SKILL.md as commands/judgment: `pnpm audit --prod`, secrets scan (`git grep` for key patterns), Mozilla Observatory / securityheaders.com cross-check, "is this CSP too loose for this app" table.

- [ ] Step 1: fixtures — good = full header set (CSP `default-src 'self'; script-src 'self'`, HSTS 2y+preload, nosniff, frame-ancestors via CSP, Referrer-Policy, Permissions-Policy, no cookies, `GET http /` → 301 https), broken = no headers, `set-cookie: session=x` (no flags), inline `http://` script + cross-origin script without integrity, `GET http /` → 200, `server: Apache/2.4.41`.
- [ ] Step 2: failing tests — score formula; good→100/info-only; broken→asserts `sec.tls.http-not-redirected, sec.csp.missing, sec.hsts.missing, sec.xcto.missing, sec.xfo.missing, sec.referrer-policy.missing, sec.cookies.flags, sec.mixed-content, sec.sri.missing, sec.server.verbose` + field validity; targeted tests: unsafe-inline CSP → major, nonce'd unsafe-inline → clean, report-only → minor, short max-age → minor, throwing fetch → findings not crash.
- [ ] Step 3: run tests, confirm RED (module missing).
- [ ] Step 4: implement `check-headers.mjs`; tests GREEN.
- [ ] Step 5: SKILL.md against baseline gaps; GREEN subagent re-run with the skill.
- [ ] Step 6: real-site validation (daniellocatelli.com, github.com, mdn or similar); fix script bugs with regression tests.
- [ ] Step 7: commit.

### Task 2: `auditing-seo-and-social`

**Interfaces:**
- Produces: `export async function audit(baseUrl, { fetch, locales = [], maxPages = 5 } = {})` → `dimension: "seo-and-social"`. Discovers pages from sitemap (robots `Sitemap:` line, else `/sitemap.xml`, `/sitemap-index.xml`; one level of nesting), samples homepage + up to `maxPages` sitemap URLs.

**Checks:**

| id | sev | eff | auto | rule |
|---|---|---|---|---|
| `seo.sitemap.missing` | major | S | true | no sitemap found |
| `seo.sitemap.broken-url` | major | S | false | sampled sitemap URL not 200 |
| `seo.noindex.in-sitemap` | major | S | true | sampled sitemap page has meta robots/x-robots noindex |
| `seo.title.missing` | major | S | true | page lacks `<title>` (or empty) |
| `seo.meta-description.missing` | minor | S | true | per page |
| `seo.canonical.missing` | minor | S | true | per page |
| `seo.canonical.mismatch` | minor | S | false | canonical ≠ self (normalized: scheme/host/trailing slash); evidence shows both |
| `seo.canonical.not-in-sitemap` | minor | S | false | canonical URL absent from sitemap URL set |
| `seo.og.missing` | major | S | true | none of og:title/og:description/og:image |
| `seo.og.partial` | minor | S | true | some but not all three |
| `seo.og.image-broken` | major | S | false | og:image URL not 200 |
| `seo.twitter.missing` | minor | S | true | no `twitter:card` |
| `seo.jsonld.invalid` | major | S | false | ld+json block fails JSON.parse |
| `seo.jsonld.incomplete` | minor | S | false | parsed block missing `@context` or `@type` |
| `seo.jsonld.none` | info | M | false | no structured data anywhere sampled |
| `seo.hreflang.missing` | major | S | true | locales configured but sampled page has no hreflang |
| `seo.hreflang.missing-locale` | major | S | true | hreflang set lacks a configured locale |
| `seo.hreflang.no-x-default` | minor | S | true | no x-default alternate |
| `seo.hreflang.broken-alternate` | major | S | false | alternate URL not 200 |
| `seo.links.broken` | major | M | false | internal links from sampled pages (dedup, cap 30) that 404; one finding listing them |
| `seo.links.redirected` | minor | S | true | internal links answering 301/308 (chain risk); one finding |
| `seo.unchecked` | info | S | false | fetch threw |

- [ ] Step 1: fixtures — good = sitemap with 2 pages + pt locale, pages with full title/desc/canonical/OG/twitter/valid JSON-LD/hreflang(en,pt,x-default), all links 200; broken = sitemap present but page lacking OG/twitter/canonical, invalid JSON-LD, no hreflang (locales:["pt"]), one 404 internal link, one 301 internal link, one sitemap URL 404.
- [ ] Step 2: failing tests — good 100/info-only (with `locales:["pt"]`); broken asserts `seo.og.missing, seo.twitter.missing, seo.canonical.missing, seo.jsonld.invalid, seo.hreflang.missing, seo.links.broken, seo.links.redirected, seo.sitemap.broken-url`; targeted: missing-locale hreflang, og.partial, no sitemap at all, throwing fetch.
- [ ] Steps 3–7: RED → implement → SKILL.md RED/GREEN → real sites (daniellocatelli.com, astro.build, a news/docs site) → commit.

### Task 3: `auditing-content-integrity`

**Interfaces:**
- Produces: `export async function audit(contentDir, { sourceLocale = "en", locales = [], exports = [] } = {})` → `dimension: "content-integrity"`; findings use `file` (repo-relative, forward slashes) not `url`. Locale autodetect: subdirs of each collection when `locales` empty. Underscore-prefixed files are drafts — exempt from parity. `exports` = generated artifact paths (e.g. `public/llms.txt`) for freshness vs newest content mtime.

**Checks:**

| id | sev | eff | auto | rule |
|---|---|---|---|---|
| `ci.parity.missing-translation` | major | M | false | per target locale: source files with no counterpart; one finding per locale listing files |
| `ci.parity.orphan` | minor | S | false | target-locale file with no source counterpart |
| `ci.structure.missing-fields` | minor | S | false | translation frontmatter lacks keys the source has (per file, aggregated) |
| `ci.structure.value-drift` | minor | S | false | invariant fields (`date`, `startDate`, `endDate`, `url`, `link`, `image`, `cover`) differ between source and translation |
| `ci.style.em-dash` | minor | S | true | `—` in body prose (aggregate, list files+count) |
| `ci.style.h1-in-body` | minor | S | true | `# ` heading in body (aggregate) |
| `ci.images.missing-alt` | minor | S | false | `![](…)` with empty alt (aggregate) |
| `ci.freshness.stale-export` | major | S | true | an `exports` file older (mtime) than the newest content file |
| `ci.freshness.export-missing` | minor | S | true | listed export path doesn't exist |
| `ci.unchecked` | info | S | false | contentDir unreadable |

CLI: `node check-content.mjs <contentDir> [--source en] [--locales pt,de] [--exports public/llms.txt,...] [--json]`. Frontmatter parsed with a minimal `---`-fence key: value splitter (top-level keys only) — no YAML dep.

- [ ] Step 1: fixture trees — `good-tree/projects/{en,pt}/a.md` in full parity, clean style; `broken-tree` with: `projects/en/{a,b}.md` but `pt` only `a.md` (+ b missing), `pt/orphan.md`, translation missing a frontmatter key + drifted `date`, em dash + h1 + `![](x.png)` in a body, `_draft.md` in en only (must NOT flag).
- [ ] Step 2: failing tests — good 100/info-only; broken asserts `ci.parity.missing-translation, ci.parity.orphan, ci.structure.missing-fields, ci.structure.value-drift, ci.style.em-dash, ci.style.h1-in-body, ci.images.missing-alt` and NOT flagging `_draft.md`; freshness test builds a temp tree in the OS tmpdir and sets mtimes with `fs.utimes`; nonexistent dir → findings not crash.
- [ ] Steps 3–7: RED → implement → SKILL.md RED/GREEN → validate on `C:\repos\github\daniel-locatelli\daniellocatelli\src\content` (+ its exports) and the broken fixture → commit.

### Task 4: Release 1.5.0

- [ ] Flip the three "(planned)" rows in `skills/web/auditing-website-quality/SKILL.md`.
- [ ] Add three paths to `.claude-plugin/plugin.json` `skills`; bump both manifests to 1.5.0.
- [ ] README Web bullets + layout tree; CHANGELOG 1.5.0 entry.
- [ ] Junctions: `cmd /c mklink /J "%USERPROFILE%\.claude\skills\<name>" "<repo path>"` ×3; `pwsh ~/.claude/skills/system/scripts/refresh-index.ps1`.
- [ ] Full test sweep `node --test skills/web/*/scripts/*.test.mjs`; commit; push.
