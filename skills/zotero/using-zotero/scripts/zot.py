#!/usr/bin/env python3
"""zot.py — read and write a running Zotero (7–10) through its local API.

No zotero.org account, no plugin. Reads need nothing; writes need a local API
key (`authorize`) and the Zotero-Server-ID header — both handled here.

Exit codes: 0 ok · 1 error · 2 guard refused (message names the fix) · 3 not found.
Output: one JSON object on stdout (`--pretty` renders lists as a table).
"""
from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
KEY_RE = re.compile(r"^[A-Z0-9]{8}$")
IMPORTED = ("imported_file", "imported_url")
TIMEOUT = 30
ENABLE_HINT = ("local API is disabled: Zotero → Settings → Advanced → "
               "'Allow other applications on this computer to communicate with Zotero'")


class ZotError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# --- config -----------------------------------------------------------------

def load_config() -> dict:
    path = Path(os.environ.get("ZOTERO_CONFIG") or SKILL_ROOT / "zotero.config.json")
    cfg = {"port": 23119, "dataDir": None, "appName": "Claude Code", "keyFile": "~/.config/zotero-local-api.key"}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ZotError(1, f"{path} is not valid JSON: {e}")
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
    cfg["port"] = int(cfg["port"])
    cfg["keyFile"] = str(Path(os.path.expanduser(cfg["keyFile"])))
    cfg["_configPath"] = str(path)
    return cfg


# --- http -------------------------------------------------------------------

class Response:
    def __init__(self, status, headers, body: bytes):
        self.status, self.headers, self.body = status, headers, body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self):
        try:
            return json.loads(self.body)
        except json.JSONDecodeError:
            raise ZotError(1, f"Zotero returned non-JSON ({self.status}): {self.text[:200]}")


def request(cfg, method, path, *, query=None, data=None, form=None, headers=None, timeout=TIMEOUT) -> Response:
    url = path if path.startswith("http") else f"http://127.0.0.1:{cfg['port']}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    hdrs = dict(headers or {})
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif isinstance(data, (bytes, bytearray)):
        body = bytes(data)
        hdrs.setdefault("Content-Type", "application/octet-stream")
    elif data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, r.headers, r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.headers, e.read())
    except TimeoutError as e:  # urllib wraps connect errors only; a read timeout escapes bare
        raise ZotError(1, f"timed out after {timeout}s talking to Zotero on port {cfg['port']}: {e}")
    except urllib.error.URLError as e:
        raise ZotError(1, f"cannot reach Zotero on port {cfg['port']}: {e.reason}. Is Zotero running on this "
                          f"machine? Is 'port' right in {cfg['_configPath']} (Zotero's default is 23119)?")


def get_json_with_headers(cfg, path, query=None, what="request"):
    r = request(cfg, "GET", path, query=query)
    if r.status == 404:
        raise ZotError(3, f"{what}: not found")
    if r.status == 403:
        raise ZotError(2, ENABLE_HINT)
    if r.status != 200:
        raise ZotError(1, f"{what}: {r.status} {r.text[:200]}")
    return r.json(), r.headers


def get_json(cfg, path, query=None, what="request"):
    return get_json_with_headers(cfg, path, query, what)[0]


def listing(rows: list, headers, limit: int) -> dict:
    """count/total/warnings for a capped list read. `Total-Results` is the web API header
    for the unpaged size; if this Zotero omits it, warn whenever the cap was hit."""
    raw = headers.get("Total-Results")
    total = int(raw) if raw and str(raw).isdigit() else None
    if total is None:
        warn = [f"showing {len(rows)}; no Total-Results header, there may be more; raise --limit"]
        return {"count": len(rows), "total": None, "warnings": warn if len(rows) >= limit else []}
    warn = [f"showing {len(rows)} of {total}; raise --limit"]
    return {"count": len(rows), "total": total, "warnings": warn if total > len(rows) else []}


# --- guards -----------------------------------------------------------------

def ping(cfg) -> str:
    r = request(cfg, "GET", "/connector/ping")
    if r.status != 200:
        raise ZotError(1, f"/connector/ping returned {r.status}")
    return r.headers.get("X-Zotero-Version", "unknown")


