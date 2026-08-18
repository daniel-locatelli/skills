# Hub + Agent Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `auditing-website-quality` hub and the first sub-skill `auditing-agent-readiness` (rollout step 2 of `docs/superpowers/specs/2026-08-18-web-quality-audit-skills-design.md`).

**Architecture:** Each sub-skill is a folder with `SKILL.md` + a zero-dependency Node ESM check script that emits the shared findings contract as JSON. The hub's `aggregate.mjs` merges any number of such JSON files into a dated markdown scorecard with ranked fixes. Skill prose is written RED→GREEN with subagents (writing-skills); scripts are written test-first with `node:test` and injected fakes (no network in tests).

**Tech Stack:** Node ≥ 20 (`fetch`, `node:test`, `node:fs`), ESM `.mjs`, no npm dependencies. Windows-friendly paths.

## Global Constraints

- SKILL.md < ~500 words; `description` = "Use when…" triggers only, no workflow summary.
- Findings contract (verbatim from spec): `{ dimension, score 0-100, findings: [{ id, severity: blocker|major|minor|info, title, evidence, url|file, fix, effort: S|M|L, autoFixable }] }`.
- Score = 100 − (blocker×25 + major×10 + minor×3 + info×0), floored at 0.
- Hub rank = severityWeight / effortWeight with severity blocker 25, major 10, minor 3, info 0 and effort S=1, M=2, L=4; ties by dimension order: performance, agent-readiness, security-headers, seo-and-social, content-integrity.
- Scripts run as `node <skill>/scripts/<check>.mjs <url|path> [--json]`, zero deps.
- Tests: `node --test skills/web/**/scripts/*.test.mjs`, no network.
- Generic core; Astro/Cloudflare specifics only under "If Astro" / "If Cloudflare" markers.
- Cross-reference Addy Osmani's `web-quality-skills` for fix catalogues; do not duplicate.
- Deploy = directory junction `~/.claude/skills/<name>` → repo folder (`cmd /c mklink /J`), then `pwsh ~/.claude/skills/system/scripts/refresh-index.ps1`.

---

## File structure

```
skills/web/
  auditing-agent-readiness/
    SKILL.md
    scripts/
      check-agent-readiness.mjs        # audit(baseUrl, deps) + CLI
      check-agent-readiness.test.mjs   # node:test, fake fetch
      fixtures/
        good-site.mjs                  # url -> {status, headers, body}
        broken-site.mjs
  auditing-website-quality/
    SKILL.md
    templates/scorecard.md
    scripts/
      aggregate.mjs                    # aggregate(reports, meta) -> markdown + CLI
      aggregate.test.mjs
      fixtures/
        agent-readiness.json           # a findings-contract sample
        performance.json
```

---

### Task 1: Agent-readiness check script (fixtures + core checks)

**Files:**
- Create: `skills/web/auditing-agent-readiness/scripts/check-agent-readiness.mjs`
- Create: `skills/web/auditing-agent-readiness/scripts/check-agent-readiness.test.mjs`
- Create: `skills/web/auditing-agent-readiness/scripts/fixtures/good-site.mjs`
- Create: `skills/web/auditing-agent-readiness/scripts/fixtures/broken-site.mjs`

**Interfaces:**
- Produces: `export async function audit(baseUrl, { fetch, locales = [], dohUrl } = {})` → findings-contract object with `dimension: "agent-readiness"`. `export function score(findings)`. `export function makeFakeFetch(table)` lives in the test file. Fixture modules export `default` = `{ [pathOrUrl]: { status, headers: {}, body } }` keyed by `METHOD path` (e.g. `"GET /llms.txt"`, `"POST /api/mcp"`), plus optional per-request-header variants keyed `"GET /projects/x accept=text/markdown"`.

- [ ] **Step 1: Write the good/broken fixtures**

`fixtures/good-site.mjs`:
```js
// Minimal agent-ready site. Keys: "METHOD /path" or "METHOD /path accept=<value>".
const md = { "content-type": "text/markdown; charset=utf-8" };
const json = { "content-type": "application/json" };
export default {
  "GET /": { status: 200, headers: { "content-type": "text/html", link: '</sitemap-index.xml>; rel="sitemap"', "x-robots-tag": "all" }, body: "<html></html>" },
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body:
    "User-agent: *\nAllow: /\nUser-agent: GPTBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\nUser-agent: CCBot\nAllow: /\nContent-Signal: search=yes, ai-train=yes, ai-input=yes\nSitemap: https://example.com/sitemap-index.xml\n" },
  "GET /sitemap-index.xml": { status: 200, headers: { "content-type": "application/xml" }, body: "<sitemapindex/>" },
  "GET /llms.txt": { status: 200, headers: md, body: "# Example\n\n## Projects\n- [A](https://example.com/projects/a)\n" },
  "GET /pt/llms.txt": { status: 200, headers: md, body: "# Example\n\n- [A](https://example.com/pt/projects/a)\n" },
  "GET /projects/a.md": { status: 200, headers: md, body: "# A\n" },
  "GET /projects/a accept=text/markdown": { status: 200, headers: md, body: "# A\n" },
  "GET /projects/a": { status: 200, headers: { "content-type": "text/html" }, body: "<html></html>" },
  "GET /.well-known/api-catalog": { status: 200, headers: { "content-type": "application/linkset+json" }, body: JSON.stringify({ linkset: [{ anchor: "https://example.com", "service-desc": [{ href: "https://example.com/.well-known/mcp.json" }, { href: "https://example.com/.well-known/agent-skills/index.json" }] }] }) },
  "GET /.well-known/mcp.json": { status: 200, headers: json, body: JSON.stringify({ name: "example", transport: { type: "streamable-http", url: "https://example.com/api/mcp" }, tools: [{ name: "get_page" }] }) },
  "POST /api/mcp initialize": { status: 200, headers: json, body: JSON.stringify({ jsonrpc: "2.0", id: 0, result: { protocolVersion: "2025-06-18", serverInfo: { name: "example" }, capabilities: { tools: {} } } }) },
  "POST /api/mcp tools/list": { status: 200, headers: json, body: JSON.stringify({ jsonrpc: "2.0", id: 1, result: { tools: [{ name: "get_page", inputSchema: { type: "object" } }] } }) },
  "GET /.well-known/agent-skills/index.json": { status: 200, headers: json, body: JSON.stringify({ skills: [{ name: "example-content", type: "skill-md", url: "https://example.com/.well-known/agent-skills/example-content/SKILL.md", digest: "sha256:" + "a".repeat(64) }] }) },
  "GET /.well-known/agent-skills/example-content/SKILL.md": { status: 200, headers: md, body: "---\nname: example-content\ndescription: x\n---\n# x\n" },
  "DOH _mcp._agents.example.com": { status: 200, headers: json, body: JSON.stringify({ Status: 0, Answer: [{ name: "_mcp._agents.example.com", type: 64, data: "1 example.com. alpn=h2" }] }) },
};
```

