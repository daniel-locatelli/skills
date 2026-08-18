#!/usr/bin/env node
// Agent-readiness audit: llms.txt, markdown variants, robots AI rules, sitemap,
// .well-known (api-catalog, mcp.json, agent-skills), MCP handshake, DNS-AID.
// Usage: node check-agent-readiness.mjs https://site [--locales pt,de] [--json]
// Emits the findings contract (see docs/superpowers/specs/2026-08-18-*.md).
// Zero dependencies; Node >= 20.

const WEIGHT = { blocker: 25, major: 10, minor: 3, info: 0 };
export function score(findings) {
  return Math.max(0, 100 - findings.reduce((s, f) => s + (WEIGHT[f.severity] ?? 0), 0));
}

const AI_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"];
const DOH = "https://cloudflare-dns.com/dns-query";

export async function audit(baseUrl, { fetch: f = globalThis.fetch, locales = [], dohUrl = DOH } = {}) {
  const base = new URL(baseUrl);
  const origin = base.origin;
  const findings = [];
  const add = (id, severity, title, evidence, url, fix, effort, autoFixable = false) =>
    findings.push({ id, severity, title, evidence, url, fix, effort, autoFixable });
  const get = async (path, headers) => {
    const url = path.startsWith("http") ? path : origin + path;
    try {
      const r = await f(url, { headers, redirect: "follow" });
      return { url, r, ct: r.headers.get("content-type") || "" };
    } catch (e) { return { url, r: null, ct: "", error: String(e) }; }
  };
  const st = (x) => x.r?.status ?? x.error ?? "no response";
  const isMd = (ct) => /^text\/markdown/i.test(ct);
  const safeJson = async (r) => { try { return await r.json(); } catch { return null; } };
  const safeText = async (r) => { try { return await r.text(); } catch { return ""; } };

  // Root headers
  const root = await get("/");
  if (root.r) {
    const xr = root.r.headers.get("x-robots-tag") || "";
    if (/noindex/i.test(xr)) add("ar.headers.x-robots-noindex", "blocker", "X-Robots-Tag: noindex on the homepage", `X-Robots-Tag: ${xr}`, root.url, "Remove noindex from the response headers (or scope it to private paths only).", "S", true);
    const link = root.r.headers.get("link") || "";
    if (!/rel="?sitemap"?/i.test(link)) add("ar.headers.link-sitemap.missing", "info", "No Link: rel=sitemap header on the homepage", `Link: ${link || "(none)"}`, root.url, "Add `Link: </sitemap-index.xml>; rel=\"sitemap\"` (If Cloudflare: in `public/_headers`).", "S", true);
  } else {
    add("ar.site.unreachable", "blocker", "Homepage did not respond", String(root.error), root.url, "Check the URL / network and re-run.", "S", false);
  }

  // robots.txt
  const robots = await get("/robots.txt");
  let sitemapUrl = null;
  if (robots.r?.status !== 200) add("ar.robots.missing", "major", "robots.txt missing", `status ${st(robots)}`, robots.url, "Serve /robots.txt with `User-agent: *`, `Allow: /` and a `Sitemap:` line.", "S", true);
  else {
    const body = await safeText(robots.r);
    const m = body.match(/^Sitemap:\s*(\S+)/im);
    if (m) sitemapUrl = m[1]; else add("ar.robots.no-sitemap", "minor", "robots.txt has no Sitemap: line", body.slice(0, 200) || "(empty)", robots.url, "Append `Sitemap: <absolute sitemap URL>` to robots.txt.", "S", true);
    // A bot is "blocked" if its User-agent group contains a bare `Disallow: /`.
    const groups = body.split(/\n(?=User-agent:)/i);
    const blocked = AI_BOTS.filter((b) => groups.some((g) => new RegExp(`^User-agent:\\s*${b}\\s*$`, "im").test(g) && /^Disallow:\s*\/\s*$/im.test(g)));
    if (blocked.length) add("ar.robots.blocks-ai-crawlers", "major", "robots.txt blocks AI crawlers", `Disallow: / for ${blocked.join(", ")}`, robots.url, "Decide per crawler; if the site wants to be found by AI agents, `Allow: /` for these user agents (and consider a `Content-Signal:` line). A deliberate block is fine: record it as declined by design.", "S", true);
    else if (!AI_BOTS.some((b) => new RegExp(`^User-agent:\\s*${b}\\s*$`, "im").test(body))) add("ar.robots.no-ai-rules", "info", "robots.txt has no explicit AI-crawler rules", "only wildcard rules found", robots.url, "Optional: add explicit `User-agent: GPTBot|ClaudeBot|…` blocks and a `Content-Signal:` line to state intent.", "S", true);
  }

  // sitemap
  const candidates = sitemapUrl ? [sitemapUrl] : ["/sitemap-index.xml", "/sitemap.xml"];
  let sitemapOk = false;
  for (const c of candidates) { const s = await get(c); if (s.r?.status === 200) { sitemapOk = true; break; } }
  if (!sitemapOk) add("ar.sitemap.missing", "major", "No sitemap reachable", `tried ${candidates.join(", ")}`, sitemapUrl || origin + "/sitemap-index.xml", "Generate a sitemap (If Astro: `@astrojs/sitemap`) and reference it from robots.txt.", "S", true);

  // llms.txt (root + locales)
  const llms = await get("/llms.txt");
  const sampleLinks = [];
  if (llms.r?.status !== 200) add("ar.llms-txt.missing", "major", "/llms.txt missing", `status ${st(llms)}`, llms.url, "Publish /llms.txt (llmstxt.org): H1 site name, blockquote summary, H2 sections with links to the canonical pages.", "M", false);
  else {
    if (!isMd(llms.ct)) add("ar.llms-txt.wrong-content-type", "minor", "/llms.txt not served as text/markdown", `content-type: ${llms.ct || "(none)"}`, llms.url, "Set `Content-Type: text/markdown; charset=utf-8` for /llms.txt (If Cloudflare: `public/_headers`).", "S", true);
    const body = await safeText(llms.r);
    // Up to 3 distinct same-origin links to non-root pages (the homepage rarely has a .md twin).
    for (const m of body.matchAll(/\]\((https?:\/\/[^)\s]+)\)/g)) {
      try {
        const u = new URL(m[1]);
        const path = u.pathname.replace(/\/$/, "");
        if (u.origin === origin && path && !sampleLinks.includes(path)) sampleLinks.push(path);
        if (sampleLinks.length >= 3) break;
      } catch {}
    }
    if (!/^# /m.test(body)) add("ar.llms-txt.no-h1", "minor", "/llms.txt has no H1", body.slice(0, 120) || "(empty)", llms.url, "Start llms.txt with `# <site name>`.", "S", true);
  }
  for (const loc of locales) {
    const l = await get(`/${loc}/llms.txt`);
    if (l.r?.status !== 200) add("ar.llms-txt.missing-locale", "major", `/${loc}/llms.txt missing`, `status ${st(l)}`, l.url, `Publish a localized llms.txt for ${loc} linking the ${loc} pages.`, "M", false);
    else if (!isMd(l.ct)) add("ar.llms-txt.wrong-content-type", "minor", `/${loc}/llms.txt not served as text/markdown`, `content-type: ${l.ct || "(none)"}`, l.url, "Set `Content-Type: text/markdown; charset=utf-8`.", "S", true);
  }
  const full = await get("/llms-full.txt");
  if (full.r?.status !== 200) add("ar.llms-full.missing", "info", "/llms-full.txt not present", `status ${st(full)}`, full.url, "Optional: publish a concatenated llms-full.txt for single-fetch ingestion.", "M", false);

  // markdown variant + negotiation, probed on sample same-origin llms.txt links
  if (sampleLinks.length) {
    const noMd = [], noNeg = [];
    for (const path of sampleLinks) {
      const md = await get(`${path}.md`);
      if (!(md.r?.status === 200 && isMd(md.ct))) noMd.push(`${path}.md → ${st(md)} ${md.ct}`.trim());
      const neg = await get(path, { Accept: "text/markdown" });
      if (!(neg.r?.status === 200 && isMd(neg.ct))) noNeg.push(`${path} → ${neg.ct || st(neg)}`);
    }
    const all = (arr) => arr.length === sampleLinks.length;
    if (noMd.length) add("ar.markdown-variant.missing", all(noMd) ? "major" : "minor", all(noMd) ? "Content pages have no .md variant" : "Some pages have no .md variant", noMd.join("; "), origin + sampleLinks[0] + ".md", "Serve each content page at `<path>.md` as text/markdown (If Astro: emit `.md` endpoints from the content collection).", "M", false);
    if (noNeg.length) add("ar.negotiation.missing", all(noNeg) ? "minor" : "info", "No Accept: text/markdown negotiation on canonical URLs", noNeg.join("; "), origin + sampleLinks[0], "Rewrite to the .md variant when `Accept: text/markdown` (If Cloudflare: a zone Snippet/Worker; prerendered pages cannot negotiate on their own).", "M", false);
  } else if (llms.r?.status === 200) {
    add("ar.markdown-variant.unchecked", "info", "Could not probe .md variants: llms.txt has no same-origin markdown link", "no `[text](https://<same host>/…)` link found", llms.url, "Link canonical pages from llms.txt so agents (and this checker) can find them.", "S", true);
  }

  // .well-known
  const cat = await get("/.well-known/api-catalog");
  if (cat.r?.status !== 200) add("ar.well-known.api-catalog.missing", "minor", "/.well-known/api-catalog missing", `status ${st(cat)}`, cat.url, "Publish an RFC 9727 linkset (`application/linkset+json`) pointing at mcp.json / agent-skills index.", "S", true);
  const mcp = await get("/.well-known/mcp.json");
  if (mcp.r?.status !== 200) add("ar.mcp.not-advertised", "info", "No /.well-known/mcp.json", `status ${st(mcp)}`, mcp.url, "Optional: expose a read-only MCP server (streamable-http) and advertise it in mcp.json.", "L", false);
  else {
    const j = await safeJson(mcp.r);
    const ep = j?.transport?.url;
    if (!ep) add("ar.mcp.manifest-invalid", "major", "mcp.json is not JSON or has no transport.url", JSON.stringify(j)?.slice(0, 200) ?? "(unparseable)", mcp.url, "Add `transport: { type: \"streamable-http\", url }` and a `tools` array.", "S", true);
    else {
      const post = async (payload) => {
        try {
          const r = await f(ep, { method: "POST", headers: { "content-type": "application/json", accept: "application/json, text/event-stream" }, body: JSON.stringify(payload) });
          return { r, j: r.status === 200 ? await safeJson(r) : null };
        } catch (e) { return { r: null, j: null, error: String(e) }; }
      };
      const init = await post({ jsonrpc: "2.0", id: 0, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "auditing-agent-readiness", version: "0" } } });
      if (!init.j?.result?.protocolVersion) add("ar.mcp.initialize-failed", "major", "MCP initialize handshake failed", `POST ${ep} → ${init.r?.status ?? init.error}`, ep, "Make the endpoint answer JSON-RPC `initialize` with `result.protocolVersion` and `serverInfo`.", "M", false);
      const tl = await post({ jsonrpc: "2.0", id: 1, method: "tools/list" });
      const tools = tl.j?.result?.tools;
      if (!Array.isArray(tools) || tools.length === 0) add("ar.mcp.tools-list-failed", "major", "MCP tools/list returned no tools", `POST ${ep} → ${tl.r?.status ?? tl.error}`, ep, "Return the tool list with `inputSchema.type: \"object\"` per tool.", "M", false);
      else if (Array.isArray(j?.tools) && j.tools.map((t) => t.name).sort().join() !== tools.map((t) => t.name).sort().join()) add("ar.mcp.manifest-drift", "minor", "mcp.json tools differ from live tools/list", `manifest: ${j.tools.map((t) => t.name).join(",")} live: ${tools.map((t) => t.name).join(",")}`, mcp.url, "Regenerate mcp.json from the server's tool registry at build time.", "S", true);
    }
  }
  const idx = await get("/.well-known/agent-skills/index.json");
  if (idx.r?.status !== 200) add("ar.agent-skills.not-advertised", "info", "No /.well-known/agent-skills/index.json", `status ${st(idx)}`, idx.url, "Optional: publish an Agent Skills index whose SKILL.md files teach agents how to use the site.", "M", false);
  else {
    const j = await safeJson(idx.r);
    if (!Array.isArray(j?.skills)) add("ar.agent-skills.index-invalid", "minor", "agent-skills index is not JSON with a `skills` array", JSON.stringify(j)?.slice(0, 200) ?? "(unparseable)", idx.url, "Emit `{ skills: [{ name, type: \"skill-md\", url, digest }] }`.", "S", true);
    for (const s of j?.skills ?? []) {
      if (!/^sha256:[0-9a-f]{64}$/.test(s.digest || "")) add("ar.agent-skills.bad-digest", "minor", `Skill ${s.name} has no sha256 digest`, `digest: ${s.digest}`, idx.url, "Compute `sha256:<hex>` of the SKILL.md at build time.", "S", true);
      const sk = s.url ? await get(s.url) : { r: null, url: idx.url, error: "no url" };
      const body = sk.r ? await safeText(sk.r) : "";
      if (!(sk.r?.status === 200 && new RegExp(`^---\\r?\\nname: ${s.name}\\r?\\n`).test(body))) add("ar.agent-skills.unresolvable", "major", `Skill ${s.name} URL does not resolve to a SKILL.md with that name`, `${s.url} → ${st(sk)}`, s.url || idx.url, "Fix the URL or the frontmatter `name:`; regenerate the index.", "S", true);
    }
  }

  // DNS-AID (SVCB via DoH; Node's dns module has no SVCB support)
  const host = base.hostname;
  try {
    const r = await f(`${dohUrl}?name=_mcp._agents.${host}&type=SVCB`, { headers: { accept: "application/dns-json" } });
    const j = await r.json();
    if (!(j.Status === 0 && Array.isArray(j.Answer) && j.Answer.length)) add("ar.dns.aid.missing", "info", "No DNS-AID `_mcp._agents` SVCB record", `DoH Status ${j.Status}, ${j.Answer?.length ?? 0} answers`, `dns://_mcp._agents.${host}`, "Optional: add `_mcp._agents.<host> SVCB 1 <host>. alpn=h2` (+ `_index._agents`) so agents can find the MCP endpoint from the domain.", "S", true);
  } catch (e) { add("ar.dns.aid.unchecked", "info", "DNS-AID lookup failed", String(e), `dns://_mcp._agents.${host}`, "Re-run with network access, or query `dig _mcp._agents.<host> SVCB` manually.", "S", false); }

  return { dimension: "agent-readiness", score: score(findings), findings };
}

// CLI (guard tolerates Windows paths)
if (process.argv[1] && /check-agent-readiness\.mjs$/.test(process.argv[1])) {
  const args = process.argv.slice(2);
  const url = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--locales");
  if (!url) { console.error("Usage: node check-agent-readiness.mjs <url> [--locales pt,de] [--json]"); process.exit(2); }
  const li = args.indexOf("--locales");
  const locales = li >= 0 ? (args[li + 1] || "").split(",").filter(Boolean) : [];
  const report = await audit(url, { locales });
  if (args.includes("--json")) console.log(JSON.stringify(report, null, 2));
  else {
    console.log(`agent-readiness  score ${report.score}/100  (${report.findings.length} findings)`);
    for (const f of report.findings) console.log(`  [${f.severity}] ${f.id}  ${f.title}\n      ${f.evidence}\n      fix: ${f.fix}`);
  }
}
