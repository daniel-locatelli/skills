import ifcopenshell
import pytest

import make_fixture
from conftest import MAPPING, run, write_mapping


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
                    "--storeys", "3,0,6")
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


@pytest.mark.parametrize("value", ["2056,1,2,3", "EPSG:2056,1,2", "EPSG:x,1,2,3"])
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