def server_id(cfg) -> str:
    r = request(cfg, "GET", "/api/")
    if r.status == 403:
        raise ZotError(2, ENABLE_HINT)
    sid = r.headers.get("Zotero-Server-ID")
    if r.status != 200 or not sid:
        raise ZotError(1, f"/api/ returned {r.status} without a Zotero-Server-ID header")
    return sid


def file_url_to_path(url: str) -> str:
    p = urllib.parse.unquote(urllib.parse.urlparse(url.strip()).path)
    if re.match(r"^/[A-Za-z]:", p):
        p = p[1:]
    return p


def _norm(p: str) -> str:
    return p.replace("\\", "/").rstrip("/").casefold()


def data_dir_guard(cfg) -> tuple[bool, str]:
    """The trap: a plugin dev profile on the same port, serving a *copy* of the library
    with the same server ID. Only the served file paths tell them apart."""
    want = cfg.get("dataDir")
    if not want:
        return False, "config has no 'dataDir'; set it to Zotero's data directory (Settings → Advanced → Files and Folders)"
    r = request(cfg, "GET", "/api/users/0/items", query={"itemType": "attachment", "limit": 5})
    if r.status != 200:
        return False, f"could not list attachments ({r.status})"
    files = [i for i in r.json() if i["data"].get("linkMode") in IMPORTED]
    if not files:
        return True, "library has no file attachments; data-dir guard skipped"
    keys = [f["key"] for f in files]
    for key in keys:  # any one attachment may be missing from disk; the first that resolves decides
        r = request(cfg, "GET", f"/api/users/0/items/{key}/file/view/url")
        if r.status != 200:
            continue
        served = file_url_to_path(r.text)
        if not _norm(served).startswith(_norm(want) + "/"):
            root = served.split("/storage/")[0]
            return False, (f"Zotero on port {cfg['port']} serves files from '{root}' but config dataDir is '{want}' "
                           f"— a different profile (plugin dev instance?) owns this port")
        return True, f"data dir ok: {want}"
    return False, f"tried {keys}: no attachment resolved; is Zotero's storage on disk?"


def load_key(cfg) -> dict | None:
    p = Path(cfg["keyFile"])
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"key": raw, "remember": None}


def consume_single_use_key(cfg) -> None:
    """A `remember: false` key is deleted server-side by the first validated write; drop our
    copy too, so `doctor` reports the key as missing instead of a 401 on the next write."""
    entry = load_key(cfg)
    if entry and entry.get("remember") is False:
        Path(cfg["keyFile"]).unlink(missing_ok=True)


def write_headers(cfg) -> dict:
    """The guard chain every write runs. Exit 2 with the fix named on any failure."""
    ping(cfg)
    sid = server_id(cfg)
    ok, msg = data_dir_guard(cfg)
    if not ok:
        raise ZotError(2, f"refusing to write: {msg}")
    entry = load_key(cfg)
    if not entry or not entry.get("key"):
        raise ZotError(2, f"no local API key at {cfg['keyFile']}: run `zot.py authorize` (Zotero open; click Always Allow)")
    return {"Zotero-Server-ID": sid, "Zotero-API-Key": entry["key"]}


def check_write(r: Response, what: str) -> None:
    if r.status == 401:
        raise ZotError(2, f"{what}: Zotero rejected the API key (a plain 'Allow' key is single-use) — "
                          f"run `zot.py authorize` and click Always Allow")
    if r.status == 412:
        raise ZotError(1, f"{what}: 412 {r.text.strip()} — stale version or server ID; run `zot.py doctor` and retry")
    if r.status == 428:
        raise ZotError(1, f"{what}: 428 {r.text.strip()} (a precondition header is missing — bug in zot.py)")
    if r.status >= 400:
        raise ZotError(1, f"{what}: {r.status} {r.text.strip()[:300]}")


# --- shared -----------------------------------------------------------------

def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return re.sub(r"^doi:\s*", "", doi, flags=re.I).lower()


def item_doi(data: dict) -> str:
    doi = data.get("DOI") or ""
    if not doi:
        m = re.search(r"^DOI:\s*(\S+)", data.get("extra") or "", re.M | re.I)
        if m:
            doi = m.group(1)
    return normalize_doi(doi) if doi else ""


