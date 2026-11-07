"""reading_list.py — the reading-list note of Meristema Reading, ported to Python (stdlib).

The contract is `fixtures/README.md` in the zotero-meristema-reading repo, which every
implementation must pass; `tests/test_reading_list_fixtures.py` runs its list cases here.
Only the list half of the format is ported: the read-state note (`meristema-reading-state`,
paper ids, merging, next-up) is not needed by the skill and is left out.

Regex rules from the README: patterns compile with re.ASCII and IGNORECASE folds ASCII only;
JavaScript's `\\s` is spelled out as JS_WS; whole-string checks use fullmatch.
"""
from __future__ import annotations

import json
import re
from typing import Callable

READING_LIST_TAG = "meristema-reading-list"
READING_LIST_ATTRIBUTE = "meristema-reading-list"
ITEM_KEY_CHARS = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

# JavaScript's \s: the characters String.prototype.trim removes.
JS_WS = "[\t\n\v\f\r    -     　﻿]"

_ITEM_KEY = re.compile(f"[{ITEM_KEY_CHARS}]{{8}}", re.ASCII)
_ENTITY = re.compile(r"&(#x[0-9a-f]+|#\d+|[a-z]+);", re.ASCII | re.IGNORECASE)
_BR = re.compile(f"<br{JS_WS}*/?>", re.ASCII | re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>", re.ASCII)
_PRE = re.compile(r"<pre\b[^>]*>([\s\S]*?)</pre>", re.ASCII | re.IGNORECASE)
_SURROGATES = re.compile("([\ud800-\udbff][\udc00-\udfff])|([\ud800-\udfff])")
_NAMED = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}
_BAD_SHAPE = {"ok": False, "reason": "bad-shape"}


# --- html -------------------------------------------------------------------------

def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _entity(m: re.Match) -> str:
    body = m.group(1)
    if body.startswith("#"):
        hexa = body[1] in "xX"
        digits = (body[2:] if hexa else body[1:]).lstrip("0") or "0"
        if len(digits) > 8:  # far above 0x10FFFF; also keeps int() clear of Python's digit limit
            return m.group(0)
        code = int(digits, 16 if hexa else 10)
        return chr(code) if code <= 0x10FFFF else m.group(0)
    return _NAMED.get(body.lower(), m.group(0))


def unescape_html(text: str) -> str:
    """One pass; only the six named forms (any case) and numeric references up to 0x10FFFF."""
    return _ENTITY.sub(_entity, text)


def _block_text(inner: str) -> str:
    return unescape_html(_TAG.sub("", _BR.sub("\n", inner)))


def extract_data_block(html: str, attribute: str) -> str | None:
    """The text of the first `<pre>` carrying `data-<attribute>="1"` (leniently), or None."""
    pattern = re.compile(f"<pre\\b[^>]*\\bdata-{attribute}{JS_WS}*={JS_WS}*[\"']?1[\"']?[^>]*>([\\s\\S]*?)</pre>",
                         re.ASCII | re.IGNORECASE)
    m = pattern.search(html)
    return _block_text(m.group(1)) if m else None


def pre_block_texts(html: str) -> list[str]:
    """Every `<pre>`'s text in order: the note editor saves `<pre>` without its attribute."""
    return [_block_text(m.group(1)) for m in _PRE.finditer(html)]


# --- json ---------------------------------------------------------------------------

class _NotJSON(Exception):
    pass


def _reject_constant(name: str):
    raise _NotJSON(name)  # NaN, Infinity, -Infinity: Python accepts them, JSON.parse does not


def js_parse(text: str):
    """JSON.parse: raises _NotJSON. Numbers are doubles, as in JavaScript (so a 5000-digit
    integer is inf rather than Python's digit-limit error)."""
    try:
        return json.loads(text, parse_int=float, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as e:
        raise _NotJSON(str(e)) from None


def _surrogate(m: re.Match) -> str:
    if m.group(1):
        hi, lo = (ord(c) for c in m.group(1))
        return chr(0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00))
    return f"\\u{ord(m.group(2)):04x}"


def js_json(value) -> str:
    """JSON.stringify(value): no spaces, non-ASCII as itself, lone surrogates as \\udxxx."""
    return _SURROGATES.sub(_surrogate, json.dumps(value, ensure_ascii=False, separators=(",", ":")))


# --- common -------------------------------------------------------------------------

def is_item_key(value) -> bool:
    return isinstance(value, str) and _ITEM_KEY.fullmatch(value) is not None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _versioned_pre_text(html: str) -> str | None:
    for text in pre_block_texts(html):
        try:
            data = js_parse(text)
        except _NotJSON:
            continue
        if isinstance(data, dict) and "version" in data:
            return text
    return None