`fixtures/broken-site.mjs`:
```js
// Site with nothing agent-facing and a robots.txt that blocks AI crawlers.
export default {
  "GET /": { status: 200, headers: { "content-type": "text/html", "x-robots-tag": "noindex" }, body: "<html></html>" },
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "User-agent: *\nAllow: /\nUser-agent: GPTBot\nDisallow: /\nUser-agent: ClaudeBot\nDisallow: /\n" },
  "GET /sitemap.xml": { status: 404, headers: {}, body: "" },
  "GET /sitemap-index.xml": { status: 404, headers: {}, body: "" },
  "GET /llms.txt": { status: 404, headers: {}, body: "" },
  "GET /.well-known/api-catalog": { status: 404, headers: {}, body: "" },
  "GET /.well-known/mcp.json": { status: 404, headers: {}, body: "" },
  "GET /.well-known/agent-skills/index.json": { status: 404, headers: {}, body: "" },
  "DOH _mcp._agents.example.com": { status: 200, headers: { "content-type": "application/json" }, body: JSON.stringify({ Status: 3, Answer: [] }) },
};
```

- [ ] **Step 2: Write the failing tests**

`check-agent-readiness.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { audit, score } from "./check-agent-readiness.mjs";
import good from "./fixtures/good-site.mjs";
import broken from "./fixtures/broken-site.mjs";

// Builds a fetch(url, init) that answers from a fixture table.
export function makeFakeFetch(table) {
  return async (url, init = {}) => {
    const u = new URL(url);
    const method = (init.method || "GET").toUpperCase();
    let key;
    if (u.hostname === "cloudflare-dns.com") key = `DOH ${u.searchParams.get("name")}`;
    else if (method === "POST") key = `POST ${u.pathname} ${JSON.parse(init.body).method}`;
    else {
      const accept = init.headers?.Accept || init.headers?.accept;
      key = accept ? `GET ${u.pathname} accept=${accept}` : `GET ${u.pathname}`;
    }
    const hit = table[key] || { status: 404, headers: {}, body: "" };
    return {
      status: hit.status, ok: hit.status >= 200 && hit.status < 300,
      headers: new Headers(hit.headers), text: async () => hit.body,
      json: async () => JSON.parse(hit.body),
    };
  };
}

const ids = (r) => r.findings.map((f) => f.id).sort();

test("score deducts by severity and floors at 0", () => {
  assert.equal(score([]), 100);
  assert.equal(score([{ severity: "blocker" }, { severity: "major" }, { severity: "minor" }, { severity: "info" }]), 62);
  assert.equal(score(Array(5).fill({ severity: "blocker" })), 0);
});

test("good site scores 100 with only info findings", async () => {
  const r = await audit("https://example.com", { fetch: makeFakeFetch(good), locales: ["pt"] });
  assert.equal(r.dimension, "agent-readiness");
  assert.equal(r.score, 100);
  assert.ok(r.findings.every((f) => f.severity === "info"), JSON.stringify(r.findings, null, 2));
});

test("broken site reports the expected findings", async () => {
  const r = await audit("https://example.com", { fetch: makeFakeFetch(broken), locales: ["pt"] });
  const got = ids(r);
  for (const id of [
    "ar.robots.blocks-ai-crawlers", "ar.robots.no-sitemap", "ar.sitemap.missing",
    "ar.llms-txt.missing", "ar.well-known.api-catalog.missing", "ar.headers.x-robots-noindex",
    "ar.mcp.not-advertised", "ar.agent-skills.not-advertised", "ar.dns.aid.missing",
  ]) assert.ok(got.includes(id), `missing ${id} in ${got}`);
  assert.ok(r.score < 50, `score ${r.score}`);
  for (const f of r.findings) {
    assert.ok(["blocker", "major", "minor", "info"].includes(f.severity));
    assert.ok(["S", "M", "L"].includes(f.effort));
    assert.equal(typeof f.autoFixable, "boolean");
    assert.ok(f.title && f.evidence && f.fix && f.url);
  }
});

test("missing locale llms.txt is a major finding", async () => {
  const table = { ...good }; delete table["GET /pt/llms.txt"];
  const r = await audit("https://example.com", { fetch: makeFakeFetch(table), locales: ["pt"] });
  const f = r.findings.find((x) => x.id === "ar.llms-txt.missing-locale");
  assert.ok(f); assert.equal(f.severity, "major"); assert.equal(f.url, "https://example.com/pt/llms.txt");
});

test("mcp advertised but handshake fails is major", async () => {
  const table = { ...good }; delete table["POST /api/mcp initialize"];
  const r = await audit("https://example.com", { fetch: makeFakeFetch(table) });
  assert.ok(ids(r).includes("ar.mcp.initialize-failed"));
  assert.equal(r.findings.find((f) => f.id === "ar.mcp.initialize-failed").severity, "major");
});

test("markdown variant + negotiation are probed from the first llms.txt link", async () => {
  const table = { ...good }; delete table["GET /projects/a.md"]; delete table["GET /projects/a accept=text/markdown"];
  const r = await audit("https://example.com", { fetch: makeFakeFetch(table) });
  assert.ok(ids(r).includes("ar.markdown-variant.missing"));
  assert.ok(ids(r).includes("ar.negotiation.missing"));
});
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `node --test skills/web/auditing-agent-readiness/scripts/`
Expected: FAIL — `Cannot find module './check-agent-readiness.mjs'`.

- [ ] **Step 4: Write the implementation**

`check-agent-readiness.mjs`:
```js
#!/usr/bin/env node
// Agent-readiness audit: llms.txt, markdown variants, robots AI rules, sitemap,
// .well-known (api-catalog, mcp.json, agent-skills), MCP handshake, DNS-AID.
// Usage: node check-agent-readiness.mjs https://site [--locales pt,de] [--json]
// Emits the findings contract (see docs/superpowers/specs/2026-08-18-*.md).

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
    try { const r = await f(url, { headers }); return { url, r, ct: r.headers.get("content-type") || "" }; }
    catch (e) { return { url, r: null, error: String(e) }; }
  };
  const isMd = (ct) => /^text\/markdown/i.test(ct);

  // Root headers
  const root = await get("/");
  if (root.r) {
    const xr = root.r.headers.get("x-robots-tag") || "";
    if (/noindex/i.test(xr)) add("ar.headers.x-robots-noindex", "blocker", "X-Robots-Tag: noindex on the homepage", `X-Robots-Tag: ${xr}`, root.url, "Remove noindex from the response headers (or scope it to private paths only).", "S", true);
    const link = root.r.headers.get("link") || "";
    if (!/rel="?sitemap"?/i.test(link)) add("ar.headers.link-sitemap.missing", "info", "No Link: rel=sitemap header on the homepage", `Link: ${link || "(none)"}`, root.url, "Add `Link: </sitemap-index.xml>; rel=\"sitemap\"` (If Cloudflare: in `public/_headers`).", "S", true);
  }

  // robots.txt
  const robots = await get("/robots.txt");
  let sitemapUrl = null;
  if (!robots.r || robots.r.status !== 200) add("ar.robots.missing", "major", "robots.txt missing", `status ${robots.r?.status ?? robots.error}`, robots.url, "Serve /robots.txt with `User-agent: *`, `Allow: /` and a `Sitemap:` line.", "S", true);
  else {
    const body = await robots.r.text();
    const m = body.match(/^Sitemap:\s*(\S+)/im);
    if (m) sitemapUrl = m[1]; else add("ar.robots.no-sitemap", "minor", "robots.txt has no Sitemap: line", body.slice(0, 200), robots.url, "Append `Sitemap: <absolute sitemap URL>` to robots.txt.", "S", true);
    const blocked = AI_BOTS.filter((b) => new RegExp(`User-agent:\\s*${b}\\s*\\n(?:[^\\n]*\\n)*?\\s*Disallow:\\s*/\\s*$`, "im").test(body));
    if (blocked.length) add("ar.robots.blocks-ai-crawlers", "major", "robots.txt blocks AI crawlers", `Disallow: / for ${blocked.join(", ")}`, robots.url, "Decide per crawler; if the site wants to be found by AI agents, `Allow: /` for these user agents (and consider a `Content-Signal:` line).", "S", true);
    else if (!AI_BOTS.some((b) => body.includes(`User-agent: ${b}`))) add("ar.robots.no-ai-rules", "info", "robots.txt has no explicit AI-crawler rules", "only wildcard rules found", robots.url, "Optional: add explicit `User-agent: GPTBot|ClaudeBot|…` blocks and a `Content-Signal:` line to state intent.", "S", true);
  }

  // sitemap
  const candidates = sitemapUrl ? [sitemapUrl] : ["/sitemap-index.xml", "/sitemap.xml"];
  let sitemapOk = false;
  for (const c of candidates) { const s = await get(c); if (s.r?.status === 200) { sitemapOk = true; break; } }
  if (!sitemapOk) add("ar.sitemap.missing", "major", "No sitemap reachable", `tried ${candidates.join(", ")}`, origin + (sitemapUrl ? "" : "/sitemap-index.xml"), "Generate a sitemap (If Astro: `@astrojs/sitemap`) and reference it from robots.txt.", "S", true);

  // llms.txt (root + locales)
  const llms = await get("/llms.txt");
  let firstLink = null;
  if (llms.r?.status !== 200) add("ar.llms-txt.missing", "major", "/llms.txt missing", `status ${llms.r?.status ?? llms.error}`, llms.url, "Publish /llms.txt (llmstxt.org): H1 site name, blockquote summary, H2 sections with links to the canonical pages.", "M", false);
  else {
    if (!isMd(llms.ct)) add("ar.llms-txt.wrong-content-type", "minor", "/llms.txt not served as text/markdown", `content-type: ${llms.ct}`, llms.url, "Set `Content-Type: text/markdown; charset=utf-8` for /llms.txt (If Cloudflare: `public/_headers`).", "S", true);
    const body = await llms.r.text();
    const lm = body.match(/\]\((https?:\/\/[^)\s]+)\)/); if (lm && new URL(lm[1]).origin === origin) firstLink = lm[1];
    if (!/^# /m.test(body)) add("ar.llms-txt.no-h1", "minor", "/llms.txt has no H1", body.slice(0, 120), llms.url, "Start llms.txt with `# <site name>`.", "S", true);
  }
  for (const loc of locales) {
    const l = await get(`/${loc}/llms.txt`);
    if (l.r?.status !== 200) add("ar.llms-txt.missing-locale", "major", `/${loc}/llms.txt missing`, `status ${l.r?.status ?? l.error}`, l.url, `Publish a localized llms.txt for ${loc} linking the ${loc} pages.`, "M", false);
    else if (!isMd(l.ct)) add("ar.llms-txt.wrong-content-type", "minor", `/${loc}/llms.txt not served as text/markdown`, `content-type: ${l.ct}`, l.url, "Set `Content-Type: text/markdown; charset=utf-8`.", "S", true);
  }
  const full = await get("/llms-full.txt");
  if (full.r?.status !== 200) add("ar.llms-full.missing", "info", "/llms-full.txt not present", `status ${full.r?.status ?? full.error}`, full.url, "Optional: publish a concatenated llms-full.txt for single-fetch ingestion.", "M", false);

  // markdown variant + negotiation, probed on the first same-origin llms.txt link
  if (firstLink) {
    const path = new URL(firstLink).pathname.replace(/\/$/, "");
    const md = await get(`${path}.md`);
    if (!(md.r?.status === 200 && isMd(md.ct))) add("ar.markdown-variant.missing", "major", "Content pages have no .md variant", `${path}.md → ${md.r?.status ?? md.error} ${md.ct || ""}`, md.url, "Serve each content page at `<path>.md` as text/markdown (If Astro: emit `.md` endpoints from the content collection).", "M", false);
    const neg = await get(path, { Accept: "text/markdown" });
    if (!(neg.r?.status === 200 && isMd(neg.ct))) add("ar.negotiation.missing", "minor", "No Accept: text/markdown negotiation on canonical URLs", `${path} with Accept: text/markdown → ${neg.ct || neg.r?.status || neg.error}`, neg.url, "Rewrite to the .md variant when `Accept: text/markdown` (If Cloudflare: a zone Snippet/Worker; prerendered pages cannot negotiate on their own).", "M", false);
  }

  // .well-known
  const cat = await get("/.well-known/api-catalog");
  if (cat.r?.status !== 200) add("ar.well-known.api-catalog.missing", "minor", "/.well-known/api-catalog missing", `status ${cat.r?.status ?? cat.error}`, cat.url, "Publish an RFC 9727 linkset (`application/linkset+json`) pointing at mcp.json / agent-skills index.", "S", true);
  const mcp = await get("/.well-known/mcp.json");
  if (mcp.r?.status !== 200) add("ar.mcp.not-advertised", "info", "No /.well-known/mcp.json", `status ${mcp.r?.status ?? mcp.error}`, mcp.url, "Optional: expose a read-only MCP server (streamable-http) and advertise it in mcp.json.", "L", false);
  else {
    let j = null; try { j = await mcp.r.json(); } catch {}
    const ep = j?.transport?.url;
    if (!ep) add("ar.mcp.manifest-invalid", "major", "mcp.json has no transport.url", JSON.stringify(j).slice(0, 200), mcp.url, "Add `transport: { type: \"streamable-http\", url }` and a `tools` array.", "S", true);
    else {
      const post = async (payload) => { try { const r = await f(ep, { method: "POST", headers: { "content-type": "application/json", accept: "application/json, text/event-stream" }, body: JSON.stringify(payload) }); return { r, j: r.status === 200 ? await r.json().catch(() => null) : null }; } catch (e) { return { r: null, j: null, error: String(e) }; } };
      const init = await post({ jsonrpc: "2.0", id: 0, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "auditing-agent-readiness", version: "0" } } });
      if (!init.j?.result?.protocolVersion) add("ar.mcp.initialize-failed", "major", "MCP initialize handshake failed", `POST ${ep} → ${init.r?.status ?? init.error}`, ep, "Make the endpoint answer JSON-RPC `initialize` with `result.protocolVersion` and `serverInfo`.", "M", false);
      const tl = await post({ jsonrpc: "2.0", id: 1, method: "tools/list" });
      const tools = tl.j?.result?.tools;
      if (!Array.isArray(tools) || tools.length === 0) add("ar.mcp.tools-list-failed", "major", "MCP tools/list returned no tools", `POST ${ep} → ${tl.r?.status ?? tl.error}`, ep, "Return the tool list with `inputSchema.type: \"object\"` per tool.", "M", false);
      else if (Array.isArray(j?.tools) && j.tools.map((t) => t.name).sort().join() !== tools.map((t) => t.name).sort().join()) add("ar.mcp.manifest-drift", "minor", "mcp.json tools differ from live tools/list", `manifest: ${j.tools.map((t) => t.name)} live: ${tools.map((t) => t.name)}`, mcp.url, "Regenerate mcp.json from the server's tool registry at build time.", "S", true);
    }
  }
  const idx = await get("/.well-known/agent-skills/index.json");
  if (idx.r?.status !== 200) add("ar.agent-skills.not-advertised", "info", "No /.well-known/agent-skills/index.json", `status ${idx.r?.status ?? idx.error}`, idx.url, "Optional: publish an Agent Skills index whose SKILL.md files teach agents how to use the site.", "M", false);
  else {
    let j = null; try { j = await idx.r.json(); } catch {}
    for (const s of j?.skills ?? []) {
      if (!/^sha256:[0-9a-f]{64}$/.test(s.digest || "")) add("ar.agent-skills.bad-digest", "minor", `Skill ${s.name} has no sha256 digest`, `digest: ${s.digest}`, idx.url, "Compute `sha256:<hex>` of the SKILL.md at build time.", "S", true);
      const sk = await get(s.url);
      if (!(sk.r?.status === 200 && new RegExp(`^---\\r?\\nname: ${s.name}\\r?\\n`).test(await sk.r.text().catch(() => "")))) add("ar.agent-skills.unresolvable", "major", `Skill ${s.name} URL does not resolve to a SKILL.md with that name`, `${s.url} → ${sk.r?.status ?? sk.error}`, s.url, "Fix the URL or the frontmatter `name:`; regenerate the index.", "S", true);
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

// CLI
if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, "/")}` || import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) { console.error("Usage: node check-agent-readiness.mjs <url> [--locales pt,de] [--json]"); process.exit(2); }
  const li = args.indexOf("--locales");
  const locales = li >= 0 ? args[li + 1].split(",").filter(Boolean) : [];
  const report = await audit(url, { locales });
  if (args.includes("--json")) console.log(JSON.stringify(report, null, 2));
  else {
    console.log(`agent-readiness  score ${report.score}/100  (${report.findings.length} findings)`);
    for (const f of report.findings) console.log(`  [${f.severity}] ${f.id}  ${f.title}\n      ${f.evidence}\n      fix: ${f.fix}`);
  }
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `node --test skills/web/auditing-agent-readiness/scripts/`
Expected: 6 pass, 0 fail. If the good-site test lists non-info findings, adjust the fixture (not the severities) until the fixture represents an actually agent-ready site.

- [ ] **Step 6: Smoke the CLI against a real site (network)**

Run: `node skills/web/auditing-agent-readiness/scripts/check-agent-readiness.mjs https://daniellocatelli.com --locales pt,de`
Expected: score ≥ 90; only info-level findings (`ar.llms-full.missing` is expected). Also run `--json` and confirm it parses. Fix the CLI-detection line if it prints nothing on Windows.

