"""The reading-list half of the Meristema Reading note format, against the shared fixtures.

The fixtures live in the format's own repo (zotero-meristema-reading/fixtures); point
MERISTEMA_READING_FIXTURES at them, or keep that repo next to this one. Read state, paper ids,
next-up and the queue rule are run too; state write cases are not ported.
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


STATE_CASES = INDEX["states"]


def merge_all(notes):
    doc = {"version": 1, "states": {}}
    for note in notes:
        parsed = rl.parse_read_state((FIXTURES / "states" / note).read_text(encoding="utf-8"))
        assert parsed["ok"], f"{note}: {parsed}"
        doc = rl.merge_read_states(doc, parsed["value"])
    return doc


@pytest.mark.parametrize("case", STATE_CASES)
def test_state_case(case):
    c = json.loads((FIXTURES / "states" / case).read_text(encoding="utf-8"))
    want = c["expect"]
    if not want["ok"]:
        assert len(c["notes"]) == 1
        html = (FIXTURES / "states" / c["notes"][0]).read_text(encoding="utf-8")
        assert rl.parse_read_state(html) == {"ok": False, "reason": want["reason"]}
    else:
        orders = [c["notes"], list(reversed(c["notes"]))] if len(c["notes"]) > 1 else [c["notes"]]
        for notes in orders:
            doc = merge_all(notes)
            assert doc["states"] == want["states"], notes
            for pid in want["absent"]:
                assert pid not in doc["states"] and rl.state_of(doc, pid) == "unread"
            for pid, tag in want["mirror"].items():
                assert rl.MIRROR_TAGS[rl.state_of(doc, pid)] == tag
    RAN.add(f"states/{case}")


def test_paper_ids():
    for c in json.loads((FIXTURES / INDEX["paperIds"]).read_text(encoding="utf-8")):
        assert rl.paper_id(c["ref"]) == c["id"], c
        assert rl.is_paper_id(c["id"]), c
    RAN.add(INDEX["paperIds"])


def test_next_up():
    for c in json.loads((FIXTURES / INDEX["nextUp"]).read_text(encoding="utf-8")):
        assert rl.next_up(c["steps"], lambda k: c["states"].get(k, "unread")) == c["expect"], c
    RAN.add(INDEX["nextUp"])


def test_queue():
    q = json.loads((FIXTURES / INDEX["queue"]).read_text(encoding="utf-8"))
    for c in q["pick"]:
        assert rl.pick_queue(c["notes"]) == c["expect"], c["name"]
    for c in q["sourceLists"]:
        assert rl.source_lists(c["queueNote"], c["queue"], c["lists"]) == c["expect"], c["name"]
    RAN.add(INDEX["queue"])


def test_ran_exactly_the_indexed_cases(request):
    """Last in the file: every case the index names ran here."""
    want = ({f"lists/{c}" for c in LIST_CASES} | {f"writes/{c}" for c in LIST_WRITES}
            | {f"states/{c}" for c in STATE_CASES} | {INDEX["paperIds"], INDEX["nextUp"], INDEX["queue"]})
    kinds = {"test_list_case": "lists", "test_list_write_case": "writes", "test_state_case": "states"}
    names = {"test_paper_ids": INDEX["paperIds"], "test_next_up": INDEX["nextUp"], "test_queue": INDEX["queue"]}
    selected = set()
    for i in request.session.items:
        if i.originalname in kinds:
            selected.add(f"{kinds[i.originalname]}/{i.callspec.params['case']}")
        elif i.originalname in names:
            selected.add(names[i.originalname])
    if selected != want:
        pytest.skip("only part of the fixture cases were selected")
    assert want and RAN == want