def summary(entry: dict) -> dict:
    d = entry["data"]
    creators = "; ".join(c.get("lastName") or c.get("name", "") for c in d.get("creators", []))
    return {"key": d["key"], "itemType": d.get("itemType"), "title": d.get("title", ""), "creators": creators,
            "date": d.get("date", ""), "DOI": d.get("DOI", ""), "collections": d.get("collections", []),
            "tags": [t["tag"] for t in d.get("tags", [])]}


def resolve_collection(cfg, name_or_key: str) -> str:
    cols = get_json(cfg, "/api/users/0/collections", what="collections")
    if KEY_RE.match(name_or_key) and any(c["key"] == name_or_key for c in cols):
        return name_or_key
    hits = [c for c in cols if c["data"]["name"].casefold() == name_or_key.casefold()]
    if not hits:
        raise ZotError(3, f"no collection named '{name_or_key}' (run `zot.py collections`)")
    if len(hits) > 1:
        raise ZotError(1, f"collection name '{name_or_key}' is ambiguous: {[c['key'] for c in hits]} — use the key")
    return hits[0]["key"]


def find_doi(cfg, doi: str) -> list[dict]:
    want = normalize_doi(doi)
    rows = get_json(cfg, "/api/users/0/items/top", {"q": want, "qmode": "everything", "limit": 50}, "doi search")
    return [e for e in rows if item_doi(e["data"]) == want]


def file_attachments(cfg, key: str) -> list[dict]:
    d = get_json(cfg, f"/api/users/0/items/{key}", what=f"item {key}")["data"]
    if d.get("itemType") == "attachment":
        return [d]
    kids = get_json(cfg, f"/api/users/0/items/{key}/children", what="children")
    return [k["data"] for k in kids if k["data"].get("itemType") == "attachment"]


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")


def strip_html(s: str) -> str:
    p = _Text()
    p.feed(s or "")
    return re.sub(r"\n{3,}", "\n\n", "".join(p.parts)).strip()


CSL_TYPES = {"article-journal": "journalArticle", "journal-article": "journalArticle",
             "paper-conference": "conferencePaper", "proceedings-article": "conferencePaper",
             "book": "book", "monograph": "book",
             "chapter": "bookSection", "book-chapter": "bookSection",
             "thesis": "thesis", "dissertation": "thesis",
             "report": "report",
             "posted-content": "preprint"}
DOI_FIELD_TYPES = {"journalArticle", "conferencePaper"}


