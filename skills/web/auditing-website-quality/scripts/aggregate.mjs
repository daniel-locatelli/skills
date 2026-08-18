#!/usr/bin/env node
// Merge findings-contract JSON reports into a dated markdown scorecard.
// Usage: node aggregate.mjs --site <url> [--commit <sha>] [--date YYYY-MM-DD] [--top 10] [--out <file>] <report.json>...
// Zero dependencies; Node >= 20.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const SEV = { blocker: 25, major: 10, minor: 3, info: 0 };
const EFF = { S: 1, M: 2, L: 4 };
export const DIMENSION_ORDER = ["performance", "agent-readiness", "security-headers", "seo-and-social", "content-integrity"];
const dimIdx = (d) => { const i = DIMENSION_ORDER.indexOf(d); return i < 0 ? DIMENSION_ORDER.length : i; };

// Rank = severity weight / effort weight; ties by canonical dimension order, then severity.
export function rank(findings) {
  const w = (f) => (SEV[f.severity] ?? 0) / (EFF[f.effort] ?? 2);
  return [...findings].sort((a, b) => w(b) - w(a) || dimIdx(a.dimension) - dimIdx(b.dimension) || (SEV[b.severity] ?? 0) - (SEV[a.severity] ?? 0));
}

const esc = (s) => String(s ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
const table = (header, rows) => [`| ${header.join(" | ")} |`, `|${header.map(() => "---").join("|")}|`, ...rows.map((r) => `| ${r.map(esc).join(" | ")} |`)].join("\n");

export function aggregate(reports, { site, date, commit = "n/a", topN = 10, template } = {}) {
  const tpl = template ?? readFileSync(new URL("../templates/scorecard.md", import.meta.url), "utf8");
  const sorted = [...reports].sort((a, b) => dimIdx(a.dimension) - dimIdx(b.dimension));
  const all = sorted.flatMap((r) => (r.findings ?? []).map((f) => ({ ...f, dimension: r.dimension })));
  const ranked = rank(all);
  const overall = sorted.length ? Math.round(sorted.reduce((s, r) => s + (r.score ?? 0), 0) / sorted.length) : 0;
  const scoreTable = table(["Dimension", "Score", "Blockers", "Major", "Minor", "Info"], sorted.map((r) => {
    const c = (s) => (r.findings ?? []).filter((f) => f.severity === s).length;
    return [r.dimension, r.score, c("blocker"), c("major"), c("minor"), c("info")];
  }));
  const top = ranked.filter((f) => f.severity !== "info").slice(0, topN);
  const rankedTable = top.length
    ? table(["#", "ID", "Severity", "Effort", "Dimension", "Title", "Fix"], top.map((f, i) => [i + 1, f.id, f.severity, f.effort, f.dimension, f.title, f.fix]))
    : "_No actionable findings._";
  const nextActions = top.slice(0, 5).map((f, i) => `${i + 1}. ${f.title} — ${f.fix}${f.autoFixable ? " *(auto-fixable)*" : ""}`).join("\n") || "_No actionable findings._";
  const allFindings = ranked.length
    ? table(["ID", "Severity", "Dimension", "Title", "Evidence", "Location", "Effort", "Auto"], ranked.map((f) => [f.id, f.severity, f.dimension, f.title, f.evidence, f.url ?? f.file ?? "", f.effort, f.autoFixable ? "yes" : "no"]))
    : "_None._";
  const vars = { site, date, commit, overall, topN, scoreTable, rankedTable, nextActions, allFindings };
  return tpl.replace(/\{\{(\w+)\}\}/g, (_, k) => String(vars[k] ?? ""));
}

// CLI (guard tolerates Windows paths)
if (process.argv[1] && /aggregate\.mjs$/.test(process.argv[1])) {
  const a = process.argv.slice(2);
  const FLAGS = ["--site", "--commit", "--date", "--top", "--out"];
  const opt = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
  const files = a.filter((x, i) => !x.startsWith("--") && !FLAGS.includes(a[i - 1]));
  const site = opt("--site"); const out = opt("--out");
  if (!site || !files.length) { console.error("Usage: node aggregate.mjs --site <url> [--commit sha] [--date YYYY-MM-DD] [--top N] [--out file] <report.json>..."); process.exit(2); }
  const reports = files.map((f) => JSON.parse(readFileSync(f, "utf8")));
  const md = aggregate(reports, { site, commit: opt("--commit", "n/a"), date: opt("--date", new Date().toISOString().slice(0, 10)), topN: Number(opt("--top", 10)) });
  if (out) { mkdirSync(dirname(out), { recursive: true }); writeFileSync(out, md); console.log(`wrote ${out}`); } else process.stdout.write(md);
}
