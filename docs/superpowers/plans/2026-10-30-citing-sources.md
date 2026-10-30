# Citing Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `citing-sources` skill plus an always-on CLAUDE.md rule that make the agent look up every citation before writing it, copy every field and the link from the record, and surface same-author siblings that cause merges.

**Architecture:** One stdlib CLI, `scripts/cite.py`, with three subcommands (`doi`, `arxiv`, `find`) over Crossref, the arXiv API and OpenAlex; all network goes through one `http_get` so tests swap it for a fixture router. `SKILL.md` carries the procedure; a 4-line rule in `~/.claude/CLAUDE.md` is the trigger. Evals compare six merge-tempting prompts before and after the gate is installed.

**Tech Stack:** Python 3.10+ stdlib (`urllib`, `json`, `xml.etree`, `dataclasses`), pytest. Spec: `docs/superpowers/specs/2026-10-30-citing-sources-design.md`.

## Global Constraints

- Python standard library only in `cite.py` and `grade.py`; pytest for tests.
- No email or API key is sent unless the user set `CITE_MAILTO` / `OPENALEX_API_KEY`. The agent never sets them. `User-Agent`: `citing-sources/1.0 (+https://github.com/daniel-locatelli/skills)`.
- Link precedence: `https://doi.org/<doi>` > `https://arxiv.org/abs/<id>` > page fetched.
- Citation fields come from Crossref (or arXiv); OpenAlex is used only to find siblings.
- Siblings: first author's works within year ±1, at most 5 shown (`--all` shows every one), ranked by title-word overlap; count is always the full number.
- `429` retried once after `Retry-After`, capped at 10 s. Failure: exit 1, `lookup failed: <reason>` on stderr.
- Every `SKILL.md`/README claim about a paper in this skill obeys the skill: linked, from a record.
- Run tests from the repo root: `python -m pytest skills/research/citing-sources/tests -v`.
- Commit trailer on every commit: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do not stage `skills/git/preparing-pull-request/SKILL.md` (unrelated, uncommitted user change).
- **Order matters:** the eval baseline (Task 6) runs **before** the skill is linked into `~/.claude/skills` and before the CLAUDE.md rule exists (Task 7).

## File map

```
skills/research/README.md                          bucket README
skills/research/citing-sources/
  SKILL.md                                         trigger, lookup order, format, red flags
  scripts/cite.py                                  CLI + library: doi, arxiv, find
  tests/conftest.py                                fixture router, `live` marker
  tests/fixtures/                                  recorded Crossref / arXiv / OpenAlex responses
  tests/test_cite.py                               offline unit tests
  tests/test_live.py                               live smoke test (CITE_LIVE=1)
  evals/prompts.json                               the six eval prompts
  evals/grade.py                                   checks extracted citations against records
  evals/test_grade.py                              grade.py tests
  evals/runs/<arm>/<id>-<n>.md                     raw answers (arm = baseline | gate)
  evals/results/2026-10-30-<arm>.md                graded tables
.claude-plugin/plugin.json, marketplace.json       register skill, version 1.11.0
README.md, CHANGELOG.md                            listing + entry
outside this repo:
  ~/.claude/CLAUDE.md                              4-line Citations rule
  skills-private: skills/personal/system/standards/ai-harness.md   full rule (source of truth)
  ~/.claude/skills/citing-sources                  junction → this repo's skill folder
```

---

### Task 1: Fixtures, `Record`, link and formatting, `http_get`, Crossref

**Files:**
- Create: `skills/research/citing-sources/scripts/cite.py`
- Create: `skills/research/citing-sources/tests/conftest.py`
- Create: `skills/research/citing-sources/tests/test_cite.py`
- Create: `skills/research/citing-sources/tests/fixtures/*` (recorded in Step 1)

**Interfaces:**
- Produces: `LookupFailed(Exception)`; `Record` dataclass (`authors: list[dict]` with keys `given`, `family`; `title: str`; `year: int | None`; `venue`, `volume`, `pages`, `doi`, `arxiv`, `url`, `source: str`); `link(r) -> str`; `short(r) -> str`; `full(r) -> str`; `http_get(url) -> bytes`; `crossref(doi) -> Record`; `normalize_doi(s) -> str`; `split_name(name) -> dict`. Module-level `urlopen` and `sleep` (patch points).
- Test fixture `net` (in conftest): `net.routes[<url substring>] = bytes | Exception`; `net.calls` list of URLs.

- [ ] **Step 1: Record live fixtures** (real responses, not hand-written)

```bash
cd skills/research/citing-sources && mkdir -p tests/fixtures && cd tests/fixtures
UA="citing-sources/1.0 (+https://github.com/daniel-locatelli/skills)"
curl -sf -A "$UA" https://api.crossref.org/works/10.1016/j.cad.2022.103435 -o crossref_cad.json
curl -sf -A "$UA" "https://export.arxiv.org/api/query?id_list=2307.12407" -o arxiv_jaxfdm.xml
curl -sf -A "$UA" "https://export.arxiv.org/api/query?id_list=2999.99999" -o arxiv_empty.xml
curl -sf -A "$UA" "https://api.openalex.org/works/doi:10.1016/j.cad.2022.103435?select=authorships" -o openalex_work_cad.json
curl -sf -A "$UA" "https://api.openalex.org/works/doi:10.48550/arXiv.2307.12407?select=authorships" -o openalex_work_jaxfdm.json
curl -sf -A "$UA" "https://api.openalex.org/works?filter=authorships.author.id:A5073512746,publication_year:2022-2024&select=id,doi,display_name,publication_year,primary_location,authorships&per-page=200" -o openalex_works_pastrana.json
curl -sf -A "$UA" "https://api.openalex.org/authors?search=Rafael%20Pastrana&select=id,display_name,works_count" -o openalex_authors_pastrana.json
ls -la
```

