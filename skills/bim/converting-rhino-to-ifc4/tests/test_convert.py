import json

import ifcopenshell
import pytest

import make_fixture
from conftest import EXTRA, MAPPING, replace, run, write_mapping


@pytest.fixture(scope="module")
def ifc(model3dm, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ifc")
    out = tmp / "out.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp), "-o", out, "--storeys",
                    "--north", "North", "--georef", "EPSG:2056,2600000,1200000,400")
    assert code == 0, doc
    return ifcopenshell.open(str(out)), doc


def pset(element):
    for rel in element.IsDefinedBy:
        ps = rel.RelatingPropertyDefinition
        if ps.Name == "Pset_RhinoSource":
            return {p.Name: p.NominalValue.wrappedValue for p in ps.HasProperties}
    return None


@pytest.mark.parametrize("schema", ["IFC4", "IFC4X3_ADD2"])
def test_element_counts_per_schema(model3dm, tmp_path, schema):
    out = tmp_path / "out.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp_path, schema=schema), "-o", out)
    assert code == 0, doc
    assert doc["schema"] == schema
    assert doc["elements"] == {"IfcColumn": 5, "IfcSlab": 2, "IfcGeographicElement": 1,
                               "IfcFurniture": 2}
    assert ifcopenshell.open(str(out)).schema_identifier == schema


def test_names_and_pset(ifc):
    f, _ = ifc
    columns = f.by_type("IfcColumn")
    assert sorted(c.Name for c in columns) == ["C1", "Layer 01#1", "Layer 01#1",
                                               "Stützen", "Stützen"]
    ps = pset(next(c for c in columns if c.Name == "C1"))
    assert ps["LayerPath"] == "Existing::Stützen"
    assert ps["Confidence"] == "high" and "columns" in ps["Rationale"]
    assert len(ps["ObjectIds"]) == 36


def test_merged_element_and_tessellation(ifc):
    f, _ = ifc
    terrain, = f.by_type("IfcGeographicElement")
    assert terrain.PredefinedType == "TERRAIN"
    body = terrain.Representation.Representations[0]
    assert body.RepresentationType == "Tessellation"
    assert body.Items[0].is_a("IfcPolygonalFaceSet")


def test_predefined_type_upper_cased(ifc):
    f, _ = ifc
    assert {s.PredefinedType for s in f.by_type("IfcSlab")} == {"FLOOR"}


def test_terrain_on_site(ifc):
    f, _ = ifc
    terrain, = f.by_type("IfcGeographicElement")
    assert terrain.ContainedInStructure[0].RelatingStructure.is_a("IfcSite")


def test_storeys_detected(ifc):
    f, doc = ifc
    assert doc["storeys"] == [0.0, 3.0]
    storeys = {s.Name: s for s in f.by_type("IfcBuildingStorey")}
    upper = [e.Name for r in storeys["Level 1"].ContainsElements for e in r.RelatedElements]
    assert upper == ["Layer 01#2"]


def test_storeys_explicit(model3dm, tmp_path):
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", tmp_path / "x.ifc",
                    "--storeys", "3,0,6,3")
    assert code == 0 and doc["storeys"] == [0.0, 3.0, 6.0]


def test_storeys_without_floor_slabs(model3dm, tmp_path):
    entries = MAPPING[:2] + [dict(MAPPING[2], predefinedType="ROOF")] + MAPPING[3:]
    code, doc = run("convert", model3dm, write_mapping(tmp_path, entries), "-o",
                    tmp_path / "x.ifc", "--storeys")
    assert code == 2 and "--storeys 0,3.2" in doc["error"]["fix"]


def test_no_storeys_by_default(model3dm, tmp_path):
    out = tmp_path / "x.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", out)
    assert code == 0 and doc["storeys"] == []
    assert ifcopenshell.open(str(out)).by_type("IfcBuildingStorey") == ()


def test_colours(ifc):
    f, _ = ifc
    colours = {(round(c.Red, 3), round(c.Green, 3), round(c.Blue, 3))
               for c in f.by_type("IfcColourRgb")}
    assert (1.0, 0.0, 0.0) in colours   # Stützen layer colour
    assert (0.0, 0.0, 1.0) in colours   # Chair part "by parent" takes the instance's object colour
    assert (0.0, 1.0, 0.0) in colours   # Set instance: Furniture layer colour


def test_anonymous_header(ifc):
    f, _ = ifc
    assert f.by_type("IfcOwnerHistory") == () and f.by_type("IfcPerson") == ()
    assert f.header.file_name.author == ("",)
    assert f.header.file_name.originating_system == "rhino2ifc"


def test_georef_and_north(ifc):
    f, _ = ifc
    conv, = f.by_type("IfcMapConversion")
    assert conv.TargetCRS.Name == "EPSG:2056" and conv.Eastings == 2600000.0
    assert conv.XAxisAbscissa == 1.0 and conv.XAxisOrdinate == 0.0
    north = f.by_type("IfcGeometricRepresentationContext")[0].TrueNorth.DirectionRatios
    assert north == pytest.approx((0.7071068, 0.7071068))


@pytest.mark.parametrize("value", ["2056,1,2,3", "EPSG:2056,1,2", "EPSG:x,1,2,3",
                                   "EPSG:2056,nan,2,3", "EPSG:2056,1,inf,3", "EPSG:2056,1,2,3,-inf"])
