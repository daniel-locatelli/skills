"""Level 3 -- BTLx export, schema validation and read-back.

Note what is NOT here: `pytest.importorskip("xmlschema")`. `xmlschema` is deliberately
not a dependency of this host (validation is optional and is needed by none of its
dependencies), so that line would skip this whole module every time it ran. Validation is
shelled out to its own venv and only the validation test skips, and only when that venv or
the schema archive is missing.
"""

import math

import numpy as np
import pytest

pytest.importorskip("compas_timber")

from btlx import (SCHEMA_PATH, VALIDATOR_PYTHON, declared_version, element_numbers,
                  export_btlx, read_back, validate_btlx, validator_available)
from timber import build_model

needs_validator = pytest.mark.skipif(
    not validator_available(),
    reason=f"needs the validator venv at {VALIDATOR_PYTHON} and the schema at {SCHEMA_PATH}",
)


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """CORRECTED: the payload key is `timber_model` (the model is not in the JSON block),
    and `--thickness` is in METRES like everything upstream of timber.py -- the plan's `20`
    would have been a twenty-metre plate."""
    from run import build_config, run
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--thickness", "0.02"]))
    path = tmp_path_factory.mktemp("btlx") / "eggcrate.btlx"
    export_btlx(out["timber_model"], path)
    return path, out


@pytest.mark.slow
@needs_validator
def test_btlx_validates_against_the_archived_schema(exported):
    """spec Level 3: schema validation is a SOLVED problem, not a risk. Measured here: the
    85-part egg-crate export validates against the real BTLx 2.0.0 xsd with 0 errors."""
    path, _ = exported
    assert validate_btlx(path) == []


@pytest.mark.slow
def test_the_export_declares_the_version_its_schema_accepts(exported):
    """Each BTLx schema accepts exactly one `Version`, so validating against the wrong one
    fails on the root element and nothing else. compas_timber pins 2.0.0."""
    assert declared_version(exported[0]) == "2.0.0"


@pytest.mark.slow
def test_part_count_survives_the_round_trip(exported):
    """CORRECTED: the element count lives in the payload's `timber` block."""
    path, out = exported
    assert read_back(path)["part_count"] == out["timber"]["element_count"]


@pytest.mark.slow
def test_thickness_survives_the_round_trip(exported):
    path, _ = exported
    assert all(t == pytest.approx(20.0, rel=1e-6) for t in read_back(path)["thicknesses"])


@pytest.mark.slow
def test_blanks_are_present_but_their_dimensions_are_not_asserted(exported):
    """spec Level 3 [M]: assert blank PRESENCE, not exact length/width -- blank orientation
    differs between 2.2.0 and main and will flip when main is released."""
    back = read_back(exported[0])
    assert len(back["blank_dimensions"]) == back["part_count"]
    assert all(all(d > 0 for d in dim) for dim in back["blank_dimensions"])


@pytest.mark.slow
def test_the_reader_duplicates_contours_so_outlines_are_not_asserted(exported):
    """The reader rebuilds every plate as a rectangular blank and duplicates
    the contour. Asserted so the lossiness is recorded rather than mistaken for a host bug:
    every part comes back with exactly two contour features, not the one that was written."""
    counts = read_back(exported[0])["contour_counts"]
    assert set(counts) == {2}


@pytest.mark.slow
def test_the_shape_block_is_absent_and_why(exported):
    """Why `export_btlx` clears the geometry cache: building `<Shape>`
    raises on COMPAS 2.15.1 (`'Plane' object has no attribute 'frame_at'`), and the writer
    only attempts it when something has touched `.geometry` -- which our own Level 2 solid
    check does on every plate. `<Shape>` is minOccurs="0", so dropping it is schema-legal."""
    assert read_back(exported[0])["has_shape_block"] is False


def test_the_shape_block_is_what_breaks_the_writer_measured_not_assumed():
    """The workaround is only justified while the thing it works around is real, so the
    crash is pinned. If upstream fixes `shape_strings`, this test fails and `export_btlx`
    can drop the cache-clearing line."""
    from compas_timber.fabrication.btlx import BTLxPart
    ang = np.linspace(0, 2 * math.pi, 6, endpoint=False)
    ring = np.column_stack([1000 * np.cos(ang), 1000 * np.sin(ang), np.zeros(6)])
    model, _ = build_model([ring], thickness=20.0)
    element = list(model.elements())[0]
    assert element._geometry is not None          # Level 2's solid check cached it
    with pytest.raises(AttributeError, match="frame_at"):
        BTLxPart(element, order_num=0).shape_strings


@pytest.mark.slow
def test_element_number_is_four_hex_digits_of_the_guid_and_collides_at_this_scale(exported):
    """Upstream: `ElementNumber` is `str(guid)[:4]` -- 16 bits (`fabrication/btlx.py:452`).

    CORRECTED. The plan asserted a collision, with an `or True` that made the assertion
    vacuous. A collision is a BIRTHDAY event, ~5 % at 85 parts and ~16 % at 151, so
    asserting one either way is asserting a coin toss -- the same class of error as A7.
    What is deterministic is the MECHANISM, so that is what is asserted; the probability is
    150 plates being this strategy's own target is the point.
    """
    path, out = exported
    written = read_back(path)["element_numbers"]
    assert written == element_numbers(out["timber_model"])
    assert all(len(n) == 4 for n in written)
    assert 1 - math.exp(-len(written) * (len(written) - 1) / (2 * 16 ** 4)) > 0.05