- [ ] **Step 7: Commit**

```bash
git add skills/web/auditing-agent-readiness/scripts
git commit -m "auditing-agent-readiness: check script with fixture tests"
```

---

### Task 2: Agent-readiness SKILL.md (RED → GREEN with subagents)

**Files:**
- Create: `skills/web/auditing-agent-readiness/SKILL.md`

**Interfaces:**
- Consumes: `scripts/check-agent-readiness.mjs` CLI from Task 1.
- Produces: skill folder that the hub (Task 4) references by name `auditing-agent-readiness`.

- [ ] **Step 1: RED baseline — subagent WITHOUT the skill**

Dispatch a `general-purpose` subagent with exactly this prompt and record its answer verbatim in the scratchpad (`baseline-agent-readiness.md`):

> You are auditing whether https://daniellocatelli.com is "agent-ready" (discoverable and usable by AI agents/crawlers). Do NOT run any tools; describe the concrete checks you would perform, the URLs you would fetch, and how you would score/report the result. Be specific.

Note which of these it misses: locale llms.txt, `.md` variants, `Accept: text/markdown` negotiation, `/.well-known/api-catalog`, `mcp.json` + live JSON-RPC handshake, agent-skills index digest check, DNS-AID SVCB, `Content-Signal`, X-Robots-Tag; whether it proposes a scoring rubric; whether it distinguishes "deliberately declined" items (OAuth, A2A card, WebMCP for read-only sites) from real gaps.

