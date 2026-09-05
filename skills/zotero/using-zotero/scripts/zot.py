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
        cfg.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if not k.startswith("_")})
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
    except urllib.error.URLError as e:
        raise ZotError(1, f"cannot reach Zotero on port {cfg['port']}: {e.reason}. Is Zotero running on this "
                          f"machine? Is 'port' right in {cfg['_configPath']} (Zotero's default is 23119)?")


def get_json(cfg, path, query=None, what="request"):
    r = request(cfg, "GET", path, query=query)
    if r.status == 404:
        raise ZotError(3, f"{what}: not found")
    if r.status == 403:
        raise ZotError(2, ENABLE_HINT)
    if r.status != 200:
        raise ZotError(1, f"{what}: {r.status} {r.text[:200]}")
    return r.json()


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
    key = files[0]["key"]
    r = request(cfg, "GET", f"/api/users/0/items/{key}/file/view/url")
    if r.status != 200:
        return False, f"file/view/url for {key} returned {r.status}"
    served = file_url_to_path(r.text)
    if not _norm(served).startswith(_norm(want) + "/"):
        root = served.split("/storage/")[0]
        return False, (f"Zotero on port {cfg['port']} serves files from '{root}' but config dataDir is '{want}' "
                       f"— a different profile (plugin dev instance?) owns this port")
    return True, f"data dir ok: {want}"


def load_key(cfg) -> dict | None:
    p = Path(cfg["keyFile"])
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"key": raw, "remember": None}


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
    rows = get_json(cfg, "/api/users/0/items/top", q, "search")
    return {"ok": True, "count": len(rows), "items": [summary(e) for e in rows]}


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
    rows = get_json(cfg, f"/api/users/0/collections/{key}/items/top", {"limit": 100}, "collection items")
    return {"ok": True, "collection": key, "count": len(rows), "items": [summary(e) for e in rows]}


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
    server_id(cfg)
    print(f"Zotero is asking whether to allow '{cfg['appName']}' — click Always Allow in the Zotero window.", file=sys.stderr)
    r = request(cfg, "POST", "/api/local/authorize", data={"appName": cfg["appName"]}, timeout=180)
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
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(load_config(), args)
    except ZotError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return e.code
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
