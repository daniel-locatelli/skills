"""Level 2 -- the compas_timber stage.

Three of the plan's tests for this task were ill-posed and are corrected here, each with
the reason in its docstring. That is the fourth, fifth and sixth such correction in this
host; the standing rule is to decide whether the test or the implementation is wrong
before touching either, and in all six cases it was the test.
"""

import math

import numpy as np
import pytest

pytest.importorskip("compas_timber")

from timber import (PLANARITY_BUDGET, RejectionReason, build_model, build_timber_model,
                    is_valid_solid, planarise, rotate_to_sharpest_corner)


def _hex(radius=1000.0):
    ang = np.linspace(0, 2 * math.pi, 6, endpoint=False)
    return np.column_stack([radius * np.cos(ang), radius * np.sin(ang), np.zeros(6)])


def _coplanarity(ring):
    """Max distance from the ring's own best-fit plane -- frame-independent."""
    centred = ring - ring.mean(axis=0)
    normal = np.linalg.svd(centred, full_matrices=False)[2][-1]
    return float(np.max(np.abs(centred @ normal)))


def test_planarise_returns_a_zero_residual_for_a_planar_ring():
    _, residual = planarise(_hex())
    assert residual < 1e-12


def test_planarise_projects_a_lifted_vertex_and_reports_the_residual():
    """CORRECTED. The plan asserted the OUTPUT ring has constant z, which is only true if
    the fitted plane is horizontal. It is not: a least-squares plane through five vertices
    at z=0 and one at z=0.5 tilts towards the lifted one by ~1.4e-4, so the projected z
    spreads over ~0.17 -- eight orders above the 1e-9 the plan asserted. What planarisation
    owes is COPLANARITY, not horizontality, so that is what is asserted.
    """
    r = _hex()
    r[2, 2] = 0.5
    out, residual = planarise(r)
    assert residual > 0.0
    assert _coplanarity(out) < 1e-9
    assert _coplanarity(r) == pytest.approx(residual, rel=1e-9)


def test_planarise_moves_each_vertex_along_the_plane_normal_only():
    """A projection, not a re-fit: the in-plane footprint must survive. Otherwise the
    plate's outline is silently a different shape from the one the geometry produced."""
    r = _hex()
    r[2, 2] = 0.5
    out, _ = planarise(r)
    shifts = out - r
    directions = shifts / np.linalg.norm(shifts, axis=1, keepdims=True)
    assert np.allclose(np.abs(directions @ directions[0]), 1.0)


def test_planarity_budget_is_the_measured_one_not_the_nominal_one():
    """PlateGeometry rejects outline_a at 1e-9 absolute, but the measured
    usable budget is 3.3e-10 and varies by vertex index."""
    assert PLANARITY_BUDGET == pytest.approx(3.3e-10)
    assert PLANARITY_BUDGET < 1e-9


def test_rotate_to_sharpest_corner_puts_the_sharpest_vertex_first():
    """Upstream, plate_geometry.py:211 -- the frame-derivation loop never breaks, so `pt_c`
    always settles on outline[2] and the frame is Frame.from_points(p0, p1, p2) over three
    CONSECUTIVE vertices. What has to be maximised is therefore that triple's conditioning,
    |(p1-p0) x (p2-p0)| normalised, and the rotation that does it here starts at (50,101).
    Note that vertex is the outline's FLATTEST corner, not its sharpest -- the plan's name
    for the function describes the wrong end of the measure, and is kept only because the
    plan's own expected value is the conditioning-optimal one.
    """
    r = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 100.0, 0.0],
                  [50.0, 101.0, 0.0], [0.0, 100.0, 0.0]])
    out = rotate_to_sharpest_corner(r)
    assert np.allclose(out[0], [50.0, 101.0, 0.0])
    assert len(out) == len(r)
    assert {tuple(p) for p in out} == {tuple(p) for p in r}


def test_a_convex_plate_builds_with_the_expected_volume():
    model, rejections = build_model([_hex()], thickness=20.0)
    assert not rejections
    assert len(list(model.elements())) == 1
    expected = 1.5 * math.sqrt(3.0) * 1000.0 ** 2 * 20.0
    volume = list(model.elements())[0].geometry.volume
    assert volume == pytest.approx(expected, rel=1e-3)


def test_a_self_intersecting_plate_is_rejected_by_name():
    """A true bow-tie is accepted silently by compas_timber and yields a Brep
    reporting is_solid=True with NEGATIVE volume and is_valid=False. A host guarding on
    is_solid passes it straight through."""
    bow = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [0.0, 1000.0, 0.0],
                    [1000.0, 1000.0, 0.0]])
    model, rejections = build_model([bow], thickness=20.0)
    assert len(list(model.elements())) == 0
    assert rejections[0][1] is RejectionReason.SELF_INTERSECTING


def test_is_valid_solid_guards_on_validity_and_volume_not_on_is_solid():
    class _Fake:
        is_solid, is_valid, volume = True, False, -1.0
    assert not is_valid_solid(_Fake())


def test_a_reflex_but_simple_plate_is_accepted():
    """spec: 'a strongly reflex outline is accepted with an exactly correct solid volume'.
    Concave is normal on a hyperbolic surface; only SELF-INTERSECTING is a defect."""
    r = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [1000.0, 1000.0, 0.0],
                  [500.0, 300.0, 0.0], [0.0, 1000.0, 0.0]])
    model, rejections = build_model([r], thickness=20.0)
    assert not rejections and len(list(model.elements())) == 1