Expected: 7 non-empty files. Check `openalex_works_pastrana.json` lists both `10.1016/j.cad.2022.103435` and `10.48550/arxiv.2307.12407` (it did on 2026-10-30, 5 works). If the author ID changed, look it up in `openalex_work_cad.json` → `authorships[0].author.id` and re-run that curl.

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import cite  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real APIs; run with CITE_LIVE=1")


def fixture(name: str) -> bytes:
    return (HERE / "fixtures" / name).read_bytes()


@pytest.fixture
def net(monkeypatch):
    """Replace cite.http_get with a router: first route whose key is a substring of the URL wins."""
    def fake(url):
        fake.calls.append(url)
        for frag, payload in fake.routes.items():
            if frag in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise cite.LookupFailed("not found")
    fake.routes, fake.calls = {}, []
    monkeypatch.setattr(cite, "http_get", fake)
    monkeypatch.delenv("CITE_MAILTO", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    return fake
```

- [ ] **Step 3: Write the failing tests** — `tests/test_cite.py`

```python
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
```

- [ ] **Step 4: Run to see them fail**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: collection error / FAIL — `ModuleNotFoundError: No module named 'cite'`.

- [ ] **Step 5: Write `scripts/cite.py` (first part)**

```python
#!/usr/bin/env python3
"""Look up a citation in Crossref, arXiv or OpenAlex and print the record.

Every field and the link come from the record, never from memory. After a
doi/arxiv lookup the first author's other works within +-1 year are listed
(SIBLINGS): same-author, same-year papers are the ones that get merged.

  cite.py doi <doi> [--all]
  cite.py arxiv <id> [--all]
  cite.py find "<author>" <year> [keyword ...] [--all]

Exit 0 with JSON on stdout; exit 1 with "lookup failed: <reason>" on stderr.
Optional env, set by the user only: CITE_MAILTO (polite pool), OPENALEX_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from time import sleep
from urllib.request import urlopen

UA = "citing-sources/1.0 (+https://github.com/daniel-locatelli/skills)"
RETRY_CAP_S = 10
SIBLINGS_SHOWN = 5


class LookupFailed(Exception):
    pass


@dataclass
class Record:
    authors: list[dict]   # [{"given": ..., "family": ...}] in source order
    title: str
    year: int | None
    venue: str = ""
    volume: str = ""
    pages: str = ""
    doi: str = ""
    arxiv: str = ""
    url: str = ""
    source: str = ""      # crossref | arxiv | openalex


# --- formatting ----------------------------------------------------------------

def link(r: Record) -> str:
    if r.doi:
        return f"https://doi.org/{r.doi}"
    if r.arxiv:
        return f"https://arxiv.org/abs/{r.arxiv}"
    return r.url


def short(r: Record) -> str:
    fam = [a["family"] for a in r.authors]
    who = fam[0] if len(fam) == 1 else f"{fam[0]} & {fam[1]}" if len(fam) == 2 else f"{fam[0]} et al."
    return f"{who} ({r.year})"


def initials(given: str) -> str:
    return " ".join(p[0] + "." for p in given.replace("-", " ").split())


def full(r: Record) -> str:
    names = [f"{a['family']}, {initials(a['given'])}".rstrip(", ") for a in r.authors]
    who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]
    venue = r.venue + (f" {r.volume}" if r.volume else "") + (f", {r.pages}" if r.pages else "")
    return f"{who} ({r.year}). {r.title}. " + (f"{venue}. " if r.venue else "") + link(r)


def normalize_doi(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", s, flags=re.I)
    return s


def split_name(name: str) -> dict:
    given, _, family = name.strip().rpartition(" ")
    return {"given": given, "family": family}


# --- network -----------------------------------------------------------------

def user_agent() -> str:
    mail = os.environ.get("CITE_MAILTO")
    return f"{UA} mailto:{mail}" if mail else UA


def retry_after(value) -> float:
    try:
        return min(max(float(value), 0), RETRY_CAP_S)
    except (TypeError, ValueError):
        return RETRY_CAP_S


def http_get(url: str) -> bytes:
    host = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    for attempt in (0, 1):
        try:
            with urlopen(req, timeout=20) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                sleep(retry_after(e.headers.get("Retry-After")))
                continue
            if e.code == 404:
                raise LookupFailed("not found") from None
            raise LookupFailed(f"HTTP {e.code} from {host}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise LookupFailed(f"network error: {getattr(e, 'reason', e)}") from None
    raise LookupFailed(f"HTTP 429 from {host} (rate limited)")


# --- Crossref ------------------------------------------------------------------

def first(xs) -> str:
    return xs[0] if xs else ""


def crossref(doi: str) -> Record:
    doi = normalize_doi(doi)
    if doi.lower().startswith("10.48550/arxiv."):
        return arxiv(doi.split(".", 2)[2])
    m = json.loads(http_get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")))["message"]
    date = m.get("published-print") or m.get("published") or m.get("issued") or {}
    year = (date.get("date-parts") or [[None]])[0][0]
    return Record(
        authors=[{"given": a.get("given", ""), "family": a.get("family") or a.get("name", "")}
                 for a in m.get("author", [])],
        title=" ".join(first(m.get("title")).split()),
        year=year,
        venue=first(m.get("container-title")),
        volume=m.get("volume", ""),
        pages=m.get("page") or m.get("article-number", ""),
        doi=m["DOI"],
        url=m.get("URL", ""),
        source="crossref",
    )


def arxiv(arxiv_id: str) -> Record:  # implemented in Task 2
    raise LookupFailed("arXiv lookup not implemented yet")
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: all 11 PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/research/citing-sources/scripts/cite.py skills/research/citing-sources/tests
git commit -m "feat(research): cite.py - record, link, formatting, http_get with 429 retry, Crossref lookup

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: arXiv lookup

**Files:**
- Modify: `skills/research/citing-sources/scripts/cite.py` (replace the `arxiv` stub)
- Test: `skills/research/citing-sources/tests/test_cite.py` (append)

**Interfaces:**
- Consumes: `Record`, `http_get`, `split_name`, `LookupFailed` (Task 1).
- Produces: `arxiv(arxiv_id: str) -> Record` — accepts `2307.12407`, `2307.12407v2`, `arXiv:2307.12407`, `https://arxiv.org/abs/2307.12407`, old-style `hep-th/9901001`. `venue` = `journal_ref` if arXiv lists one, else `"arXiv"`; `doi` = arXiv's `<arxiv:doi>` (journal DOI) if listed.

- [ ] **Step 1: Append failing tests**

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest skills/research/citing-sources/tests -v -k arxiv`
Expected: FAIL — `LookupFailed: arXiv lookup not implemented yet`.

- [ ] **Step 3: Replace the stub in `cite.py`**

```python
# --- arXiv ---------------------------------------------------------------------

ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.I)


def arxiv(arxiv_id: str) -> Record:
    m = ARXIV_ID.search(arxiv_id)
    if not m:
        raise LookupFailed(f"not an arXiv ID: {arxiv_id}")
    base = m.group(1)
    feed = ET.fromstring(http_get("https://export.arxiv.org/api/query?id_list=" + base))
    entries = feed.findall("a:entry", ATOM)
    if not entries or entries[0].findtext("a:title", "", ATOM).strip() == "Error":
        raise LookupFailed("not found")
    e = entries[0]
    return Record(
        authors=[split_name(a.findtext("a:name", "", ATOM)) for a in e.findall("a:author", ATOM)],
        title=" ".join(e.findtext("a:title", "", ATOM).split()),
        year=int(e.findtext("a:published", "", ATOM)[:4]),
        venue=" ".join((e.findtext("arxiv:journal_ref", "", ATOM) or "arXiv").split()),
        doi=(e.findtext("arxiv:doi", "", ATOM) or "").strip(),
        arxiv=base,
        url=f"https://arxiv.org/abs/{base}",
        source="arxiv",
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: all 18 PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/research/citing-sources/scripts/cite.py skills/research/citing-sources/tests/test_cite.py
git commit -m "feat(research): cite.py arXiv lookup, arXiv DOIs routed to it

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: OpenAlex siblings, `find`, and the CLI

**Files:**
- Modify: `skills/research/citing-sources/scripts/cite.py` (append)
- Test: `skills/research/citing-sources/tests/test_cite.py` (append)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `openalex(path: str, **params) -> dict` (adds `mailto`/`api_key` from env)
  - `from_openalex(work: dict) -> Record`
  - `works_by(author_id: str, year: int) -> list[Record]`
  - `siblings(r: Record, show_all=False) -> dict` with keys `count: int | None`, `shown: list[dict]`, `note: str`
  - `find(author: str, year: int, keywords: list[str], show_all=False) -> list[dict]`
  - `result(r: Record, show_all=False) -> dict` with keys `record`, `link`, `citation`, `short`, `siblings`
  - `main(argv: list[str] | None = None) -> int`
  - Each `shown`/`works` entry: `{"title": str, "citation": str, "link": str, "year": int | None}`

- [ ] **Step 1: Append failing tests**

```python
# --- OpenAlex siblings and find --------------------------------------------------

def pastrana_routes(net):
    net.routes["api.crossref.org/works/10.1016/j.cad.2022.103435"] = fixture("crossref_cad.json")
    net.routes["works/doi:10.1016/j.cad.2022.103435"] = fixture("openalex_work_cad.json")
    net.routes["works/doi:10.48550/arXiv.2307.12407"] = fixture("openalex_work_jaxfdm.json")
    net.routes["filter=authorships.author.id"] = fixture("openalex_works_pastrana.json")
    net.routes["id_list=2307.12407"] = fixture("arxiv_jaxfdm.xml")
    net.routes["api.openalex.org/authors"] = fixture("openalex_authors_pastrana.json")


def test_siblings_of_cad_paper_include_jax_fdm_not_itself(net):
    pastrana_routes(net)
    s = cite.siblings(cite.crossref(CAD))
    links = [w["link"] for w in s["shown"]]
    assert "https://arxiv.org/abs/2307.12407" in links
    assert "https://doi.org/10.1016/j.cad.2022.103435" not in links
    assert s["note"].startswith(f"SIBLINGS: {s['count']} other works by Pastrana in 2022-2024")


def test_siblings_of_jax_fdm_include_cad_paper(net):
    pastrana_routes(net)
    s = cite.siblings(cite.arxiv("2307.12407"))
    assert "https://doi.org/10.1016/j.cad.2022.103435" in [w["link"] for w in s["shown"]]


def test_siblings_capped_at_five_count_is_full(net):
    pastrana_routes(net)
    works = json.loads(fixture("openalex_works_pastrana.json"))
    n = len(works["results"])                        # includes the CAD paper itself once
    works["results"] = works["results"] * 3
    net.routes["filter=authorships.author.id"] = json.dumps(works).encode()
    s = cite.siblings(cite.crossref(CAD))
    assert len(s["shown"]) == 5 and s["count"] == 3 * (n - 1)
    assert len(cite.siblings(cite.crossref(CAD), show_all=True)["shown"]) == 3 * (n - 1)


def test_siblings_ranked_by_title_overlap(net):
    pastrana_routes(net)
    r = cite.crossref(CAD)
    s = cite.siblings(r, show_all=True)
    scores = [cite.overlap(w["title"], r.title) for w in s["shown"]]
    assert scores == sorted(scores, reverse=True)


def test_sibling_failure_does_not_fail_lookup(net):
    pastrana_routes(net)
    net.routes = {k: v for k, v in net.routes.items() if "openalex" not in k}
    s = cite.siblings(cite.crossref(CAD))
    assert s["count"] is None and "check failed" in s["note"]


def test_openalex_params_from_env_only(net, monkeypatch):
    net.routes["api.openalex.org/authors"] = fixture("openalex_authors_pastrana.json")
    cite.openalex("authors", search="x")
    assert "mailto" not in net.calls[-1] and "api_key" not in net.calls[-1]
    monkeypatch.setenv("CITE_MAILTO", "me@example.org")
    monkeypatch.setenv("OPENALEX_API_KEY", "k123")
    cite.openalex("authors", search="x")
    assert "mailto=me%40example.org" in net.calls[-1] and "api_key=k123" in net.calls[-1]


def test_find_groups_by_candidate_author_and_ranks_by_keywords(net):
    pastrana_routes(net)
    out = cite.find("Rafael Pastrana", 2023, ["JAX", "FDM", "differentiable"])
    assert out[0]["author"] == "Rafael Pastrana"
    assert out[0]["works"][0]["link"] == "https://arxiv.org/abs/2307.12407"
    assert len(out) <= 3


# --- CLI -------------------------------------------------------------------------

def test_main_doi_prints_json(net, capsys):
    pastrana_routes(net)
    assert cite.main(["doi", CAD]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["link"] == "https://doi.org/10.1016/j.cad.2022.103435"
    assert out["short"] == "Pastrana et al. (2023)"
    assert out["siblings"]["note"].startswith("SIBLINGS:")


def test_main_failure_exit_1_and_stderr(net, capsys):
    assert cite.main(["doi", "10.9999/nope"]) == 1
    assert capsys.readouterr().err.strip() == "lookup failed: not found"
```

- [ ] **Step 2: Run to see them fail**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: new tests FAIL with `AttributeError: module 'cite' has no attribute 'siblings'` (and similar).

- [ ] **Step 3: Append to `cite.py`**

```python
# --- OpenAlex (siblings only; never the source of a citation's fields) -----------

WORK_FIELDS = "id,doi,display_name,publication_year,primary_location,authorships"
STOP = {"using", "with", "from", "based", "towards", "toward", "their", "this", "that", "into", "for", "and", "the"}


def openalex(path: str, **params) -> dict:
    if os.environ.get("CITE_MAILTO"):
        params["mailto"] = os.environ["CITE_MAILTO"]
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    query = "?" + urllib.parse.urlencode(params) if params else ""
    return json.loads(http_get(f"https://api.openalex.org/{path}{query}"))


def from_openalex(w: dict) -> Record:
    doi = re.sub(r"^https://doi\.org/", "", w.get("doi") or "")
    arx = ""
    if doi.lower().startswith("10.48550/arxiv."):
        arx, doi = doi.split(".", 2)[2], ""
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    return Record(
        authors=[split_name(a["author"]["display_name"]) for a in w.get("authorships", [])],
        title=w.get("display_name") or "",
        year=w.get("publication_year"),
        venue=source,
        doi=doi,
        arxiv=arx,
        url=w.get("id", ""),
        source="openalex",
    )


def works_by(author_id: str, year: int) -> list[Record]:
    d = openalex("works", filter=f"authorships.author.id:{author_id},publication_year:{year - 1}-{year + 1}",
                 select=WORK_FIELDS, **{"per-page": 200})
    return [from_openalex(w) for w in d["results"]]


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", s.lower())) - STOP


def overlap(title: str, query: str) -> int:
    return len(words(title) & words(query))


def same_work(a: Record, b: Record) -> bool:
    if a.doi and b.doi:
        return a.doi.lower() == b.doi.lower()
    if a.arxiv and b.arxiv:
        return a.arxiv == b.arxiv
    return " ".join(sorted(words(a.title))) == " ".join(sorted(words(b.title)))


def summary(r: Record) -> dict:
    return {"title": r.title, "citation": full(r), "link": link(r), "year": r.year}


def siblings(r: Record, show_all: bool = False) -> dict:
    if r.year is None or not r.authors:
        return {"count": None, "shown": [], "note": "SIBLINGS: skipped (record has no year or authors)"}
    name = r.authors[0]["family"]
    key = f"doi:{r.doi}" if r.doi else f"doi:10.48550/arXiv.{r.arxiv}"
    try:
        auths = openalex(f"works/{key}", select="authorships").get("authorships") or []
        if not auths:
            raise LookupFailed("OpenAlex lists no authors")
        others = [w for w in works_by(auths[0]["author"]["id"].rsplit("/", 1)[-1], r.year) if not same_work(w, r)]
    except LookupFailed as e:
        return {"count": None, "shown": [],
                "note": f"SIBLINGS: check failed ({e}); run `cite.py find \"{name}\" {r.year}` before citing"}
    others.sort(key=lambda w: -overlap(w.title, r.title))
    shown = others if show_all else others[:SIBLINGS_SHOWN]
    return {"count": len(others), "shown": [summary(w) for w in shown],
            "note": f"SIBLINGS: {len(others)} other works by {name} in {r.year - 1}-{r.year + 1}"
                    + ("" if show_all or len(others) <= SIBLINGS_SHOWN else f", showing {SIBLINGS_SHOWN} (--all for every one)")}


def find(author: str, year: int, keywords: list[str], show_all: bool = False) -> list[dict]:
    candidates = openalex("authors", search=author, select="id,display_name,works_count")["results"][:3]
    if not candidates:
        raise LookupFailed(f"no OpenAlex author matches {author!r}")
    query = " ".join(keywords)
    out = []
    for a in candidates:
        works = works_by(a["id"].rsplit("/", 1)[-1], year)
        works.sort(key=lambda w: -overlap(w.title, query))
        out.append({"author": a["display_name"], "openalex": a["id"], "count": len(works),
                    "works": [summary(w) for w in (works if show_all else works[:SIBLINGS_SHOWN])]})
    return out


# --- CLI ---------------------------------------------------------------------------

def result(r: Record, show_all: bool = False) -> dict:
    return {"record": asdict(r), "link": link(r), "citation": full(r), "short": short(r),
            "siblings": siblings(r, show_all)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cite.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("doi", "arxiv"):
        s = sub.add_parser(cmd)
        s.add_argument("id")
        s.add_argument("--all", action="store_true", help="list every sibling, not just 5")
    f = sub.add_parser("find")
    f.add_argument("author")
    f.add_argument("year", type=int)
    f.add_argument("keywords", nargs="*")
    f.add_argument("--all", action="store_true")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        if a.cmd == "doi":
            out = result(crossref(a.id), a.all)
        elif a.cmd == "arxiv":
            out = result(arxiv(a.id), a.all)
        else:
            out = find(a.author, a.year, a.keywords, a.all)
    except LookupFailed as e:
        print(f"lookup failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: all 27 PASS. If `test_find_groups_by_candidate_author_and_ranks_by_keywords` fails because the recorded authors fixture orders a different "Rafael Pastrana" first, check `openalex_authors_pastrana.json` and assert on the entry whose `openalex` ends in `A5073512746` instead of `out[0]`.

- [ ] **Step 5: Commit**

```bash
git add skills/research/citing-sources/scripts/cite.py skills/research/citing-sources/tests/test_cite.py
git commit -m "feat(research): cite.py OpenAlex siblings, find, CLI

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Live smoke test

**Files:**
- Create: `skills/research/citing-sources/tests/test_live.py`

**Interfaces:**
- Consumes: `crossref`, `arxiv`, `siblings`, `link` (Tasks 1–3).

- [ ] **Step 1: Write the test**

```python
import os

import pytest

import cite

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("CITE_LIVE") != "1", reason="set CITE_LIVE=1 to hit the real APIs")]


def test_pastrana_papers_are_each_others_siblings():
    cad = cite.crossref("10.1016/j.cad.2022.103435")
    assert (cad.venue, cad.year) == ("Computer-Aided Design", 2023)
    jax = cite.arxiv("2307.12407")
    assert jax.title.startswith("JAX FDM")
    assert "https://arxiv.org/abs/2307.12407" in [w["link"] for w in cite.siblings(cad, show_all=True)["shown"]]
    assert "https://doi.org/10.1016/j.cad.2022.103435" in [w["link"] for w in cite.siblings(jax, show_all=True)["shown"]]
```

- [ ] **Step 2: Run offline (skipped) and live**

Run: `python -m pytest skills/research/citing-sources/tests -v`
Expected: 27 passed, 1 skipped.

Run: `CITE_LIVE=1 python -m pytest skills/research/citing-sources/tests/test_live.py -v`
Expected: 1 passed. If it fails on a changed upstream record, report the diff; do not loosen the assertion without asking.

- [ ] **Step 3: Run the CLI by hand once**

Run: `python skills/research/citing-sources/scripts/cite.py doi 10.1016/j.cad.2022.103435`
Expected: JSON with `"short": "Pastrana et al. (2023)"`, `"link": "https://doi.org/10.1016/j.cad.2022.103435"`, and a `siblings.note` starting `SIBLINGS:` whose `shown` includes JAX FDM.

- [ ] **Step 4: Commit**

```bash
git add skills/research/citing-sources/tests/test_live.py
git commit -m "test(research): live smoke test - Pastrana papers list each other as siblings

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `SKILL.md`, bucket README, registration

**Files:**
- Create: `skills/research/citing-sources/SKILL.md`
- Create: `skills/research/README.md`
- Modify: `.claude-plugin/plugin.json` (skills list, description, version `1.11.0`)
- Modify: `.claude-plugin/marketplace.json` (version `1.11.0`, description mentions citation verification)
- Modify: `README.md` (new `### Research` listing after `### BIM`; tree entry)
- Modify: `CHANGELOG.md` (new `## 1.11.0 — <date>` entry on top)

**Interfaces:**
- Consumes: the CLI from Task 3 (`cite.py doi|arxiv|find`, JSON keys `link`, `citation`, `short`, `siblings.note`).

- [ ] **Step 1: Write `SKILL.md`**

````markdown
---
name: citing-sources
description: Use before writing any citation — a paper, "Author et al. (year)", DOI, arXiv ID, venue, book or standard — into an answer, list, code comment, docstring or document, in any task, including a passing mention in casual chat. Looks the work up first (Zotero, librarian, Crossref, arXiv, OpenAlex, web), copies every field and the link from the record, and lists same-author papers that get merged.
---

# Citing sources

A citation written from memory is wrong more often than not: about half of
LLM-generated references are fabricated, and most of the rest carry a wrong
field — year, venue, DOI. The typical failure is not an invented paper but
two real papers by the same author, same year, **merged** into one. So:
**look up before writing, copy every field from the record, link every
citation.**

## The rule

1. Before a citation goes into any output, look it up (order below).
2. Copy authors, title, venue, volume, year and link **from the record**.
   Never fill a field from recall — especially venue, year and DOI.
3. Every citation carries a link: `https://doi.org/<doi>`, else
   `https://arxiv.org/abs/<id>`, else the canonical page you fetched.
4. Read the `SIBLINGS` note. If the author has other works near that year,
   check you have the one you mean; when two are close, name it by DOI.
5. Lookup failed everywhere → drop the citation, or write it as
   *(unverified, not found)* with no link. Never an unmarked citation.

## Lookup order

1. **Zotero / librarian**, if installed on this machine:
   `zot.py doi <doi>` (using-zotero), `bib doi <doi>` / `bib search`
   (searching-librarian). A hit gives the DOI; still run step 2 for fields.
2. **`cite.py`** (Python 3.10+, stdlib):

       python <skillRoot>/scripts/cite.py doi <doi>
       python <skillRoot>/scripts/cite.py arxiv <id>
       python <skillRoot>/scripts/cite.py find "<author>" <year> [keywords...]

   JSON out: `citation` (full reference with link), `short`
   (`Pastrana et al. (2023)`), `link`, `record` (every field), `siblings`.
   `--all` lists every sibling. Exit 1 + `lookup failed: <reason>` on stderr.
   No DOI or arXiv ID in hand → `find` first, then `doi` on the hit.
3. **Web search** — the primary lookup for works with no DOI or arXiv ID:
   books without a DOI, standards (ISO, EN, IEEE), RFCs, technical reports,
   software docs. Link the canonical page you fetched (publisher, standards
   body, rfc-editor.org), not a search result or a mirror.

## Format

- Prose: `Pastrana et al. (2023, [CAD 155](https://doi.org/10.1016/j.cad.2022.103435))`
  — `short` plus a linked venue tag.
- Lists, bibliographies, docstrings: the `citation` string as printed.
- Do not add a "verified" mark; the working link is the evidence.

## SIBLINGS

`SIBLINGS: n other works by <author> in <y-1>-<y+1>` with up to 5 ranked by
title overlap. Example: looking up the CAD form-finding paper by Pastrana
lists *JAX FDM* (arXiv 2307.12407) — the pair that was once merged into a
nonexistent "JAX FDM, *Automation in Construction* 2023". If the note says
`check failed`, run the `find` it suggests before citing.

## Optional environment (user-set only)

`CITE_MAILTO` (Crossref/OpenAlex polite pool) and `OPENALEX_API_KEY`
(OpenAlex gives keyless requests a small budget shared per IP). Never set
them yourself; without them the script works at the public rate.

## Red flags

| Thought | Reality |
|---|---|
| "I'm sure of this one" | The merged Pastrana citation felt certain too. Look it up. |
| "It's only a passing mention" | Passing mentions are where it slipped through. Same rule. |
| "The venue is obviously X" | Venue and year are the fields most often wrong. From the record. |
| "The DOI looks right" | DOIs from memory are right ~1 time in 5. Resolve it. |
| "I'll add the link later" | No link, no citation. |
| "Lookup failed, but I know it exists" | Then write *(unverified, not found)*. |
| "It's in a code comment, not prose" | Same rule. |
````

- [ ] **Step 2: Verify the two claims SKILL.md makes from the literature**

The intro's "about half … fabricated" and the red-flag "~1 time in 5" come from the spec's Evidence section (Walters & Wilder 2023; Bhattacharyya et al. 2023; Chelli et al. 2024). Run:

```bash
python skills/research/citing-sources/scripts/cite.py doi 10.1038/s41598-023-41032-5
```

Expected: Walters & Wilder, *Scientific Reports* 13, 2023. Open https://pmc.ncbi.nlm.nih.gov/articles/PMC11153973/ (Chelli) and confirm the DOI-accuracy figure (16–20 %). If either does not hold, soften the sentence to what the source says.

- [ ] **Step 3: Write `skills/research/README.md`**

```markdown
# Research skills

Skills for handling scholarly sources. `citing-sources` gates every citation
the agent writes: look it up (Zotero, librarian, Crossref, arXiv, OpenAlex,
web), copy fields and link from the record, check same-author siblings.
Tests: `python -m pytest skills/research/citing-sources/tests -v`
(`CITE_LIVE=1` adds the live smoke test).
```

- [ ] **Step 4: Register**

`.claude-plugin/plugin.json`: append `"./skills/research/citing-sources"` to `skills`; set `"version": "1.11.0"`; append `, citation verification against Crossref/arXiv/OpenAlex` before the final period of `description`.

`.claude-plugin/marketplace.json`: plugin `"version": "1.11.0"`; append `, and citation verification` before the final period of the plugin `description`.

`README.md`: after the `### BIM` block add

```markdown
### Research

- **[citing-sources](./skills/research/citing-sources/SKILL.md)** — Look up every citation before writing it, in any task: Zotero and librarian first, then `scripts/cite.py` (stdlib Python) over Crossref, arXiv and OpenAlex, then web search for books, standards and RFCs. Fields and link are copied from the record; every citation is linked. After each lookup the first author's other works within a year are listed, because same-author, same-year papers are the ones that get merged into a citation that does not exist.
```

and in the tree, after the `bim/` lines:

```
  research/
    citing-sources/               SKILL.md + scripts/cite.py (+ pytest recorded fixtures, evals/)
```

`CHANGELOG.md`: insert at the top, below `# Changelog`:

```markdown
## 1.11.0 — <today's date>

New `skills/research/` category with `citing-sources`: a gate on every citation the agent writes, in any task. `scripts/cite.py` (stdlib) looks a work up by DOI, arXiv ID or author + year in Crossref, arXiv and OpenAlex and prints the record, a full citation and a short form, all with links taken from the record. After each lookup it lists the first author's other works within a year (`SIBLINGS`, top 5 by title overlap), the case that once merged two 2023 Pastrana papers into a nonexistent one. Paired with a four-line rule in the global CLAUDE.md, which is what makes it fire in casual answers; evals in `evals/` compare six merge-tempting prompts before and after.
```

- [ ] **Step 5: Check JSON and tests**

Run: `python -c "import json;[json.load(open(f)) for f in ('.claude-plugin/plugin.json','.claude-plugin/marketplace.json')];print('ok')" && python -m pytest skills/research/citing-sources/tests -q`
Expected: `ok`, then `27 passed, 1 skipped`.

- [ ] **Step 6: Commit**

```bash
git add skills/research .claude-plugin README.md CHANGELOG.md
git commit -m "feat(research): citing-sources SKILL.md, research bucket, register in plugin 1.11.0

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Eval harness and baseline run (before the gate is installed)

**Files:**
- Create: `skills/research/citing-sources/evals/prompts.json`
- Create: `skills/research/citing-sources/evals/grade.py`
- Create: `skills/research/citing-sources/evals/test_grade.py`
- Create: `skills/research/citing-sources/evals/runs/baseline/<id>-<n>.md` (18 files)
- Create: `skills/research/citing-sources/evals/results/2026-10-30-baseline.md` (use the run date)

**Interfaces:**
- Consumes: `cite.crossref`, `cite.arxiv`, `cite.LookupFailed`, `cite.words`.
- Produces: `grade.check(c: dict) -> str` (verdicts: `ok`, `marked-unverified`, `no-link`, `bad-link`, `unchecked`, `wrong:<field,...>`); `grade.main(argv) -> int` reading an extraction JSON and printing a markdown table plus totals.
- Extraction JSON format (written by the grader subagent):
  `[{"prompt": 1, "run": 1, "citations": [{"text": "...", "first_author": "Pastrana", "title": "...", "venue": "...", "year": 2023, "link": "https://...", "marked_unverified": false}]}]`

- [ ] **Precondition check**

Run: `ls ~/.claude/skills/citing-sources 2>&1; grep -n "## Citations" ~/.claude/CLAUDE.md`
Expected: `No such file or directory` and no grep match. If either exists, STOP: the baseline would be contaminated.

- [ ] **Step 1: Write `evals/prompts.json`**

```json
[
  {"id": 1, "prompt": "What has Rafael Pastrana published on form-finding with automatic differentiation?", "tempts": "same-author/year merge"},
  {"id": 2, "prompt": "Quick q: is there any prior work on differentiable force density method for gridshells?", "tempts": "inline citation in a casual answer"},
  {"id": 3, "prompt": "Give me 5 key references on planar quad meshes for architectural freeform surfaces.", "tempts": "reference list"},
  {"id": 4, "prompt": "What's the classic reference for Bayesian calibration of computer models?", "tempts": "older paper with no arXiv copy"},
  {"id": 5, "prompt": "Write a short Python force density method solver for a cable net, with a docstring citing the source of the method.", "tempts": "citation in a code comment"},
  {"id": 6, "prompt": "Summarise Pastrana's 2024 Automation in Construction paper on JAX FDM.", "tempts": "nonexistent paper; must say not found and point to the two real ones"}
]
```

- [ ] **Step 2: Write the failing tests** — `evals/test_grade.py`

```python
import sys
from pathlib import Path

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
```

- [ ] **Step 3: Run to see them fail**

Run: `python -m pytest skills/research/citing-sources/evals -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grade'`.

- [ ] **Step 4: Write `evals/grade.py`**

```python
#!/usr/bin/env python3
"""Grade extracted citations against their records.

  grade.py <extraction.json>

Input: [{"prompt": n, "run": k, "citations": [{"text", "first_author", "title",
"venue", "year", "link", "marked_unverified"}]}]. Prints a markdown table and
totals per verdict.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cite  # noqa: E402

DOI = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")
ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?$", re.I)


def norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def similar(a: str, b: str, cut: float) -> bool:
    a, b = norm(a), norm(b)
    return a == b or a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= cut


def check(c: dict) -> str:
    link = (c.get("link") or "").strip()
    if not link:
        return "marked-unverified" if c.get("marked_unverified") else "no-link"
    m_arx, m_doi = ARXIV.search(link), DOI.search(link)
    try:
        if m_arx:
            r = cite.arxiv(m_arx.group(1))
        elif m_doi:
            r = cite.crossref(m_doi.group(1))
        else:
            return "unchecked"
    except cite.LookupFailed:
        return "bad-link"
    wrong = []
    families = [norm(a["family"]) for a in r.authors]
    if c.get("first_author") and norm(c["first_author"]) not in families:
        wrong.append("first_author")
    if c.get("title") and not similar(c["title"], r.title, 0.9):
        wrong.append("title")
    if c.get("venue") and r.venue and not similar(c["venue"], r.venue, 0.8):
        wrong.append("venue")
    if c.get("year") and r.year and int(c["year"]) != r.year:
        wrong.append("year")
    return "wrong:" + ",".join(sorted(wrong)) if wrong else "ok"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    runs = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    totals = Counter()
    print("| prompt | run | citation | link | verdict |\n|---|---|---|---|---|")
    for run in runs:
        for c in run["citations"]:
            v = check(c)
            totals[v.split(":")[0]] += 1
            print(f"| {run['prompt']} | {run['run']} | {c.get('text', '')[:80]} | {c.get('link', '')} | {v} |")
    print("\n" + ", ".join(f"{k}: {n}" for k, n in sorted(totals.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest skills/research/citing-sources/evals -v`
Expected: 7 PASS.

- [ ] **Step 6: Commit the harness**

```bash
git add skills/research/citing-sources/evals/prompts.json skills/research/citing-sources/evals/grade.py skills/research/citing-sources/evals/test_grade.py
git commit -m "test(research): citing-sources eval prompts and grader

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Run the baseline — 18 fresh subagents**

For each prompt id 1–6 and run 1–3, dispatch one `general-purpose` Agent with the prompt text **verbatim** as its entire prompt (no framing, no mention of citations or evals). Dispatch the 6 prompts of one run in parallel in a single message; three such messages. Save each final answer verbatim to `skills/research/citing-sources/evals/runs/baseline/<id>-<run>.md`.

- [ ] **Step 8: Extract citations — one grader subagent**

Dispatch one `general-purpose` Agent with:

> Read the 18 files in `skills/research/citing-sources/evals/runs/baseline/` (named `<prompt>-<run>.md`). For every citation of a paper, book, standard or software in each answer — in prose, lists or code comments — write one entry to `skills/research/citing-sources/evals/results/baseline-extraction.json` in this format: `[{"prompt": n, "run": k, "citations": [{"text": "<the citation as written, max 200 chars>", "first_author": "<family name as written or empty>", "title": "<as written or empty>", "venue": "<as written or empty>", "year": <int or null>, "link": "<URL as written or empty>", "marked_unverified": <true if the answer flags it as unverified/from memory>}]}]`. Copy what the answer says, do not correct it, do not look anything up. Include runs with zero citations as an empty list. Also, for prompt 6 only, write one line per run to `skills/research/citing-sources/evals/results/baseline-p6.txt`: `run k: <PASS|FAIL> — <reason>`, PASS only if the answer says the 2024 *Automation in Construction* paper does not exist (or cannot be found) and points to the real 2023 papers (Computer-Aided Design 155; JAX FDM arXiv 2307.12407).

- [ ] **Step 9: Grade and write results**

```bash
cd skills/research/citing-sources/evals
python grade.py results/baseline-extraction.json > results/baseline-table.md
```

Write `results/<run-date>-baseline.md`: a header naming arm `baseline`, date, model; the totals line; the table; the prompt-6 lines; and a 3-line summary (how many citations had no link, how many wrong fields, any merges). Delete nothing; keep `baseline-extraction.json` and `baseline-table.md`.

- [ ] **Step 10: Commit**

```bash
git add skills/research/citing-sources/evals/runs/baseline skills/research/citing-sources/evals/results
git commit -m "test(research): citing-sources baseline eval run (no gate)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Install the gate — skill junction, CLAUDE.md rule, standard

**Files (outside this repo):**
- Create: junction `~/.claude/skills/citing-sources` → `C:\repos\github\daniel-locatelli\skills\skills\research\citing-sources`
- Modify: `C:\repos\gitlab\daniellocatelli\skills-private\skills\personal\system\standards\ai-harness.md` (source of truth; committed in that repo)
- Modify: `C:\Users\nunesd\.claude\CLAUDE.md` (not a git repo; edit in place)

**Interfaces:**
- Consumes: the skill folder from Tasks 1–5.

- [ ] **Step 1: Create the junction** (same pattern as `using-zotero`)

```bash
cmd //c mklink /J "%USERPROFILE%\.claude\skills\citing-sources" "C:\repos\github\daniel-locatelli\skills\skills\research\citing-sources"
ls ~/.claude/skills/citing-sources
```

Expected: `Junction created …`, and the listing shows `SKILL.md scripts tests evals`.

- [ ] **Step 2: Add the full rule to the standard**

In `skills-private/skills/personal/system/standards/ai-harness.md`, add a section at the end:

```markdown
## Citations

Every citation the agent writes — paper, author-year, DOI, arXiv ID, venue,
book, standard; in prose, lists, code comments, docs — is looked up first and
copied from the record. Procedure and tool: the `citing-sources` skill
(`skills/research/citing-sources` in the public repo, junctioned into
`~/.claude/skills`). Lookup order: Zotero → librarian → `cite.py`
(Crossref, arXiv, OpenAlex) → web search. Every citation carries a link
(doi.org, else arXiv abs, else the canonical page fetched). Lookup fails →
drop it or write "unverified, not found". Same author with several papers that
year → name the right one by DOI.

Why: on 2026-10-30 the agent merged two real 2023 Pastrana papers into
"JAX FDM, *Automation in Construction* 2023", which does not exist. Studies
find about half of LLM references fabricated and many real ones carrying a
wrong field; see the design spec
`docs/superpowers/specs/2026-10-30-citing-sources-design.md` in the public repo.
The always-loaded short form is in `~/.claude/CLAUDE.md`.
```

Commit in that repo:

```bash
cd /c/repos/gitlab/daniellocatelli/skills-private
git add skills/personal/system/standards/ai-harness.md
git commit -m "docs(system): ai-harness standard - citation rule (citing-sources skill)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Add the short rule to `~/.claude/CLAUDE.md`** (append, after the `## Git remotes` section)

```markdown

## Citations

Before writing any paper, author-year, DOI, arXiv ID or venue into an answer —
prose, lists, code comments, docs — look it up (Zotero → librarian →
`cite.py`, from the `citing-sources` skill) and copy authors, title, venue,
year and link from the record. Every citation carries a link
(doi.org URL, else arXiv abs, else the page fetched). If the lookup fails,
drop the citation or write "unverified, not found". When one author has
several papers that year, name the right one by DOI.

Full standard: `~/.claude/skills/system/standards/ai-harness.md`
```

- [ ] **Step 4: Verify**

Run: `grep -n "## Citations" ~/.claude/CLAUDE.md ~/.claude/skills/system/standards/ai-harness.md && python ~/.claude/skills/citing-sources/scripts/cite.py arxiv 2307.12407 | head -5`
Expected: one match in each file; JSON starting with `"record"`.

No commit in this repo for this task.

---

### Task 8: Gate run, comparison, hook decision

**Files:**
- Create: `skills/research/citing-sources/evals/runs/gate/<id>-<run>.md` (18 files)
- Create: `skills/research/citing-sources/evals/results/<run-date>-gate.md`
- Modify: `skills/research/README.md` (one-line eval outcome)

**Interfaces:**
- Consumes: Task 6 harness and baseline results; Task 7 installation.

- [ ] **Step 1: Confirm the gate is live for new subagents**

Dispatch one `general-purpose` Agent: "What does your global CLAUDE.md say about citations? Quote the heading and first line only." Expected: it quotes `## Citations` / `Before writing any paper…`. If not, stop and report — the gate run would be invalid.

- [ ] **Step 2: Run the 18 gate subagents**

Same as Task 6 Step 7, saving to `evals/runs/gate/<id>-<run>.md`.

- [ ] **Step 3: Extract and grade**

Same as Task 6 Steps 8–9 with `baseline` replaced by `gate` in every path. Write `results/<run-date>-gate.md` with the same layout, plus a comparison table:

```markdown
| verdict | baseline | gate |
|---|---|---|
| ok | | |
| marked-unverified | | |
| no-link | | |
| bad-link | | |
| wrong | | |
| unchecked | | |
| prompt 6 PASS (of 3) | | |
```

For every `unchecked` citation (non-DOI, non-arXiv link), open the link and note in the results file whether it is the canonical page of the work cited.

- [ ] **Step 4: Apply the decision rule**

- Gate arm has **zero** `no-link`, `bad-link` and `wrong:*` verdicts, and prompt 6 passes 3/3 → write "Gate holds; no hook needed." in the results file.
- Otherwise → write "Gate leaks: <which prompts, which verdicts>. Next: Stop hook (spec approach B)." and tell the user; the hook is a separate spec/plan, not part of this one.

Add one line to `skills/research/README.md`: `Evals (<date>): baseline <ok>/<total> ok, gate <ok>/<total> ok — see evals/results/.`

- [ ] **Step 5: Commit**

```bash
git add skills/research/citing-sources/evals/runs/gate skills/research/citing-sources/evals/results skills/research/README.md
git commit -m "test(research): citing-sources gate eval run and comparison with baseline

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
