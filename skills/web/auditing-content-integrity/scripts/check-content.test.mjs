import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, utimes } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { audit, score } from "./check-content.mjs";

const fix = (name) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
const ids = (r) => r.findings.map((f) => f.id).sort();

test("score deducts by severity and floors at 0", () => {
  assert.equal(score([]), 100);
  assert.equal(score([{ severity: "blocker" }, { severity: "major" }, { severity: "minor" }, { severity: "info" }]), 62);
  assert.equal(score(Array(5).fill({ severity: "blocker" })), 0);
});

test("good tree scores 100 with only info findings", async () => {
  const r = await audit(fix("good-tree"));
  assert.equal(r.dimension, "content-integrity");
  assert.equal(r.score, 100);
  assert.ok(r.findings.every((f) => f.severity === "info"), JSON.stringify(r.findings, null, 2));
});

test("broken tree reports the expected findings", async () => {
  const r = await audit(fix("broken-tree"));
  const got = ids(r);
  for (const id of [
    "ci.parity.missing-translation", "ci.parity.orphan", "ci.parity.untranslated",
    "ci.structure.missing-fields", "ci.structure.value-drift",
    "ci.style.em-dash", "ci.style.h1-in-body", "ci.images.missing-alt",
  ]) assert.ok(got.includes(id), `missing ${id} in ${got}`);
  assert.equal(r.findings.find((f) => f.id === "ci.parity.missing-translation").severity, "major");
  assert.equal(r.findings.find((f) => f.id === "ci.parity.untranslated").severity, "major");
  assert.ok(r.score < 70, `score ${r.score}`);
  for (const f of r.findings) {
    assert.ok(["blocker", "major", "minor", "info"].includes(f.severity));
    assert.ok(["S", "M", "L"].includes(f.effort));
    assert.equal(typeof f.autoFixable, "boolean");
    assert.ok(f.title && f.evidence && f.fix && f.file, JSON.stringify(f));
    assert.ok(!f.file.includes("\\"), `file must use forward slashes: ${f.file}`);
  }
});

test("underscore-prefixed drafts are exempt from parity", async () => {
  const r = await audit(fix("broken-tree"));
  for (const f of r.findings) assert.ok(!f.evidence.includes("_draft"), JSON.stringify(f));
});

test("missing-translation names the file and locale", async () => {
  const r = await audit(fix("broken-tree"));
  const f = r.findings.find((x) => x.id === "ci.parity.missing-translation");
  assert.match(f.evidence, /b\.md/);
  assert.match(f.evidence, /pt/);
});

test("stale and missing exports are flagged", async () => {
  const dir = await mkdtemp(join(tmpdir(), "ci-fresh-"));
  const content = join(dir, "content");
  await mkdir(join(content, "projects", "en"), { recursive: true });
  await writeFile(join(content, "projects", "en", "a.md"), "---\ntitle: A\n---\n\n## H\n\nBody.\n");
  const exportFile = join(dir, "llms.txt");
  await writeFile(exportFile, "# Export\n");
  const old = new Date(Date.now() - 7 * 24 * 3600 * 1000);
  await utimes(exportFile, old, old);
  const r = await audit(content, { exports: [exportFile, join(dir, "does-not-exist.txt")] });
  const got = ids(r);
  assert.ok(got.includes("ci.freshness.stale-export"), got.join());
  assert.ok(got.includes("ci.freshness.export-missing"), got.join());
  assert.equal(r.findings.find((f) => f.id === "ci.freshness.stale-export").severity, "major");
});

test("an unreadable content dir yields findings, not a crash", async () => {
  const r = await audit(join(tmpdir(), "ci-does-not-exist-xyz"));
  assert.equal(r.dimension, "content-integrity");
  assert.ok(ids(r).includes("ci.unchecked"));
});

test("a tree with no content files reports ci.no-content instead of a silent 100", async () => {
  const dir = await mkdtemp(join(tmpdir(), "ci-empty-"));
  await mkdir(join(dir, "img"), { recursive: true });
  const r = await audit(dir);
  const f = r.findings.find((x) => x.id === "ci.no-content");
  assert.ok(f, JSON.stringify(r.findings)); assert.equal(f.severity, "info");
});
