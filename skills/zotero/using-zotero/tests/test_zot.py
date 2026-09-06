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
                 "authorize", "from-doi", "add", "attach", "tag", "file-into"):
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
