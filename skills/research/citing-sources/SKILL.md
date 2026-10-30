---
name: citing-sources
description: Use before writing any citation — a paper, "Author et al. (year)", DOI, arXiv ID, venue, book or standard — into an answer, list, code comment, docstring or document, in any task, including a passing mention in casual chat. Looks the work up first (Zotero, librarian, Crossref, arXiv, OpenAlex, web), copies every field and the link from the record, and lists same-author papers that get merged.
---

# Citing sources

A citation written from memory is often wrong. In a study of ChatGPT-written
literature reviews, 18-55 % of the references were fabricated, and 24-43 % of
the real ones carried substantive errors
([Walters & Wilder 2023, Sci. Rep. 13](https://doi.org/10.1038/s41598-023-41032-5)).
A failure that is easy to miss: two real papers by the same author, same year,
**merged** into one. So: **look up before writing, copy
every field from the record, link every citation.**

## The rule

1. Before a citation goes into any output, look it up (order below).
2. Copy authors, title, venue, volume, year and link **from the record**.
   Never fill a field from recall — especially venue, year and DOI.
3. Every citation carries a link: `https://doi.org/<doi>`, else
   `https://arxiv.org/abs/<id>`, else the canonical page you fetched.
   The only unlinked citation is one marked unverified (rule 5).
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
   `find` prints a list of up to 3 OpenAlex authors matching the name, each
   with `count` and `works` (`title`, `year`, `link`), ranked by keyword
   overlap. Sibling and `find` entries are pointers from OpenAlex, not
   citations: look each up with `doi`/`arxiv` before citing it. It is a finder only:
   no DOI or arXiv ID in hand -> `find` first, then `doi`/`arxiv` on the hit,
   and cite from that record.
3. **Web search** — the primary lookup for works with no DOI or arXiv ID:
   books without a DOI, standards (ISO, EN, IEEE), RFCs, technical reports,
   software docs. Link the canonical page you fetched (publisher, standards
   body, rfc-editor.org), not a search result or a mirror.

## Format

- Prose: `Pastrana et al. (2023, [CAD 155](https://doi.org/10.1016/j.cad.2022.103435))`
  — `short` plus a linked venue tag.
- Lists, bibliographies, docstrings: the top-level `citation` of a `doi`/`arxiv`
  lookup, as printed — never a sibling or `find` entry.
- Do not add a "verified" mark; the working link is the evidence.

## SIBLINGS

`SIBLINGS: n other works by <author> in <y-1>-<y+1>` with up to 5 ranked by
title overlap. Example: looking up
[Pastrana et al. (2023), *Computer-Aided Design* 155](https://doi.org/10.1016/j.cad.2022.103435)
lists
[*JAX FDM*](https://arxiv.org/abs/2307.12407) (ICML 2023 workshop) — the pair
that was once merged into a nonexistent "JAX FDM, *Automation in
Construction* 2023". If the note says `check failed`, run the `find` it
suggests before citing. Sibling entries are pointers (title, year, link
from OpenAlex): run `doi`/`arxiv` on one before citing it.

## Optional environment (user-set only)

`CITE_MAILTO` (Crossref/OpenAlex polite pool) and `OPENALEX_API_KEY`
(OpenAlex gives keyless requests a small budget shared per IP). Never set
them yourself; without them the script works at the public rate.

## Red flags

| Thought | Reality |
|---|---|
| "I'm sure of this one" | Certainty is not a record. Look it up. |
| "It's only a passing mention" | Passing mentions are where it slipped through. Same rule. |
| "The venue is obviously X" | A plausible venue is what a merge looks like. From the record. |
| "The DOI looks right" | Of real ChatGPT references, the DOI was correct 16-20 % of the time ([Chelli et al. 2024, JMIR 26](https://doi.org/10.2196/53164)). Resolve it. |
| "The sibling entry already has title and year" | It is an OpenAlex pointer (OpenAlex dates the CAD paper 2022; Crossref 2023). Run `doi` on it. |
| "I'll add the link later" | No link, no citation. |
| "Lookup failed, but I know it exists" | Then write *(unverified, not found)*. |
| "It's in a code comment, not prose" | Same rule. |
