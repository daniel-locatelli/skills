#!/usr/bin/env node
// Security & headers audit. Zero deps, Node >= 20.
// Usage: node check-headers.mjs <url> [--pages /a,/b] [--json]
// Emits the shared findings contract: { dimension, score, findings[] }.

const W = { blocker: 25, major: 10, minor: 3, info: 0 };
export function score(findings) {
  return Math.max(0, 100 - findings.reduce((s, f) => s + (W[f.severity] ?? 0), 0));
}

const parseCsp = (csp) => {
  const d = {};
  for (const part of csp.split(";")) {
    const toks = part.trim().split(/\s+/).filter(Boolean);
    if (toks.length) d[toks[0].toLowerCase()] = toks.slice(1).map((t) => t.toLowerCase());
  }
  return d;
};

const getCookies = (res) =>
  res.headers.getSetCookie ? res.headers.getSetCookie()
    : res.headers.get("set-cookie") ? [res.headers.get("set-cookie")] : [];

export async function audit(baseUrl, { fetch = globalThis.fetch, pages = [] } = {}) {
  const base = new URL(baseUrl);
  const findings = [];
  const add = (id, severity, title, evidence, url, fix, effort, autoFixable) =>
    findings.push({ id, severity, title, evidence, url, fix, effort, autoFixable });

  // Plaintext-HTTP probe: must redirect to https.
  try {
    const httpUrl = `http://${base.host}/`;
    const r = await fetch(httpUrl, { redirect: "manual" });
    const loc = r.headers.get("location") || "";
    if (![301, 302, 307, 308].includes(r.status) || !loc.startsWith("https://"))
      add("sec.tls.http-not-redirected", "blocker", "Plain HTTP is served without redirecting to HTTPS",
        `GET ${httpUrl} -> ${r.status}${loc ? ` location: ${loc}` : ""}`, httpUrl,
        "Force 301 to https:// at the edge (host/platform setting) and enable HSTS", "S", false);
  } catch (e) {
    add("sec.tls.http-unchecked", "info", "Plain-HTTP redirect could not be checked",
      String(e), `http://${base.host}/`, "Verify manually: curl -sI http://host/ should 301 to https", "S", false);
  }

  let root;
  try {
    root = await fetch(base.href, { redirect: "follow" });
  } catch (e) {
    add("sec.unchecked", "info", "Site unreachable; header checks skipped", String(e), base.href,
      "Re-run when the site is reachable", "S", false);
    return { dimension: "security-headers", score: score(findings), findings };
  }
  const h = root.headers;

  // CSP
  const csp = h.get("content-security-policy");
  const cspRO = h.get("content-security-policy-report-only");
  let enforced = null;
  if (csp) {
    enforced = parseCsp(csp);
    const script = enforced["script-src"] ?? enforced["default-src"] ?? [];
    const hasNonceOrHash = script.some((t) => /^'(nonce-|sha(256|384|512)-)/.test(t));
    if (script.includes("'unsafe-inline'") && !hasNonceOrHash)
      add("sec.csp.unsafe-inline", "major", "CSP allows 'unsafe-inline' scripts without nonce/hash",
        `script-src: ${script.join(" ") || "(default-src fallback)"}`, base.href,
        "Move inline scripts to files or add nonces/hashes, then drop 'unsafe-inline'", "M", false);
    if (script.includes("'unsafe-eval'"))
      add("sec.csp.unsafe-eval", "major", "CSP allows 'unsafe-eval'",
        `script-src: ${script.join(" ")}`, base.href,
        "Remove 'unsafe-eval'; replace eval/new Function usage in bundles", "M", false);
    if (script.includes("*") || script.includes("http:"))
      add("sec.csp.wildcard", "major", "CSP script sources include a wildcard or http:",
        `script-src: ${script.join(" ")}`, base.href,
        "List explicit https origins instead of * / http:", "S", false);
  } else if (cspRO) {
    add("sec.csp.report-only", "minor", "CSP is present only in Report-Only mode",
      `Content-Security-Policy-Report-Only: ${cspRO.slice(0, 120)}`, base.href,
      "Promote the policy to an enforcing Content-Security-Policy header once reports are clean", "S", false);
  } else {
    add("sec.csp.missing", "major", "No Content-Security-Policy header",
      "content-security-policy absent on the document response", base.href,
      "Add a CSP; start with default-src 'self' plus the origins the site actually uses", "M", false);
  }

  // HSTS
  const hsts = h.get("strict-transport-security");
  if (!hsts)
    add("sec.hsts.missing", "major", "No Strict-Transport-Security header",
      "strict-transport-security absent", base.href,
      "Add: Strict-Transport-Security: max-age=63072000; includeSubDomains; preload", "S", true);
  else {
    const maxAge = Number((hsts.match(/max-age=(\d+)/i) || [])[1] || 0);
    if (maxAge < 15552000)
      add("sec.hsts.short-max-age", "minor", "HSTS max-age below 180 days",
        `strict-transport-security: ${hsts}`, base.href,
        "Raise max-age to at least 15552000 (ideally 63072000)", "S", true);
  }

  // Simple header presence
  if (!(h.get("x-content-type-options") || "").toLowerCase().includes("nosniff"))
    add("sec.xcto.missing", "minor", "No X-Content-Type-Options: nosniff",
      "x-content-type-options absent", base.href, "Add: X-Content-Type-Options: nosniff", "S", true);
  if (!h.get("x-frame-options") && !(enforced && enforced["frame-ancestors"]))
    add("sec.xfo.missing", "minor", "No clickjacking protection (X-Frame-Options / frame-ancestors)",
      "Neither x-frame-options nor CSP frame-ancestors present", base.href,
      "Add CSP frame-ancestors 'none' (or X-Frame-Options: DENY)", "S", true);
  if (!h.get("referrer-policy"))
    add("sec.referrer-policy.missing", "minor", "No Referrer-Policy header",
      "referrer-policy absent", base.href,
      "Add: Referrer-Policy: strict-origin-when-cross-origin", "S", true);
  if (!h.get("permissions-policy"))
    add("sec.permissions-policy.missing", "info", "No Permissions-Policy header",
      "permissions-policy absent", base.href,
      "Add: Permissions-Policy: camera=(), microphone=(), geolocation=()", "S", true);

  const deprecated = ["x-xss-protection", "expect-ct"].filter((n) => h.get(n) && !(n === "x-xss-protection" && h.get(n).trim() === "0"));
  if (deprecated.length)
    add("sec.headers.deprecated", "info", "Deprecated security headers present",
      deprecated.map((n) => `${n}: ${h.get(n)}`).join("; "), base.href,
      "Remove them; they are obsolete and X-XSS-Protection can introduce issues", "S", true);

  for (const name of ["server", "x-powered-by"]) {
    const v = h.get(name);
    if (v && /\d/.test(v)) {
      add("sec.server.verbose", "minor", "Server header discloses software version",
        `${name}: ${v}`, base.href, "Strip or genericise the header at the edge", "S", false);
      break;
    }
  }

  // Exposed sensitive files (content-sniffed to survive SPA soft-404s)
  const probes = [["/.env", /^[A-Z0-9_]+\s*=/m], ["/.git/HEAD", /^ref: /], ["/.git/config", /\[core\]/]];
  const exposed = [];
  for (const [path, sniff] of probes) {
    try {
      const res = await fetch(new URL(path, base).href);
      if (res.status === 200 && sniff.test(await res.text())) exposed.push(path);
    } catch { /* unreachable = not exposed */ }
  }
  if (exposed.length)
    add("sec.files.exposed", "blocker", "Sensitive files are publicly reachable",
      exposed.map((p) => `${p} returns 200 with matching content`).join("; "), new URL(exposed[0], base).href,
      "Remove them from the published output; rotate any credentials they contain", "S", false);

  // security.txt
  try {
    const res = await fetch(new URL("/.well-known/security.txt", base).href);
    if (res.status !== 200)
      add("sec.security-txt.missing", "info", "No /.well-known/security.txt",
        `GET /.well-known/security.txt -> ${res.status}`, new URL("/.well-known/security.txt", base).href,
        "Publish a security.txt with a Contact: line (RFC 9116)", "S", true);
  } catch { /* skip */ }

  // Cookies on root + extra pages
  const cookieSources = [[base.href, root]];
  for (const p of pages) {
    const u = new URL(p, base).href;
    try { cookieSources.push([u, await fetch(u, { redirect: "follow" })]); }
    catch (e) {
      add("sec.unchecked", "info", "Page could not be fetched for cookie checks", String(e), u,
        "Re-check this page manually", "S", false);
    }
  }
  const badCookies = [];
  let cookieMajor = false;
  for (const [u, res] of cookieSources)
    for (const c of getCookies(res)) {
      const name = c.split("=")[0].trim();
      const missing = [];
      if (!/;\s*secure/i.test(c)) { missing.push("Secure"); cookieMajor = true; }
      if (!/;\s*httponly/i.test(c)) missing.push("HttpOnly");
      if (!/;\s*samesite=/i.test(c)) missing.push("SameSite");
      if (missing.length) badCookies.push(`${name} (${u}): missing ${missing.join(", ")}`);
    }
  if (badCookies.length)
    add("sec.cookies.flags", cookieMajor ? "major" : "minor", "Cookies set without security flags",
      badCookies.join("; "), base.href,
      "Set Secure, HttpOnly and SameSite (Lax or Strict) on every cookie", "M", false);

  // HTML body: mixed content + SRI
  try {
    const html = await root.text();
    const mixed = [...html.matchAll(/(?:src|href)=["'](http:\/\/[^"']+)["']/gi)].map((m) => m[1]);
    if (mixed.length)
      add("sec.mixed-content", "major", "Page references plain-HTTP resources",
        [...new Set(mixed)].slice(0, 3).join(", ") + (mixed.length > 3 ? ` (+${mixed.length - 3} more)` : ""),
        base.href, "Serve every referenced resource over https://", "M", false);
    const noSri = [];
    for (const m of html.matchAll(/<script\b[^>]*\bsrc=["'](https:\/\/[^"']+)["'][^>]*>|<link\b[^>]*\bhref=["'](https:\/\/[^"']+)["'][^>]*>/gi)) {
      const tag = m[0], url = m[1] || m[2];
      if (m[2] && !/rel=["']?stylesheet/i.test(tag)) continue;
      try { if (new URL(url).host !== base.host && !/\bintegrity=/i.test(tag)) noSri.push(url); } catch {}
    }
    if (noSri.length)
      add("sec.sri.missing", "minor", "Cross-origin scripts/styles without Subresource Integrity",
        [...new Set(noSri)].slice(0, 3).join(", ") + (noSri.length > 3 ? ` (+${noSri.length - 3} more)` : ""),
        base.href, "Add integrity + crossorigin attributes, or self-host the assets", "S", true);
  } catch { /* body unreadable: header findings stand */ }

  return { dimension: "security-headers", score: score(findings), findings };
}

if (process.argv[1] && /check-headers\.mjs$/.test(process.argv[1])) {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) { console.error("Usage: node check-headers.mjs <url> [--pages /a,/b] [--json]"); process.exit(2); }
  const pagesArg = args.find((a) => a.startsWith("--pages"));
  const pages = pagesArg ? (pagesArg.split("=")[1] ?? args[args.indexOf(pagesArg) + 1] ?? "").split(",").filter(Boolean) : [];
  const r = await audit(url, { pages });
  if (args.includes("--json")) console.log(JSON.stringify(r, null, 2));
  else {
    console.log(`security-headers score: ${r.score}/100`);
    for (const f of r.findings) console.log(`  [${f.severity}] ${f.id} — ${f.title}\n      ${f.evidence}`);
    if (!r.findings.length) console.log("  no findings");
  }
}