def test_a_non_planar_ring_is_rejected_by_name_when_it_is_not_planarised_first():
    """NON_PLANAR has to be a live criterion, not a dead branch: build_model is the last
    gate before PlateGeometry, which fails on a lifted vertex with a ValueError that names
    the XY-plane rather than the caller's ring."""
    r = _hex()
    r[2, 2] = 1.0
    model, rejections = build_model([r], thickness=20.0)
    assert len(list(model.elements())) == 0
    assert rejections[0][1] is RejectionReason.NON_PLANAR


def test_a_sliver_plate_is_rejected_by_min_side_when_a_minimum_is_declared():
    """spec Level 2 names 'min side < 0.05*spacing' as one of the three pre-declared
    criteria. It is only meaningful relative to spacing, so build_model takes it as an
    argument rather than inventing a length of its own."""
    r = np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [1000.0, 1000.0, 0.0],
                  [1000.0, 1000.5, 0.0], [0.0, 1000.0, 0.0]])
    model, rejections = build_model([r], thickness=20.0, min_side=100.0)
    assert len(list(model.elements())) == 0
    assert rejections[0][1] is RejectionReason.MIN_SIDE


def test_the_model_tolerance_is_millimetres():
    """spec [M]: TimberModel(tolerance=Tolerance(unit='MM')) suppresses the silent x1000
    export scaling."""
    model, _ = build_model([_hex()], thickness=20.0)
    assert model.tolerance.unit == "MM"


def test_a_json_round_trip_loses_the_tolerance_and_must_be_rebuilt():
    """spec [M], a live trap: TimberModel.__data__ has no 'tolerance' key, so a
    compas.json_dumps round-trip silently reverts MM -> M and exporting from the reloaded
    model is 1000x off. Upstream, a one-key fix."""
    from compas import json_dumps, json_loads
    model, _ = build_model([_hex()], thickness=20.0)
    reloaded = json_loads(json_dumps(model))
    assert reloaded.tolerance.unit != "MM"          # the trap, asserted so it cannot regress silently


def test_plates_are_identified_by_guid_not_key():
    """Upstream: Plate documents a `key` attribute that does not exist (plate.py:72)."""
    model, _ = build_model([_hex()], thickness=20.0)
    plate = list(model.elements())[0]
    assert plate.guid is not None
    assert not hasattr(plate, "key") or plate.key is None


@pytest.mark.slow
def test_the_full_eggcrate_run_builds_every_interior_plate_or_names_its_rejection():
    """spec Level 2: element count = post-drop minus rejected, and every rejection has a
    pre-declared reason.

    CORRECTED. The plan wrote `element_count == plate_count - rejected_count`, but
    `plate_count` is the PRE-drop count (119 on this configuration) and the timber stage is
    fed the 85 interior plates -- the boundary drop is normative and happens before it. The
    identity is against `interior_plate_count`. The keys also live in the payload's
    `timber` block, which is the contract run.py already publishes, not at the top level.
    """
    from run import build_config, run
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--thickness", "0.02"]))
    timber = out["timber"]
    assert timber["element_count"] == out["interior_plate_count"] - timber["rejected_count"]
    assert set(timber["rejections_by_reason"]) <= {r.name for r in RejectionReason}


@pytest.mark.slow
def test_the_metre_to_millimetre_conversion_happens_once_at_this_boundary():
    """The solver works in metres (spacing ~1.92); compas_timber works in millimetres. A
    conversion applied twice, or not at all, is a factor of 1e6 or 1e-3 and both look
    plausible in a viewport -- so it is asserted against the declared thickness."""
    from run import build_config, run
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--thickness", "0.02"]))
    assert out["spacing"] == pytest.approx(1.9207, abs=1e-3)          # metres, unchanged
    assert out["timber"]["thickness_mm"] == pytest.approx(20.0)
    assert 500.0 < out["timber"]["blank_length_mm"]["median"] < 5000.0


@pytest.mark.slow
def test_planarisation_answers_the_fallback_deviation_A4_measured():
    """50 of 85 interior plates carry a fallback vertex and deviate from the
    tangent plane by up to 11 % of spacing. After planarisation every ring is coplanar to
    machine precision, and the shift it took to get there is reported rather than hidden."""
    from run import build_config, run
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--thickness", "0.02"]))
    assert out["planarity_residual"]["max"] > 0.1                     # metres, pre-planarisation
    assert out["timber"]["coplanarity_after_mm"]["max"] < PLANARITY_BUDGET
    assert out["timber"]["planarisation_shift_rms_mm"]["max"] > 0.0
    # the least-squares plane is a better plane than the tangent plane, and measurably so:
    # 135.5 mm worst residual against the tangent plane's 208 mm
    assert out["timber"]["planarity_residual_mm"]["max"] < out["planarity_residual"]["max"] * 1000.0


def test_build_timber_model_reports_a_named_reason_for_every_missing_element():
    """The payload's own accounting identity, on a set small enough to check by hand."""
    rings = [_hex(), np.array([[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [0.0, 1000.0, 0.0],
                               [1000.0, 1000.0, 0.0]])]
    model, rejections = build_model(rings, thickness=20.0)
    assert len(list(model.elements())) + len(rejections) == len(rings)
