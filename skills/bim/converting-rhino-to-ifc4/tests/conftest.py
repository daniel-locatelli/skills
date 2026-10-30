import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE.parent / "scripts" / "rhino2ifc.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCRIPT.parent))

import make_fixture  # noqa: E402

MAPPING = [
    {"key": "Existing::Stützen", "class": "IfcColumn", "merge": False,
     "confidence": "high", "rationale": "vertical, slender; 'Stützen' = columns"},
    {"key": "Layer 01#1", "class": "IfcColumn", "merge": False,
     "confidence": "medium", "rationale": "linear-vertical"},
    {"key": "Layer 01#2", "class": "IfcSlab", "predefinedType": "floor", "merge": False,
     "confidence": "medium", "rationale": "plate-horizontal at two levels"},
    {"key": "Terrain", "class": "IfcGeographicElement", "predefinedType": "TERRAIN",
     "merge": True, "confidence": "high", "rationale": "flat mesh named Terrain"},
    {"key": "Chair", "class": "IfcFurniture", "merge": False,
     "confidence": "high", "rationale": "block named Chair"},
    {"key": "Set", "class": "IfcFurniture", "merge": False,
     "confidence": "medium", "rationale": "block nesting a chair"},
]


def run(*args):
    """Run the CLI; (exit code, parsed stdout JSON)."""
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout)


def write_mapping(tmp_path, entries=MAPPING, schema="IFC4"):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"schema": schema, "entries": entries}), encoding="utf-8")
    return path


def layer(inv, key):
    return next(rec for rec in inv["layers"] if rec["key"] == key)


@pytest.fixture(scope="session")
def model3dm(tmp_path_factory):
    return make_fixture.build(tmp_path_factory.mktemp("m") / "fixture.3dm")
