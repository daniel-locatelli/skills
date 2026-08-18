import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { rank, aggregate } from "./aggregate.mjs";

const ar = JSON.parse(readFileSync(new URL("./fixtures/agent-readiness.json", import.meta.url)));
const perf = JSON.parse(readFileSync(new URL("./fixtures/performance.json", import.meta.url)));

test("rank orders by severity/effort, then dimension order", () => {
  const ranked = rank([...ar.findings.map((f) => ({ ...f, dimension: "agent-readiness" })), ...perf.findings.map((f) => ({ ...f, dimension: "performance" }))]);
  // perf.contrast 10/1=10; perf.tbt 25/4=6.25; missing-locale 10/2=5; no-sitemap 3/1=3; info 0
  assert.deepEqual(ranked.map((f) => f.id), ["perf.contrast", "perf.tbt", "ar.llms-txt.missing-locale", "ar.robots.no-sitemap", "ar.dns.aid.missing"]);
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
  assert.match(md, /ar\.dns\.aid\.missing/); // appendix lists everything, even beyond topN / info
});

test("aggregate lists dimensions in canonical order regardless of input order", () => {
  const md = aggregate([ar, perf], { site: "x", date: "d", commit: "c" });
  assert.ok(md.indexOf("| performance |") < md.indexOf("| agent-readiness |"));
});
