# using-zotero

Read and write a running Zotero (7–10) through its local HTTP API — no
zotero.org account, no sync, no plugin. One stdlib Python script, `scripts/zot.py`.

    cp zotero.config.example.json zotero.config.json   # per machine, git-ignored
    python scripts/zot.py doctor
    python scripts/zot.py authorize                    # once; click Always Allow

Tests run against an in-process fake of the local API (no Zotero needed):

    python -m pytest tests -v
