#!/usr/bin/env node
// Summarize a Lighthouse JSON report on one screen.
// Usage: node lh-summary.mjs <report.json> [--all]
import { readFileSync } from "node:fs";

const [file, ...flags] = process.argv.slice(2);
if (!file) {
  console.error("usage: lh-summary.mjs <lighthouse.json> [--all]");
  process.exit(1);
}
const showAll = flags.includes("--all");
const raw = JSON.parse(readFileSync(file, "utf8"));
const r = raw.lighthouseResult ?? raw; // PageSpeed API wraps the report
const a = r.audits;

console.log(`# ${r.finalDisplayedUrl ?? r.requestedUrl}  (${r.configSettings?.formFactor})`);
console.log("\n## Categories");
for (const [k, c] of Object.entries(r.categories))
  console.log(`  ${k.padEnd(16)} ${Math.round(c.score * 100)}`);

console.log("\n## Metrics");
for (const k of [
  "first-contentful-paint",
  "largest-contentful-paint",
  "total-blocking-time",
  "cumulative-layout-shift",
  "speed-index",
  "interactive",
  "max-potential-fid",
])
  if (a[k]) console.log(`  ${k.padEnd(28)} ${a[k].displayValue ?? ""}`);

const skip = new Set(["valid-source-maps", "network-dependency-tree-insight"]);
console.log("\n## Failing audits (score < 0.9)");
for (const audit of Object.values(a)) {
  if (audit.score === null || audit.score >= 0.9) continue;
  if (audit.scoreDisplayMode === "informative") continue;
  if (!showAll && skip.has(audit.id)) continue;
  console.log(`\n[${audit.score}] ${audit.id}: ${audit.title} ${audit.displayValue ?? ""}`);
  const items = Array.isArray(audit.details?.items) ? audit.details.items : [];
  for (const it of items.slice(0, showAll ? 20 : 6)) {
    const url = it.url ?? it.node?.selector ?? it.groupLabel ?? "";
    const bytes = it.wastedBytes ? ` waste=${Math.round(it.wastedBytes / 1024)}KiB` : "";
    const total = it.totalBytes ? ` total=${Math.round(it.totalBytes / 1024)}KiB` : "";
    const ms = it.wastedMs ? ` ${Math.round(it.wastedMs)}ms` : "";
    const snippet = it.node?.snippet ? `  ${it.node.snippet.slice(0, 120)}` : "";
    const reasons = it.subItems?.items?.map((s) => s.reason ?? s.error).filter(Boolean).join(" | ");
    console.log(`   - ${url}${total}${bytes}${ms}${snippet}${reasons ? `  [${reasons}]` : ""}`);
  }
}

const bt = a["bootup-time"];
if (bt?.details?.items?.length) {
  console.log("\n## Script bootup (top)");
  for (const it of bt.details.items.slice(0, 6))
    console.log(`   ${String(Math.round(it.total)).padStart(5)}ms  ${it.url}`);
}
const mt = a["mainthread-work-breakdown"];
if (mt?.details?.items?.length) {
  console.log("\n## Main-thread breakdown");
  for (const it of mt.details.items)
    console.log(`   ${String(Math.round(it.duration)).padStart(5)}ms  ${it.groupLabel}`);
}
