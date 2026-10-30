import dataclasses
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import cite  # noqa: E402
import grade  # noqa: E402

CAD = cite.Record(authors=[{"given": "Rafael", "family": "Pastrana"}],
                  title="Constrained Form-Finding of Tension–Compression Structures using Automatic Differentiation",
                  year=2023, venue="Computer-Aided Design", volume="155", doi="10.1016/j.cad.2022.103435")


def good(**kw):
    c = {"text": "", "first_author": "Pastrana", "title": CAD.title, "venue": "Computer-Aided Design",
         "year": 2023, "link": "https://doi.org/10.1016/j.cad.2022.103435", "marked_unverified": False}
    c.update(kw)
    return c


def patch(monkeypatch, record=CAD, fail=False):
    def lookup(_):
        if fail:
            raise cite.LookupFailed("not found")
        return record
    monkeypatch.setattr(cite, "crossref", lookup)
    monkeypatch.setattr(cite, "arxiv", lookup)


def test_ok(monkeypatch):
    patch(monkeypatch)
    assert grade.check(good()) == "ok"


def test_merged_citation_flags_venue(monkeypatch):
    patch(monkeypatch)
    assert grade.check(good(venue="Automation in Construction")) == "wrong:venue"


def test_wrong_year_and_author(monkeypatch):
    patch(monkeypatch)
    assert grade.check(good(year=2022, first_author="Oktay")) == "wrong:first_author,year"


def test_no_link_and_marked_unverified():
    assert grade.check(good(link="")) == "no-link"
    assert grade.check(good(link="", marked_unverified=True)) == "marked-unverified"


def test_bad_link(monkeypatch):
    patch(monkeypatch, fail=True)
    assert grade.check(good()) == "bad-link"


def test_non_doi_link_is_unchecked():
    assert grade.check(good(link="https://www.iso.org/standard/12345.html")) == "unchecked"


def test_arxiv_link_routes_to_arxiv(monkeypatch):
    seen = []
    monkeypatch.setattr(cite, "arxiv", lambda i: seen.append(i) or CAD)
    grade.check(good(link="https://arxiv.org/abs/2307.12407v2"))
    assert seen == ["2307.12407v2"]


@pytest.mark.parametrize("written, recorded, verdict", [
    ("Journal of the Royal Statistical Society: Series B 63(3), 425–464",
     "Journal of the Royal Statistical Society Series B: Statistical Methodology", "ok"),
    ("Computers & Graphics 47, 145–164", "Computers & Graphics", "ok"),
    ("ICML 2023 Workshop Differentiable Almost Everything",
     "40th International Conference on Machine Learning (2023: Differentiable Almost Everything Workshop", "ok"),
    ("Automation in Construction", "Computer-Aided Design", "wrong:venue"),
])
def test_venue_word_containment(monkeypatch, written, recorded, verdict):
    patch(monkeypatch, record=dataclasses.replace(CAD, venue=recorded))
    assert grade.check(good(venue=written)) == verdict


@pytest.mark.parametrize("link, expected", [
    ("arXiv:2307.12407", "2307.12407"),
    ("arXiv 2307.12407v2", "2307.12407v2"),
    ("https://arxiv.org/html/2307.12407", "2307.12407"),
    ("https://ar5iv.labs.arxiv.org/html/2307.12407", "2307.12407"),
    ("https://arxiv.org/pdf/2307.12407v2.pdf", "2307.12407v2"),
])
def test_arxiv_link_forms(monkeypatch, link, expected):
    seen = []
    monkeypatch.setattr(cite, "arxiv", lambda i: seen.append(i) or CAD)
    grade.check(good(link=link))
    assert seen == [expected]


@pytest.mark.parametrize("written, recorded", [
    ("Journal of Mechanics", "Journal of the Mechanics and Physics of Solids"),
    ("Graphics", "Computers & Graphics"),
])
def test_venue_near_miss_rejected(monkeypatch, written, recorded):
    patch(monkeypatch, record=dataclasses.replace(CAD, venue=recorded))
    assert grade.check(good(venue=written)) == "wrong:venue"


def test_venue_equal_short_form_passes(monkeypatch):
    patch(monkeypatch, record=dataclasses.replace(CAD, venue="Structures"))
    assert grade.check(good(venue="Structures")) == "ok"
