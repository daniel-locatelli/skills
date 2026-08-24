"""Level 3 -- BTLx export, schema validation and read-back.

Two deliberate constraints shape this module:

  - **The xsd is not vendored.** BTLx schemas are vendor files with no redistribution
    rights -- design2machine's site is the only official channel -- so shipping one would
    redistribute it. Point `BTLX_SCHEMA_DIR` at your own copy of the schema archive. The
    validation test skips when it is absent, so the suite still runs without one.
  - **`xmlschema` is not a dependency of this host.** Validation is optional and needed by
    nothing else here, so rather than adding it to the environment the solver runs in, the
    validator lives in its own venv and this module shells out to it. Point
    `ABM_BTLX_VALIDATOR` at that interpreter, or accept the default location below.

`Version="2.0.0"` is what compas_timber's writer pins (`fabrication/btlx.py:56`), and each
BTLx schema accepts exactly one `Version` value, so 2.0.0 is the schema to validate
against -- confirmed rather than remembered, per the `working-with-btlx` standing rule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from compas_timber.btlx import BTLxReader
from compas_timber.fabrication import BTLxWriter

NAMESPACE = "{https://www.design2machine.com}"
SCHEMA_VERSION = "2.0.0"

# No default: the xsd is a vendor file and is not shipped. Set BTLX_SCHEMA_DIR to the
# directory holding BTLx_2_0_0.xsd; without it, validation reports "not checked".
SCHEMA_DIR = Path(os.environ.get("BTLX_SCHEMA_DIR", ""))
SCHEMA_PATH = SCHEMA_DIR / "BTLx_2_0_0.xsd"

VALIDATOR_PYTHON = Path(
    os.environ.get(
        "ABM_BTLX_VALIDATOR",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "abm-btlx-validator", "Scripts", "python.exe"),
    )
)

_VALIDATE = """
import json, sys
import xmlschema
schema = xmlschema.XMLSchema(sys.argv[1])
print(json.dumps([str(e) for e in schema.iter_errors(sys.argv[2])]))
"""


def validator_available() -> bool:
    return VALIDATOR_PYTHON.is_file() and SCHEMA_PATH.is_file()


def export_btlx(model, path) -> None:
    """Write `model` to `path`.

    The cached element geometry is dropped first, and that is a WORKAROUND, not tidiness.
    `BTLxWriter._create_part` writes the optional `<Shape>` block only `if element._geometry`
    -- i.e. only when something happened to touch `.geometry` earlier in the process -- and
    building that block raises `AttributeError: 'Plane' object has no attribute 'frame_at'`
    on COMPAS 2.15.1, because a planar `OccBrepFace.surface` is a `Plane` and
    `fabrication/btlx.py:654` calls `frame_at(0.5, 0.5)` on it. Our own Level 2 solid check
    touches `.geometry` on every plate, so every export would crash.

    `<Shape>` is `minOccurs="0"` in the 2.0.0 xsd, so dropping it is schema-legal and costs
    only the display mesh; the machining data is in the processings. Both halves of this go
    upstream: the crash, and the export silently depending on access history.
    """
    for element in model.elements():
        element._geometry = None
    BTLxWriter().write(model, str(path))


def validate_btlx(path, xsd=None) -> List[str]:
    """Validation errors against the BTLx xsd; `[]` means clean.

    Shells out to the validator venv (see the module docstring). Raises if that venv or the
    schema archive is missing rather than returning `[]` -- "no errors" and "nothing was
    checked" must never be the same value.
    """
    xsd = Path(xsd) if xsd is not None else SCHEMA_PATH
    if not VALIDATOR_PYTHON.is_file():
        raise FileNotFoundError(
            f"the BTLx validator venv is missing at {VALIDATOR_PYTHON}; "
            "create it with `python -m venv <path> && <path>/Scripts/python -m pip install xmlschema` "
            "or point ABM_BTLX_VALIDATOR at one."
        )
    if not xsd.is_file():
        raise FileNotFoundError(
            f"the BTLx schema is missing at {xsd}; point BTLX_SCHEMA_DIR at the archive. "
            "The xsd is a vendor file and is deliberately not in this repository."
        )
    proc = subprocess.run(
        [str(VALIDATOR_PYTHON), "-c", _VALIDATE, str(xsd), str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"the BTLx validator failed:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def declared_version(path) -> str:
    return ET.parse(str(path)).getroot().get("Version", "")


def element_numbers(model) -> List[str]:
    """`ElementNumber` as the writer produces it: `str(guid)[:4]`.

    Sixteen bits. The birthday probability of a collision is ~5 % at 85 parts and ~16 % at
    151 -- and 150 plates is this strategy's own stated target, so the field is unusable as
    an identifier at exactly the size the work is done at.
    """
    return [str(element.guid)[:4] for element in model.elements()]


def read_back(path) -> Dict[str, Any]:
    """Re-read an exported file through compas_timber's own reader.

    Assert **part count, thickness and blank PRESENCE** off this -- not outline identity and
    not exact blank length/width. The reader rebuilds every plate as a rectangular blank and
    duplicates the contour, and blank orientation differs between 2.2.0 and main and will
    flip when main is released. `contour_counts` is here to record that lossiness rather
    than let it be mistaken for a host bug.
    """
    model = BTLxReader().read(str(path))
    elements = list(model.elements())
    thicknesses, dimensions, contours = [], [], []
    for element in elements:
        blank = element.blank
        thicknesses.append(float(element.thickness))
        dimensions.append((float(blank.xsize), float(blank.ysize), float(blank.zsize)))
        contours.append(sum(1 for f in element.features if "Contour" in type(f).__name__))

    root = ET.parse(str(path)).getroot()
    return {
        "version": root.get("Version", ""),
        "part_count": len(elements),
        "xml_part_count": len(root.findall(f".//{NAMESPACE}Part")),
        "thicknesses": thicknesses,
        "blank_dimensions": dimensions,
        "contour_counts": contours,
        "element_numbers": [p.get("ElementNumber") for p in root.findall(f".//{NAMESPACE}Part")],
        "has_shape_block": bool(root.findall(f".//{NAMESPACE}Shape")),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python btlx.py <file.btlx>", file=sys.stderr)
        return 2
    errors = validate_btlx(argv[0])
    print(f"{argv[0]}: {len(errors)} validation errors against {SCHEMA_PATH.name}")
    for error in errors[:20]:
        print("  " + error.splitlines()[0])
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
