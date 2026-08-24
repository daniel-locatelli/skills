import math

import numpy as np
import pytest

from abm.plates import is_convex_ring

N = np.array([0.0, 0.0, 1.0])


def ring(n, turns=1, radius=1.0, scale=1.0):
    """Regular star polygon {n/turns}; turns=1 gives a convex n-gon."""
    ang = np.array([2 * math.pi * turns * i / n for i in range(n)])
    return scale * radius * np.column_stack([np.cos(ang), np.sin(ang), np.zeros(n)])


@pytest.mark.parametrize("n", [4, 6])
@pytest.mark.parametrize("wind", [1, -1])
def test_convex_polygons_both_windings(n, wind):
    r = ring(n)[::wind]
    assert is_convex_ring(r, N, 1.0)


def test_bowtie_is_not_convex():
    r = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])
    assert not is_convex_ring(r, N, 1.0)


def test_l_shape_is_not_convex():
    r = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0],
                  [1.0, 1.0, 0.0], [1.0, 2.0, 0.0], [0.0, 2.0, 0.0]])
    assert not is_convex_ring(r, N, 1.0)


def test_pentagram_is_not_convex():
    """All five turns agree in sign; total turning is 4pi. The turn-sign half alone says
    'convex' -- this is the bug the simplicity half exists to catch (algorithm.md 3.3)."""
    assert not is_convex_ring(ring(5, turns=2), N, 1.0)


@pytest.mark.parametrize("turns", [2, 3])
def test_heptagram_is_not_convex(turns):
    assert not is_convex_ring(ring(7, turns=turns), N, 1.0)


def test_hexagon_walked_twice_is_not_convex():
    r = np.vstack([ring(6), ring(6)])
    assert not is_convex_ring(r, N, 1.0)


def test_collinear_ring_is_not_convex():
    """algorithm.md 3.3: 'a ring whose every turn fell below the threshold is collinear,
    not convex'. The reference returned true here."""
    r = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    assert not is_convex_ring(r, N, 1.0)


def test_two_vertex_ring_is_not_convex():
    assert not is_convex_ring(np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]), N, 1.0)


def test_reversal_below_the_turn_threshold_is_not_convex():
    """algorithm.md 3.3: 'a turn that is a reversal (below the threshold but with the two
    edges antiparallel) is the ring doubling back on itself'."""
    r = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 0.0, 0.0],
                  [0.5, 1.0, 0.0], [0.0, 1.0, 0.0]])
    assert not is_convex_ring(r, N, 1.0)


def test_the_threshold_is_relative_to_spacing():
    """algorithm.md 2/3.3: 'ep.Spacing^2', NOT an absolute 1e-12. The same shapes at
    millimetre scale must give the same answers."""
    assert is_convex_ring(ring(6, scale=1000.0), N, 1000.0)
    assert not is_convex_ring(ring(5, turns=2, scale=1000.0), N, 1000.0)
    assert is_convex_ring(ring(6, scale=0.001), N, 0.001)
    assert not is_convex_ring(ring(5, turns=2, scale=0.001), N, 0.001)


def test_sub_tolerance_3d_noise_does_not_flip_a_convex_hexagon():
    """A real plate is planar by construction but not to the last bit."""
    rng = np.random.default_rng(0)
    r = ring(6) + rng.normal(scale=1e-13, size=(6, 3))
    assert is_convex_ring(r, N, 1.0)
