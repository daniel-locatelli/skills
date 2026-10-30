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


@pytest.fixture(scope="module")
def mat(materials3dm):
    return model.read(materials3dm)


def test_layer_material_beats_black_display_colour(mat):
    box, = items(mat, "Painted")[:1]
    assert (box.colour, box.transparency) == ((200, 100, 50), 0.0)


def test_object_material(mat):
    own = items(mat, "Painted")[1]
    assert own.colour == (10, 200, 30)


def test_material_transparency(mat):
    glass, = items(mat, "Glass")
    assert glass.colour == (30, 60, 200) and glass.transparency == pytest.approx(0.4)


def test_no_or_invalid_material_falls_back_to_display_colour(mat):
    for key, colour in (("Plain", (9, 8, 7)), ("Dangling", (4, 5, 6))):
        it, = items(mat, key)
        assert (it.colour, it.transparency) == (colour, 0.0)


def test_block_member_takes_material_by_parent(mat):
    by_layer, by_object, plain = sorted(items(mat, "block:Cup"), key=lambda i: min(
        v.X for v in i.mesh.Vertices))
    assert by_layer.colour == (200, 100, 50)   # instance material from its layer
    assert by_object.colour == (10, 200, 30)   # instance's own material
    assert plain.colour == (1, 2, 3)           # no material anywhere: the member's display colour