def fetch_csl(doi: str) -> dict:
    req = urllib.request.Request(f"https://doi.org/{urllib.parse.quote(doi)}",
                                 headers={"Accept": "application/vnd.citationstyles.csl+json",
                                          "User-Agent": "zot.py (Python urllib)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise ZotError(3 if e.code == 404 else 1, f"doi.org returned {e.code} for {doi}")
    except urllib.error.URLError as e:
        raise ZotError(1, f"cannot reach doi.org: {e.reason}")
    try:
        csl = json.loads(body)
    except ValueError:
        raise ZotError(1, f"doi.org returned non-JSON for {doi}")
    if not isinstance(csl, dict):
        raise ZotError(1, f"doi.org returned a non-object CSL body for {doi}")
    return csl


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def _join(v):
    return ", ".join(v) if isinstance(v, list) else v


def csl_to_zotero(csl: dict) -> dict:
    ztype = CSL_TYPES.get(csl.get("type"), "document")
    item = {"itemType": ztype, "title": " ".join(str(csl.get("title", "")).split()), "creators": [],
            "tags": [], "collections": []}
    for role in ("author", "editor"):
        for a in csl.get(role) or []:
            if a.get("family"):
                item["creators"].append({"creatorType": role, "firstName": a.get("given", ""), "lastName": a["family"]})
            elif a.get("name") or a.get("literal"):
                item["creators"].append({"creatorType": role, "name": a.get("name") or a.get("literal")})
    issued = csl.get("issued") or csl.get("published-print") or csl.get("published-online") or {}
    parts = (issued.get("date-parts") or [[]])[0]
    if parts:
        item["date"] = "-".join(str(p) if i == 0 else f"{int(p):02d}" for i, p in enumerate(parts))
    container = _first(csl.get("container-title"))
    if csl.get("URL"):
        item["url"] = csl["URL"]
    if csl.get("abstract"):
        item["abstractNote"] = re.sub(r"<[^>]+>", "", csl["abstract"]).strip()
    if csl.get("language"):
        item["language"] = csl["language"]
    fields: dict
    if ztype == "journalArticle":
        fields = {"publicationTitle": container, "volume": csl.get("volume"), "issue": csl.get("issue"),
                  "pages": csl.get("page"), "ISSN": _join(csl.get("ISSN"))}
    elif ztype == "conferencePaper":
        fields = {"proceedingsTitle": container, "pages": csl.get("page"), "publisher": csl.get("publisher")}
    elif ztype == "book":
        fields = {"publisher": csl.get("publisher"), "place": csl.get("publisher-place"), "ISBN": _join(csl.get("ISBN"))}
    elif ztype == "bookSection":
        fields = {"bookTitle": container, "pages": csl.get("page"), "publisher": csl.get("publisher")}
    else:
        fields = {"publisher": csl.get("publisher")}
    item.update({k: v for k, v in fields.items() if v})
    doi = normalize_doi(csl.get("DOI") or "")
    if doi:
        if ztype in DOI_FIELD_TYPES:
            item["DOI"] = doi
        else:
            item["extra"] = f"DOI: {doi}"
    return item


# --- verbs ------------------------------------------------------------------

def cmd_doctor(cfg, args) -> dict:
    out = {"ok": True, "port": cfg["port"], "config": cfg["_configPath"], "checks": {}, "warnings": []}
    out["checks"]["zotero"] = ping(cfg)
    out["checks"]["serverId"] = server_id(cfg)
    ok, msg = data_dir_guard(cfg)
    out["checks"]["dataDir"] = msg
    if not ok:
        out["ok"] = False
    elif msg.startswith("library has no"):
        out["warnings"].append(msg)
    entry = load_key(cfg)
    if not entry:
        out["checks"]["key"] = f"none at {cfg['keyFile']} — reads work; run `zot.py authorize` before any write"
    elif entry.get("remember") is False:
        out["checks"]["key"] = "present but single-use (plain Allow) — not probed so it is not consumed; prefer Always Allow"
    else:
        r = request(cfg, "POST", "/api/users/0/items", data=[],
                    headers={"Zotero-Server-ID": out["checks"]["serverId"], "Zotero-API-Key": entry["key"]})
        if r.status == 400:
            out["checks"]["key"] = "valid"
        else:
            out["checks"]["key"] = ("rejected — run `zot.py authorize`" if r.status == 401 else f"unexpected {r.status}")
            out["ok"] = False
    return out


def cmd_search(cfg, args) -> dict:
    q = {"q": args.query, "limit": args.limit}
    if args.everything:
        q["qmode"] = "everything"
    rows, headers = get_json_with_headers(cfg, "/api/users/0/items/top", q, "search")
    return {"ok": True, **listing(rows, headers, args.limit), "items": [summary(e) for e in rows]}


def cmd_doi(cfg, args) -> dict:
    hits = find_doi(cfg, args.doi)
    if not hits:
        return {"ok": True, "found": False, "doi": normalize_doi(args.doi), "_exit": 3}
    return {"ok": True, "found": True, "key": hits[0]["key"], "item": summary(hits[0])}


def cmd_item(cfg, args) -> dict:
    e = get_json(cfg, f"/api/users/0/items/{args.key}", what=f"item {args.key}")
    kids = get_json(cfg, f"/api/users/0/items/{args.key}/children", what="children")
    return {"ok": True, "item": e["data"], "children": [k["data"] for k in kids]}


def cmd_collections(cfg, args) -> dict:
    cols = get_json(cfg, "/api/users/0/collections", what="collections")
    rows = [{"key": c["key"], "name": c["data"]["name"], "parent": c["data"].get("parentCollection") or None,
             "numItems": c["meta"].get("numItems", 0)} for c in cols]
    return {"ok": True, "collections": sorted(rows, key=lambda r: (r["parent"] or "", r["name"].casefold()))}


def cmd_collection(cfg, args) -> dict:
    key = resolve_collection(cfg, args.name)
    rows, headers = get_json_with_headers(cfg, f"/api/users/0/collections/{key}/items/top",
                                          {"limit": args.limit}, "collection items")
    return {"ok": True, "collection": key, **listing(rows, headers, args.limit),
            "items": [summary(e) for e in rows]}


def cmd_annotations(cfg, args) -> dict:
    out = []
    for att in file_attachments(cfg, args.key):
        for k in get_json(cfg, f"/api/users/0/items/{att['key']}/children", what="annotations"):
            a = k["data"]
            if a.get("itemType") != "annotation":
                continue
            out.append({"attachment": att["key"], "sortIndex": a.get("annotationSortIndex", ""),
                        "page": a.get("annotationPageLabel", ""), "type": a.get("annotationType", ""),
                        "text": a.get("annotationText", ""), "comment": a.get("annotationComment", ""),
                        "color": a.get("annotationColor", "")})
    out.sort(key=lambda a: (a["attachment"], a["sortIndex"]))
    return {"ok": True, "count": len(out), "annotations": out}


def cmd_notes(cfg, args) -> dict:
    kids = get_json(cfg, f"/api/users/0/items/{args.key}/children", what="notes")
    notes = [{"key": k["data"]["key"], "text": strip_html(k["data"].get("note", ""))}
             for k in kids if k["data"].get("itemType") == "note"]
    return {"ok": True, "count": len(notes), "notes": notes}


def cmd_file(cfg, args) -> dict:
    atts = [a for a in file_attachments(cfg, args.key) if a.get("linkMode") in IMPORTED]
    if not atts:
        raise ZotError(3, f"{args.key} has no file attachment")
    r = request(cfg, "GET", f"/api/users/0/items/{atts[0]['key']}/file/view/url")
    if r.status != 200:
        raise ZotError(1, f"file/view/url: {r.status} {r.text[:200]}")
    return {"ok": True, "attachment": atts[0]["key"], "path": file_url_to_path(r.text), "md5": atts[0].get("md5")}


def cmd_authorize(cfg, args) -> dict:
    ping(cfg)
    sid = server_id(cfg)
    print(f"Zotero is asking whether to allow '{cfg['appName']}' — click Always Allow in the Zotero window.", file=sys.stderr)
    r = request(cfg, "POST", "/api/local/authorize", data={"appName": cfg["appName"]},
                headers={"Zotero-Server-ID": sid}, timeout=180)
    if r.status == 403:
        raise ZotError(2, "authorization denied in Zotero (or the local API is disabled)")
    if r.status == 429:
        raise ZotError(1, f"too many authorization prompts; retry after {r.headers.get('Retry-After')} s")
    if r.status != 200:
        raise ZotError(1, f"authorize: {r.status} {r.text[:200]}")
    body = r.json()
    remember = bool(body.get("remember"))
    p = Path(cfg["keyFile"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"key": body["key"], "remember": remember}), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    warnings = [] if remember else ["key is single-use (you clicked Allow, not Always Allow): the first write consumes it"]
    return {"ok": True, "keyFile": str(p), "remember": remember, "warnings": warnings}


def post_items(cfg, headers: dict, items: list[dict], what: str) -> list[str]:
    r = request(cfg, "POST", "/api/users/0/items", data=items, headers=headers)
    check_write(r, what)
    consume_single_use_key(cfg)
    res = r.json()
    if res.get("failed"):
        raise ZotError(1, f"{what}: Zotero rejected {len(res['failed'])} item(s): "
                          + "; ".join(f"[{i}] {f['code']} {f['message']}" for i, f in res["failed"].items()))
    return [res["success"][str(i)] for i in range(len(items))]


def patch_item(cfg, headers: dict, key: str, version: int, patch: dict, what: str) -> dict:
    r = request(cfg, "PATCH", f"/api/users/0/items/{key}", data=patch,
                headers={**headers, "If-Unmodified-Since-Version": str(version)})
    check_write(r, what)
    consume_single_use_key(cfg)
    return get_json(cfg, f"/api/users/0/items/{key}", what=f"re-read {key}")["data"]  # never trust the 204 alone


def cmd_add(cfg, args) -> dict:
    path = Path(args.json)
    if not path.is_file():
        raise ZotError(1, f"no such file: {path}")
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ZotError(1, f"{path} is not valid JSON: {e}")
    if isinstance(items, dict):
        items = [items]
    if not items:
        raise ZotError(1, "no items in the JSON file")
    if len(items) > 50:
        raise ZotError(1, "more than 50 items; split the file")
    headers = write_headers(cfg)
    col = resolve_collection(cfg, args.collection) if args.collection else None
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    for it in items:
        if not isinstance(it, dict) or not it.get("itemType"):
            raise ZotError(1, "every item needs an itemType (journalArticle, conferencePaper, book, bookSection, document, …)")
        if col:
            it["collections"] = sorted(set(it.get("collections", [])) | {col})
        if tags:
            have = {t.get("tag") for t in it.get("tags", [])}
            it["tags"] = it.get("tags", []) + [{"tag": t} for t in tags if t not in have]
    keys = post_items(cfg, headers, items, "add")
    written = [summary(get_json(cfg, f"/api/users/0/items/{k}", what=f"re-read {k}")) for k in keys]
    return {"ok": True, "keys": keys, "items": written}


def cmd_tag(cfg, args) -> dict:
    headers = write_headers(cfg)
    e = get_json(cfg, f"/api/users/0/items/{args.key}", what=f"item {args.key}")
    d = e["data"]
    have = {t["tag"] for t in d.get("tags", [])}
    new = [{"tag": t} for t in args.tags if t not in have]
    if not new:
        return {"ok": True, "key": args.key, "tags": sorted(have), "warnings": ["nothing to add"]}
    after = patch_item(cfg, headers, args.key, e["version"], {"tags": d.get("tags", []) + new}, "tag")
    got = {t["tag"] for t in after.get("tags", [])}
    missing = [t for t in args.tags if t not in got]
    if missing:
        raise ZotError(1, f"tag: re-read shows tags missing: {missing}")
    return {"ok": True, "key": args.key, "tags": sorted(got), "warnings": []}


def cmd_file_into(cfg, args) -> dict:
    headers = write_headers(cfg)
    col = resolve_collection(cfg, args.collection)
    e = get_json(cfg, f"/api/users/0/items/{args.key}", what=f"item {args.key}")
    d = e["data"]
    if col in d.get("collections", []):
        return {"ok": True, "key": args.key, "collections": d["collections"], "warnings": ["already in that collection"]}
    after = patch_item(cfg, headers, args.key, e["version"], {"collections": d.get("collections", []) + [col]}, "file-into")
    if col not in after.get("collections", []):
        raise ZotError(1, "file-into: re-read does not show the collection")
    return {"ok": True, "key": args.key, "collections": after["collections"], "warnings": []}


def cmd_from_doi(cfg, args) -> dict:
    return csl_to_zotero(fetch_csl(normalize_doi(args.doi)))  # bare item JSON: `> item.json` then `add --json`


def cmd_attach(cfg, args) -> dict:
    headers = write_headers(cfg)
    path = Path(args.file)
    if not path.is_file():
        raise ZotError(1, f"no such file: {path}")
    parent = get_json(cfg, f"/api/users/0/items/{args.key}", what=f"item {args.key}")["data"]
    if parent.get("itemType") in ("attachment", "note", "annotation"):
        raise ZotError(1, f"{args.key} is a {parent['itemType']}, not a parent item")
    data = path.read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    ctype = "application/pdf" if path.suffix.lower() == ".pdf" else (mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    [akey] = post_items(cfg, headers, [{"itemType": "attachment", "parentItem": args.key, "linkMode": "imported_file",
                                        "title": args.title or path.name, "contentType": ctype,
                                        "filename": path.name, "tags": []}], "attach: create attachment item")
    form = {"md5": md5, "filename": path.name, "filesize": str(len(data)), "mtime": str(int(path.stat().st_mtime * 1000))}
    r = request(cfg, "POST", f"/api/users/0/items/{akey}/file", form=form, headers={**headers, "If-None-Match": "*"})
    try:  # the attachment item exists from here on; every failure below must name it
        check_write(r, "attach: authorize upload")
        auth = r.json()
        if not auth.get("exists"):
            r = request(cfg, "POST", auth["url"], data=data, timeout=300)
            if r.status != 201:
                raise ZotError(1, f"attach: upload returned {r.status} {r.text[:200]}")
            r = request(cfg, "POST", f"/api/users/0/items/{akey}/file", form={"upload": auth["uploadKey"]},
                        headers={**headers, "If-None-Match": "*"})
            check_write(r, "attach: register upload")
    except ZotError as e:
        raise ZotError(e.code, f"{e} — attachment item {akey} was created without a file; "
                               f"delete it in Zotero before retrying")
    after = get_json(cfg, f"/api/users/0/items/{akey}", what="re-read attachment")["data"]
    if after.get("md5") != md5:
        raise ZotError(1, f"attach: Zotero reports md5 {after.get('md5')} but the file is {md5}")
    return {"ok": True, "parent": args.key, "attachment": akey, "md5": md5, "filename": path.name, "contentType": ctype}


# --- main -------------------------------------------------------------------

def pretty(result: dict) -> None:
    for k in ("items", "collections", "annotations", "notes", "children"):
        rows = result.get(k)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            cols = [c for c in rows[0] if not isinstance(rows[0][c], (list, dict))]
            width = {c: min(60, max(len(c), *(len(str(r.get(c, ""))) for r in rows))) for c in cols}
            print("  ".join(c.ljust(width[c]) for c in cols))
            for r in rows:
                print("  ".join(str(r.get(c, "")).replace("\n", " ")[:width[c]].ljust(width[c]) for c in cols))
            return
    print(json.dumps(result, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zot.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pretty", action="store_true", help="render list results as a table")
    sub = p.add_subparsers(dest="verb", required=True)
    sub.add_parser("doctor", help="Zotero up, server ID, local API on, data-dir guard, key valid").set_defaults(func=cmd_doctor)
    s = sub.add_parser("search", help="title/creator/year search; --everything for all fields")
    s.add_argument("query")
    s.add_argument("--everything", action="store_true")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)
    d = sub.add_parser("doi", help="exact DOI lookup; exit 3 when absent")
    d.add_argument("doi")
    d.set_defaults(func=cmd_doi)
    i = sub.add_parser("item", help="item + children")
    i.add_argument("key")
    i.set_defaults(func=cmd_item)
    sub.add_parser("collections", help="collection tree with counts").set_defaults(func=cmd_collections)
    c = sub.add_parser("collection", help="top-level items of a collection (name or key)")
    c.add_argument("name")
    c.add_argument("--limit", type=int, default=100)
    c.set_defaults(func=cmd_collection)
    a = sub.add_parser("annotations", help="PDF annotations of an item in page order")
    a.add_argument("key")
    a.set_defaults(func=cmd_annotations)
    n = sub.add_parser("notes", help="child notes, HTML stripped")
    n.add_argument("key")
    n.set_defaults(func=cmd_notes)
    sub.add_parser("authorize", help="get a local API key (Zotero shows Allow / Always Allow / Deny)").set_defaults(func=cmd_authorize)
    f = sub.add_parser("file", help="local path of the item's PDF")
    f.add_argument("key")
    f.set_defaults(func=cmd_file)
    ad = sub.add_parser("add", help="create item(s) from Zotero item JSON (object or array)")
    ad.add_argument("--json", required=True, help="file with Zotero item JSON")
    ad.add_argument("--collection", help="collection name or key to file into")
    ad.add_argument("--tags", help="comma-separated tags to add")
    ad.set_defaults(func=cmd_add)
    t = sub.add_parser("tag", help="add tags to an item")
    t.add_argument("key")
    t.add_argument("tags", nargs="+")
    t.set_defaults(func=cmd_tag)
    fi = sub.add_parser("file-into", help="add an item to a collection (name or key)")
    fi.add_argument("key")
    fi.add_argument("collection")
    fi.set_defaults(func=cmd_file_into)
    fd = sub.add_parser("from-doi", help="Zotero item JSON from a DOI (doi.org content negotiation)")
    fd.add_argument("doi")
    fd.set_defaults(func=cmd_from_doi)
    at = sub.add_parser("attach", help="attach a file to an item (imported_file + upload + md5 check)")
    at.add_argument("key")
    at.add_argument("file")
    at.add_argument("--title", help="attachment title (default: file name)")
    at.set_defaults(func=cmd_attach)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(load_config(), args)
    except ZotError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return e.code
    except Exception as e:  # the contract is one JSON object on stdout, never a traceback
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1
    code = result.pop("_exit", 0)
    if args.pretty:
        pretty(result)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    if code:
        return code
    return 0 if result.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
