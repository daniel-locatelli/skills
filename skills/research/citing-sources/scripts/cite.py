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
