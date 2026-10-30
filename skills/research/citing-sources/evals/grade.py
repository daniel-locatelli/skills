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
ARXIV = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html)/|^\s*arxiv[:\s]\s*)([^\s?#]+?)(?:\.pdf)?\s*$", re.I)


def norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def similar(a: str, b: str, cut: float) -> bool:
    a, b = norm(a), norm(b)
    return a == b or a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= cut


VENUE_STOP = {"of", "the", "and", "in", "on", "for", "a", "an", "at", "to"}


def venue_words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (s or "").lower())) - VENUE_STOP


def venue_matches(written: str, recorded: str, cut: float = 0.8) -> bool:
    a, b = norm(written), norm(recorded)
    if a == b or b in a:  # equal, or the record is contained in a longer written form
        return True
    w, r = venue_words(written), venue_words(recorded)
    if not w or not r:
        return False
    shared = len(w & r)
    # most written words must be in the record, and the overlap must be substantial:
    # 3+ shared words, or more than half of the record's words covered
    return shared / len(w) >= cut and (shared >= 3 or shared / len(r) > 0.5)


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
    # A bare arXiv record is the preprint: it cannot refute a later journal venue.
    # The year on any arXiv record is the first version's, so only an earlier
    # written year is wrong. "ok-preprint" = authors and title checked, venue not.
    preprint = r.source == "arxiv" and r.venue == "arXiv"
    if c.get("venue") and r.venue and not preprint and not venue_matches(c["venue"], r.venue):
        wrong.append("venue")
    if c.get("year") and r.year and (int(c["year"]) < r.year if r.source == "arxiv" else int(c["year"]) != r.year):
        wrong.append("year")
    if wrong:
        return "wrong:" + ",".join(sorted(wrong))
    return "ok-preprint" if preprint else "ok"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