- [ ] **Step 2: Write SKILL.md addressing the gaps**

```markdown
---
name: auditing-agent-readiness
description: Use when asked whether a website is agent-ready, AI-crawler friendly, or discoverable by LLM agents — llms.txt, markdown variants, robots AI rules, .well-known (mcp.json, api-catalog, agent-skills), MCP handshake, DNS-AID — or when re-checking an isitagentready.com score.
---

# Auditing agent readiness

Agent readiness = an agent can **find** the site (robots, sitemap, DNS-AID,
`.well-known`), **read** it cheaply (llms.txt per locale, `.md` variants,
`Accept: text/markdown`), and **act** on it (MCP, Agent Skills). Machine checks
first, judgment second, one findings JSON out.

## 1. Run the checker

```bash
node ~/.claude/skills/auditing-agent-readiness/scripts/check-agent-readiness.mjs \
  https://example.com --locales pt,de --json > $S/agent-readiness.json
```
Human-readable without `--json`. Locales = the site's non-default locale
prefixes. Needs network; DNS-AID goes through Cloudflare DoH.

## 2. Judge what the script can't

| Check | Verdict rule |
|---|---|
| llms.txt content | H1 + one-line blockquote + H2 sections linking canonical URLs; per locale, links point at that locale's pages |
| Blocked AI crawlers | Only a *finding* if the owner wants AI visibility; a deliberate block is `info` with the reason recorded |
| MCP present | Read-only sites: `list_*` + `get_page` + `search` is enough; every tool needs `inputSchema.type: object` |
| Auth / OAuth discovery, A2A agent card, WebMCP | **Not gaps** for a site with nothing to log in to, no agent-to-agent service, no in-page actions. Record as "declined by design" so re-audits do not resurface them |
| isitagentready.com | Re-run for the external number; expect the API/auth category to stay open on read-only sites |

## 3. Report

Findings contract: `{ dimension, score, findings[{ id, severity, title, evidence, url, fix, effort, autoFixable }] }`. Standalone: paste the ranked table into
the answer. Under the hub (`auditing-website-quality`): hand the JSON path over.

## If Astro / If Cloudflare

- **If Astro:** llms.txt and `.md` variants are static endpoints built from the
  content collection; agent-skills index + digests from a build script.
- **If Cloudflare:** headers in `public/_headers` (`Link: rel=sitemap`,
  `X-Robots-Tag`, `Content-Type` for `.txt`/`.md`); `Accept: text/markdown`
  needs a zone Snippet/Worker rewrite because prerendered assets do not
  negotiate.

## Common mistakes

- Reporting the isitagentready checklist verbatim (auth items on a brochure site).
- Checking `/llms.txt` only in the default locale.
- Trusting `mcp.json` without a live `initialize` + `tools/list`.
- Scoring "no MCP" as a blocker; it is `info` unless the owner asked for one.
```

