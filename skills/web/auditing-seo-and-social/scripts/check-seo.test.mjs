import { test } from "node:test";
import assert from "node:assert/strict";
import { audit, score } from "./check-seo.mjs";
import good from "./fixtures/good-site.mjs";
import broken from "./fixtures/broken-site.mjs";

// fetch(url, init) answering from a fixture table keyed "METHOD /path".
export function makeFakeFetch(table) {
  return async (url, init = {}) => {
    const u = new URL(url);
    const method = (init.method || "GET").toUpperCase();
    const hit = table[`${method} ${u.pathname}`] || { status: 404, headers: {}, body: "" };
    return {
      status: hit.status, ok: hit.status >= 200 && hit.status < 300,
      headers: new Headers(hit.headers), text: async () => hit.body,
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
  assert.equal(r.dimension, "seo-and-social");
  assert.equal(r.score, 100);
  assert.ok(r.findings.every((f) => f.severity === "info"), JSON.stringify(r.findings, null, 2));
});

test("broken site reports the expected findings", async () => {
  const r = await audit("https://example.com", { fetch: makeFakeFetch(broken), locales: ["pt"] });
  const got = ids(r);
  for (const id of [
    "seo.sitemap.broken-url", "seo.meta-description.missing", "seo.canonical.missing",
    "seo.og.missing", "seo.twitter.missing", "seo.jsonld.invalid", "seo.hreflang.missing",
    "seo.links.broken", "seo.links.redirected", "seo.title.duplicate", "seo.soft-404",
  ]) assert.ok(got.includes(id), `missing ${id} in ${got}`);
  assert.ok(r.score < 50, `score ${r.score}`);
  for (const f of r.findings) {
    assert.ok(["blocker", "major", "minor", "info"].includes(f.severity));
    assert.ok(["S", "M", "L"].includes(f.effort));
    assert.equal(typeof f.autoFixable, "boolean");
    assert.ok(f.title && f.evidence && f.fix && f.url, JSON.stringify(f));
  }
});

test("hreflang set lacking a configured locale is major", async () => {
  const r = await audit("https://example.com", { fetch: makeFakeFetch(good), locales: ["pt", "de"] });
  const f = r.findings.find((x) => x.id === "seo.hreflang.missing-locale");
  assert.ok(f, JSON.stringify(r.findings)); assert.equal(f.severity, "major");
  assert.match(f.evidence, /de/);
});

test("partial OG set is minor, not og.missing", async () => {
  const body = good["GET /projects/a"].body.replace(/<meta property="og:image"[^>]*>\n?/, "");
  const t = { ...good, "GET /projects/a": { ...good["GET /projects/a"], body } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  const got = ids(r);
  assert.ok(got.includes("seo.og.partial"), got.join());
  assert.ok(!got.includes("seo.og.missing"));
});

test("broken og:image URL is major", async () => {
  const t = { ...good }; delete t["GET /og.png"];
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  const f = r.findings.find((x) => x.id === "seo.og.image-broken");
  assert.ok(f); assert.equal(f.severity, "major");
});

test("no sitemap at all is major and audit still samples the homepage", async () => {
  const t = { ...good, "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "User-agent: *\nAllow: /\n" } };
  delete t["GET /sitemap.xml"];
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  assert.ok(ids(r).includes("seo.sitemap.missing"));
  assert.ok(!ids(r).includes("seo.title.missing"), JSON.stringify(r.findings));
});

test("noindex on a sitemap page is major", async () => {
  const t = { ...good, "GET /projects/a": { ...good["GET /projects/a"], headers: { ...good["GET /projects/a"].headers, "x-robots-tag": "noindex" } } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  const f = r.findings.find((x) => x.id === "seo.noindex.in-sitemap");
  assert.ok(f); assert.equal(f.severity, "major");
});

test("a fetch that throws yields findings, not a crash", async () => {
  const throwing = async () => { throw new Error("ECONNRESET"); };
  const r = await audit("https://example.com", { fetch: throwing });
  assert.equal(r.dimension, "seo-and-social");
  assert.ok(r.findings.length > 0);
  assert.ok(ids(r).includes("seo.unchecked"));
});

test("same title on locale variants of the same page is not a duplicate", async () => {
  const body = good["GET /pt/"].body.replace(/<title>[^<]*<\/title>/, "<title>Example — Home</title>");
  const t = { ...good, "GET /pt/": { ...good["GET /pt/"], body } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  assert.ok(!r.findings.some((f) => f.id === "seo.title.duplicate"), JSON.stringify(r.findings));
});

test("same title on two non-locale pages is still a duplicate", async () => {
  const body = good["GET /projects/a"].body.replace(/<title>[^<]*<\/title>/, "<title>Example — Home</title>");
  const t = { ...good, "GET /projects/a": { ...good["GET /projects/a"], body } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  assert.ok(r.findings.some((f) => f.id === "seo.title.duplicate"), JSON.stringify(r.findings));
});

test("attribute values containing the other quote character parse fully", async () => {
  const body = good["GET /projects/a"].body.replace(
    'content="https://example.com/og.png"',
    'content="https://example.com/it\'s-og.png"');
  const t = { ...good,
    "GET /projects/a": { ...good["GET /projects/a"], body },
    "GET /it's-og.png": { status: 200, headers: { "content-type": "image/png" }, body: "png" },
  };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), locales: ["pt"] });
  assert.ok(!r.findings.some((f) => f.id === "seo.og.image-broken"), JSON.stringify(r.findings));
});
