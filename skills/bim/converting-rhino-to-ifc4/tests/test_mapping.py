import pytest

from conftest import MAPPING, run, write_mapping


@pytest.mark.parametrize("change, expected", [
    (lambda m: m[:-1], "Set: missing"),
    (lambda m: m + [dict(m[0])], "key listed twice"),
    (lambda m: [dict(m[0], **{"class": "IfcWal"})] + m[1:], "not a concrete IfcElement"),
    (lambda m: [dict(m[0], **{"class": "IfcBuildingStorey"})] + m[1:], "not a concrete IfcElement"),
    (lambda m: m[:2] + [dict(m[2], predefinedType="CEILING")] + m[3:], "not in"),
    (lambda m: m[:2] + [dict(m[2], predefinedType="USERDEFINED")] + m[3:], "needs objectType"),
    (lambda m: [dict(m[0], **{"class": "IfcFurniture", "predefinedType": "X"})] + m[1:], "not in"),
    (lambda m: [dict(m[0], confidence="sure")] + m[1:], "confidence must be"),
    (lambda m: [dict(m[0], rationale="")] + m[1:], "rationale missing"),
    (lambda m: m + [{"key": "Nope", "skip": True, "rationale": "x"}], "not an inventory key"),
])
def test_problems_exit_2(model3dm, tmp_path, change, expected):
    code, doc = run("convert", model3dm, write_mapping(tmp_path, change(MAPPING)),
                    "-o", tmp_path / "x.ifc")
    assert code == 2
    assert any(expected in p for p in doc["error"]["problems"]), doc
    assert not (tmp_path / "x.ifc").exists()


def test_userdefined_with_object_type_accepted(model3dm, tmp_path):
    entries = MAPPING[:2] + [dict(MAPPING[2], predefinedType="userdefined",
                                  objectType="Podium")] + MAPPING[3:]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0, doc


def test_skip_accepted(model3dm, tmp_path):
    entries = MAPPING[:-1] + [{"key": "Set", "skip": True, "rationale": "not needed"}]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0 and doc["skipped"] == ["Set"]


def test_bad_schema(model3dm, tmp_path):
    code, doc = run("convert", model3dm, write_mapping(tmp_path, schema="IFC2X3"),
                    "-o", tmp_path / "x.ifc")
    assert code == 2 and "schema" in doc["error"]["message"]


def test_unreadable_mapping(model3dm, tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text("{not json", encoding="utf-8")
    code, doc = run("convert", model3dm, bad, "-o", tmp_path / "x.ifc")
    assert code == 2 and "cannot read mapping" in doc["error"]["message"]
