import pytest

import make_fixture
from conftest import layer, run


@pytest.fixture(scope="module")
def inv(model3dm):
    code, doc = run("inventory", model3dm)
    assert code == 0, doc
    return doc


def test_keys_and_units(inv):
    assert inv["keys"] == ["Existing::Stützen", "Layer 01#1", "Layer 01#2", "Terrain",
                           "block:Chair", "block:Set"]
    assert inv["units"] == {"model": "Meters", "toMetres": 1.0}
    assert inv["objectCount"] == 10


def test_forms_and_statistics(inv):
    st = layer(inv, "Existing::Stützen")
    assert st["forms"] == {"linear-vertical": 3}
    assert st["size"]["dz"]["median"] == 3.0
    assert st["slenderness"]["median"] == 7.5
    assert layer(inv, "Terrain")["forms"] == {"plate-horizontal": 1}


def test_mixed_layer_split_into_clusters(inv):
    clusters = layer(inv, "Layer 01")["clusters"]
    assert [(c["key"], c["form"], c["count"]) for c in clusters] == [
        ("Layer 01#1", "linear-vertical", 2), ("Layer 01#2", "plate-horizontal", 2)]
    assert clusters[1]["zMin"] == {"min": 0.0, "median": 1.5, "max": 3.0}


def test_blocks_in_world_space(inv):
    assert layer(inv, "block:Chair")["kind"] == "block"
    assert layer(inv, "block:Chair")["bbox"]["min"] == [2.0, 2.0, 0.0]
    assert layer(inv, "block:Set")["bbox"]["min"] == [11.0, 0.0, 0.0]


def test_non_geometric_listed_not_keyed(inv):
    assert inv["nonGeometric"] == {"Notes": {"LineCurve": 1}, "North": {"LineCurve": 1}}
    assert "Notes" not in inv["keys"]


def test_output_file(model3dm, tmp_path):
    out = tmp_path / "inventory.json"
    code, summary = run("inventory", model3dm, "-o", out)
    assert code == 0 and summary["ok"] and summary["keys"] == 6
    assert out.read_text(encoding="utf-8").count("Stützen") >= 1


def test_missing_mesh_exit_3(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    code, doc = run("inventory", path)
    assert code == 3
    miss = doc["error"]["missingMesh"]
    assert miss[0]["key"] == "Solids" and miss[0]["geometryType"] == "Brep"
    assert "save it normally" in doc["error"]["fix"]


@pytest.fixture(scope="module")
def extra(extra3dm):
    code, doc = run("inventory", extra3dm)
    assert code == 0, doc
    return doc


def test_layer_and_block_of_one_name_are_two_keys(extra):
    assert {"Chair", "block:Chair"} <= set(extra["keys"])
    assert layer(extra, "Chair")["kind"] == "layer" and layer(extra, "Chair")["count"] == 1
    assert layer(extra, "block:Chair")["kind"] == "block"


def test_block_statistics_per_instance(extra):
    chair = layer(extra, "block:Chair")
    assert chair["count"] == 3 and chair["forms"] == {"bulky": 3}
    assert "clusters" not in chair and "block:Chair" in extra["keys"]
    assert chair["size"]["dz"]["median"] == 0.48


def test_parent_keys_of_mixed_layers(inv, extra):
    assert inv["parentKeys"] == {"Layer 01": ["Layer 01#1", "Layer 01#2"]}
    assert extra["parentKeys"] == {"Facade": ["Facade#1", "Facade#2"]}
    assert "Facade" not in extra["keys"]


def test_curves_inside_blocks_counted(extra):
    assert extra["nonGeometric"] == {"Furniture": {"LineCurve": 2}, "Lounge": {"LineCurve": 1}}


def test_unresolved_block_object_counted(tmp_path):
    code, doc = run("inventory", make_fixture.build_broken(tmp_path / "b.3dm"))
    assert code == 0, doc
    assert doc["nonGeometric"] == {"A": {"unresolved block object": 1}}
    assert layer(doc, "block:B")["count"] == 1


def test_dangling_block_exit_2(tmp_path):
    code, doc = run("inventory", make_fixture.build_broken(tmp_path / "b.3dm", dangling=True))
    assert code == 2 and "block definition" in doc["error"]["message"] and doc["error"]["fix"]


def test_empty_mesh_is_missing(tmp_path):
    code, doc = run("inventory", make_fixture.build_extra(tmp_path / "e.3dm", empty_mesh=True))
    assert code == 3 and doc["error"]["missingMesh"][0]["key"] == "Empty"


def test_unwritable_output_exit_2(model3dm, tmp_path):
    code, doc = run("inventory", model3dm, "-o", tmp_path / "no" / "such" / "inv.json")
    assert code == 2 and "cannot write" in doc["error"]["message"] and doc["error"]["fix"]
