import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
sys.path.insert(0, str(HERE))
import zot  # noqa: E402
from fake_zotero import FakeZotero  # noqa: E402

PDF = b"%PDF-1.4 fake body for tests\n"


def seed(s):
    s.phd = s.add_collection("PhD")
    s.tmpl = s.add_collection("Data Template")
    s.paper = s.add_item({"itemType": "journalArticle", "title": "Planar hexagonal meshing for architecture",
                          "creators": [{"creatorType": "author", "firstName": "Ada", "lastName": "Author"}],
                          "date": "2024", "DOI": "10.1000/xyz123", "publicationTitle": "J. Shells",
                          "tags": [{"tag": "meshing"}], "collections": [s.phd]})
    s.decoy = s.add_item({"itemType": "journalArticle", "title": "Decoy with a longer DOI", "creators": [],
                          "date": "2023", "DOI": "10.1000/xyz1234"})
    s.att = s.add_item({"itemType": "attachment", "parentItem": s.paper, "linkMode": "imported_file",
                        "title": "Full Text PDF", "contentType": "application/pdf", "filename": "paper.pdf",
                        "md5": hashlib.md5(PDF).hexdigest(), "mtime": 1700000000000})
    f = s.storage_dir / "storage" / s.att / "paper.pdf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(PDF)
    s.note = s.add_item({"itemType": "note", "parentItem": s.paper, "note": "<p>First <b>note</b></p><p>Second</p>"})
    s.ann2 = s.add_item({"itemType": "annotation", "parentItem": s.att, "annotationType": "highlight",
                         "annotationText": "second", "annotationComment": "", "annotationPageLabel": "3",
                         "annotationSortIndex": "00002|000000|00010", "annotationColor": "#ffd400"})
    s.ann1 = s.add_item({"itemType": "annotation", "parentItem": s.att, "annotationType": "highlight",
                         "annotationText": "first", "annotationComment": "why", "annotationPageLabel": "1",
                         "annotationSortIndex": "00000|000000|00005", "annotationColor": "#ffd400"})


@pytest.fixture
def z(tmp_path, monkeypatch):
    data_dir = tmp_path / "zotero-data"
    (data_dir / "storage").mkdir(parents=True)
    server = FakeZotero(data_dir)
    seed(server.state)
    server.cfg_path = tmp_path / "zotero.config.json"
    server.key_file = tmp_path / "keys" / "zotero-local-api.key"
    server.data_dir = data_dir
    write_cfg(server, data_dir)
    monkeypatch.setenv("ZOTERO_CONFIG", str(server.cfg_path))
    yield server
    server.stop()


def write_cfg(server, data_dir):
    server.cfg_path.write_text(json.dumps({"port": server.port, "dataDir": str(data_dir), "appName": "zot tests",
                                           "keyFile": str(server.key_file)}), encoding="utf-8")


def run(capsys, *argv):
    code = zot.main(list(argv))
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def authorize(capsys, z, mode="always"):
    z.state.authorize_mode = mode
    code, res = run(capsys, "authorize")
    assert code == 0, res
    return res


# --- doctor -----------------------------------------------------------------

def test_doctor_ok_without_key(z, capsys):
    code, res = run(capsys, "doctor")
    assert code == 0 and res["ok"] is True
    assert res["checks"]["zotero"] == "10.0.1" and res["checks"]["serverId"] == "FAKESRV00001"
    assert res["checks"]["dataDir"].startswith("data dir ok") and "authorize" in res["checks"]["key"]


def test_doctor_refuses_wrong_data_dir(z, tmp_path, capsys):
    write_cfg(z, tmp_path / "somewhere-else")
    code, res = run(capsys, "doctor")
    assert code == 2 and res["ok"] is False
    assert "different profile" in res["checks"]["dataDir"] and "zotero-data" in res["checks"]["dataDir"]


def test_doctor_passes_with_warning_when_no_attachments(z, capsys):
    z.state.items = {k: v for k, v in z.state.items.items() if v.get("itemType") != "attachment"}
    code, res = run(capsys, "doctor")
    assert code == 0 and any("no file attachments" in w for w in res["warnings"])


def test_doctor_reports_disabled_local_api(z, capsys):
    z.state.local_api_enabled = False
    code, res = run(capsys, "doctor")
    assert code == 2 and "Allow other applications" in res["error"]


def test_doctor_connection_refused_names_port(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"port": 1, "dataDir": str(tmp_path)}), encoding="utf-8")
    monkeypatch.setenv("ZOTERO_CONFIG", str(cfg))
    code, res = run(capsys, "doctor")
    assert code == 1 and "Is Zotero running" in res["error"] and "port" in res["error"]


def test_timeout_talking_to_zotero_is_a_json_error(z, capsys, monkeypatch):
    def boom(req, timeout=None):
        raise TimeoutError("the read operation timed out")
    monkeypatch.setattr(zot.urllib.request, "urlopen", boom)
    code, res = run(capsys, "search", "x")
    assert code == 1 and res["ok"] is False and "timed out" in res["error"]


def test_unexpected_exception_is_a_json_error(z, capsys, monkeypatch):
    def boom(cfg, args):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(zot, "cmd_search", boom)
    code, res = run(capsys, "search", "x")
    assert code == 1 and res == {"ok": False, "error": "RuntimeError: kaboom"}


