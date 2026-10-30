import pytest

import rhino3dm as r

import make_fixture
from r2i import model
from r2i.errors import R2IError


@pytest.fixture(scope="module")
def m(model3dm):
    return model.read(model3dm)


def items(m, key):
    return [it for it in m.items if it.key == key]


def test_units(m):
    assert (m.unit, m.scale) == ("Meters", 1.0)


def test_layer_items(m):
    cols = items(m, "Existing::Stützen")
    assert len(cols) == 3 and {it.kind for it in cols} == {"layer"}
    assert [it.name for it in cols] == ["C1", "", ""]
    assert cols[0].colour == (255, 0, 0)
    assert all(it.mesh is not None for it in cols)


def test_block_items_world_space_and_colour(m):
    chair, = items(m, "block:Chair")
    assert chair.kind == "block" and chair.layer == "Furniture"
    assert chair.colour == (0, 0, 255)  # by parent -> the instance's object colour
    xs = [v.X for v in chair.mesh.Vertices]
    assert min(xs) == 2.0
    nested, = items(m, "block:Set")
    assert min(v.X for v in nested.mesh.Vertices) == 11.0  # 10 (Set) + 1 (Chair in Set)
    assert nested.colour == (0, 255, 0)


def test_definition_geometry_not_listed_twice(m):
    assert len(m.items) == 3 + 4 + 1 + 2


def test_non_geometric(m):
    assert m.non_geometric == {"Notes": {"LineCurve": 1}, "North": {"LineCurve": 1}}


def test_missing_mesh_kept_as_none(tmp_path):
    m = model.read(make_fixture.build(tmp_path / "s.3dm", missing_mesh=True))
    solid, = items(m, "Solids")
    assert solid.mesh is None and solid.geometry_type == "Brep"


def test_north(m):
    assert model.north(m, "North") == pytest.approx((0.7071068, 0.7071068))
    with pytest.raises(R2IError) as exc:
        model.north(m, "Terrain")
    assert exc.value.code == 2


def test_unreadable_file(tmp_path):
    bad = tmp_path / "bad.3dm"
    bad.write_text("not a model")
    with pytest.raises(R2IError) as exc:
        model.read(bad)
    assert exc.value.code == 2


def test_empty_geometry_has_no_mesh():
    assert model.mesh_of(r.Mesh()) is None
    assert model.mesh_of(r.Brep()) is None


def test_north_ignores_block_definition_curves(extra3dm):
    with pytest.raises(R2IError) as exc:
        model.north(model.read(extra3dm), "Chair parts")
    assert exc.value.code == 2
