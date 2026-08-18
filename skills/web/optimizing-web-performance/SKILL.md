---
name: optimizing-web-performance
description: Use when asked to run Lighthouse / PageSpeed Insights, improve Core Web Vitals (LCP, TBT, INP, CLS), shrink JavaScript bundles, fix accessibility contrast findings, or generally "optimize this website" for a deployed site (Astro, Cloudflare Workers, or any static/SSR framework).
---

# Optimizing web performance (Lighthouse loop)

Audit → summarize → fix the few things that move the score → verify with a
comparable measurement → ship. The trap is spending the session on measurement
noise; the win is usually two or three targeted changes.

This skill is the **procedure**. For the full catalogue of *what* to fix per
audit (150+ Lighthouse audits, LCP/INP/CLS patterns, a11y, SEO), install and
consult Addy Osmani's plugin: `/plugin marketplace add addyosmani/web-quality-skills`
then `/plugin install web-quality-skills@addy-web-quality-skills`
(skills: `web-quality-skills:performance`, `:core-web-vitals`, `:accessibility`).

## 1. Audit production first

```bash
S=<scratchpad>; npx --yes lighthouse https://example.com \
  --output=json --output-path=$S/lh-prod.json \
  --chrome-flags="--headless=new --no-sandbox" --quiet \
  --only-categories=performance,accessibility,best-practices,seo \
  --form-factor=mobile --screenEmulation.mobile
```

- **On Windows the CLI often exits non-zero** with a chrome-launcher
  `destroyTmp` stack trace *after* the JSON was written. Check the file exists;
  the report is valid.
- Fallback with no Chrome: PageSpeed API
  `curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<url>&strategy=mobile"`
  (also returns CrUX field data).
- Start with one run of the homepage; take a second run before trusting a
  delta smaller than ~5 points / 100 ms (Lighthouse noise). Widen to other
  pages / desktop only after the homepage is clean.
- `S` is the session scratchpad dir from the system prompt.

## 2. Summarize, don't read the JSON

`node ~/.claude/skills/optimizing-web-performance/scripts/lh-summary.mjs $S/lh-prod.json` prints
category scores, the six metrics, every audit scoring < 0.9 with its top items,
and the unused-JS / image / main-thread breakdowns. Everything you need to
prioritise fits on one screen. Accepts a raw PageSpeed API response too
(it unwraps `lighthouseResult`).

## 3. Prioritise by lever, not by list order

| Finding | Usual root cause | Fix |
|---|---|---|
| Island hydrated with `client:load` but not needed at first paint | wrong Astro directive | `client:visible` / `client:idle` first; keep `client:load` only for above-the-fold interactive UI |
| Unused JS ≥ 50 % on a hydrated island | Modal / editor / markdown renderer bundled with the always-visible shell | Split at the **interaction boundary**: shell stays `client:load`, heavy part becomes `React.lazy` / dynamic `import()`, prefetch on `focus`/`hover` |
| TBT / long tasks from one chunk (Three.js, charts) | Loaded near-viewport at load, perpetual rAF loop | `requestIdleCallback` (with timeout) before import; render-on-demand loop that stops when settled; cap `devicePixelRatio` at 2; `{ passive: true }` scroll |
| Colour contrast (a11y < 100) | muted greys (`zinc-500`, `#71717a`) on dark bg ≈ 4.2:1 | Bump one step (`zinc-400`) in footer / captions / "powered by" lines |
| Image delivery | missing intermediate `widths`, default quality | add breakpoint near displayed CSS px × DPR, `quality≈70` |
| Render-blocking CSS ~150 ms | one global stylesheet | usually not worth it; leave unless FCP is the gap |

Skip: `valid-source-maps`, third-party beacon cache lifetime (Cloudflare
insights) — not actionable.

## 4. Verify with a *comparable* measurement

- `pnpm build` then inspect `dist/**/_astro/*.js` sizes: the split shell should
  be a few KB; the heavy chunk must not be `modulepreload`ed in the HTML.
- Local Lighthouse (`pnpm preview` / `wrangler dev`) serves **uncompressed,
  un-CDN'd** bytes → FCP/LCP/Speed Index will look *worse* than prod. Compare
  only **TBT, a11y, unused-JS, byte counts** locally; compare paint metrics
  prod-vs-prod after deploy.
- Anything you lazy-split needs a **scripted** interaction check, not "test
  manually": Playwright script that stubs the API, triggers the interaction,
  asserts the lazy chunk was requested, the UI rendered, and `pageerror` is
  empty. Run it from inside the repo so `@playwright/test` resolves; run
  `pnpm exec playwright install chromium` if the browser is missing.
- Astro's dev server is detached and may be **stale** (old Vite dep cache →
  500 "file does not exist in optimize deps directory"). `astro dev stop`,
  `rm -rf node_modules/.vite`, restart.
- Run the existing unit + e2e suites; prettier the touched files.

## 5. Ship

Update any self-description / changelog the project requires, commit with a
before/after summary (scores, KB, ms), push, then re-run step 1 on prod for
the real delta.

## Common mistakes

- Chasing 93 → 100 perf with FCP micro-tweaks while a11y sits at 95 for a
  one-class contrast fix.
- Comparing local preview paint metrics to production and "fixing" a
  regression that isn't there.
- Lazy-loading the LCP element or hero content (regresses LCP, adds CLS).
- Splitting the chunk but leaving a `client:load` island that still imports
  it statically (nothing changed; check the built chunk sizes).

## Under the hub

When invoked by `auditing-website-quality`, do not fix; convert the
`lh-summary` output into `$S/performance.json` in the findings contract
(blocker: CWV metric score < 0.5; major: category < 90; minor: audit < 0.9)
and return.