- [ ] **Step 3: GREEN — same subagent prompt WITH the skill**

Re-dispatch the Step 1 prompt, prepending: "Read `C:\repos\github\daniel-locatelli\skills\skills\web\auditing-agent-readiness\SKILL.md` first and follow it." Confirm it names the checker, the locale sweep, negotiation, live MCP handshake, DNS-AID, and treats auth/A2A/WebMCP as declined-by-design. If it still misses an item, add one line to the skill (not a paragraph) and re-run once.

- [ ] **Step 4: Word count and description check**

Run: `wc -w skills/web/auditing-agent-readiness/SKILL.md` — expected < ~500. Description starts with "Use when", no workflow summary.

- [ ] **Step 5: Commit**

```bash
git add skills/web/auditing-agent-readiness/SKILL.md
git commit -m "auditing-agent-readiness: SKILL.md (RED/GREEN tested)"
```

---

### Task 3: Hub aggregator script + scorecard template

**Files:**
- Create: `skills/web/auditing-website-quality/scripts/aggregate.mjs`
- Create: `skills/web/auditing-website-quality/scripts/aggregate.test.mjs`
- Create: `skills/web/auditing-website-quality/scripts/fixtures/agent-readiness.json`
- Create: `skills/web/auditing-website-quality/scripts/fixtures/performance.json`
- Create: `skills/web/auditing-website-quality/templates/scorecard.md`

