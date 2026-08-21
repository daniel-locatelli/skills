import { test } from "node:test";
import assert from "node:assert/strict";
import { audit, score } from "./check-headers.mjs";
import good from "./fixtures/good-site.mjs";
import broken from "./fixtures/broken-site.mjs";

// fetch(url, init) answering from a fixture table; http: URLs key as "GET http /path".
export function makeFakeFetch(table) {
  return async (url, init = {}) => {
    const u = new URL(url);
    const method = (init.method || "GET").toUpperCase();
    const key = u.protocol === "http:" ? `${method} http ${u.pathname}` : `${method} ${u.pathname}`;
    const hit = table[key] || { status: 404, headers: {}, body: "" };
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
  const r = await audit("https://example.com", { fetch: makeFakeFetch(good) });
  assert.equal(r.dimension, "security-headers");
  assert.equal(r.score, 100);
  assert.ok(r.findings.every((f) => f.severity === "info"), JSON.stringify(r.findings, null, 2));
});

test("broken site reports the expected findings", async () => {
  const r = await audit("https://example.com", { fetch: makeFakeFetch(broken) });
  const got = ids(r);
  for (const id of [
    "sec.tls.http-not-redirected", "sec.csp.missing", "sec.hsts.missing",
    "sec.xcto.missing", "sec.xfo.missing", "sec.referrer-policy.missing",
    "sec.permissions-policy.missing", "sec.cookies.flags", "sec.mixed-content",
    "sec.sri.missing", "sec.server.verbose",
  ]) assert.ok(got.includes(id), `missing ${id} in ${got}`);
  assert.equal(r.findings.find((f) => f.id === "sec.tls.http-not-redirected").severity, "blocker");
  assert.equal(r.findings.find((f) => f.id === "sec.cookies.flags").severity, "major");
  assert.ok(r.score < 50, `score ${r.score}`);
  for (const f of r.findings) {
    assert.ok(["blocker", "major", "minor", "info"].includes(f.severity));
    assert.ok(["S", "M", "L"].includes(f.effort));
    assert.equal(typeof f.autoFixable, "boolean");
    assert.ok(f.title && f.evidence && f.fix && f.url, JSON.stringify(f));
  }
});

test("unsafe-inline script-src without nonce/hash is major; with nonce it is clean", async () => {
  const t = (csp) => ({ ...good, "GET /": { ...good["GET /"], headers: { ...good["GET /"].headers, "content-security-policy": csp } } });
  let r = await audit("https://example.com", { fetch: makeFakeFetch(t("default-src 'self'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")) });
  const f = r.findings.find((x) => x.id === "sec.csp.unsafe-inline");
  assert.ok(f); assert.equal(f.severity, "major");
  r = await audit("https://example.com", { fetch: makeFakeFetch(t("default-src 'self'; script-src 'self' 'unsafe-inline' 'nonce-abc'; frame-ancestors 'none'")) });
  assert.ok(!ids(r).includes("sec.csp.unsafe-inline"), JSON.stringify(r.findings));
});

test("unsafe-eval and wildcard script sources are major", async () => {
  const t = { ...good, "GET /": { ...good["GET /"], headers: { ...good["GET /"].headers, "content-security-policy": "default-src *; script-src * 'unsafe-eval'; frame-ancestors 'none'" } } };
  const got = ids(await audit("https://example.com", { fetch: makeFakeFetch(t) }));
  assert.ok(got.includes("sec.csp.unsafe-eval"));
  assert.ok(got.includes("sec.csp.wildcard"));
});

test("CSP only in report-only mode is minor, not csp.missing", async () => {
  const h = { ...good["GET /"].headers };
  delete h["content-security-policy"];
  h["content-security-policy-report-only"] = "default-src 'self'";
  const t = { ...good, "GET /": { ...good["GET /"], headers: h } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  const got = ids(r);
  assert.ok(got.includes("sec.csp.report-only"));
  assert.ok(!got.includes("sec.csp.missing"));
  assert.equal(r.findings.find((f) => f.id === "sec.csp.report-only").severity, "minor");
});

test("short HSTS max-age is minor", async () => {
  const t = { ...good, "GET /": { ...good["GET /"], headers: { ...good["GET /"].headers, "strict-transport-security": "max-age=86400" } } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  const f = r.findings.find((x) => x.id === "sec.hsts.short-max-age");
  assert.ok(f); assert.equal(f.severity, "minor");
});

test("deprecated headers are reported as info", async () => {
  const t = { ...good, "GET /": { ...good["GET /"], headers: { ...good["GET /"].headers, "x-xss-protection": "1; mode=block" } } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  const f = r.findings.find((x) => x.id === "sec.headers.deprecated");
  assert.ok(f); assert.equal(f.severity, "info");
});

test("extra pages are probed for cookies", async () => {
  const t = { ...good, "GET /login": { status: 200, headers: { "content-type": "text/html", "set-cookie": "sid=1; Path=/" }, body: "" } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t), pages: ["/login"] });
  const f = r.findings.find((x) => x.id === "sec.cookies.flags");
  assert.ok(f); assert.match(f.evidence, /sid/);
});

test("a fetch that throws yields findings, not a crash", async () => {
  const throwing = async () => { throw new Error("ECONNRESET"); };
  const r = await audit("https://example.com", { fetch: throwing });
  assert.equal(r.dimension, "security-headers");
  assert.ok(r.findings.length > 0);
  assert.ok(ids(r).includes("sec.unchecked"));
});

test("reachable .env or .git files are a blocker", async () => {
  const t = { ...good, "GET /.env": { status: 200, headers: { "content-type": "text/plain" }, body: "API_KEY=sk-live" } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  const f = r.findings.find((x) => x.id === "sec.files.exposed");
  assert.ok(f); assert.equal(f.severity, "blocker"); assert.match(f.evidence, /\.env/);
});

test("security.txt: missing is info, present is not flagged", async () => {
  let r = await audit("https://example.com", { fetch: makeFakeFetch(good) });
  const f = r.findings.find((x) => x.id === "sec.security-txt.missing");
  assert.ok(f); assert.equal(f.severity, "info");
  const t = { ...good, "GET /.well-known/security.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "Contact: mailto:x@example.com\n" } };
  r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  assert.ok(!r.findings.some((x) => x.id === "sec.security-txt.missing"));
});

test("x-xss-protection: 0 (the recommended disable) is not flagged as deprecated", async () => {
  const t = { ...good, "GET /": { ...good["GET /"], headers: { ...good["GET /"].headers, "x-xss-protection": "0" } } };
  const r = await audit("https://example.com", { fetch: makeFakeFetch(t) });
  assert.ok(!r.findings.some((x) => x.id === "sec.headers.deprecated"), JSON.stringify(r.findings));
});
