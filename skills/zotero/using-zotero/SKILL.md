---
name: using-zotero
description: Use when reading or writing a Zotero library from an agent — searching items, checking whether a DOI is already in Zotero, listing a collection, reading PDF annotations or notes, adding a paper by DOI or item JSON, writing a folder's reading list (Meristema Reading), attaching a PDF, tagging or filing into a collection — or when zotero:// links, the Zotero local API, ports 23119/23124, or "Allow other applications on this computer" come up.
---

# Using Zotero

Zotero 7–10 serves its library on `http://127.0.0.1:<port>`.
**Reads need nothing; writes need a local API key plus the `Zotero-Server-ID`
header.** `scripts/zot.py` (Python 3.10+, stdlib) does both.

## Setup

- Zotero must run **on this machine**: loopback only.
- Settings → Advanced → *Allow other applications on this computer to
  communicate with Zotero* must be on. Default port 23119, else
  `extensions.zotero.httpServer.port` in `prefs.js`.
- Copy `zotero.config.example.json` to `zotero.config.json` (git-ignored):
  `port`, `dataDir`, `appName`, `keyFile` (outside any repo).

## Doctor first

    python <skillRoot>/scripts/zot.py doctor

Checks Zotero, server ID, local API, **data-dir guard**, key; exit `2` names
the fix. Run before any write.

## Verbs (JSON out; `--pretty` before the verb for a table)

| Read | |
|---|---|
| `search <q> [--everything] [--limit N]` | title/creator/year, or all fields |
| `doi <doi>` | exact DOI match (also `extra: DOI:`); exit 3 if absent |
| `item <key>` | item + children |
| `collections` / `collection <name-or-key> [--limit N]` | tree / top-level items |
| `annotations <key>` | PDF annotations, page order |
| `notes <key>` | child notes, HTML stripped |
| `file <key>` | PDF's local path and md5 |
| `reading-overview` | every list: steps, read states, next up, the queue |

`search` and `collection` report `total` and warn when `--limit` truncates.

| Write | |
|---|---|
| `authorize` | Zotero's dialog: click **Always Allow** (plain *Allow* is single-use) |
| `from-doi <doi> > item.json` | doi.org CSL-JSON → Zotero item JSON |
| `add --json item.json [--collection NAME] [--tags a,b]` | creates items |
| `attach <key> <file> [--title T]` | imported-file child + upload; md5 verified |
| `tag <key> <tag>…` / `file-into <key> <collection>` | PATCH with version check |
| `reading-list --topic T --collection C --steps steps.json [--replace]` | below |
| `reading-list --queue --steps steps.json [--replace]` | the queue |

Every write runs the guard chain first and re-reads what it wrote. Keys are 8 chars.

`reading-list` writes a folder's Meristema Reading list note; `steps.json` is
`[{"doi" | "key", "why"}]`. An existing list exits 2 unless `--replace`.

**Reading queue.** One list in My Library, tagged `meristema-reading-queue`,
is the user's queue across all lists. Read `reading-overview` first; propose
an order with reasons; write it with `reading-list --queue --replace`. The
queue's folder then holds exactly its steps. Read state is never written.

## The dev-instance trap

A dev profile started with `--dataDir <copy>` shares the port and **server
ID**; only file paths differ. `doctor` refuses (exit 2) if an attachment lands
outside `dataDir`. Close the dev instance; never edit `dataDir`.

## Errors

| Symptom | Meaning | Do |
|---|---|---|
| connection refused | not running, or wrong port | start Zotero; check `port` |
| 403 on `/api/` | local API disabled | enable the setting above |
| 401 on a write | key missing or revoked | `authorize`, Always Allow |
| 412 | stale version or server-ID mismatch | `doctor`, retry |

Protocol details: `reference/local-api.md`.