**Interfaces:**
- Consumes: findings-contract JSON files (any dimension).
- Produces: `export function rank(findings)`, `export function aggregate(reports, meta)` → markdown string; CLI `node aggregate.mjs --site <url> [--commit <sha>] [--date YYYY-MM-DD] --out <file> <report.json>...`.

- [ ] **Step 1: Write fixtures**

`fixtures/agent-readiness.json`:
```json
{ "dimension": "agent-readiness", "score": 87, "findings": [
  { "id": "ar.llms-txt.missing-locale", "severity": "major", "title": "/pt/llms.txt missing", "evidence": "status 404", "url": "https://example.com/pt/llms.txt", "fix": "Publish a localized llms.txt for pt.", "effort": "M", "autoFixable": false },
  { "id": "ar.robots.no-sitemap", "severity": "minor", "title": "robots.txt has no Sitemap: line", "evidence": "User-agent: *", "url": "https://example.com/robots.txt", "fix": "Append Sitemap: line.", "effort": "S", "autoFixable": true },
  { "id": "ar.dns.aid.missing", "severity": "info", "title": "No DNS-AID record", "evidence": "Status 3", "url": "dns://_mcp._agents.example.com", "fix": "Optional SVCB record.", "effort": "S", "autoFixable": true }
] }
```
`fixtures/performance.json`:
```json
{ "dimension": "performance", "score": 75, "findings": [
  { "id": "perf.tbt", "severity": "blocker", "title": "TBT 620 ms on mobile", "evidence": "lighthouse total-blocking-time 620", "url": "https://example.com/", "fix": "Defer the Three.js chunk with requestIdleCallback.", "effort": "L", "autoFixable": false },
  { "id": "perf.contrast", "severity": "major", "title": "Contrast 4.2:1 in footer", "evidence": "zinc-500 on #09090b", "url": "https://example.com/", "fix": "Use zinc-400.", "effort": "S", "autoFixable": true }
] }
```

`templates/scorecard.md` (placeholders `{{…}}` are filled by `aggregate.mjs`; `{{#…}}` blocks are generated tables):
```markdown
# Website quality audit — {{site}}

Date: {{date}} · Commit: {{commit}} · Generated by `auditing-website-quality`

## Scores

{{scoreTable}}

Overall: **{{overall}}/100** (mean of dimension scores).

## Ranked fixes (top {{topN}})

{{rankedTable}}

## Proposed next actions

{{nextActions}}

**Awaiting approval before any fix is applied.**

## Appendix — all findings

{{allFindings}}
```

- [ ] **Step 2: Write the failing tests**

`aggregate.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { rank, aggregate } from "./aggregate.mjs";

const ar = JSON.parse(readFileSync(new URL("./fixtures/agent-readiness.json", import.meta.url)));
const perf = JSON.parse(readFileSync(new URL("./fixtures/performance.json", import.meta.url)));

test("rank orders by severity/effort, then dimension order", () => {
  const ranked = rank([...ar.findings.map((f) => ({ ...f, dimension: "agent-readiness" })), ...perf.findings.map((f) => ({ ...f, dimension: "performance" }))]);
  assert.deepEqual(ranked.map((f) => f.id), ["perf.contrast", "perf.tbt", "ar.llms-txt.missing-locale", "ar.robots.no-sitemap", "ar.dns.aid.missing"]);
  // perf.contrast: 10/1 = 10; perf.tbt: 25/4 = 6.25; missing-locale: 10/2 = 5; no-sitemap 3/1 = 3; info 0
});

test("aggregate renders a scorecard from the template", () => {
  const md = aggregate([perf, ar], { site: "https://example.com", date: "2026-08-18", commit: "abc1234", topN: 3 });
  assert.match(md, /^# Website quality audit — https:\/\/example.com/);
  assert.match(md, /\| performance \| 75 \|/);
  assert.match(md, /\| agent-readiness \| 87 \|/);
  assert.match(md, /Overall: \*\*81\/100\*\*/);
  assert.match(md, /\| 1 \| perf\.contrast \|/);
  assert.match(md, /Awaiting approval/);
  assert.ok(md.indexOf("perf.contrast") < md.indexOf("perf.tbt"));
  assert.match(md, /ar\.dns\.aid\.missing/); // appears in appendix even if beyond topN
});

test("aggregate lists dimensions in canonical order regardless of input order", () => {
  const md = aggregate([ar, perf], { site: "x", date: "d", commit: "c" });
  assert.ok(md.indexOf("| performance |") < md.indexOf("| agent-readiness |"));
});
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `node --test skills/web/auditing-website-quality/scripts/`
Expected: FAIL — cannot find `./aggregate.mjs`.

- [ ] **Step 4: Implement `aggregate.mjs`**

```js
#!/usr/bin/env node
// Merge findings-contract JSON reports into a dated markdown scorecard.
// Usage: node aggregate.mjs --site <url> [--commit <sha>] [--date YYYY-MM-DD] [--top 10] --out <file> <report.json>...
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const SEV = { blocker: 25, major: 10, minor: 3, info: 0 };
const EFF = { S: 1, M: 2, L: 4 };
export const DIMENSION_ORDER = ["performance", "agent-readiness", "security-headers", "seo-and-social", "content-integrity"];
const dimIdx = (d) => { const i = DIMENSION_ORDER.indexOf(d); return i < 0 ? DIMENSION_ORDER.length : i; };

