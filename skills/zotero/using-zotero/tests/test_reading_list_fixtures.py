"""The reading-list half of the Meristema Reading note format, against the shared fixtures.

The fixtures live in the format's own repo (zotero-meristema-reading/fixtures); point
MERISTEMA_READING_FIXTURES at them, or keep that repo next to this one. The read-state
half (states/, state writes, paper ids, next-up) is not ported, so its cases are not run.
"""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import reading_list as rl  # noqa: E402

REPO_ROOT = HERE.parents[3]
FIXTURES = Path(os.environ.get("MERISTEMA_READING_FIXTURES")
                or REPO_ROOT.parent / "zotero-meristema-reading" / "fixtures")
if not (FIXTURES / "index.json").is_file():
    pytest.skip(f"format fixtures not found at {FIXTURES}: clone zotero-meristema-reading next to this repo "
                f"or set MERISTEMA_READING_FIXTURES", allow_module_level=True)

INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
LIST_CASES = INDEX["lists"]
LIST_WRITES = [f for f in INDEX["writes"]
               if json.loads((FIXTURES / "writes" / f).read_text(encoding="utf-8"))["kind"] == "list"]
RAN: set[str] = set()


def note_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")  # byte-exact: read_text would fold \r\n


@pytest.mark.parametrize("case", LIST_CASES)
def test_list_case(case):
    spec = json.loads((FIXTURES / "lists" / case).read_text(encoding="utf-8"))
    parsed = rl.parse_reading_list(note_text(FIXTURES / "lists" / spec["note"]))
    if parsed["ok"]:
        doc = parsed["value"]
        resolved = rl.resolve_reading_list(doc, spec["folder"])
        got = {"ok": True, "topic": doc["topic"], "steps": resolved["steps"], "unordered": resolved["unordered"]}
    else:
        got = parsed
    assert got == spec["expect"]
    RAN.add(f"lists/{case}")


@pytest.mark.parametrize("case", LIST_WRITES)
def test_list_write_case(case):
    spec = json.loads((FIXTURES / "writes" / case).read_text(encoding="utf-8"))
    written = rl.write_reading_list(spec["doc"], spec["labels"].__getitem__, spec["library"])
    assert written == note_text(FIXTURES / "writes" / spec["note"])
    assert rl.parse_reading_list(written) == {"ok": True, "value": spec["doc"]}
    RAN.add(f"writes/{case}")


def test_index_names_every_case_file_and_every_note_belongs_to_a_case():
    for folder in ("lists", "states", "writes"):
        on_disk = sorted(p.name for p in (FIXTURES / folder).glob("*.json"))
        assert on_disk == sorted(INDEX[folder]), folder
    notes = {f"lists/{json.loads((FIXTURES / 'lists' / c).read_text(encoding='utf-8'))['note']}" for c in LIST_CASES}
    for c in INDEX["states"]:
        notes |= {f"states/{n}" for n in json.loads((FIXTURES / "states" / c).read_text(encoding="utf-8"))["notes"]}
    for c in INDEX["writes"]:
        notes.add(f"writes/{json.loads((FIXTURES / 'writes' / c).read_text(encoding='utf-8'))['note']}")
    html = {p.relative_to(FIXTURES).as_posix() for p in FIXTURES.rglob("*.html")}
    assert html == notes


def test_ran_exactly_the_indexed_list_cases(request):
    """Last in the file: every list case and list write case the index names ran here."""
    want = {f"lists/{c}" for c in LIST_CASES} | {f"writes/{c}" for c in LIST_WRITES}
    selected = {f"{'lists' if i.originalname == 'test_list_case' else 'writes'}/{i.callspec.params['case']}"
                for i in request.session.items if i.originalname in ("test_list_case", "test_list_write_case")}
    if selected != want:
        pytest.skip("only part of the fixture cases were selected")
    assert want and RAN == want
