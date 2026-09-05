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
