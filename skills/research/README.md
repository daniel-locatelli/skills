# Research skills

Skills for handling scholarly sources. `citing-sources` gates every citation
the agent writes: look it up (Zotero, librarian, Crossref, arXiv, OpenAlex,
web), copy fields and link from the record, check same-author siblings.
Tests: `python -m pytest skills/research/citing-sources/tests -v`
(`CITE_LIVE=1` adds the live smoke test).
Evals (2026-10-30): baseline 28/90 ok, gate 56/78 ok (64 after adjudication); unlinked 49 → 1. The gate leaked 5 wrong years copied from sibling output; after the fix, prompts 1 and 6 had 0 wrong (gate v2) — see `citing-sources/evals/results/`.
