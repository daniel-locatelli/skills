---
name: auditing-security-headers
description: Use when asked to audit a website's security posture, check security headers (CSP, HSTS, cookies, TLS), harden a deployed site, or re-check a securityheaders.com / Mozilla Observatory grade.
---

# Auditing security & headers

Machine checks first, judgment second, one findings JSON out. Scope is the
**deployed site + its repo**; DNS/email posture (SPF/DMARC), WAF tuning and
pentesting are out of scope — name them as not-covered, don't improvise them.

## 1. Run the checker

```bash
node ~/.claude/skills/auditing-security-headers/scripts/check-headers.mjs \
  https://example.com --pages /login,/de/ --json > $S/security-headers.json
```

Human-readable without `--json`. `--pages` adds paths probed for cookies (use
pages that set them). It checks: http→https redirect, CSP (unsafe-inline/eval,
wildcards, report-only), HSTS, nosniff, clickjacking, Referrer-/Permissions-
Policy, deprecated headers, version disclosure, cookie flags, mixed content,
SRI on cross-origin assets, exposed `/.env` + `/.git/*`, security.txt.

## 2. Repo side (when the repo is local)

- `pnpm audit --prod` — prod/runtime findings are real; build-tool-only CVEs
  are `info` with a note.
- Secrets: scan history (`gitleaks` if available, else `git grep -iE
  "(api|secret|private)[_-]?key\s*[:=]"`) and the built output. Any live
  credential = blocker until rotated.
- `public/` ships verbatim: look for `.env`, backups, PII, EXIF-GPS photos.

## 3. Judge what the script can't

| Check | Verdict rule |
|---|---|
| "Is this CSP too loose?" | Static site with no third parties: `default-src 'self'` is achievable — looser is a finding. App with analytics/embeds: each extra origin must be nameable; `'unsafe-inline'` scripts only via nonce/hash |
| Rolling out a new CSP | Propose Report-Only first on any interactive site; enforcing straight away is itself a risk |
| Cookie without HttpOnly | If JS must read it (theme, locale), record as declined by design; session cookies never |
| SRI on your own CDN/subdomain | Accepted-risk `info` if assets are hash-named and same org; third-party scripts always need it |
| External grades | securityheaders.com / Mozilla Observatory as corroboration, never as the finding itself |

## 4. Report

Findings contract: `{ dimension: "security-headers", score, findings[{ id,
severity, title, evidence, url, fix, effort, autoFixable }] }`, severity
`blocker|major|minor|info`, effort `S|M|L` — use these words, not
high/medium/low. Standalone: ranked table, `info` last, plus a "passed checks"
line so silence is auditable. Under the hub (`auditing-website-quality`): hand
over the JSON path and stop.

## If Astro / If Cloudflare

- **If Astro:** headers belong in `public/_headers` (Pages) — one hardening
  block on `/*`; islands may need nonces or external files before CSP enforces.
- **If Cloudflare:** `sec.tls.http-not-redirected` usually means **Always Use
  HTTPS** is off (dashboard, not code); also set Minimum TLS 1.2. The
  `<project>.pages.dev` twin serves the same content — noindex or Access-gate
  it. `_headers` scoping misses 404/asset responses — spot-check one of each.

## Common mistakes

- Reporting Observatory's grade instead of your own curl-level evidence.
- Flagging `x-xss-protection: 0` (that's the recommended value).
- Treating dev-dependency CVEs as majors on a static site.
- Proposing a strict CSP without inventorying inline scripts first.
- Padding with SPF/DMARC/subdomain-takeover checks instead of naming them
  out-of-scope.
