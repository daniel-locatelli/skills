"""Unit cases for scripts/reading_list.py where the shared fixtures are thin: the README's
port rules (ASCII regexes, JavaScript whitespace, JSON.parse and JSON.stringify edges)."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import reading_list as rl  # noqa: E402

LIST = '<pre data-meristema-reading-list="1">{}</pre>'


def parse_block(text: str) -> dict:
    return rl.parse_reading_list(LIST.format(rl.escape_html(text)))


def ok(topic="T", steps=()):
    return {"ok": True, "value": {"version": 1, "topic": topic, "steps": list(steps)}}


# --- entities -------------------------------------------------------------------

@pytest.mark.parametrize("raw, want", [
    ("&AMP;&Lt;&gT;&QUOT;&apos;&NBSP;", "&<>\"' "),
    ("&amp;lt;", "&lt;"),                     # one pass
    ("&#65;&#x42;&#X43;&#x1F600;", "ABC\U0001F600"),
    ("&#65", "&#65"),                         # no semicolon
    ("&#x110000;&#1114112;", "&#x110000;&#1114112;"),  # above 0x10FFFF
    ("&#x10FFFF;", "\U0010FFFF"),
    ("&#" + "1" * 5000 + ";", "&#" + "1" * 5000 + ";"),  # parseInt gives Infinity; no digit-limit error
    ("&#0000000065;&#x000000041;", "AA"),     # leading zeros
    ("&eacute;&copy;", "&eacute;&copy;"),     # other named entities stay
    ("&ſamp;&ampK;", "&ſamp;&ampK;"),  # ASCII case folding only
    ("&#１２;", "&#１２;"),                     # fullwidth digits are not \d
    ("&#xD800;", "\ud800"),                   # a lone surrogate code point, as String.fromCodePoint gives
])
def test_unescape_html(raw, want):
    assert rl.unescape_html(raw) == want


def test_escape_html_leaves_apostrophes_and_controls():
    assert rl.escape_html("&<>\"'\x01 ") == "&amp;&lt;&gt;&quot;'\x01 "


# --- block finding ----------------------------------------------------------------

DOC = '{"version":1,"topic":"T","steps":[]}'


@pytest.mark.parametrize("attr", [
    'data-meristema-reading-list="1"', "data-meristema-reading-list='1\"", "data-meristema-reading-list=1",
    "data-meristema-reading-list　=﻿1", "DATA-MERISTEMA-READING-LIST=10", "x-data-meristema-reading-list=1",
])
def test_attribute_leniency(attr):
    html = f"<pre>{{\"version\":1,\"topic\":\"plain\",\"steps\":[]}}</pre><PRE {attr}>{DOC}</PRE>"
    assert rl.parse_reading_list(html) == ok("T")


@pytest.mark.parametrize("attr", [
    "data-meristema-reading-list\x1c=1",      # U+001C is Python whitespace, not JavaScript's
    "data-meristema-reading-list=2", "data-meristema-reading-listx=1",
])
def test_attribute_that_does_not_match_falls_back_to_content(attr):
    html = f"<pre {attr}>{{\"version\":1,\"topic\":\"A\",\"steps\":[]}}</pre>"
    assert rl.parse_reading_list(html) == ok("A")   # found again by the content fallback


def test_attribute_needs_ascii_case_folding():
    html = f"<pre data-meriſtema-reading-list=1>{DOC}</pre>"   # long s is not s
    assert rl.extract_data_block(html, rl.READING_LIST_ATTRIBUTE) is None


def test_fallback_skips_non_objects_and_objects_without_version():
    html = ("<pre>[1]</pre><pre>null</pre><pre>\"s\"</pre><pre>3</pre><pre>{\"topic\":1}</pre>"
            "<pre>not json</pre><pre>{\"version\":2}</pre><pre>" + DOC + "</pre>")
    assert rl.parse_reading_list(html) == {"ok": False, "reason": "unknown-version"}


def test_fallback_counts_null_version_as_present():
    assert rl.parse_reading_list('<pre>{"version":null}</pre>' + LIST.format("")) != {"ok": False, "reason": "no-data"}
    assert rl.parse_reading_list('<pre>{"version":null}</pre>') == {"ok": False, "reason": "bad-shape"}


def test_br_forms_and_tags_inside_the_block():
    html = ('<pre data-meristema-reading-list="1">{"version":1,<BR/>"topic":<span>"T"</span>,<br >'
            '"steps":[]}</pre>')
    assert rl.parse_reading_list(html) == ok("T")


def test_block_ends_at_the_first_closing_pre():
    html = '<pre data-meristema-reading-list="1">{"version":1,"topic":"</pre>","steps":[]}</pre>'
    assert rl.parse_reading_list(html) == {"ok": False, "reason": "bad-json"}


# --- JSON.parse edges -------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    '{"version":NaN,"topic":"","steps":[]}', '{"version":Infinity}', '{"version":-Infinity}',
    '﻿{"version":1,"topic":"","steps":[]}', '{"version":1,"topic":"a\tb","steps":[]}',
    '{"version":1}x', "",
])
def test_bad_json(text):
    assert parse_block(text) == {"ok": False, "reason": "bad-json"}


@pytest.mark.parametrize("version, reason", [
    ("1e0", None), ("1.0000000000000000001", None), ("1e400", "unknown-version"), ("-0", "unknown-version"),
    ("1" * 5000, "unknown-version"),  # a double, as in JavaScript: Infinity, not Python's int-digit limit
    ("true", "bad-shape"), ("false", "bad-shape"), ('"1"', "bad-shape"), ("[1]", "bad-shape"),
])
def test_version_is_the_number_one(version, reason):
    got = parse_block(f'{{"version":{version},"topic":"","steps":[]}}')
    assert got == (ok("") if reason is None else {"ok": False, "reason": reason})


@pytest.mark.parametrize("key", ["ABCD2345\n", "abcd2345", "ABCD234O", "ABCD234", "ABCD23451", "ＡBCD2345", 12345678])
def test_bad_item_keys(key):
    text = json.dumps({"version": 1, "topic": "", "steps": [{"key": key}]})
    assert parse_block(text) == {"ok": False, "reason": "bad-shape"}


@pytest.mark.parametrize("step", [[], "ABCD2345", None, {"key": "ABCD2345", "why": 1}, {"key": "ABCD2345", "why": None}])
def test_bad_steps(step):
    text = json.dumps({"version": 1, "topic": "", "steps": [step]})
    assert parse_block(text) == {"ok": False, "reason": "bad-shape"}


def test_unknown_keys_are_dropped_and_duplicates_keep_first_place():
    text = json.dumps({"version": 1, "topic": "t", "extra": 1, "steps": [
        {"key": "ABCD2345", "why": "a", "x": 1}, {"key": "BCDE3456"}, {"key": "ABCD2345", "why": "b"}]})
    assert parse_block(text) == ok("t", [{"key": "ABCD2345", "why": "a"}, {"key": "BCDE3456", "why": ""}])


# --- JSON.stringify ------------------------------------------------------------------------

def test_js_json_matches_json_stringify():
    value = {"version": 1, "topic": "\x08\t\n\x0c\r\x00\x1f\x7f/\\\"é  😀", "steps": []}
    assert rl.js_json(value) == ('{"version":1,"topic":"\\b\\t\\n\\f\\r\\u0000\\u001f\x7f/\\\\\\"é  😀",'
                                 '"steps":[]}')


def test_js_json_escapes_lone_surrogates_and_joins_pairs():
    assert rl.js_json("a\udc00b\ud83d") == '"a\\udc00b\\ud83d"'
    assert rl.js_json("😀") == '"😀"'   # a pair held as two code points is one character in JavaScript


def test_writer_drops_unknown_keys_and_writes_why_always():
    doc = {"version": 1, "topic": "t", "steps": [{"key": "ABCD2345", "why": "", "x": 1}], "extra": 2}
    html = rl.write_reading_list(doc, lambda k: "L", {"kind": "user"})
    assert html.endswith('<pre data-meristema-reading-list="1">{&quot;version&quot;:1,&quot;topic&quot;:&quot;t&quot;,'
                         '&quot;steps&quot;:[{&quot;key&quot;:&quot;ABCD2345&quot;,&quot;why&quot;:&quot;&quot;}]}</pre>')
    assert '<li><a href="zotero://select/library/items/ABCD2345">L</a></li>' in html


def test_item_href():
    assert rl.item_href({"kind": "user"}, "ABCD2345") == "zotero://select/library/items/ABCD2345"
    assert rl.item_href({"kind": "group", "id": 7}, "ABCD2345") == "zotero://select/groups/7/items/ABCD2345"


# --- resolve ---------------------------------------------------------------------------------

def test_resolve_numbers_present_steps_and_sorts_the_rest_by_code_unit():
    doc = {"version": 1, "topic": "", "steps": [{"key": "ZZZZ2222", "why": "gone"}, {"key": "BBBB2222", "why": "b"}]}
    folder = [{"key": "BBBB2222", "title": "B"}, {"key": "CCCC2222", "title": "￿"},
              {"key": "DDDD2222", "title": "\U00010000"}, {"key": "EEEE2222", "title": "İ"}]
    got = rl.resolve_reading_list(doc, folder)
    assert got["steps"] == [{"step": 1, "key": "BBBB2222", "why": "b"}]
    assert got["unordered"] == ["EEEE2222", "DDDD2222", "CCCC2222"]
