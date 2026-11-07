---
name: using-zotero
description: Use when reading or writing a Zotero library from an agent — searching items, checking whether a DOI is already in Zotero, listing a collection, reading PDF annotations or notes, adding a paper by DOI or item JSON, attaching a PDF, tagging or filing into a collection — or when zotero:// links, the Zotero local API, ports 23119/23124, or "Allow other applications on this computer" come up.
---

# Using Zotero

Zotero 7–10 serves its library on `http://127.0.0.1:<port>`.
**Reads need nothing; writes need a local API key plus the `Zotero-Server-ID`
header.** No account, no sync, no plugin: `scripts/zot.py`
(Python 3.10+, stdlib) does both.

## Setup

- Zotero must run **on this machine**: loopback only.
- Settings → Advanced → *Allow other applications on this computer to
  communicate with Zotero* must be on. Default port 23119, else see
  `extensions.zotero.httpServer.port` in `prefs.js`.
- Copy `zotero.config.example.json` to `zotero.config.json` (git-ignored):
  `port`, `dataDir` (Settings → Advanced → Files and Folders), `appName`,
  `keyFile` (outside any repo).

## Doctor first

    python <skillRoot>/scripts/zot.py doctor

Checks Zotero up, server ID, local API enabled, **data-dir guard**, key
valid; exit `2` names the fix. Run before any write.

## Verbs (JSON out; `--pretty` before the verb for a table)

| Read | |
|---|---|
| `search <q> [--everything] [--limit N]` | title/creator/year, or every field |
| `doi <doi>` | exact DOI match (also `extra: DOI:`); exit 3 if absent |
| `item <key>` | item + children |
| `collections` / `collection <name-or-key> [--limit N]` | tree with counts / its top-level items |
| `annotations <key>` | PDF annotations, page order |
| `notes <key>` | child notes, HTML stripped |
| `file <key>` | PDF's local path and md5 |

`search` and `collection` report `total` and warn when `--limit` truncates.

| Write | |
|---|---|
| `authorize` | Zotero's dialog: click **Always Allow** (plain *Allow* is single-use) |
| `from-doi <doi> > item.json` | doi.org CSL-JSON → Zotero item JSON |
| `add --json item.json [--collection NAME] [--tags a,b]` | creates item(s), prints keys |
| `attach <key> <file> [--title T]` | imported-file child + upload; md5 verified |
| `tag <key> <tag>…` / `file-into <key> <collection>` | PATCH with version check |
| `reading-list --topic T --collection C --steps s.json [--replace]` | see below |

Every write runs the guard chain first and re-reads what it wrote: a 200 or
204 is never "done". Keys are 8 chars.

`reading-list` writes a folder's Meristema Reading list note (tag
`meristema-reading-list`). `s.json` is `[{"doi" | "key", "why"}]`;
absent DOIs are added, papers filed into `C` (made if absent). An existing
list exits 2 unless `--replace`. Format: `fixtures/README.md` in
zotero-meristema-reading.

## The dev-instance trap

A plugin dev profile started with `--dataDir <copy>` uses the same port and
the **same server ID**. Only file paths tell them apart: `doctor` resolves
an attachment's `file/view/url` and refuses (exit 2) if it lands outside
`dataDir` or no sampled file is on disk. Close the dev instance — never
edit `dataDir` to match.

## Errors

| Symptom | Meaning | Do |
|---|---|---|
| connection refused | not running, or wrong port | start Zotero; check `port` |
| 403 on `/api/` | local API disabled | enable the setting above |
| 401 on a write | key missing or revoked | `authorize`, Always Allow |
| 412 | stale version or server-ID mismatch | `doctor`, retry |

Protocol details: `reference/local-api.md`.
