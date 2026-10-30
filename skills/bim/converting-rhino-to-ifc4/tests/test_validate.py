import ifcopenshell
import ifcopenshell.guid

from conftest import run, write_mapping


def test_valid_file(model3dm, tmp_path):
    out = tmp_path / "out.ifc"
    assert run("convert", model3dm, write_mapping(tmp_path), "-o", out)[0] == 0
    code, report = run("validate", out)
    assert code == 0, report
    assert report["ok"] and report["schema"] == "IFC4"
    assert report["schemaErrorCount"] == 0 and report["withoutGeometry"] == []
    assert report["identity"] == {"IfcOwnerHistory": 0, "IfcPerson": 0, "IfcOrganization": 0}
    assert report["header"] == {"author": [""], "organization": [""]}
    assert report["elements"]["IfcColumn"] == 5


def test_element_without_geometry_exit_4(tmp_path):
    f = ifcopenshell.file(schema="IFC4")
    f.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="bare")
    path = tmp_path / "bare.ifc"
    f.write(str(path))
    code, report = run("validate", path)
    assert code == 4 and not report["ok"] and len(report["withoutGeometry"]) == 1


def test_schema_error_exit_4(tmp_path):
    f = ifcopenshell.file(schema="IFC4")
    f.create_entity("IfcWall", GlobalId="not-a-guid", Name="bad")
    path = tmp_path / "bad.ifc"
    f.write(str(path))
    code, report = run("validate", path)
    assert code == 4 and report["schemaErrorCount"] >= 1


def test_unreadable_file_exit_2(tmp_path):
    code, doc = run("validate", tmp_path / "nope.ifc")
    assert code == 2 and "cannot open" in doc["error"]["message"]


def test_valid_ifc4x3_file(model3dm, tmp_path):
    out = tmp_path / "out.ifc"
    code, doc = run("convert", model3dm, write_mapping(tmp_path, schema="IFC4X3_ADD2"), "-o", out,
                    "--storeys", "--georef", "EPSG:2056,1,2,3", "--north", "North")
    assert code == 0, doc
    code, report = run("validate", out)
    assert code == 0, report
    assert report["schema"] == "IFC4X3_ADD2" and report["schemaErrorCount"] == 0
