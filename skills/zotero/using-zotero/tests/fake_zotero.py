"""In-process fake of the Zotero 10 local API — only the subset zot.py uses.

Mirrors server_localAPI.js: reads are open; writes go enabled → server ID
(428/412) → API key (401); single-use keys are consumed on first validated
write; uploads are three-phase with md5 verification.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import string
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

IMPORTED = ("imported_file", "imported_url")


def rand(n, alphabet=string.ascii_uppercase + string.digits):
    return "".join(random.choices(alphabet, k=n))


class State:
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.server_id = "FAKESRV00001"
        self.local_api_enabled = True
        self.authorize_mode = "always"   # always | once | deny
        self.version = 0
        self.items: dict[str, dict] = {}
        self.collections: dict[str, dict] = {}
        self.keys: dict[str, bool] = {}  # api key -> remember
        self.pending: dict[str, dict] = {}
        self.requests: list[tuple[str, str]] = []

    def add_item(self, data: dict) -> str:
        key = data.get("key") or rand(8)
        self.version += 1
        d = {"tags": [], "collections": [], "relations": {}, **data, "key": key, "version": self.version}
        self.items[key] = d
        return key

    def add_collection(self, name: str, parent=False) -> str:
        key = rand(8)
        self.collections[key] = {"key": key, "version": 1, "name": name, "parentCollection": parent, "relations": {}}
        return key

    def file_path(self, key: str) -> Path:
        return self.storage_dir / "storage" / key / self.items[key]["filename"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    state: State

    def log_message(self, *args):  # silence
        pass

    # -- plumbing -----------------------------------------------------------
    def _send(self, status, body=b"", ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Zotero-Server-ID", self.state.server_id)
        self.send_header("X-Zotero-Version", "10.0.1")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)
        return True

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _wrap(self, d: dict) -> dict:
        kids = sum(1 for x in self.state.items.values() if x.get("parentItem") == d["key"])
        return {"key": d["key"], "version": d["version"], "library": {"type": "user", "id": 0},
                "meta": {"numChildren": kids}, "data": d}

    def _wrap_collection(self, c: dict) -> dict:
        s = self.state
        return {"key": c["key"], "version": c["version"], "library": {"type": "user", "id": 0},
                "meta": {"numCollections": sum(1 for x in s.collections.values() if x["parentCollection"] == c["key"]),
                         "numItems": sum(1 for d in s.items.values() if c["key"] in d.get("collections", []) and not d.get("parentItem"))},
                "data": c}

    def _write_gate(self) -> bool:
        """True when the request was refused (response already sent)."""
        s = self.state
        if not s.local_api_enabled:
            return self._send(403, "Local API is not enabled", "text/plain")
        sid = self.headers.get("Zotero-Server-ID")
        if sid is None:
            return self._send(428, "Zotero-Server-ID not provided", "text/plain")
        if sid != s.server_id:
            return self._send(412, "Zotero-Server-ID does not match this server", "text/plain")
        key = self.headers.get("Zotero-API-Key")
        if not key:
            return self._send(401, "API key required -- POST /api/local/authorize to obtain one", "text/plain",
                              {"WWW-Authenticate": 'Zotero-API-Key realm="Zotero Local API"'})
        if key not in s.keys:
            return self._send(401, "Invalid or expired API key", "text/plain")
        if not s.keys[key]:
            del s.keys[key]  # single-use: consumed by the first validated write
        return False

    # -- GET ----------------------------------------------------------------
    def do_GET(self):
        s = self.state
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path
        s.requests.append(("GET", p))
        if p == "/connector/ping":
            return self._send(200, "<!DOCTYPE html><html><body>Zotero is running</body></html>", "text/html")
        if not p.startswith("/api/"):
            return self._send(404, "Not found", "text/plain")
        if not s.local_api_enabled:
            return self._send(403, "Local API is not enabled", "text/plain")
        if p == "/api/":
            return self._send(200, "Nothing to see here.", "text/plain")
        if p == "/api/users/0/collections":
            return self._send(200, [self._wrap_collection(c) for c in s.collections.values()])
        m = re.fullmatch(r"/api/users/0/collections/([A-Z0-9]{8})/items/top", p)
        if m:
            return self._send(200, [self._wrap(d) for d in s.items.values()
                                    if m.group(1) in d.get("collections", []) and not d.get("parentItem")])
        m = re.fullmatch(r"/api/users/0/items/([A-Z0-9]{8})/file/view/url", p)
        if m:
            d = s.items.get(m.group(1))
            if not d:
                return self._send(404, "Not found", "text/plain")
            if d.get("itemType") != "attachment" or d.get("linkMode") not in IMPORTED:
                return self._send(400, f"Not a file attachment: {d['key']}", "text/plain")
            return self._send(200, s.file_path(d["key"]).as_uri(), "text/plain")
        m = re.fullmatch(r"/api/users/0/items/([A-Z0-9]{8})/children", p)
        if m:
            return self._send(200, [self._wrap(d) for d in s.items.values() if d.get("parentItem") == m.group(1)])
        m = re.fullmatch(r"/api/users/0/items/([A-Z0-9]{8})", p)
        if m:
            d = s.items.get(m.group(1))
            return self._send(200, self._wrap(d)) if d else self._send(404, "Not found", "text/plain")
        if p in ("/api/users/0/items", "/api/users/0/items/top"):
            rows = [d for d in s.items.values() if not (p.endswith("/top") and d.get("parentItem"))]
            if "itemType" in q:
                rows = [d for d in rows if d.get("itemType") == q["itemType"][0]]
            if "q" in q:
                needle = q["q"][0].lower()
                everything = q.get("qmode", [""])[0] == "everything"

                def hay(d):
                    if everything:
                        return json.dumps(d).lower()
                    return (d.get("title", "") + " " + d.get("date", "") + " "
                            + " ".join(c.get("lastName", c.get("name", "")) for c in d.get("creators", []))).lower()
                rows = [d for d in rows if needle in hay(d)]
            limit = int(q.get("limit", ["100"])[0])
            return self._send(200, [self._wrap(d) for d in rows[:limit]])
        return self._send(404, "Not found", "text/plain")

    # -- POST ---------------------------------------------------------------
    def do_POST(self):
        s = self.state
        p = urlparse(self.path).path
        s.requests.append(("POST", p))
        raw = self._body()
        if p == "/api/local/authorize":
            if not s.local_api_enabled:
                return self._send(403, "Local API is not enabled", "text/plain")
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict) or not str(body.get("appName", "")).strip():
                return self._send(400, "appName is required", "text/plain")
            if s.authorize_mode == "deny":
                return self._send(403, {"denied": True})
            key = rand(32, string.ascii_letters + string.digits)
            remember = s.authorize_mode == "always"
            s.keys[key] = remember
            return self._send(200, {"key": key, "remember": remember})
        m = re.fullmatch(r"/api/local/uploads/([A-Za-z0-9]{32})", p)
        if m:
            up = s.pending.get(m.group(1))
            if not up:
                return self._send(404, "Unknown or expired upload key", "text/plain")
            got = hashlib.md5(raw).hexdigest()
            if got != up["md5"]:
                del s.pending[m.group(1)]
                return self._send(400, f"File MD5 does not match expected (got {got}, expected {up['md5']})", "text/plain")
            up["bytes"] = raw
            up["uploaded"] = True
            return self._send(201, "", "text/plain")
        if self._write_gate():
            return
        if p == "/api/users/0/items":
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                return self._send(400, "Invalid JSON", "text/plain")
            if not isinstance(body, list):
                return self._send(400, "Uploaded data must be a JSON array", "text/plain")
            if not body:
                return self._send(400, "No items provided", "text/plain")
            res = {"successful": {}, "success": {}, "unchanged": {}, "failed": {}}
            for i, entry in enumerate(body):
                if not isinstance(entry, dict) or not entry.get("itemType"):
                    res["failed"][str(i)] = {"key": "", "code": 400, "message": "'itemType' property not provided"}
                    continue
                if entry.get("parentItem") and entry["parentItem"] not in s.items:
                    res["failed"][str(i)] = {"key": "", "code": 400, "message": "Parent item doesn't exist"}
                    continue
                key = s.add_item(entry)
                res["successful"][str(i)] = self._wrap(s.items[key])
                res["success"][str(i)] = key
            return self._send(200, res, extra={"Last-Modified-Version": str(s.version)})
        m = re.fullmatch(r"/api/users/0/items/([A-Z0-9]{8})/file", p)
        if m:
            form = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
            return self._file_write(m.group(1), form)
        return self._send(404, "Not found", "text/plain")

    def _file_write(self, key: str, form: dict):
        s = self.state
        d = s.items.get(key)
        if not d:
            return self._send(404, "Not found", "text/plain")
        if d.get("itemType") != "attachment" or d.get("linkMode") not in IMPORTED:
            return self._send(400, "Cannot upload files for non-imported attachments", "text/plain")
        if "upload" in form:  # register phase
            up = s.pending.pop(form["upload"], None)
            if not up or up["itemKey"] != key:
                return self._send(400, "Invalid or expired upload key", "text/plain")
            if not up.get("uploaded"):
                return self._send(400, "File contents were not uploaded", "text/plain")
            dest = s.storage_dir / "storage" / key / up["filename"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(up["bytes"])
            s.version += 1
            d.update({"filename": up["filename"], "md5": up["md5"], "mtime": up["mtime"], "version": s.version})
            return self._send(204, "", "text/plain", {"Last-Modified-Version": str(s.version)})
        # authorize phase
        if self.headers.get("If-Match") is None and self.headers.get("If-None-Match") is None:
            return self._send(428, "If-Match/If-None-Match header not provided", "text/plain")
        if self.headers.get("If-None-Match") == "*" and d.get("md5"):
            return self._send(412, "If-None-Match: * set but file exists", "text/plain")
        for f in ("md5", "filename", "filesize", "mtime"):
            if not form.get(f):
                return self._send(400, f"{f} not provided", "text/plain")
        if int(form["mtime"]) < 10_000_000_000:
            return self._send(400, "mtime must be provided in milliseconds, not seconds", "text/plain")
        uk = rand(32, string.ascii_letters + string.digits)
        s.pending[uk] = {"itemKey": key, "md5": form["md5"].lower(), "filename": form["filename"],
                         "mtime": int(form["mtime"]), "uploaded": False}
        return self._send(200, {"url": f"http://{self.headers.get('Host')}/api/local/uploads/{uk}", "uploadKey": uk,
                                "contentType": d.get("contentType", "application/octet-stream"), "prefix": "", "suffix": ""})

    # -- PATCH --------------------------------------------------------------
    def do_PATCH(self):
        s = self.state
        p = urlparse(self.path).path
        s.requests.append(("PATCH", p))
        raw = self._body()
        if self._write_gate():
            return
        m = re.fullmatch(r"/api/users/0/items/([A-Z0-9]{8})", p)
        d = s.items.get(m.group(1)) if m else None
        if not d:
            return self._send(404, "Not found", "text/plain")
        h = self.headers.get("If-Unmodified-Since-Version")
        if h is None:
            return self._send(428, "If-Unmodified-Since-Version not provided", "text/plain")
        if d["version"] > int(h):
            return self._send(412, f"item has been modified since specified version (expected {h}, found {d['version']})", "text/plain")
        patch = json.loads(raw)
        s.version += 1
        d.update({k: v for k, v in patch.items() if k not in ("key", "version")})
        d["version"] = s.version
        return self._send(204, "", "text/plain", {"Last-Modified-Version": str(s.version)})


class FakeZotero:
    def __init__(self, storage_dir):
        self.state = State(storage_dir)
        handler = type("BoundHandler", (Handler,), {"state": self.state})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
