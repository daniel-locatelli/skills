#!/usr/bin/env node
// SEO & social depth audit (beyond Lighthouse). Zero deps, Node >= 20.
// Usage: node check-seo.mjs <url> [--locales pt,de] [--max-pages 5] [--json]
// Emits the shared findings contract: { dimension, score, findings[] }.

const W = { blocker: 25, major: 10, minor: 3, info: 0 };
export function score(findings) {
  return Math.max(0, 100 - findings.reduce((s, f) => s + (W[f.severity] ?? 0), 0));
}

const norm = (u) => { try { const x = new URL(u); return `${x.origin}${x.pathname.replace(/\/$/, "") || "/"}`; } catch { return u; } };
const attr = (tag, name) => {
  const m = tag.match(new RegExp(`${name}\\s*=\\s*("([^"]*)"|'([^']*)')`, "i"));
  return m ? (m[2] ?? m[3]) : undefined;
};
const metaTags = (html) => [...html.matchAll(/<meta\b[^>]*>/gi)].map((m) => ({
  key: (attr(m[0], "(?:name|property)"))?.toLowerCase(),
  content: attr(m[0], "content"),
})).filter((t) => t.key);
const linkTags = (html) => [...html.matchAll(/<link\b[^>]*>/gi)].map((m) => ({
  rel: attr(m[0], "rel")?.toLowerCase(),
  href: attr(m[0], "href"),
  hreflang: attr(m[0], "hreflang")?.toLowerCase(),
}));

