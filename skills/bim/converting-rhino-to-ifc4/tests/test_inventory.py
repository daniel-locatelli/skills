import pytest

import make_fixture
from conftest import layer, run


@pytest.fixture(scope="module")
def inv(model3dm):
    code, doc = run("inventory", model3dm)
    assert code == 0, doc
    return doc


def test_keys_and_units(inv):
    assert inv["keys"] == ["Chair", "Existing::Stützen", "Layer 01#1", "Layer 01#2",
                           "Set", "Terrain"]
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
    assert layer(inv, "Chair")["kind"] == "block"
    assert layer(inv, "Chair")["bbox"]["min"] == [2.0, 2.0, 0.0]
    assert layer(inv, "Set")["bbox"]["min"] == [11.0, 0.0, 0.0]


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
