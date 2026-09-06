# Zotero local API — protocol notes (Zotero 10.0.1, `server_localAPI.js`)

Web API v3 shapes, served by the desktop app on `127.0.0.1:<port>` for user
library `0`. Differences from api.zotero.org, in the order the server checks them.

## Request gate

1. Pref `extensions.zotero.httpServer.localAPI.enabled` — off → **403** `Local API is not enabled`.
2. `Zotero-Server-ID` (writes only) — missing → **428**; different → **412**. Read it from any
   response header; it is stored in the database (`settings` table), so a copied library reports
   the same ID.
3. `Zotero-API-Key` (writes only) — missing/unknown → **401** with `WWW-Authenticate: Zotero-API-Key`.

## Keys

`POST /api/local/authorize` `{"appName": "…"}` → modal Allow / Always Allow / Deny.
200 `{"key": "<32 chars>", "remember": bool}`; 403 `{"denied": true}`; 429 after 5 prompts per
minute (`Retry-After`). `remember: false` keys are deleted on the first validated write — a
probe counts, so `zot.py` deletes its copy of the key file at the same moment. Keys are unrelated to zotero.org keys.

## Writes

- `POST /api/users/0/items` — JSON **array** ≤ 50 → `{"successful","success","unchanged","failed"}`
  keyed by index. Keyed entries need `version` or `If-Unmodified-Since-Version`.
- `PATCH /api/users/0/items/<key>` — object + `If-Unmodified-Since-Version: <item.version>` → 204
  `Last-Modified-Version`. 428 without the header, 412 when stale. `POST` on an existing key
  follows PATCH semantics (merge).
- `Zotero-Write-Token` (5–32 chars) is honoured for 12 h to make a POST idempotent.
- Deletes: `DELETE /items?itemKey=a,b` (≤ 50).

## File upload (imported_file / imported_url attachments only)

1. `POST /api/users/0/items/<key>/file` form `md5, filename, filesize, mtime` (**milliseconds**),
   header `If-None-Match: *` (new file) or `If-Match: <md5>` (replace) → 200 `{"url", "uploadKey",
   "contentType", "prefix": "", "suffix": ""}`, or `{"exists": 1}` when the local file already
   matches. `params=1` returns the multipart form variant instead.
2. `POST <url>` (`/api/local/uploads/<uploadKey>`) raw bytes → 201; 400 if md5 differs. No
   server-ID or key needed here (mirrors S3). Keys expire after 1 h.
3. `POST …/file` form `upload=<uploadKey>` + the same `If-*` header → 204 `Last-Modified-Version`.
   The staged file moves into `<dataDir>/storage/<KEY>/<filename>` and the item's `md5`, `mtime`,
   `filename` update. `PATCH …/file` (partial upload) → 405.

`GET /items/<key>/file/view/url` → `file:///…` path; `/file/view` → 302 to it; `/file` → 302 too.

## Reads worth knowing

- `/items/top?q=&qmode=titleCreatorYear|everything&limit=&itemType=` — quicksearch, so
  substring hits; filter exactly client-side. `limit` silently truncates: web API v3 reports the
  unpaged size in a `Total-Results` header, but the local API's coverage of it is unverified, so
  `zot.py` uses it when present — otherwise `total` is `null` and it warns whenever the result
  fills the cap.
- `/items/<key>/children` — attachments, notes **and annotations** (annotations hang off the
  attachment, so ask the attachment for its children).
- `/collections/<key>/items/top`, `/collections` (`meta.numItems`, `data.parentCollection`).
- `/fulltext`, `/searches`, `/tags`, `/schema`, `/itemTypes` exist; types/fields come back
  localized (`/creatorFields` in English).
- HTTP/1.0 responses; no Atom; no groups beyond metadata.

## The dev-instance trap

`zotero -profile <p> --dataDir <copy>` (what plugin scaffolds run) is a second Zotero on the
**same port** with a **copy** of the library and therefore the **same server ID**. Only the
`file/view/url` prefix distinguishes it. Guard before every write; the guard also refuses
(exit 2) if none of the sampled attachments has its file on disk.