def read_versioned_block(html: str, attribute: str) -> dict:
    """{"ok": True, "value": object} once the block's version is 1, else {"ok": False, "reason"}."""
    text = extract_data_block(html, attribute)
    if text is None:
        text = _versioned_pre_text(html)
    if text is None:
        return {"ok": False, "reason": "no-data"}
    try:
        data = js_parse(text)
    except _NotJSON:
        return {"ok": False, "reason": "bad-json"}
    if not isinstance(data, dict):
        return dict(_BAD_SHAPE)
    version = data.get("version")
    if _is_number(version) and version == 1:
        return {"ok": True, "value": data}
    return {"ok": False, "reason": "unknown-version" if _is_number(version) else "bad-shape"}


# --- reading list -------------------------------------------------------------------

def parse_reading_list(html: str) -> dict:
    """{"ok": True, "value": {"version": 1, "topic", "steps": [{"key", "why"}]}} or
    {"ok": False, "reason": "no-data" | "bad-json" | "unknown-version" | "bad-shape"}."""
    block = read_versioned_block(html, READING_LIST_ATTRIBUTE)
    if not block["ok"]:
        return block
    topic, steps = block["value"].get("topic"), block["value"].get("steps")
    if not isinstance(topic, str) or not isinstance(steps, list):
        return dict(_BAD_SHAPE)
    seen: set[str] = set()
    kept: list[dict] = []
    for step in steps:
        if not isinstance(step, dict):
            return dict(_BAD_SHAPE)
        key, why = step.get("key"), step.get("why", "")
        if not is_item_key(key) or not isinstance(why, str):
            return dict(_BAD_SHAPE)
        if key in seen:
            continue
        seen.add(key)
        kept.append({"key": key, "why": why})
    return {"ok": True, "value": {"version": 1, "topic": topic, "steps": kept}}


def _code_units(text: str) -> bytes:
    """Compare as UTF-16 code units: big-endian bytes order the same way."""
    return text.encode("utf-16-be", "surrogatepass")


def resolve_reading_list(doc: dict, folder: list[dict]) -> dict:
    """{"steps": [{"step", "key", "why"}], "unordered": [key]} against a folder's [{"key", "title"}]."""
    present = {item["key"] for item in folder}
    steps = [{"step": i + 1, "key": s["key"], "why": s["why"]}
             for i, s in enumerate(s for s in doc["steps"] if s["key"] in present)]
    ordered = {s["key"] for s in steps}
    rest = sorted((item for item in folder if item["key"] not in ordered),
                  key=lambda item: (_code_units(item["title"].lower()), _code_units(item["key"])))
    return {"steps": steps, "unordered": [item["key"] for item in rest]}


def item_href(link: dict, key: str) -> str:
    """link is {"kind": "user"} or {"kind": "group", "id": N}."""
    if link["kind"] == "user":
        return f"zotero://select/library/items/{key}"
    return f"zotero://select/groups/{link['id']}/items/{key}"


def write_reading_list(doc: dict, label: Callable[[str], str], link: dict) -> str:
    """The whole note, one line: the readable part rebuilt from doc, then the data block."""
    items = "".join(
        f'<li><a href="{item_href(link, s["key"])}">{escape_html(label(s["key"]))}</a>'
        + (f": {escape_html(s['why'])}" if s["why"] else "") + "</li>"
        for s in doc["steps"])
    data = js_json({"version": 1, "topic": doc["topic"],
                    "steps": [{"key": s["key"], "why": s["why"]} for s in doc["steps"]]})
    return (f"<h1>Reading list - {escape_html(doc['topic'])}</h1><ol>{items}</ol>"
            f"<p>Plugin data (do not edit)</p>"
            f'<pre data-{READING_LIST_ATTRIBUTE}="1">{escape_html(data)}</pre>')


# --- doi ----------------------------------------------------------------------------

_DOI_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.)?doi\.org/", re.ASCII | re.IGNORECASE)
_DOI_SCHEME = re.compile(f"^doi:{JS_WS}*", re.ASCII | re.IGNORECASE)
_DOI_FIND = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.ASCII | re.IGNORECASE)
_JS_TRIM = re.compile(f"^{JS_WS}+|{JS_WS}+$")


def normalize_doi(value) -> str | None:
    """The README's normalizeDOI: the lowercased DOI inside value, or None."""
    text = "" if value is None else str(value)
    text = _JS_TRIM.sub("", text)
    text = _DOI_SCHEME.sub("", _DOI_PREFIX.sub("", text, count=1), count=1)
    text = _JS_TRIM.sub("", text).lower()
    m = _DOI_FIND.search(text)
    return m.group(0).rstrip(".,;").lower() if m else None
