# Research skills

Skills for handling scholarly sources. `citing-sources` gates every citation
the agent writes: look it up (Zotero, librarian, Crossref, arXiv, OpenAlex,
web), copy fields and link from the record, check same-author siblings.
Tests: `python -m pytest skills/research/citing-sources/tests -v`
(`CITE_LIVE=1` adds the live smoke test).
