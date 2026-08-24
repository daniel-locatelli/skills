import math

import numpy as np
import pytest

from abm.seeding import auto_spacing, dominant_principal_angle, hex_seed, random_seed
from abm.surfaces import MongeSurface, SphereSurface


def test_auto_spacing_uses_surface_area():
    """algorithm.md 6: sqrt(A/(0.866.count)) from SURFACE area; 2 quotes 'spacing ~ 1.9'."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    assert auto_spacing(s, 150) == pytest.approx(math.sqrt(s.area() / (0.8660254 * 150)), rel=1e-9)
    assert 1.85 < auto_spacing(s, 150) < 1.95


def test_dominant_principal_angle_on_the_eggcrate_is_15_degrees():
    """algorithm.md 1: 'On the egg-crate the answer is 15 deg.' Also the harness's reported
    'auto angle 15' in STATUS. The single most consequential quantity in the strategy."""
    deg = math.degrees(dominant_principal_angle(MongeSurface(h=3.0, periods=2.0, length=20.0)))
    assert min(abs(deg - 15.0), abs(deg + 15.0)) < 0.5


def test_dominant_principal_angle_is_reduced_mod_30_degrees():
    """12-fold, not 6-fold: atan2(...)/12 lands in [-15, 15] deg. The 12-fold claim is the one
    place a fresh agent is confidently and specifically wrong (STATUS GREEN test, S2)."""
    ang = dominant_principal_angle(MongeSurface(h=3.0, periods=2.0, length=20.0))
    assert -math.pi / 12.0 - 1e-12 <= ang <= math.pi / 12.0 + 1e-12


def test_dominant_principal_angle_returns_zero_on_a_sphere():
    """Umbilic everywhere: every sample has w = anisotropy.(|k1|+|k2|) = 0 and is skipped."""
    assert dominant_principal_angle(SphereSurface(radius=10.0)) == 0.0


def test_hex_seed_realises_fewer_agents_than_the_nominal_count():
    """algorithm.md 1: count is NOMINAL; measured 131 for 150. Section 8's band is 125-135."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    for seed in range(4):
        assert 125 <= len(hex_seed(s, 150, rng=np.random.default_rng(seed))) <= 135


def test_hex_seed_pitch_derives_from_parameter_domain_area_not_surface_area():
    """algorithm.md 1: pitch from du.dv (plan 400), spacing from surface area (479), ~12% apart.
    The packing is therefore seeded denser than its own target and separation expands it."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    pitch = math.sqrt(400.0 / (0.8660254 * 150))
    assert pitch < auto_spacing(s, 150)
    assert pitch / auto_spacing(s, 150) == pytest.approx(0.913, abs=0.01)


def test_hex_seed_margin_is_tested_before_jitter_so_agents_can_be_clamped():
    """algorithm.md 1: the margin is tested on the UN-jittered point and the jitter is applied
    afterwards, so an agent may land outside and be clamped. Reference behaviour, not a bug."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    d = s.domain
    clamped = 0
    for seed in range(6):
        uv = hex_seed(s, 150, hex_jitter=0.9, rng=np.random.default_rng(seed))
        clamped += int(np.sum((uv[:, 0] <= d.u0 + 1e-12) | (uv[:, 0] >= d.u1 - 1e-12)
                              | (uv[:, 1] <= d.v0 + 1e-12) | (uv[:, 1] >= d.v1 - 1e-12)))
    assert clamped > 0


def test_hex_seed_stays_in_domain():
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    d = s.domain
    uv = hex_seed(s, 150, rng=np.random.default_rng(3))
    assert np.all(uv[:, 0] >= d.u0 - 1e-12) and np.all(uv[:, 0] <= d.u1 + 1e-12)
    assert np.all(uv[:, 1] >= d.v0 - 1e-12) and np.all(uv[:, 1] <= d.v1 + 1e-12)


def test_hex_seed_zero_angle_differs_from_auto():
    """The negative control of section 8 depends on these being genuinely different lattices."""
    s = MongeSurface(h=3.0, periods=2.0, length=20.0)
    a = hex_seed(s, 150, hex_angle=0.0, hex_jitter=0.0, rng=np.random.default_rng(1))
    b = hex_seed(s, 150, hex_angle=None, hex_jitter=0.0, rng=np.random.default_rng(1))
    assert a.shape != b.shape or not np.allclose(np.sort(a, axis=0), np.sort(b, axis=0))


def test_random_seed_is_uniform_per_unit_area_not_uniform_in_uv():
    """algorithm.md 1: uniform in uv would over-sample poles and stretched patches. The area
    fraction above |lat| = 60 deg on a sphere is 1 - sin 60 = 0.134; uv-uniform gives 0.333."""
    uv = random_seed(SphereSurface(radius=10.0), 4000, rng=np.random.default_rng(0))
    assert len(uv) == 4000
    assert float(np.mean(np.abs(uv[:, 1]) > math.radians(60.0))) == pytest.approx(0.134, abs=0.02)


def test_random_seed_realises_exactly_count():
    assert len(random_seed(MongeSurface(), 150, rng=np.random.default_rng(2))) == 150
