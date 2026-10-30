import io
import json
import urllib.error

import pytest

import cite
from conftest import fixture

CAD = "10.1016/j.cad.2022.103435"


def rec(**kw):
    base = dict(authors=[{"given": "Rafael", "family": "Pastrana"}], title="T", year=2023)
    base.update(kw)
    return cite.Record(**base)


# --- link and formatting ---------------------------------------------------

def test_link_prefers_doi_then_arxiv_then_url():
    assert cite.link(rec(doi="10.1/x", arxiv="2307.12407", url="https://u")) == "https://doi.org/10.1/x"
    assert cite.link(rec(arxiv="2307.12407", url="https://u")) == "https://arxiv.org/abs/2307.12407"
    assert cite.link(rec(url="https://u")) == "https://u"


def test_short_one_two_many_authors():
    a = {"given": "A", "family": "Ann"}
    b = {"given": "B", "family": "Bee"}
    c = {"given": "C", "family": "Cee"}
    assert cite.short(rec(authors=[a])) == "Ann (2023)"
    assert cite.short(rec(authors=[a, b])) == "Ann & Bee (2023)"
    assert cite.short(rec(authors=[a, b, c])) == "Ann et al. (2023)"


def test_full_has_initials_venue_volume_pages_and_link():
    r = rec(authors=[{"given": "Patrick Ole", "family": "Ohlbrock"}, {"given": "Rafael", "family": "Pastrana"}],
            title="Title", venue="Computer-Aided Design", volume="155", pages="103435", doi=CAD)
    assert cite.full(r) == ("Ohlbrock, P. O. & Pastrana, R. (2023). Title. Computer-Aided Design 155, 103435. "
                            "https://doi.org/10.1016/j.cad.2022.103435")


def test_normalize_doi_strips_prefixes():
    assert cite.normalize_doi(" https://doi.org/10.1/AbC ") == "10.1/AbC"
    assert cite.normalize_doi("doi:10.1/x") == "10.1/x"


def test_split_name_last_token_is_family():
    assert cite.split_name("Ryan P. Adams") == {"given": "Ryan P.", "family": "Adams"}
    assert cite.split_name("Plato") == {"given": "", "family": "Plato"}


# --- http_get ----------------------------------------------------------------

class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://x", code, "err", headers or {}, None)


def test_http_get_retries_429_once_with_capped_wait(monkeypatch):
    seq = [http_error(429, {"Retry-After": "120"}), Resp(b"ok")]
    waits = []

    def fake_urlopen(req, timeout):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(cite, "urlopen", fake_urlopen)
    monkeypatch.setattr(cite, "sleep", waits.append)
    assert cite.http_get("https://api.crossref.org/works/x") == b"ok"
    assert waits == [10]


def test_http_get_second_429_fails(monkeypatch):
    def fake_urlopen(req, timeout):
        raise http_error(429, {"Retry-After": "1"})

    monkeypatch.setattr(cite, "urlopen", fake_urlopen)
    monkeypatch.setattr(cite, "sleep", lambda s: None)
    with pytest.raises(cite.LookupFailed, match="429"):
        cite.http_get("https://api.crossref.org/works/x")


def test_http_get_404_is_not_found(monkeypatch):
    def fake_urlopen(req, timeout):
        raise http_error(404)

    monkeypatch.setattr(cite, "urlopen", fake_urlopen)
    with pytest.raises(cite.LookupFailed, match="not found"):
        cite.http_get("https://api.crossref.org/works/x")


def test_user_agent_mailto_only_when_env_set(monkeypatch):
    monkeypatch.delenv("CITE_MAILTO", raising=False)
    assert "mailto" not in cite.user_agent()
    monkeypatch.setenv("CITE_MAILTO", "me@example.org")
    assert cite.user_agent().endswith("mailto:me@example.org")


# --- Crossref ------------------------------------------------------------------

def test_crossref_record_fields_from_published_print(net):
    net.routes["api.crossref.org/works/10.1016/j.cad.2022.103435"] = fixture("crossref_cad.json")
    r = cite.crossref("https://doi.org/" + CAD)
    assert r.title.startswith("Constrained Form-Finding of Tension")
    assert r.authors[0] == {"given": "Rafael", "family": "Pastrana"}
    assert len(r.authors) == 5
    assert (r.venue, r.volume, r.pages, r.year) == ("Computer-Aided Design", "155", "103435", 2023)
    assert r.doi == CAD and r.source == "crossref"


def test_crossref_not_found_raises(net):
    with pytest.raises(cite.LookupFailed, match="not found"):
        cite.crossref("10.9999/nope")


# --- arXiv ---------------------------------------------------------------------

@pytest.mark.parametrize("given", ["2307.12407", "2307.12407v2", "arXiv:2307.12407",
                                   "https://arxiv.org/abs/2307.12407v1"])
def test_arxiv_parses_entry(net, given):
    net.routes["export.arxiv.org/api/query?id_list=2307.12407"] = fixture("arxiv_jaxfdm.xml")
    r = cite.arxiv(given)
    assert r.title == "JAX FDM: A differentiable solver for inverse form-finding"
    assert [a["family"] for a in r.authors] == ["Pastrana", "Oktay", "Adams", "Adriaenssens"]
    assert r.year == 2023 and r.arxiv == "2307.12407" and r.doi == ""
    assert r.venue.startswith("40th International Conference on Machine Learning")
    assert cite.link(r) == "https://arxiv.org/abs/2307.12407"


def test_arxiv_empty_feed_is_not_found(net):
    net.routes["id_list=2999.99999"] = fixture("arxiv_empty.xml")
    with pytest.raises(cite.LookupFailed, match="not found"):
        cite.arxiv("2999.99999")


def test_arxiv_rejects_non_id():
    with pytest.raises(cite.LookupFailed, match="not an arXiv ID"):
        cite.arxiv("JAX FDM")


def test_crossref_routes_arxiv_doi_to_arxiv(net):
    net.routes["id_list=2307.12407"] = fixture("arxiv_jaxfdm.xml")
    r = cite.crossref("10.48550/arXiv.2307.12407")
    assert r.source == "arxiv" and r.arxiv == "2307.12407"
