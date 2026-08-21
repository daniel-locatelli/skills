#!/usr/bin/env node
// Content & i18n integrity audit over a repo content tree. Zero deps, Node >= 20.
// Usage: node check-content.mjs <contentDir> [--source en] [--locales pt,de]
//        [--exports public/llms.txt,public/pt/llms.txt] [--json]
// Layout audited: <contentDir>/<collection>/<locale>/<file>.md|.mdx
// Emits the shared findings contract; findings carry "file", not "url".

import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

const W = { blocker: 25, major: 10, minor: 3, info: 0 };
export function score(findings) {
  return Math.max(0, 100 - findings.reduce((s, f) => s + (W[f.severity] ?? 0), 0));
}

const splitDoc = (raw) => {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  const fm = {};
  if (m) for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].trim();
  }
  return { fm, body: m ? raw.slice(m[0].length) : raw };
};
const prose = (body) => body.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]*`/g, "");
const stem = (name) => name.replace(/\.(md|mdx)$/i, "");
const INVARIANT = ["date", "startDate", "endDate", "url", "link", "image", "cover"];

export async function audit(contentDir, { sourceLocale = "en", locales = [], exports = [] } = {}) {
  const findings = [];
  const add = (id, severity, title, evidence, file, fix, effort, autoFixable) =>
    findings.push({ id, severity, title, evidence, file, fix, effort, autoFixable });
  const agg = {}; const firstFile = {};
  const bump = (id, ev, file) => { (agg[id] = agg[id] || []).push(ev); firstFile[id] ??= file; };
  const list = (a, n = 5) => a.slice(0, n).join("; ") + (a.length > n ? ` (+${a.length - n} more)` : "");

  let collections;
  try {
    collections = (await readdir(contentDir, { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name);
  } catch (e) {
    add("ci.unchecked", "info", "Content directory unreadable", String(e), String(contentDir),
      "Check the path and re-run", "S", false);
    return { dimension: "content-integrity", score: score(findings), findings };
  }

  // tree[collection][locale] = { name -> { fm, body, rel } } ; drafts (_-prefixed) skipped entirely
  const tree = {}; const seenLocales = new Set();
  let newestContent = 0;
  for (const c of collections) {
    tree[c] = {};
    let localeDirs = [];
    try { localeDirs = (await readdir(join(contentDir, c), { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name); } catch { continue; }
    for (const loc of localeDirs) {
      seenLocales.add(loc);
      tree[c][loc] = {};
      let files = [];
      try { files = (await readdir(join(contentDir, c, loc))).filter((f) => /\.(md|mdx)$/i.test(f) && !f.startsWith("_")); } catch { continue; }
      for (const f of files) {
        const p = join(contentDir, c, loc, f);
        try {
          const [raw, st] = [await readFile(p, "utf8"), await stat(p)];
          newestContent = Math.max(newestContent, st.mtimeMs);
          tree[c][loc][stem(f)] = { ...splitDoc(raw), rel: `${c}/${loc}/${f}` };
        } catch (e) { bump("ci.unchecked", `${c}/${loc}/${f}: ${e}`, `${c}/${loc}/${f}`); }
      }
    }
  }
  const targets = locales.length ? locales : [...seenLocales].filter((l) => l !== sourceLocale).sort();
  if (!newestContent)
    add("ci.no-content", "info", "No content files found under this directory",
      `no <collection>/<locale>/*.md(x) below ${contentDir} — is the path the content root?`,
      String(contentDir).replaceAll("\\", "/"), "Point the checker at the directory that contains the collections", "S", false);

  for (const c of collections) {
    const src = tree[c][sourceLocale] || {};
    for (const loc of targets) {
      const tr = tree[c][loc] || {};
      for (const [name, doc] of Object.entries(src)) {
        const t = tr[name];
        if (!t) { bump("ci.parity.missing-translation", `${loc}: ${doc.rel} has no ${loc} counterpart`, doc.rel); continue; }
        const a = doc.body.trim(), b = t.body.trim();
        if (a && a === b) bump("ci.parity.untranslated", `${t.rel} body is identical to ${doc.rel}`, t.rel);
        const missing = Object.keys(doc.fm).filter((k) => !(k in t.fm));
        if (missing.length) bump("ci.structure.missing-fields", `${t.rel}: missing ${missing.join(", ")}`, t.rel);
        for (const k of INVARIANT)
          if (k in doc.fm && k in t.fm && doc.fm[k] !== t.fm[k])
            bump("ci.structure.value-drift", `${t.rel}: ${k} "${t.fm[k]}" != source "${doc.fm[k]}"`, t.rel);
      }
      for (const [name, doc] of Object.entries(tr))
        if (!src[name]) bump("ci.parity.orphan", `${doc.rel} has no ${sourceLocale} counterpart`, doc.rel);
    }
    // Style checks on every non-draft file, all locales
    for (const loc of Object.keys(tree[c]))
      for (const doc of Object.values(tree[c][loc])) {
        const p = prose(doc.body);
        const em = (p.match(/—/g) || []).length;
        if (em) bump("ci.style.em-dash", `${doc.rel}: ${em}x`, doc.rel);
        if (/^#[ \t]/m.test(p)) bump("ci.style.h1-in-body", doc.rel, doc.rel);
        if (/!\[\s*\]\(/.test(p)) bump("ci.images.missing-alt", doc.rel, doc.rel);
      }
  }

  // Generated-export freshness
  for (const ex of exports) {
    try {
      const st = await stat(ex);
      if (newestContent && st.mtimeMs < newestContent)
        bump("ci.freshness.stale-export", `${ex} older than newest content file`, String(ex));
    } catch {
      bump("ci.freshness.export-missing", `${ex} does not exist`, String(ex));
    }
  }

  const META = {
    "ci.parity.missing-translation": ["major", "M", false, "Source entries without translations", "Translate the listed entries (or mark them draft with a leading underscore)"],
    "ci.parity.orphan": ["minor", "S", false, "Translations without a source counterpart", "Restore the source entry or remove/rename the orphan"],
    "ci.parity.untranslated": ["major", "M", false, "Translations identical to the source (placeholder copies)", "Actually translate the body, or remove the copy until translated"],
    "ci.structure.missing-fields": ["minor", "S", false, "Translations missing frontmatter fields the source has", "Add the missing fields so schemas and templates behave identically"],
    "ci.structure.value-drift": ["minor", "S", false, "Invariant frontmatter values differ between locales", "Dates, links and image paths must match the source exactly"],
    "ci.style.em-dash": ["minor", "S", true, "Em dashes in prose (house style forbids them)", "Rewrite with commas, colons or parentheses"],
    "ci.style.h1-in-body": ["minor", "S", true, "H1 headings inside content bodies", "Start content headings at h2; the layout owns h1"],
    "ci.images.missing-alt": ["minor", "S", false, "Images with empty alt text", "Write descriptive alt text (per locale, translated)"],
    "ci.freshness.stale-export": ["major", "S", true, "Generated exports older than the content", "Re-run the knowledge pipeline / build so llms.txt matches the content"],
    "ci.freshness.export-missing": ["minor", "S", true, "Configured export files that do not exist", "Generate them or drop them from --exports"],
    "ci.unchecked": ["info", "S", false, "Files that could not be read", "Inspect the listed files manually"],
  };
  for (const [id, evs] of Object.entries(agg)) {
    const [severity, effort, autoFixable, title, fix] = META[id];
    add(id, severity, title, list(evs), (firstFile[id] ?? String(contentDir)).replaceAll("\\", "/"), fix, effort, autoFixable);
  }

  return { dimension: "content-integrity", score: score(findings), findings };
}

if (process.argv[1] && /check-content\.mjs$/.test(process.argv[1])) {
  const args = process.argv.slice(2);
  const dir = args.find((a) => !a.startsWith("--"));
  if (!dir) { console.error("Usage: node check-content.mjs <contentDir> [--source en] [--locales pt,de] [--exports a,b] [--json]"); process.exit(2); }
  const opt = (name) => { const i = args.findIndex((a) => a === name || a.startsWith(`${name}=`)); return i < 0 ? undefined : (args[i].split("=")[1] ?? args[i + 1]); };
  const r = await audit(dir, {
    sourceLocale: opt("--source") ?? "en",
    locales: (opt("--locales") ?? "").split(",").filter(Boolean),
    exports: (opt("--exports") ?? "").split(",").filter(Boolean),
  });
  if (args.includes("--json")) console.log(JSON.stringify(r, null, 2));
  else {
    console.log(`content-integrity score: ${r.score}/100`);
    for (const f of r.findings) console.log(`  [${f.severity}] ${f.id} — ${f.title}\n      ${f.evidence}`);
    if (!r.findings.length) console.log("  no findings");
  }
}