def test_malformed_config_is_a_json_error(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "c.json"
    cfg.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("ZOTERO_CONFIG", str(cfg))
    code, res = run(capsys, "doctor")
    assert code == 1 and "not valid JSON" in res["error"]


def test_data_dir_guard_tries_every_attachment(z, capsys):
    z.state.missing_files.add(z.state.att)          # first candidate has no file on disk
    z.state.add_item({"itemType": "attachment", "parentItem": z.state.decoy, "linkMode": "imported_file",
                      "title": "Other PDF", "contentType": "application/pdf", "filename": "other.pdf"})
    code, res = run(capsys, "doctor")
    assert code == 0 and res["checks"]["dataDir"].startswith("data dir ok")
    authorize(capsys, z, "always")
    code, res = run(capsys, "tag", z.state.paper, "guarded")
    assert code == 0, res


def test_data_dir_guard_fails_when_no_attachment_resolves(z, capsys):
    z.state.missing_files.add(z.state.att)
    code, res = run(capsys, "doctor")
    assert code == 2 and res["ok"] is False
    assert "no attachment resolved" in res["checks"]["dataDir"] and z.state.att in res["checks"]["dataDir"]


# --- reads --------------------------------------------------------------------

def test_search_title_vs_everything(z, capsys):
    code, res = run(capsys, "search", "hexagonal")
    assert code == 0 and [i["key"] for i in res["items"]] == [z.state.paper]
    assert res["items"][0]["creators"] == "Author" and res["items"][0]["DOI"] == "10.1000/xyz123"
    code, res = run(capsys, "search", "xyz123")
    assert res["count"] == 0
    code, res = run(capsys, "search", "xyz123", "--everything")
    assert res["count"] == 2


def test_doi_exact_match_beats_substring_and_normalizes(z, capsys):
    code, res = run(capsys, "doi", "10.1000/xyz123")
    assert code == 0 and res["found"] and res["key"] == z.state.paper
    code, res = run(capsys, "doi", "https://doi.org/10.1000/XYZ123")
    assert code == 0 and res["key"] == z.state.paper
    code, res = run(capsys, "doi", "10.1000/nope")
    assert code == 3 and res["found"] is False


def test_doi_reads_extra_field_for_types_without_doi(z, capsys):
    key = z.state.add_item({"itemType": "book", "title": "A book", "extra": "DOI: 10.5555/book1\nOther: x"})
    code, res = run(capsys, "doi", "10.5555/BOOK1")
    assert code == 0 and res["key"] == key


def test_item_returns_children(z, capsys):
    code, res = run(capsys, "item", z.state.paper)
    assert code == 0 and res["item"]["title"].startswith("Planar")
    assert {c["itemType"] for c in res["children"]} == {"attachment", "note"}
    code, res = run(capsys, "item", "ZZZZZZZZ")
    assert code == 3


def test_collections_and_collection(z, capsys):
    code, res = run(capsys, "collections")
    assert code == 0 and [c["name"] for c in res["collections"]] == ["Data Template", "PhD"]
    assert next(c for c in res["collections"] if c["name"] == "PhD")["numItems"] == 1
    code, res = run(capsys, "collection", "phd")
    assert code == 0 and res["collection"] == z.state.phd and [i["key"] for i in res["items"]] == [z.state.paper]
    code, res = run(capsys, "collection", z.state.tmpl)
    assert code == 0 and res["count"] == 0
    code, res = run(capsys, "collection", "Nope")
    assert code == 3 and "no collection named" in res["error"]



def test_search_reports_total_and_warns_when_truncated(z, capsys):
    for i in range(12):
        z.state.add_item({"itemType": "journalArticle", "title": f"Bulk paper {i}"})
    code, res = run(capsys, "search", "Bulk paper", "--limit", "5")
    assert code == 0 and res["count"] == 5 and res["total"] == 12
    assert res["warnings"] == ["showing 5 of 12; raise --limit"]
    code, res = run(capsys, "search", "Bulk paper")
    assert res["count"] == 12 and res["total"] == 12 and res["warnings"] == []


def test_search_total_is_null_without_total_results_header(z, capsys):
    z.state.send_totals = False
    for i in range(12):
        z.state.add_item({"itemType": "journalArticle", "title": f"Bulk paper {i}"})
    code, res = run(capsys, "search", "Bulk paper", "--limit", "5")
    assert code == 0 and res["count"] == 5 and res["total"] is None
    assert any("no Total-Results header" in w for w in res["warnings"])
    code, res = run(capsys, "search", "Bulk paper", "--limit", "50")
    assert code == 0 and res["count"] == 12 and res["total"] is None and res["warnings"] == []


def test_collection_takes_a_limit_and_reports_the_total(z, capsys):
    for i in range(12):
        z.state.add_item({"itemType": "journalArticle", "title": f"In phd {i}", "collections": [z.state.phd]})
    code, res = run(capsys, "collection", "PhD", "--limit", "5")
    assert code == 0 and res["count"] == 5 and res["total"] == 13
    assert res["warnings"] == ["showing 5 of 13; raise --limit"]
    code, res = run(capsys, "collection", "PhD")
    assert res["count"] == 13 and res["total"] == 13 and res["warnings"] == []


def test_annotations_in_sort_order(z, capsys):
    code, res = run(capsys, "annotations", z.state.paper)
    assert code == 0 and [a["text"] for a in res["annotations"]] == ["first", "second"]
    assert res["annotations"][0]["page"] == "1" and res["annotations"][0]["comment"] == "why"


def test_notes_stripped(z, capsys):
    code, res = run(capsys, "notes", z.state.paper)
    assert code == 0 and res["notes"][0]["text"] == "First note\nSecond"


def test_file_path_and_md5(z, capsys):
    code, res = run(capsys, "file", z.state.paper)
    assert code == 0 and res["attachment"] == z.state.att
    assert res["path"].replace("\\", "/").endswith(f"/storage/{z.state.att}/paper.pdf")
    assert res["md5"] == hashlib.md5(PDF).hexdigest()
    code, res = run(capsys, "file", z.state.decoy)
    assert code == 3


# --- authorize --------------------------------------------------------------

def test_authorize_writes_key_file_and_doctor_probes_it(z, capsys):
    res = authorize(capsys, z, "always")
    assert res["remember"] is True and res["warnings"] == []
    saved = json.loads(z.key_file.read_text(encoding="utf-8"))
    assert saved["key"] in z.state.keys and saved["remember"] is True
    code, res = run(capsys, "doctor")
    assert code == 0 and res["checks"]["key"] == "valid"
    assert saved["key"] in z.state.keys  # the probe did not consume a remembered key


def test_authorize_single_use_warns_and_doctor_does_not_probe(z, capsys):
    res = authorize(capsys, z, "once")
    assert res["remember"] is False and any("single-use" in w for w in res["warnings"])
    code, res = run(capsys, "doctor")
    assert code == 0 and "single-use" in res["checks"]["key"]
    assert not any(m == "POST" and p == "/api/users/0/items" for m, p in z.state.requests)


def test_authorize_sends_server_id_header(z, capsys):
    authorize(capsys, z, "always")
    idx = max(i for i, (m, p) in enumerate(z.state.requests) if m == "POST" and p == "/api/local/authorize")
    headers = {k.lower(): v for k, v in z.state.request_headers[idx].items()}
    assert headers.get("zotero-server-id") == z.state.server_id


def test_authorize_denied_is_exit_2(z, capsys):
    z.state.authorize_mode = "deny"
    code, res = run(capsys, "authorize")
    assert code == 2 and "denied" in res["error"] and not z.key_file.exists()


def test_doctor_reports_revoked_key(z, capsys):
    authorize(capsys, z, "always")
    z.state.keys.clear()
    code, res = run(capsys, "doctor")
    assert code == 2 and "rejected" in res["checks"]["key"]


# --- writes -----------------------------------------------------------------

def test_write_without_key_asks_for_authorize(z, capsys):
    code, res = run(capsys, "tag", z.state.paper, "x")
    assert code == 2 and "authorize" in res["error"]


def test_write_refuses_wrong_data_dir_before_touching_zotero(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    write_cfg(z, tmp_path / "somewhere-else")
    code, res = run(capsys, "tag", z.state.paper, "x")
    assert code == 2 and "different profile" in res["error"]
    assert not any(m == "PATCH" for m, _ in z.state.requests)


def test_single_use_key_is_consumed_by_first_write(z, capsys):
    authorize(capsys, z, "once")
    code, res = run(capsys, "tag", z.state.paper, "first")
    assert code == 0
    code, res = run(capsys, "tag", z.state.paper, "second")
    assert code == 2 and "Always Allow" in res["error"]



def test_single_use_key_file_is_deleted_after_the_write(z, capsys):
    authorize(capsys, z, "once")
    code, res = run(capsys, "tag", z.state.paper, "first")
    assert code == 0, res
    assert not z.key_file.exists()
    code, res = run(capsys, "doctor")
    assert code == 0 and "none at" in res["checks"]["key"] and "authorize" in res["checks"]["key"]


def test_add_missing_json_file_is_a_json_error(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    code, res = run(capsys, "add", "--json", str(tmp_path / "nope.json"))
    assert code == 1 and "no such file" in res["error"]


def test_add_refuses_invalid_json(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    f = tmp_path / "broken.json"
    f.write_text("{", encoding="utf-8")
    code, res = run(capsys, "add", "--json", str(f))
    assert code == 1 and "not valid JSON" in res["error"] and str(f) in res["error"]


def test_add_refuses_more_than_50_items(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    f = tmp_path / "many.json"
    f.write_text(json.dumps([{"itemType": "journalArticle", "title": f"n{i}"} for i in range(51)]), encoding="utf-8")
    code, res = run(capsys, "add", "--json", str(f))
    assert code == 1 and "more than 50 items" in res["error"]
    assert not any(m == "POST" and p == "/api/users/0/items" for m, p in z.state.requests)


def test_add_with_collection_and_tags_reads_back(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    f = tmp_path / "item.json"
    f.write_text(json.dumps({"itemType": "journalArticle", "title": "New one", "DOI": "10.1000/new",
                             "creators": [{"creatorType": "author", "firstName": "B", "lastName": "Bee"}]}), encoding="utf-8")
    code, res = run(capsys, "add", "--json", str(f), "--collection", "PhD", "--tags", "phd,to-read")
    assert code == 0 and len(res["keys"]) == 1
    key = res["keys"][0]
    stored = z.state.items[key]
    assert stored["collections"] == [z.state.phd] and [t["tag"] for t in stored["tags"]] == ["phd", "to-read"]
    assert res["items"][0]["title"] == "New one" and res["items"][0]["key"] == key
    code, res = run(capsys, "doi", "10.1000/new")
    assert code == 0 and res["key"] == key


def test_add_reports_rejected_items(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    f = tmp_path / "bad.json"
    f.write_text(json.dumps([{"title": "no type"}]), encoding="utf-8")
    code, res = run(capsys, "add", "--json", str(f))
    assert code == 1 and "itemType" in res["error"]


def test_tag_and_file_into_are_idempotent(z, capsys):
    authorize(capsys, z, "always")
    code, res = run(capsys, "tag", z.state.decoy, "alpha", "beta")
    assert code == 0 and res["tags"] == ["alpha", "beta"]
    code, res = run(capsys, "tag", z.state.decoy, "alpha")
    assert code == 0 and res["warnings"] == ["nothing to add"]
    code, res = run(capsys, "file-into", z.state.decoy, "Data Template")
    assert code == 0 and res["collections"] == [z.state.tmpl]
    code, res = run(capsys, "file-into", z.state.decoy, z.state.tmpl)
    assert code == 0 and res["warnings"] == ["already in that collection"]
    assert z.state.items[z.state.decoy]["collections"] == [z.state.tmpl]


# --- from-doi ---------------------------------------------------------------

CSL_ARTICLE = {"type": "article-journal", "DOI": "10.1000/ART", "title": "Hexagonal  meshes\n for shells",
               "author": [{"given": "Ada", "family": "Author"}, {"given": "Bo", "family": "Builder"}],
               "container-title": "Journal of Shells", "volume": "12", "issue": "3", "page": "1-20",
               "ISSN": ["1234-5678"], "issued": {"date-parts": [[2024, 5]]}, "URL": "https://example.org/a",
               "abstract": "<jats:p>An abstract.</jats:p>"}
CSL_CONF = {"type": "paper-conference", "DOI": "10.1000/conf", "title": "A conference paper",
            "author": [{"given": "Cy", "family": "Coder"}], "container-title": "Proc. of Things", "page": "5-9",
            "publisher": "ACM", "issued": {"date-parts": [[2023]]}}
CSL_BOOK = {"type": "book", "DOI": "10.1000/book", "title": "The Book", "author": [{"literal": "Some Institute"}],
            "publisher": "Springer", "publisher-place": "Cham", "ISBN": ["978-3-16-148410-0"],
            "issued": {"date-parts": [[2020, 1, 15]]}}
CSL_CHAPTER = {"type": "chapter", "DOI": "10.1000/ch", "title": "Chapter 3", "author": [{"given": "D", "family": "Dee"}],
               "editor": [{"given": "E", "family": "Ed"}], "container-title": "Big Handbook", "page": "40-60",
               "publisher": "Wiley", "issued": {"date-parts": [[2019]]}}


def test_csl_article_maps_to_journal_article():
    it = zot.csl_to_zotero(CSL_ARTICLE)
    assert it["itemType"] == "journalArticle" and it["title"] == "Hexagonal meshes for shells"
    assert it["creators"] == [{"creatorType": "author", "firstName": "Ada", "lastName": "Author"},
                              {"creatorType": "author", "firstName": "Bo", "lastName": "Builder"}]
    assert it["publicationTitle"] == "Journal of Shells" and it["volume"] == "12" and it["issue"] == "3"
    assert it["pages"] == "1-20" and it["ISSN"] == "1234-5678" and it["date"] == "2024-05"
    assert it["DOI"] == "10.1000/art" and it["url"] == "https://example.org/a" and it["abstractNote"] == "An abstract."
    assert "extra" not in it


def test_csl_conference_and_chapter():
    c = zot.csl_to_zotero(CSL_CONF)
    assert c["itemType"] == "conferencePaper" and c["proceedingsTitle"] == "Proc. of Things"
    assert c["publisher"] == "ACM" and c["DOI"] == "10.1000/conf" and c["date"] == "2023"
    ch = zot.csl_to_zotero(CSL_CHAPTER)
    assert ch["itemType"] == "bookSection" and ch["bookTitle"] == "Big Handbook" and ch["pages"] == "40-60"
    assert {"creatorType": "editor", "firstName": "E", "lastName": "Ed"} in ch["creators"]
    assert ch["extra"] == "DOI: 10.1000/ch" and "DOI" not in ch


def test_csl_book_and_unknown_type():
    b = zot.csl_to_zotero(CSL_BOOK)
    assert b["itemType"] == "book" and b["publisher"] == "Springer" and b["place"] == "Cham"
    assert b["ISBN"] == "978-3-16-148410-0" and b["date"] == "2020-01-15" and b["extra"] == "DOI: 10.1000/book"
    assert b["creators"] == [{"creatorType": "author", "name": "Some Institute"}]
    d = zot.csl_to_zotero({"type": "dataset", "title": "R", "DOI": "10.1/r", "publisher": "Org"})
    assert d["itemType"] == "document" and d["publisher"] == "Org" and d["extra"] == "DOI: 10.1/r"


def test_csl_accepts_crossref_type_names():
    j = zot.csl_to_zotero({"type": "journal-article", "title": "T", "DOI": "10.1/j"})
    assert j["itemType"] == "journalArticle"
    c = zot.csl_to_zotero({"type": "proceedings-article", "title": "T", "DOI": "10.1/c"})
    assert c["itemType"] == "conferencePaper"


def test_fetch_csl_raises_on_non_json_body(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html>"

    monkeypatch.setattr(zot.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())
    with pytest.raises(zot.ZotError) as ei:
        zot.fetch_csl("10.1/x")
    assert ei.value.code == 1



def test_fetch_csl_raises_on_non_object_body(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"[]"

    monkeypatch.setattr(zot.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())
    with pytest.raises(zot.ZotError) as ei:
        zot.fetch_csl("10.1/x")
    assert ei.value.code == 1 and "non-object" in str(ei.value)


def test_from_doi_verb_prints_bare_item(monkeypatch, capsys):
    monkeypatch.setattr(zot, "fetch_csl", lambda doi: {**CSL_ARTICLE, "DOI": doi})
    code, res = run(capsys, "from-doi", "https://doi.org/10.1000/ART")
    assert code == 0 and res["itemType"] == "journalArticle" and res["DOI"] == "10.1000/art" and "ok" not in res


# --- attach -----------------------------------------------------------------

def test_attach_round_trip_verifies_md5(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    pdf = tmp_path / "new-paper.pdf"
    pdf.write_bytes(b"%PDF-1.7 new bytes " * 100)
    code, res = run(capsys, "attach", z.state.decoy, str(pdf), "--title", "Full Text PDF")
    assert code == 0, res
    akey = res["attachment"]
    assert res["md5"] == hashlib.md5(pdf.read_bytes()).hexdigest() and res["contentType"] == "application/pdf"
    stored = z.state.items[akey]
    assert stored["parentItem"] == z.state.decoy and stored["linkMode"] == "imported_file"
    assert stored["title"] == "Full Text PDF" and stored["md5"] == res["md5"]
    assert (z.data_dir / "storage" / akey / "new-paper.pdf").read_bytes() == pdf.read_bytes()
    assert ("POST", f"/api/users/0/items/{akey}/file") in z.state.requests
    assert any(p.startswith("/api/local/uploads/") for m, p in z.state.requests if m == "POST")
    code, res = run(capsys, "file", z.state.decoy)
    assert code == 0 and res["attachment"] == akey


def test_attach_refuses_missing_file_and_child_target(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    code, res = run(capsys, "attach", z.state.decoy, str(tmp_path / "nope.pdf"))
    assert code == 1 and "no such file" in res["error"]
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    code, res = run(capsys, "attach", z.state.note, str(pdf))
    assert code == 1 and "not a parent item" in res["error"]


def test_attach_upload_failure_names_the_orphan_attachment(z, tmp_path, capsys):
    authorize(capsys, z, "always")
    z.state.fail_uploads = True
    pdf = tmp_path / "orphan.pdf"
    pdf.write_bytes(b"%PDF-1.7 orphan")
    code, res = run(capsys, "attach", z.state.decoy, str(pdf))
    assert code == 1 and "without a file" in res["error"]
    akey = re.search(r"attachment item ([A-Z0-9]{8})", res["error"]).group(1)
    assert akey in z.state.items and not z.state.items[akey].get("md5")


# --- reading-list -----------------------------------------------------------

import reading_list as rl  # noqa: E402

CSL_NEW = {"type": "article-journal", "DOI": "10.1000/new-one", "title": "Glued joints, tested",
           "author": [{"given": "Cy", "family": "Coder"}, {"given": "Di", "family": "Dee"}],
           "issued": {"date-parts": [[2021, 3]]}}


def steps_file(tmp_path, steps, name="steps.json"):
    f = tmp_path / name
    f.write_text(steps if isinstance(steps, str) else json.dumps(steps), encoding="utf-8")
    return str(f)


def writes(z):
    return [(m, p) for m, p in z.state.requests if m in ("POST", "PATCH") and p != "/api/local/authorize"]


def list_note(s, collection, steps, date_added, key=None, topic="Old"):
    doc = {"version": 1, "topic": topic, "steps": steps}
    html = rl.write_reading_list(doc, lambda k: k, {"kind": "user"})
    data = {"itemType": "note", "note": html, "tags": [{"tag": rl.READING_LIST_TAG}], "collections": [collection],
            "dateAdded": date_added}
    return s.add_item({**data, "key": key} if key else data)


@pytest.fixture
def stub_doi(monkeypatch):
    fetched = []

    def fake(doi):
        fetched.append(doi)
        if doi != "10.1000/new-one":
            raise zot.ZotError(3, f"doi.org returned 404 for {doi}")
        return CSL_NEW
    monkeypatch.setattr(zot, "fetch_csl", fake)
    return fetched


def test_reading_list_creates_folder_adds_and_files_papers_and_writes_the_note(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    steps = steps_file(tmp_path, [{"key": s.paper, "why": "Start: the vocabulary."},
                                  {"doi": "https://doi.org/10.1000/XYZ1234"},
                                  {"doi": "10.1000/new-one", "why": "Then the tests."}])
    code, res = run(capsys, "reading-list", "--topic", "Timber joints", "--collection", "Reading", "--steps", steps)
    assert code == 0, res
    [new] = res["added"]
    col = res["collection"]
    assert s.collections[col]["name"] == "Reading" and s.collections[col]["parentCollection"] is False
    assert res["collectionCreated"] is True and res["replaced"] is False
    assert res["steps"] == [{"key": s.paper, "why": "Start: the vocabulary."}, {"key": s.decoy, "why": ""},
                            {"key": new, "why": "Then the tests."}]
    assert stub_doi == ["10.1000/new-one"]
    assert s.items[new]["DOI"] == "10.1000/new-one" and s.items[new]["collections"] == [col]
    assert set(res["filed"]) == {s.paper, s.decoy}
    assert col in s.items[s.paper]["collections"] and s.phd in s.items[s.paper]["collections"]
    note = s.items[res["note"]]
    assert note["itemType"] == "note" and note["collections"] == [col]
    assert [t["tag"] for t in note["tags"]] == ["meristema-reading-list"]
    labels = {s.paper: "Author, 2024, Planar hexagonal meshing for architecture",
              s.decoy: "2023, Decoy with a longer DOI", new: "Coder and Dee, 2021, Glued joints, tested"}
    doc = {"version": 1, "topic": "Timber joints", "steps": res["steps"]}
    assert note["note"] == rl.write_reading_list(doc, labels.__getitem__, {"kind": "user"})


def test_reading_list_uses_an_existing_folder_by_key_and_files_only_what_is_missing(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    steps = steps_file(tmp_path, [{"key": s.paper}, {"key": s.decoy, "why": "b"}])
    code, res = run(capsys, "reading-list", "--topic", "PhD", "--collection", s.phd, "--steps", steps)
    assert code == 0, res
    assert res["collection"] == s.phd and res["collectionCreated"] is False and res["added"] == []
    assert res["filed"] == [s.decoy]
    assert ("PATCH", f"/api/users/0/items/{s.paper}") not in z.state.requests
    assert not any(p == "/api/users/0/collections" for m, p in writes(z))


def test_reading_list_refuses_a_folder_that_holds_a_list(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    old = list_note(s, s.phd, [{"key": s.paper, "why": ""}], "2025-01-01T00:00:00Z")
    before = s.items[old]["note"]
    code, res = run(capsys, "reading-list", "--topic", "New", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": s.decoy}]))
    assert code == 2 and old in res["error"] and "--replace" in res["error"]
    assert writes(z) == [] and s.items[old]["note"] == before


def test_reading_list_replace_rewrites_the_oldest_list_note_only(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    later = list_note(s, s.phd, [], "2025-01-01T00:00:00Z", key="AAAA2222", topic="Later")
    tie_b = list_note(s, s.phd, [], "2024-06-01T00:00:00Z", key="CCCC2222", topic="Tie, bigger key")
    oldest = list_note(s, s.phd, [], "2024-06-01T00:00:00Z", key="BBBB2222", topic="Oldest")
    elsewhere = list_note(s, s.tmpl, [], "2020-01-01T00:00:00Z", topic="Other folder")
    plain = s.add_item({"itemType": "note", "note": "<p>not a list</p>", "collections": [s.phd],
                        "dateAdded": "2000-01-01T00:00:00Z"})
    untouched = {k: s.items[k]["note"] for k in (later, tie_b, elsewhere, plain)}
    code, res = run(capsys, "reading-list", "--topic", "Rewritten", "--collection", "PhD", "--replace",
                    "--steps", steps_file(tmp_path, [{"key": s.decoy, "why": "x"}]))
    assert code == 0, res
    assert res["note"] == oldest and res["replaced"] is True
    parsed = rl.parse_reading_list(s.items[oldest]["note"])
    assert parsed == {"ok": True, "value": {"version": 1, "topic": "Rewritten", "steps": [{"key": s.decoy, "why": "x"}]}}
    assert {k: s.items[k]["note"] for k in untouched} == untouched
    assert any(later in w and tie_b in w for w in res["warnings"])
    assert not any(m == "POST" and p == "/api/users/0/items" for m, p in writes(z))


@pytest.mark.parametrize("steps, needle", [
    ("[{", "not valid JSON"),
    ({"key": "ABCD2345"}, "non-empty JSON array"),
    ([], "non-empty JSON array"),
    (["ABCD2345"], "step 1"),
    ([{"why": "no paper"}], "exactly one of"),
    ([{"key": "ABCD2345", "doi": "10.1000/xyz123"}], "exactly one of"),
    ([{"key": "abcd2345"}], "not an item key"),
    ([{"key": "ABCD2345"}, {"doi": "not a doi"}], "step 2"),
    ([{"doi": 10.1}], "not a DOI"),
    ([{"key": "ABCD2345", "why": None}], "why"),
    ([{"key": "ABCD2345", "reason": "typo"}], "unknown field"),
])
def test_reading_list_bad_steps_fail_before_any_write(z, tmp_path, capsys, stub_doi, steps, needle):
    authorize(capsys, z)
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "New folder",
                    "--steps", steps_file(tmp_path, steps))
    assert code == 1 and needle in res["error"], res
    assert writes(z) == [] and stub_doi == []


def test_reading_list_unknown_or_non_paper_keys_fail_before_any_write(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    for steps, want in (([{"doi": "10.1000/new-one"}, {"key": "ZZZZ2222"}], 3),
                        ([{"key": s.paper}, {"key": s.note}], 1),
                        ([{"doi": "10.1000/gone"}], 3)):
        code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "New folder",
                        "--steps", steps_file(tmp_path, steps))
        assert code == want, res
    trashed = s.add_item({"itemType": "book", "title": "Binned", "deleted": True})
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "New folder",
                    "--steps", steps_file(tmp_path, [{"key": trashed}]))
    assert code == 1 and "trash" in res["error"]
    assert writes(z) == [] and "New folder" not in [c["name"] for c in s.collections.values()]


def test_reading_list_refuses_blank_topic(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    code, res = run(capsys, "reading-list", "--topic", "  ", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": z.state.paper}]))
    assert code == 1 and "topic" in res["error"] and writes(z) == []


def test_reading_list_duplicates_keep_their_first_place(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    steps = steps_file(tmp_path, [{"doi": "10.1000/new-one", "why": "first"}, {"key": s.paper, "why": "p1"},
                                  {"doi": "10.1000/XYZ123", "why": "p again"}, {"doi": "10.1000/new-one"}])
    code, res = run(capsys, "reading-list", "--topic", "Dups", "--collection", "PhD", "--steps", steps)
    assert code == 0, res
    [new] = res["added"]
    assert res["steps"] == [{"key": new, "why": "first"}, {"key": s.paper, "why": "p1"}]
    assert stub_doi == ["10.1000/new-one"]
    assert sum(1 for d in s.items.values() if d.get("DOI") == "10.1000/new-one") == 1
    assert any("step 3" in w and "step 4" in w for w in res["warnings"])


def test_reading_list_re_read_catches_a_server_that_mangles_the_note(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    s.note_filter = lambda html: html.replace("keep me", "kept")
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": s.paper, "why": "keep me"}]))
    assert code == 1 and "step 1" in res["error"] and "keep me" in res["error"] and "kept" in res["error"]
    s.note_filter = lambda html: "<p>gone</p>"
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "Data Template",
                    "--steps", steps_file(tmp_path, [{"key": s.paper}]))
    assert code == 1 and "no-data" in res["error"]


def test_reading_list_accepts_the_note_editor_saving_it_without_the_attribute(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    s.note_filter = lambda html: ('<div data-schema-version="9">'
                                  + html.replace(' data-meristema-reading-list="1"', "") + "</div>")
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": s.paper, "why": "a & b"}]))
    assert code == 0, res
    assert "data-meristema-reading-list" not in s.items[res["note"]]["note"]


def test_reading_list_runs_the_write_guard_first(z, tmp_path, capsys, stub_doi):
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": z.state.paper}]))
    assert code == 2 and "authorize" in res["error"] and writes(z) == []


def test_step_label_falls_back_without_meta():
    entry = {"data": {"title": "  ", "creators": [{"creatorType": "author", "name": "Some Institute"}, {"creatorType": "author", "lastName": "B"}], "date": "1999"},
             "meta": {}}
    assert zot.step_label(entry) == "Some Institute, Untitled"
    entry["meta"] = {"creatorSummary": "Inst. and B", "parsedDate": "0000-01"}
    assert zot.step_label(entry) == "Inst. and B, Untitled"
    entry["meta"]["parsedDate"] = "1999-02-03"
    assert zot.step_label(entry) == "Inst. and B, 1999, Untitled"


def test_reading_list_help_says_user_library_only(capsys):
    with pytest.raises(SystemExit):
        zot.main(["reading-list", "--help"])
    assert "groups are out of scope" in capsys.readouterr().out


# --- SKILL.md / packaging ---------------------------------------------------

SKILL_ROOT = HERE.parents[0]
REPO_ROOT = HERE.parents[3]


def test_skill_md_is_short_and_references_real_files():
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: using-zotero\ndescription: Use when ")
    body = text.split("---", 2)[2]
    assert len(body.split()) < 500, f"SKILL.md body is {len(body.split())} words"
    for rel in ("scripts/zot.py", "zotero.config.example.json", "reference/local-api.md"):
        assert rel in text and (SKILL_ROOT / rel).exists()
    for verb in ("doctor", "search", "doi", "item", "collections", "collection", "annotations", "notes", "file",
                 "authorize", "from-doi", "add", "attach", "tag", "file-into", "reading-list"):
        assert f"`{verb}" in text, verb


def test_no_private_identifiers_in_skill_tree():
    bad = re.compile(r"100\.94\.18\.7|dnl" + "@" + "|/srv/" + "librarian|nune" + "sd")
    for p in SKILL_ROOT.rglob("*"):
        if p.is_file() and p.name != "zotero.config.json" and "__pycache__" not in p.parts:
            assert not bad.search(p.read_text(encoding="utf-8", errors="ignore")), p


def test_registered_in_plugin_manifest():
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert "./skills/zotero/using-zotero" in manifest["skills"]
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["plugins"][0]["version"] == manifest["version"]


# --- reading-list: review fixes -----------------------------------------------------

@pytest.mark.parametrize("html, reason", [
    ('<pre data-meristema-reading-list="1">{"version":2,"topic":"T","steps":[]}</pre>', "unknown-version"),
    ('<pre data-meristema-reading-list="1">{not json</pre>', "bad-json"),
    ('<pre data-meristema-reading-list="1">{"version":1,"topic":"T","steps":"no"}</pre>', "bad-shape"),
    ("<p>tagged but no data</p>", "no-data"),
])
@pytest.mark.parametrize("flags", [["--replace"], []])
def test_reading_list_never_rewrites_a_note_that_is_not_a_list(z, tmp_path, capsys, stub_doi, html, reason, flags):
    authorize(capsys, z)
    s = z.state
    bad = s.add_item({"itemType": "note", "note": html, "tags": [{"tag": rl.READING_LIST_TAG}],
                      "collections": [s.phd], "dateAdded": "2024-01-01T00:00:00Z"})
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD", *flags,
                    "--steps", steps_file(tmp_path, [{"key": s.decoy}]))
    assert code == 2 and bad in res["error"] and reason in res["error"] and "Zotero" in res["error"], res
    assert writes(z) == [] and s.items[bad]["note"] == html


def test_reading_list_refusal_says_the_existing_list_is_readable(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    old = list_note(s, s.phd, [{"key": s.paper, "why": ""}, {"key": s.decoy, "why": ""}], "2025-01-01T00:00:00Z")
    code, res = run(capsys, "reading-list", "--topic", "New", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": s.decoy}]))
    assert code == 2 and old in res["error"] and "readable list of 2 steps" in res["error"], res


def test_reading_list_replace_still_works_over_a_readable_list(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    old = list_note(s, s.phd, [{"key": s.paper, "why": ""}], "2025-01-01T00:00:00Z")
    code, res = run(capsys, "reading-list", "--topic", "New", "--collection", "PhD", "--replace",
                    "--steps", steps_file(tmp_path, [{"key": s.decoy}]))
    assert code == 0 and res["note"] == old and res["replaced"] is True, res


@pytest.mark.parametrize("doi", ["10.1000/", "10.12/short", "doi:", "10.1000/ı", "https://example.org/x"])
def test_reading_list_refuses_a_step_doi_that_does_not_normalise(z, tmp_path, capsys, stub_doi, doi):
    authorize(capsys, z)
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "New folder",
                    "--steps", steps_file(tmp_path, [{"doi": doi}]))
    assert code == 1 and "not a DOI" in res["error"], res
    assert writes(z) == [] and stub_doi == []


def test_reading_list_step_doi_is_normalised_like_the_plugin_does(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"doi": "DOI: 10.1000/XYZ123."}]))
    assert code == 0 and [e["key"] for e in res["steps"]] == [s.paper], res


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_reading_list_refuses_a_blank_collection(z, tmp_path, capsys, stub_doi, name):
    authorize(capsys, z)
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", name,
                    "--steps", steps_file(tmp_path, [{"key": z.state.paper}]))
    assert code == 1 and "--collection" in res["error"], res
    assert writes(z) == []


def test_reading_list_creates_a_folder_with_a_padded_name_and_accepts_the_re_read(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "  Padded  ",
                    "--steps", steps_file(tmp_path, [{"key": s.paper}]))
    assert code == 0, res
    assert s.collections[res["collection"]]["name"] == "Padded"


def test_reading_list_label_fallback_uses_primary_creators_only(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    s.omit_creator_summary = True
    both = s.add_item({"itemType": "book", "title": "Edited", "date": "2020",
                       "creators": [{"creatorType": "editor", "firstName": "E", "lastName": "Editor"},
                                    {"creatorType": "author", "firstName": "A", "lastName": "Writer"}]})
    only_editor = s.add_item({"itemType": "book", "title": "Volume", "date": "2019",
                              "creators": [{"creatorType": "editor", "firstName": "E", "lastName": "Editor"}]})
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"key": both}, {"key": only_editor}]))
    assert code == 0, res
    note = s.items[res["note"]]["note"]
    assert ">Writer, 2020, Edited</a>" in note and ">2019, Volume</a>" in note


def test_reading_list_finds_an_existing_doi_among_many_decoys(z, tmp_path, capsys, stub_doi):
    authorize(capsys, z)
    s = z.state
    for n in range(60):
        s.add_item({"itemType": "journalArticle", "title": f"Cites it {n}", "extra": "cites 10.1000/target-doi"})
    target = s.add_item({"itemType": "journalArticle", "title": "The target", "DOI": "10.1000/target-doi"})
    code, res = run(capsys, "reading-list", "--topic", "T", "--collection", "PhD",
                    "--steps", steps_file(tmp_path, [{"doi": "10.1000/target-doi"}]))
    assert code == 0, res
    assert [e["key"] for e in res["steps"]] == [target] and res["added"] == [] and stub_doi == []