def test_bad_georef(model3dm, tmp_path, value):
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", tmp_path / "x.ifc",
                    "--georef", value)
    assert code == 2 and "--georef" in doc["error"]["message"]


def test_missing_mesh_exit_3(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    entries = MAPPING + [{"key": "Solids", "class": "IfcWall", "merge": False,
                          "confidence": "low", "rationale": "box"}]
    code, doc = run("convert", path, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 3 and doc["error"]["missingMesh"][0]["key"] == "Solids"


def test_missing_mesh_skipped_key_converts(tmp_path):
    path = make_fixture.build(tmp_path / "solid.3dm", missing_mesh=True)
    entries = MAPPING + [{"key": "Solids", "skip": True, "rationale": "no mesh"}]
    code, doc = run("convert", path, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 0, doc


def test_storey_placement_at_level(ifc):
    f, _ = ifc
    building, = f.by_type("IfcBuilding")
    for storey in f.by_type("IfcBuildingStorey"):
        place = storey.ObjectPlacement
        assert place.PlacementRelTo == building.ObjectPlacement
        assert place.RelativePlacement.Location.Coordinates[2] == storey.Elevation
    column = next(c for c in f.by_type("IfcColumn") if c.Name == "C1")
    assert column.ObjectPlacement.PlacementRelTo is None


def test_reference_context(ifc):
    f, _ = ifc
    ids = {c.ContextIdentifier for c in f.by_type("IfcGeometricRepresentationSubContext")}
    assert ids == {"Body", "Reference"}


@pytest.fixture(scope="module")
def extra_ifc(extra3dm, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("extra")
    out = tmp / "out.ifc"
    code, doc = run("convert", extra3dm, write_mapping(tmp, EXTRA), "-o", out, "--storeys")
    assert code == 0, doc
    return ifcopenshell.open(str(out)), doc


def test_storeys_from_merged_floor_slabs(extra_ifc):
    _, doc = extra_ifc
    assert doc["storeys"] == [0.0, 3.0, 6.0]


def test_block_instance_is_one_element(extra_ifc):
    f, _ = extra_ifc
    chairs = [e for e in f.by_type("IfcFurniture") if pset(e)["LayerPath"] != "Chair"]
    assert len(chairs) == 3
    assert all(len(c.Representation.Representations[0].Items) == 5 for c in chairs)
    assert all(c.Name == "Chair" for c in chairs)


def test_merged_object_ids_capped(extra_ifc):
    f, _ = extra_ifc
    pebbles, = f.by_type("IfcGeographicElement")
    ps = pset(pebbles)
    assert ps["ObjectCount"] == 55 and len(ps["ObjectIds"].split(";")) == 50


def test_merged_layer_paths_joined(extra3dm, tmp_path):
    entries = replace(EXTRA, "block:Chair", dict(EXTRA[1], merge=True))
    out = tmp_path / "x.ifc"
    code, doc = run("convert", extra3dm, write_mapping(tmp_path, entries), "-o", out)
    assert code == 0, doc
    f = ifcopenshell.open(str(out))
    merged, = [e for e in f.by_type("IfcFurniture") if pset(e)["LayerPath"] != "Chair"]
    assert pset(merged)["LayerPath"] == "Furniture;Lounge"


def test_mixed_layer_whole_merged(extra3dm, tmp_path):
    entries = replace(replace(EXTRA, "Facade#2"), "Facade#1", {
        "key": "Facade", "class": "IfcWall", "merge": True,
        "confidence": "medium", "rationale": "the whole facade"})
    out = tmp_path / "x.ifc"
    code, doc = run("convert", extra3dm, write_mapping(tmp_path, entries), "-o", out)
    assert code == 0, doc
    f = ifcopenshell.open(str(out))
    wall, = f.by_type("IfcWall")
    assert wall.Name == "Facade" and len(wall.Representation.Representations[0].Items) == 20


def test_empty_mesh_exit_3(tmp_path):
    path = make_fixture.build_extra(tmp_path / "e.3dm", empty_mesh=True)
    entries = EXTRA + [{"key": "Empty", "class": "IfcWall", "merge": False,
                        "confidence": "low", "rationale": "x"}]
    code, doc = run("convert", path, write_mapping(tmp_path, entries), "-o", tmp_path / "x.ifc")
    assert code == 3 and doc["error"]["missingMesh"][0]["key"] == "Empty"


def test_missing_output_option_exit_2(model3dm, tmp_path):
    code, doc = run("convert", model3dm, write_mapping(tmp_path))
    assert code == 2 and "-o" in doc["error"]["message"] and doc["error"]["fix"]


@pytest.mark.parametrize("target", ["afile/x.ifc", "."])
def test_unwritable_output_exit_2(model3dm, tmp_path, target):
    (tmp_path / "afile").write_text("")
    code, doc = run("convert", model3dm, write_mapping(tmp_path), "-o", tmp_path / target)
    assert code == 2 and "cannot write" in doc["error"]["message"] and doc["error"]["fix"]


def test_internal_error_is_json(monkeypatch, capsys):
    import rhino2ifc

    def boom(args):
        raise ZeroDivisionError("division by zero")
    monkeypatch.setattr(rhino2ifc, "cmd_validate", boom)
    assert rhino2ifc.main(["validate", "x.ifc"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc == {"ok": False, "error": {
        "code": 1, "message": "ZeroDivisionError: division by zero",
        "fix": "internal error; report it with the command and file"}}
