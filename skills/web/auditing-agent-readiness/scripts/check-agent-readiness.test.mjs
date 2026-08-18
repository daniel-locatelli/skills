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
      const ua = init.headers?.["User-Agent"] || init.headers?.["user-agent"];
      key = accept ? `GET ${u.pathname} accept=${accept}` : ua ? `GET ${u.pathname} ua=${(ua.match(/GPTBot|ClaudeBot|PerplexityBot/) || [ua])[0]}` : `GET ${u.pathname}`;
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
    assert.ok(f.title && f.evidence && f.fix && f.url, JSON.stringify(f));
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

test("a fetch that throws yields findings, not a crash", async () => {
  const throwing = async () => { throw new Error("ECONNRESET"); };
  const r = await audit("https://example.com", { fetch: throwing });
  assert.equal(r.dimension, "agent-readiness");
  assert.ok(r.findings.length > 0);
});

test("homepage returning 403 / a challenge page to an AI user agent is major", async () => {
  const table = { ...good, "GET / ua=ClaudeBot": { status: 403, headers: {}, body: "" }, "GET / ua=GPTBot": { status: 200, headers: { "content-type": "text/html" }, body: "<title>Just a moment...</title>" } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(table) });
  const f = r.findings.find((x) => x.id === "ar.bots.ua-blocked");
  assert.ok(f); assert.equal(f.severity, "major");
  assert.match(f.evidence, /ClaudeBot/); assert.match(f.evidence, /GPTBot/);
});