export async function audit(baseUrl, { fetch: rawFetch = globalThis.fetch, locales = [], maxPages = 5 } = {}) {
  const fetch = (u, init = {}) => rawFetch(u, { signal: AbortSignal.timeout(15000), ...init });
  const base = new URL(baseUrl);
  const findings = [];
  const add = (id, severity, title, evidence, url, fix, effort, autoFixable) =>
    findings.push({ id, severity, title, evidence, url, fix, effort, autoFixable });
  const list = (arr, n = 4) => [...new Set(arr)].slice(0, n).join("; ") + (new Set(arr).size > n ? ` (+${new Set(arr).size - n} more)` : "");

  // Sitemap discovery
  let sitemapUrl = null, sitemapLocs = [];
  try {
    const robots = await fetch(new URL("/robots.txt", base).href);
    if (robots.status === 200) sitemapUrl = ((await robots.text()).match(/^sitemap:\s*(\S+)/im) || [])[1] || null;
    for (const cand of [sitemapUrl, new URL("/sitemap.xml", base).href, new URL("/sitemap-index.xml", base).href]) {
      if (!cand) continue;
      const res = await fetch(cand);
      if (res.status !== 200) continue;
      const xml = await res.text();
      let locs = [...xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi)].map((m) => m[1]);
      if (/<sitemapindex/i.test(xml)) {
        const children = locs.slice(0, 3); locs = [];
        for (const c of children) {
          try { const cr = await fetch(c); if (cr.status === 200) locs.push(...[...(await cr.text()).matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi)].map((m) => m[1])); } catch {}
        }
      }
      if (locs.length) { sitemapUrl = cand; sitemapLocs = locs; break; }
    }
  } catch { /* handled below */ }
  const sitemapSet = new Set(sitemapLocs.map(norm));
  if (!sitemapLocs.length)
    add("seo.sitemap.missing", "major", "No usable sitemap found",
      "robots.txt Sitemap line, /sitemap.xml and /sitemap-index.xml all failed", new URL("/sitemap.xml", base).href,
      "Generate a sitemap (e.g. @astrojs/sitemap) and reference it from robots.txt", "S", true);

  // Sample pages: homepage + sitemap URLs (same-origin)
  const sample = [base.href];
  for (const u of sitemapLocs) {
    if (sample.length > maxPages) break;
    try { if (new URL(u).origin === base.origin && !sample.some((s) => norm(s) === norm(u))) sample.push(u); } catch {}
  }

  const agg = {}; // id -> array of evidence strings
  const bump = (id, ev) => (agg[id] = agg[id] || []).push(ev);
  const titles = [], ogImages = [], alternates = [], pageLinks = [];
  const sampledNorm = new Set(sample.map(norm));
  let anyJsonld = false, anyPage = false, firstUrl = {};

  for (const pageUrl of sample) {
    let res, html;
    try { res = await fetch(pageUrl, { redirect: "follow" }); html = await res.text(); }
    catch (e) {
      if (pageUrl === base.href) {
        add("seo.unchecked", "info", "Site unreachable; page checks skipped", String(e), base.href, "Re-run when reachable", "S", false);
        return { dimension: "seo-and-social", score: score(findings), findings };
      }
      bump("seo.sitemap.broken-url", `${pageUrl}: ${e}`); firstUrl["seo.sitemap.broken-url"] ??= pageUrl; continue;
    }
    if (res.status !== 200) { bump("seo.sitemap.broken-url", `${pageUrl} -> ${res.status}`); firstUrl["seo.sitemap.broken-url"] ??= pageUrl; continue; }
    anyPage = true;
    const mark = (id) => { bump(id, pageUrl); firstUrl[id] ??= pageUrl; };
    const metas = metaTags(html), links = linkTags(html);
    const meta = (k) => metas.find((t) => t.key === k)?.content;

    const title = (html.match(/<title[^>]*>([^<]*)<\/title>/i) || [])[1]?.trim();
    if (!title) mark("seo.title.missing"); else titles.push([title.toLowerCase(), pageUrl]);
    if (!meta("description")) mark("seo.meta-description.missing");

    const canonical = links.find((l) => l.rel === "canonical")?.href;
    if (!canonical) mark("seo.canonical.missing");
    else {
      if (norm(canonical) !== norm(pageUrl)) { bump("seo.canonical.mismatch", `${pageUrl} -> ${canonical}`); firstUrl["seo.canonical.mismatch"] ??= pageUrl; }
      if (sitemapLocs.length && !sitemapSet.has(norm(canonical))) { bump("seo.canonical.not-in-sitemap", canonical); firstUrl["seo.canonical.not-in-sitemap"] ??= pageUrl; }
    }

    const og = { title: meta("og:title"), description: meta("og:description"), image: meta("og:image") };
    const present = Object.values(og).filter(Boolean).length;
    if (present === 0) mark("seo.og.missing");
    else if (present < 3) { bump("seo.og.partial", `${pageUrl}: missing ${Object.keys(og).filter((k) => !og[k]).map((k) => `og:${k}`).join(", ")}`); firstUrl["seo.og.partial"] ??= pageUrl; }
    if (og.image) ogImages.push(new URL(og.image, pageUrl).href);
    const ogUrl = meta("og:url");
    if (ogUrl && canonical && norm(ogUrl) !== norm(canonical)) { bump("seo.og.url-mismatch", `${pageUrl}: og:url ${ogUrl} != canonical ${canonical}`); firstUrl["seo.og.url-mismatch"] ??= pageUrl; }
    if (!meta("twitter:card")) mark("seo.twitter.missing");

    for (const m of html.matchAll(/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
      anyJsonld = true;
      try {
        const data = JSON.parse(m[1]);
        const s = JSON.stringify(data);
        if (!s.includes("@context") || !s.includes("@type")) { bump("seo.jsonld.incomplete", pageUrl); firstUrl["seo.jsonld.incomplete"] ??= pageUrl; }
      } catch { mark("seo.jsonld.invalid"); }
    }

    const robotsMeta = meta("robots") || "";
    if (/noindex/i.test(res.headers.get("x-robots-tag") || "") || /noindex/i.test(robotsMeta)) mark("seo.noindex.in-sitemap");

    if (locales.length) {
      const hl = links.filter((l) => l.rel === "alternate" && l.hreflang);
      if (!hl.length) mark("seo.hreflang.missing");
      else {
        for (const loc of locales)
          if (!hl.some((l) => l.hreflang === loc || l.hreflang.startsWith(`${loc}-`)))
            { bump("seo.hreflang.missing-locale", `${pageUrl}: no hreflang for "${loc}"`); firstUrl["seo.hreflang.missing-locale"] ??= pageUrl; }
        if (!hl.some((l) => l.hreflang === "x-default")) mark("seo.hreflang.no-x-default");
        for (const l of hl) if (l.href) alternates.push(new URL(l.href, pageUrl).href);
      }
    }

    for (const m of html.matchAll(/<a\b[^>]*\bhref=["']([^"'#][^"']*)["']/gi)) {
      try { const u = new URL(m[1], pageUrl); if (u.origin === base.origin) pageLinks.push(u.href); } catch {}
    }
  }

  // Probe collected URLs
  const probe = async (urls, cap, onBad) => {
    const targets = [...new Set(urls.map(norm))].filter((u) => !sampledNorm.has(u)).slice(0, cap);
    for (let i = 0; i < targets.length; i += 6) {
      const results = await Promise.all(targets.slice(i, i + 6).map(async (u) => {
        try { return [u, (await fetch(u, { redirect: "manual" })).status]; } catch (e) { return [u, String(e)]; }
      }));
      for (const [u, s] of results) onBad(u, s);
    }
  };
  await probe(pageLinks, 30, (u, s) => {
    if (s >= 400) { bump("seo.links.broken", `${u} -> ${s}`); firstUrl["seo.links.broken"] ??= u; }
    else if ([301, 302, 307, 308].includes(s)) { bump("seo.links.redirected", `${u} -> ${s}`); firstUrl["seo.links.redirected"] ??= u; }
  });
  await probe(ogImages, 5, (u, s) => { if (s !== 200) { bump("seo.og.image-broken", `${u} -> ${s}`); firstUrl["seo.og.image-broken"] ??= u; } });
  await probe(alternates, 10, (u, s) => { if (s !== 200 && !(s >= 300 && s < 400)) { bump("seo.hreflang.broken-alternate", `${u} -> ${s}`); firstUrl["seo.hreflang.broken-alternate"] ??= u; } });

  // Soft 404
  try {
    const probeUrl = new URL("/this-page-should-not-exist-audit-probe", base).href;
    const r = await fetch(probeUrl, { redirect: "manual" });
    if (r.status === 200)
      add("seo.soft-404", "major", "Nonexistent URLs return 200 (soft 404)", `GET ${probeUrl} -> 200`, probeUrl,
        "Return a real HTTP 404 for unknown paths", "M", false);
  } catch { /* skip */ }

  // Duplicate titles
  const seen = new Map();
  for (const [t, u] of titles) (seen.get(t) ?? seen.set(t, []).get(t)).push(u);
  // Locale variants of the same page may legitimately share a title.
  const stripLocale = (u) => { try { const p = new URL(u).pathname; return locales.length ? p.replace(new RegExp(`^/(?:${locales.join("|")})(?=/|$)`), "") || "/" : p; } catch { return u; } };
  const dups = [...seen.entries()].filter(([, us]) => us.length > 1 && new Set(us.map(stripLocale)).size > 1);
  if (dups.length)
    add("seo.title.duplicate", "minor", "Duplicate <title> across pages",
      dups.map(([t, us]) => `"${t}": ${us.join(", ")}`).join("; "), dups[0][1][0],
      "Give every page a unique, descriptive title", "S", true);

  if (anyPage && !anyJsonld)
    add("seo.jsonld.none", "info", "No JSON-LD structured data on sampled pages",
      `none of ${sample.length} sampled pages has an application/ld+json block`, base.href,
      "Add Person/WebSite (and CreativeWork per project) JSON-LD", "M", false);

  // Emit aggregated findings
  const META = {
    "seo.sitemap.broken-url": ["major", "S", false, "Sitemap lists URLs that do not resolve", "Remove or fix these URLs; sitemaps must list final 200 canonical URLs"],
    "seo.title.missing": ["major", "S", true, "Pages without a <title>", "Add a unique title per page"],
    "seo.meta-description.missing": ["minor", "S", true, "Pages without a meta description", "Add a 70-155 char description per page"],
    "seo.canonical.missing": ["minor", "S", true, "Pages without rel=canonical", "Emit an absolute self-referencing canonical in the layout"],
    "seo.canonical.mismatch": ["minor", "S", false, "Canonical differs from the served URL", "Make pages self-canonical (host, scheme and trailing slash must match)"],
    "seo.canonical.not-in-sitemap": ["minor", "S", false, "Canonical URLs missing from the sitemap", "Sitemap and canonicals must agree on the canonical form"],
    "seo.og.missing": ["major", "S", true, "Pages without Open Graph tags", "Add og:title, og:description and og:image in the layout head"],
    "seo.og.partial": ["minor", "S", true, "Pages with an incomplete Open Graph set", "Complete og:title + og:description + og:image"],
    "seo.og.url-mismatch": ["minor", "S", true, "og:url disagrees with the canonical", "Set og:url to the canonical URL"],
    "seo.og.image-broken": ["major", "S", false, "og:image URLs that do not resolve", "Point og:image at a live 1200x630 https image"],
    "seo.twitter.missing": ["minor", "S", true, "Pages without a twitter:card tag", "Add twitter:card (summary_large_image) alongside OG"],
    "seo.jsonld.invalid": ["major", "S", false, "JSON-LD blocks that fail to parse", "Fix the JSON syntax; validate with the Rich Results Test"],
    "seo.jsonld.incomplete": ["minor", "S", false, "JSON-LD missing @context/@type", "Use schema.org @context and a concrete @type"],
    "seo.noindex.in-sitemap": ["major", "S", true, "Sitemap pages marked noindex", "Remove noindex (meta or X-Robots-Tag) or drop the URL from the sitemap"],
    "seo.hreflang.missing": ["major", "S", true, "Localized site but no hreflang alternates", "Emit link rel=alternate hreflang for every locale + x-default on every page"],
    "seo.hreflang.missing-locale": ["major", "S", true, "hreflang set lacks configured locales", "Add the missing locale alternates (reciprocal on every page)"],
    "seo.hreflang.no-x-default": ["minor", "S", true, "hreflang set has no x-default", "Add an x-default alternate pointing at the default-locale page"],
    "seo.hreflang.broken-alternate": ["major", "S", false, "hreflang alternates that do not resolve", "Fix or remove alternates that 404"],
    "seo.links.broken": ["major", "M", false, "Broken internal links", "Fix or remove links that 404"],
    "seo.links.redirected": ["minor", "S", true, "Internal links answering with redirects", "Link the final URL directly to avoid chains"],
  };
  for (const [id, evs] of Object.entries(agg)) {
    const [severity, effort, autoFixable, title, fix] = META[id];
    add(id, severity, title, list(evs), firstUrl[id] ?? base.href, fix, effort, autoFixable);
  }

  return { dimension: "seo-and-social", score: score(findings), findings };
}

if (process.argv[1] && /check-seo\.mjs$/.test(process.argv[1])) {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) { console.error("Usage: node check-seo.mjs <url> [--locales pt,de] [--max-pages 5] [--json]"); process.exit(2); }
  const opt = (name) => { const i = args.findIndex((a) => a === name || a.startsWith(`${name}=`)); return i < 0 ? undefined : (args[i].split("=")[1] ?? args[i + 1]); };
  const locales = (opt("--locales") ?? "").split(",").filter(Boolean);
  const maxPages = Number(opt("--max-pages") ?? 5);
  const r = await audit(url, { locales, maxPages });
  if (args.includes("--json")) console.log(JSON.stringify(r, null, 2));
  else {
    console.log(`seo-and-social score: ${r.score}/100`);
    for (const f of r.findings) console.log(`  [${f.severity}] ${f.id} — ${f.title}\n      ${f.evidence}`);
    if (!r.findings.length) console.log("  no findings");
  }
}
