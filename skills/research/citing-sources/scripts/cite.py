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
import html
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

def text(s) -> str:
    """Plain text from a source field that may carry HTML entities."""
    return html.unescape(s) if isinstance(s, str) else s


def first(xs) -> str:
    return xs[0] if xs else ""


def quote_doi(doi: str) -> str:
    return urllib.parse.quote(doi, safe="/:()")


def crossref(doi: str) -> Record:
    doi = normalize_doi(doi)
    if doi.lower().startswith("10.48550/arxiv."):
        return arxiv(doi.split(".", 2)[2])
    body = http_get("https://api.crossref.org/works/" + quote_doi(doi))
    try:
        m = json.loads(body)["message"]
        date = m.get("published-print") or m.get("published") or m.get("issued") or {}
        year = (date.get("date-parts") or [[None]])[0][0]
        return Record(
            authors=[{"given": text(a.get("given", "")), "family": text(a.get("family") or a.get("name", ""))}
                     for a in m.get("author", [])],
            title=" ".join(text(first(m.get("title"))).split()),
            year=year,
            venue=text(first(m.get("container-title"))),
            volume=m.get("volume", ""),
            pages=m.get("page") or m.get("article-number", ""),
            doi=m["DOI"],
            url=m.get("URL", ""),
            source="crossref",
        )
    except (ValueError, LookupError, TypeError, AttributeError):
        raise LookupFailed("crossref: unexpected response") from None


# --- arXiv ---------------------------------------------------------------------

ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.I)


def arxiv(arxiv_id: str) -> Record:
    m = ARXIV_ID.search(arxiv_id)
    if not m:
        raise LookupFailed(f"not an arXiv ID: {arxiv_id}")
    base = m.group(1)
    body = http_get("https://export.arxiv.org/api/query?id_list=" + base)
    try:
        entries = ET.fromstring(body).findall("a:entry", ATOM)
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
    except (ET.ParseError, ValueError, TypeError, AttributeError):
        raise LookupFailed("arxiv: unexpected response") from None


# --- OpenAlex (siblings only; never the source of a citation's fields) -----------

WORK_FIELDS = "id,doi,display_name,publication_year,primary_location,authorships"
STOP = {"using", "with", "from", "based", "towards", "toward", "their", "this", "that", "into", "for", "and", "the"}


def openalex(path: str, **params) -> dict:
    if os.environ.get("CITE_MAILTO"):
        params["mailto"] = os.environ["CITE_MAILTO"]
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    query = "?" + urllib.parse.urlencode(params) if params else ""
    body = http_get(f"https://api.openalex.org/{path}{query}")
    try:
        return json.loads(body)
    except ValueError:
        raise LookupFailed("openalex: unexpected response") from None


def from_openalex(w: dict) -> Record:
    doi = re.sub(r"^https://doi\.org/", "", w.get("doi") or "")
    arx = ""
    if doi.lower().startswith("10.48550/arxiv."):
        arx, doi = doi.split(".", 2)[2], ""
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    return Record(
        authors=[split_name(a["author"]["display_name"]) for a in w.get("authorships", [])],
        title=text(w.get("display_name") or ""),
        year=w.get("publication_year"),
        venue=text(source),
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
    return bool(words(a.title)) and words(a.title) == words(b.title)


def summary(r: Record) -> dict:
    return {"title": r.title, "citation": full(r), "link": link(r), "year": r.year}


def siblings(r: Record, show_all: bool = False) -> dict:
    if r.year is None or not r.authors:
        return {"count": None, "shown": [], "note": "SIBLINGS: skipped (record has no year or authors)"}
    name = r.authors[0]["family"]
    key = f"doi:{quote_doi(r.doi)}" if r.doi else f"doi:10.48550/arXiv.{r.arxiv}"
    try:
        auths = openalex(f"works/{key}", select="authorships").get("authorships") or []
        if not auths:
            raise LookupFailed("OpenAlex lists no authors")
        others = [w for w in works_by(auths[0]["author"]["id"].rsplit("/", 1)[-1], r.year) if not same_work(w, r)]
    except (LookupFailed, LookupError, TypeError, AttributeError, ValueError) as e:
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
