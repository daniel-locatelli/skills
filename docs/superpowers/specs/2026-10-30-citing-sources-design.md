# Citing sources — design

Date: 2026-10-30
Skill: `skills/research/citing-sources`

## Purpose

Stop the agent from writing fabricated or merged citations. Every paper,
author-year, DOI, arXiv ID or venue that reaches an answer is looked up first,
its fields are copied from the record, and it carries a link.

Origin: in a casual chat answer the agent wrote "Pastrana et al. (JAX FDM,
*Automation in Construction* 2023)". That merged two real 2023 papers by the
same first author — Pastrana et al., "Constrained Form-Finding of
Tension–Compression Structures using Automatic Differentiation", *Computer-Aided
Design* 155, 103435 (https://doi.org/10.1016/j.cad.2022.103435), and Pastrana
et al., "JAX FDM: A Differentiable Solver for Inverse Form-Finding", ICML 2023
workshop (https://arxiv.org/abs/2307.12407) — under a venue belonging to
neither. No existing skill gates citations at the moment they are written;
`using-zotero`, `searching-librarian` and the research skills are lookup tools
or cover deliberate research only.

## Evidence the design rests on

Gathered and fetched 2026-10-30.

- "Real paper, wrong fields" is as common as outright fabrication:
  Bhattacharyya et al., *Cureus* 15(5) e39238 (2023),
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10277170/ — 47 % fabricated, 46 %
  real but inaccurate; Walters & Wilder, *Sci. Rep.* 13, 14045 (2023),
  https://doi.org/10.1038/s41598-023-41032-5 — 24 % of GPT-4's real citations
  had substantive errors. An existence check alone misses half the failures.
- DOIs from memory are mostly wrong: Chelli et al., *J Med Internet Res* 26
  e53164 (2024), https://pmc.ncbi.nlm.nih.gov/articles/PMC11153973/ — DOI
  correct in 16–20 % of non-hallucinated references.
- Merge mechanism ("amalgamated hallucination"): Zhang et al., arXiv:2407.08039,
  https://arxiv.org/abs/2407.08039 — facts sharing dominant cues blend into one
  false output.
- Long-tail facts and the retrieval fix: Kandpal et al., ICML 2023,
  https://arxiv.org/abs/2211.08411; Mallen et al., ACL 2023,
  https://arxiv.org/abs/2212.10511.
- Clean format is no evidence: Zhao et al., arXiv:2603.07287,
  https://arxiv.org/abs/2603.07287 — at most 47.5 % of citations from four
  models (incl. Claude Sonnet) confirmed to exist.
- Retrieve-then-cite beats write-then-check: Asai et al. (OpenScholar),
  https://arxiv.org/abs/2411.14199; factored per-fact verification:
  Dhuliawala et al., https://arxiv.org/abs/2309.11495.

## Decisions

| # | Decision |
|---|---|
| D1 | Scope is **everywhere**: chat prose, lists, code comments, docs, specs — any session, any project. |
| D2 | **Verify before writing.** No unmarked from-memory citation. If lookup fails, drop the citation or write it as "unverified, not found". |
| D3 | **Every citation carries a link** taken from the record: `https://doi.org/<doi>`, else the arXiv abs page, else the page actually fetched. Never a link from memory. |
| D4 | Venue, year, authors, title and link are **copied from the record**, field by field, never from recall. |
| D5 | **Same-author collision**: when the first author has other works within ±1 year, they are listed and the intended one is named by DOI. |
| D6 | Enforcement is a short always-on rule in `~/.claude/CLAUDE.md` plus this skill (approach A). A Stop hook that scans answers (approach B) is added only if the evals show A leaks. |
| D7 | Lives in the **public** repo under a new `research` category; Zotero and librarian are optional first backends on machines that have them. |

## The always-on rule (`~/.claude/CLAUDE.md`)

```markdown
## Citations

Before writing any paper, author-year, DOI, arXiv ID or venue into an answer —
prose, lists, code comments, docs — look it up (Zotero → librarian →
`cite.py`, from the `citing-sources` skill) and copy authors, title, venue,
year and link from the record. Every citation carries a link
(doi.org URL, else arXiv abs, else the page fetched). If the lookup fails,
drop the citation or write "unverified, not found". When one author has
several papers that year, name the right one by DOI.
```

The rule is the trigger; the procedure lives in the skill. Verified citations
get no extra mark — the link is the evidence.

## Layout

```
skills/research/README.md                 bucket README
skills/research/citing-sources/
  SKILL.md                                trigger, lookup order, format, red flags
  scripts/cite.py                         stdlib CLI: doi, arxiv, find
  tests/fixtures/*.json|xml               saved Crossref / arXiv / OpenAlex responses
  tests/test_cite.py                      offline pytest + one live smoke test (marked)
```

Registered in `.claude-plugin/plugin.json` and the top-level `README.md`;
`CHANGELOG.md` entry; plugin version bumped (minor).

## SKILL.md

- **Trigger:** a paper, author-year, DOI, arXiv ID or venue is about to be
  written — not only in research tasks.
- **Lookup order:** (1) Zotero `zot.py doi` and librarian `bib doi`, where
  installed; (2) `cite.py`; (3) web search. Web search is the *primary*
  lookup for works with no DOI or arXiv ID — books without a DOI, standards
  (ISO, EN, IEEE), RFCs, technical reports, software docs. The link is the
  canonical page fetched (publisher, standards body, rfc-editor.org), not a
  search-result or mirror URL.
- **Format, copied from the record:**
  - prose: `Pastrana et al. (2023, [CAD 155](https://doi.org/10.1016/j.cad.2022.103435))`
  - lists: full reference, then the link.
- **Red flags** table: "I'm sure of this one", "it's only a passing mention",
  "the venue is obviously X", "I'll add the link later", "the DOI looks right".

## `cite.py`

Python standard library only (`urllib`, `json`, `xml.etree`). Every subcommand
prints JSON and one formatted citation line with its link.

| Command | Source | Returns |
|---|---|---|
| `cite.py doi <doi>` | Crossref; `10.48550/arXiv.*` DOIs go to the arXiv API | authors, title, venue, volume, pages, year, link |
| `cite.py arxiv <id>` | arXiv API | same, plus the journal DOI if arXiv lists one |
| `cite.py find "<author>" <year> [keywords…]` | OpenAlex | all works by that author in year ±1, ranked by keyword match |

- **Collision check:** after `doi` and `arxiv`, the script runs `find` on the
  first author and year and prints
  `SIBLINGS: n other works by <author> in <year>` followed by at most 5 of them
  (titles and links), ranked by title-word overlap with the looked-up paper —
  the near-duplicates that cause merges rank first. `n` is always the full
  count; `find --all` lists every sibling.
- **Errors:** network failure or no match → non-zero exit,
  `lookup failed: <reason>` on stderr. A `429` is retried once after
  `Retry-After` (capped at 10 s), then fails. The skill then falls back to web
  search, then to "unverified, not found".
- **Identity:** by default no email or API key; Crossref and OpenAlex are used
  at the public rate, with a `User-Agent` naming the tool only. If the user
  sets `CITE_MAILTO`, it is sent as `mailto` (Crossref `User-Agent`, OpenAlex
  query parameter) to get the polite pool. Likewise `OPENALEX_API_KEY`, if
  set by the user, is sent as `api_key` (OpenAlex now gives keyless requests
  a small budget shared per IP). The agent never sets either.
- **Source of truth per field:** Crossref (or arXiv) for the citation;
  OpenAlex only for finding siblings. They disagree in practice — OpenAlex
  dates the CAD paper 2022, Crossref 2023 (published-print).
- **No cache** in v1: one lookup is about a second, and repeats within a
  session are rare. Revisit if the evals show lookup latency matters.

## Testing

- Offline unit tests on saved responses: parsing for each source, link choice
  (DOI > arXiv > page), sibling detection and the 5-item cap, `429` retry,
  `CITE_MAILTO` present/absent, error exits.
- One live smoke test (pytest marker, skipped by default) on the two Pastrana
  DOIs, asserting both appear as siblings of each other.

## Evals

Six prompts, three runs each, fresh subagent per run, **without** the gate
(run before the CLAUDE.md rule is installed — subagents load global CLAUDE.md)
and **with** it.

| # | Prompt (short form) | Tempts |
|---|---|---|
| 1 | "What has Pastrana done on AD form-finding?" | same-author/year merge |
| 2 | "Quick q: any prior work on differentiable FDM for gridshells?" | inline citation in casual answer |
| 3 | "Give me 5 key references on planar quad meshes" | reference list |
| 4 | "Classic reference for Bayesian calibration of computer models?" | older paper, no arXiv |
| 5 | "Write a Python force-density solver with a docstring citing the source" | citation in a code comment |
| 6 | "Summarise Pastrana's 2024 *Automation in Construction* paper on JAX FDM" | nonexistent paper; must say not found and point to the two real ones |

**Grader:** a grader subagent extracts every citation from each answer as
JSON (authors, title, venue, year, link as written); a script built on
`cite.py` then checks, per citation, link present and resolving, fields matching the
record, and no merge. Prompt 6 passes only on "not found" plus the two real
papers.

**Decision rule:** any unlinked or wrong-field citation in the with-gate runs
(prompts 2 and 5 especially) → add the Stop hook (approach B) and re-run.

## Out of scope

- Re-verifying citations from past sessions.
- Formatting styles (APA, BibTeX export) beyond the two formats above.
- Adding looked-up papers to Zotero automatically.