export function rank(findings) {
  const w = (f) => (SEV[f.severity] ?? 0) / (EFF[f.effort] ?? 2);
  return [...findings].sort((a, b) => w(b) - w(a) || dimIdx(a.dimension) - dimIdx(b.dimension) || (SEV[b.severity] ?? 0) - (SEV[a.severity] ?? 0));
}

const esc = (s) => String(s ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
const table = (header, rows) => [`| ${header.join(" | ")} |`, `|${header.map(() => "---").join("|")}|`, ...rows.map((r) => `| ${r.map(esc).join(" | ")} |`)].join("\n");

export function aggregate(reports, { site, date, commit = "n/a", topN = 10, template } = {}) {
  const tpl = template ?? readFileSync(new URL("../templates/scorecard.md", import.meta.url), "utf8");
  const sorted = [...reports].sort((a, b) => dimIdx(a.dimension) - dimIdx(b.dimension));
  const all = sorted.flatMap((r) => r.findings.map((f) => ({ ...f, dimension: r.dimension })));
  const ranked = rank(all);
  const overall = sorted.length ? Math.round(sorted.reduce((s, r) => s + r.score, 0) / sorted.length) : 0;
  const scoreTable = table(["Dimension", "Score", "Blockers", "Major", "Minor", "Info"], sorted.map((r) => {
    const c = (s) => r.findings.filter((f) => f.severity === s).length;
    return [r.dimension, r.score, c("blocker"), c("major"), c("minor"), c("info")];
  }));
  const top = ranked.filter((f) => f.severity !== "info").slice(0, topN);
  const rankedTable = table(["#", "ID", "Severity", "Effort", "Dimension", "Title", "Fix"], top.map((f, i) => [i + 1, f.id, f.severity, f.effort, f.dimension, f.title, f.fix]));
  const nextActions = top.slice(0, 5).map((f, i) => `${i + 1}. ${f.title} — ${f.fix}${f.autoFixable ? " *(auto-fixable)*" : ""}`).join("\n") || "_No actionable findings._";
  const allFindings = table(["ID", "Severity", "Dimension", "Title", "Evidence", "Location", "Effort", "Auto"], ranked.map((f) => [f.id, f.severity, f.dimension, f.title, f.evidence, f.url ?? f.file ?? "", f.effort, f.autoFixable ? "yes" : "no"]));
  return tpl.replace(/\{\{(\w+)\}\}/g, (_, k) => ({ site, date, commit, overall, topN, scoreTable, rankedTable, nextActions, allFindings })[k] ?? "");
}

const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/").replace(/^\/?/, "/").replace(/^\/([A-Za-z]:)/, "$1"));
if (isMain || import.meta.url === new URL(`file:///${process.argv[1].replace(/\\/g, "/")}`).href) {
  const a = process.argv.slice(2);
  const opt = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
  const files = a.filter((x, i) => !x.startsWith("--") && !["--site", "--commit", "--date", "--top", "--out"].includes(a[i - 1]));
  const site = opt("--site"); const out = opt("--out");
  if (!site || !files.length) { console.error("Usage: node aggregate.mjs --site <url> [--commit sha] [--date YYYY-MM-DD] [--top N] [--out file] <report.json>..."); process.exit(2); }
  const reports = files.map((f) => JSON.parse(readFileSync(f, "utf8")));
  const md = aggregate(reports, { site, commit: opt("--commit", "n/a"), date: opt("--date", new Date().toISOString().slice(0, 10)), topN: Number(opt("--top", 10)) });
  if (out) { mkdirSync(dirname(out), { recursive: true }); writeFileSync(out, md); console.log(`wrote ${out}`); } else process.stdout.write(md);
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `node --test skills/web/auditing-website-quality/scripts/`
Expected: 3 pass. Then a CLI smoke: `node skills/web/auditing-website-quality/scripts/aggregate.mjs --site https://example.com --date 2026-08-18 skills/web/auditing-website-quality/scripts/fixtures/*.json | head -30` prints the scorecard. If the main-module guard misfires on Windows, simplify it to `if (process.argv[1] && /aggregate\.mjs$/.test(process.argv[1]))` and apply the same simplification to Task 1's script.

- [ ] **Step 6: Commit**

```bash
git add skills/web/auditing-website-quality
git commit -m "auditing-website-quality: aggregate script, scorecard template, tests"
```

---

### Task 4: Hub SKILL.md (RED → GREEN) with perf adapter note

**Files:**
- Create: `skills/web/auditing-website-quality/SKILL.md`
- Modify: `skills/web/optimizing-web-performance/SKILL.md` (append one "Under the hub" paragraph, ≤ 5 lines)

**Interfaces:**
- Consumes: `auditing-agent-readiness` CLI, `optimizing-web-performance` `lh-summary.mjs`, `aggregate.mjs`.

- [ ] **Step 1: RED baseline**

Dispatch a `general-purpose` subagent (no tools) with:

> A client asks: "Do a full quality audit of https://example-client.com and tell me what to fix." Describe exactly what you would check, in what order, what the deliverable looks like, and when you would start changing code.

Record verbatim to scratchpad `baseline-hub.md`. Look for: does it start fixing without approval? Does it produce a written scorecard in the repo? Does it cover agent readiness at all? Does it rank by severity × effort or just list?

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: auditing-website-quality
description: Use when asked for a full website quality audit, a site health check / scorecard, "what should we fix on this site", or a client-facing review covering performance, accessibility, SEO, security headers, agent readiness, and content/i18n integrity of a deployed site.
---

# Auditing website quality (hub)

Sweep every dimension with its sub-skill, aggregate into **one dated
scorecard in the repo**, rank fixes by severity ÷ effort, then **stop and ask**
before changing anything.

## Dimensions and sub-skills

| Dimension | Sub-skill | Output |
|---|---|---|
| Performance / a11y / SEO / BP (Lighthouse) | `optimizing-web-performance` | `lh-summary.mjs` → write `performance.json` by hand from the < 0.9 audits (blocker: score < 0.5 on a CWV metric; major: any category < 90; minor: single audit < 0.9) |
| Agent readiness | `auditing-agent-readiness` | `check-agent-readiness.mjs --json` |
| Security & headers | `auditing-security-headers` (planned) | `check-headers.mjs --json` |
| SEO & social depth | `auditing-seo-and-social` (planned) | `check-seo.mjs --json` |
| Content & i18n integrity | `auditing-content-integrity` (planned) | `check-content.mjs --json` |

Skip a planned sub-skill if its folder does not exist yet; note the gap in
the scorecard.

## Procedure

1. Confirm target URL, locales, repo path (or none), and whether Lighthouse
   should be mobile, desktop, or both. `S` = session scratchpad.
2. Run each available sub-skill; save `$S/<dimension>.json` in the findings
   contract `{ dimension, score, findings[{ id, severity, title, evidence,
   url|file, fix, effort, autoFixable }] }`.
3. Aggregate:
   ```bash
   node ~/.claude/skills/auditing-website-quality/scripts/aggregate.mjs \
     --site https://example.com --commit $(git rev-parse --short HEAD) \
     --out docs/audits/$(date +%F)-website-quality.md $S/*.json
   ```
   No repo → write to the cwd and say so.
4. Read the scorecard back; add a 3–5 line **Summary** at the top in your own
   words (biggest lever, quick wins, anything declined by design).
5. Present the top-10 table and **wait for approval**. Then fix in ranked
   order, one commit per finding group, re-run the affected sub-skill, and
   append a "Re-check" section to the same scorecard.

## Rules

- Never fix before the scorecard exists and the user has approved.
- Rank = severity weight (blocker 25, major 10, minor 3) ÷ effort (S 1, M 2,
  L 4); the script does this — do not reorder by taste.
- Deliberately declined items stay in the appendix as `info` with the reason.
- Fix catalogues live in Addy Osmani's `web-quality-skills`; this hub only
  orchestrates.

## Common mistakes

- Running only Lighthouse and calling it an audit.
- Fixing the first thing you see; the scorecard comes first.
- One-off scorecard in chat instead of `docs/audits/` (loses the re-check).
```

Append to `optimizing-web-performance/SKILL.md`:
```markdown

## Under the hub

When invoked by `auditing-website-quality`, do not fix; convert the
`lh-summary` output into `$S/performance.json` in the findings contract
(blocker: CWV metric score < 0.5; major: category < 90; minor: audit < 0.9)
and return.
```

- [ ] **Step 3: GREEN**

Re-dispatch the Step 1 prompt with "Read `…\auditing-website-quality\SKILL.md` first and follow it." Confirm: scorecard file in `docs/audits/`, all dimensions listed, ranked table, explicit stop for approval. Patch the skill with one line per remaining gap and re-run once.

- [ ] **Step 4: Word count** `wc -w skills/web/auditing-website-quality/SKILL.md` < ~500.

- [ ] **Step 5: Commit**

```bash
git add skills/web/auditing-website-quality/SKILL.md skills/web/optimizing-web-performance/SKILL.md
git commit -m "auditing-website-quality: hub SKILL.md; perf skill hub note"
```

---

### Task 5: End-to-end validation on two sites

**Files:**
- Create (in scratchpad, not committed): `$S/e2e/*.json`, `$S/e2e/*.md`

- [ ] **Step 1: daniellocatelli.com** — run agent-readiness (`--locales pt,de --json`), run Lighthouse via `optimizing-web-performance` step 1 + `lh-summary.mjs`, hand-write `performance.json`, aggregate with `--out $S/e2e/dl.md`. Read the scorecard: no false positives (every non-info finding must be real when checked by hand).
- [ ] **Step 2: Unrelated public site** (e.g. `https://astro.build`) — same, without locales. Confirm the script survives redirects, non-JSON `.well-known`, missing MCP, and slow DoH without crashing (any exception → an `*.unchecked` info finding, not a crash). Fix and add a regression test in Task 1's test file for each crash found.
- [ ] **Step 3: Commit any fixes** `git commit -am "auditing-agent-readiness: hardening from e2e"`.

---

### Task 6: Register, deploy, document

**Files:**
- Modify: `.claude-plugin/plugin.json` (add two skill paths), `.claude-plugin/marketplace.json` (version), `README.md` (Web section), `CHANGELOG.md`, `skills/web/README.md`

- [ ] **Step 1: plugin.json** — append `"./skills/web/auditing-website-quality"`, `"./skills/web/auditing-agent-readiness"`; bump both manifests to `1.4.0`.
- [ ] **Step 2: README Web section** — replace the "(in progress)" bullet with two real bullets linking the SKILL.md files; add both folders to the layout tree.
- [ ] **Step 3: CHANGELOG** — `## 1.4.0 — <date>`: hub + agent-readiness shipped, findings contract, remaining sub-skills planned.
- [ ] **Step 4: Deploy junctions**
```powershell
cmd /c mklink /J "$env:USERPROFILE\.claude\skills\auditing-website-quality" "C:\repos\github\daniel-locatelli\skills\skills\web\auditing-website-quality"
cmd /c mklink /J "$env:USERPROFILE\.claude\skills\auditing-agent-readiness" "C:\repos\github\daniel-locatelli\skills\skills\web\auditing-agent-readiness"
pwsh ~/.claude/skills/system/scripts/refresh-index.ps1
```
Expected: `INDEX.md` lists both with `has-repo`, and `optimizing-web-performance` flips from `loose` to `has-repo`.
- [ ] **Step 5: Run all tests** `node --test skills/web/**/scripts/*.test.mjs` → all pass.
- [ ] **Step 6: Commit and push** `git commit -am "Ship auditing-website-quality hub + auditing-agent-readiness (1.4.0)" && git push`.
- [ ] **Step 7: Remind the user** to run `/sync-knowledge` in the portfolio repo (pending from the previous session).
