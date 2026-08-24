import math

import numpy as np
import pytest

from abm.metrics import (alignment_mean, side_ratio, side_ratio_stats, valence_tally)


class _P:
    def __init__(self, ring, cls="hyperbolic"):
        self.ring, self.curvature_class, self.touches_boundary = np.asarray(ring, float), cls, False


def test_side_ratio_of_a_regular_hexagon_is_one():
    ang = np.linspace(0, 2 * math.pi, 6, endpoint=False)
    r = np.column_stack([np.cos(ang), np.sin(ang), np.zeros(6)])
    assert side_ratio(_P(r)) == pytest.approx(1.0, abs=1e-12)


def test_side_ratio_of_a_degenerate_ring_is_zero():
    assert side_ratio(_P(np.zeros((4, 3)))) == 0.0


def test_order_statistics_use_raw_nearest_rank_without_interpolation():
    """algorithm.md 4: 'median = rs[n/2], p10 = rs[n/10]' (integer division). A host using an
    interpolating percentile reports slightly different numbers; say which you used."""
    vals = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    plates = [_P(np.zeros((3, 3))) for _ in vals]
    for p, v in zip(plates, vals):
        p._forced = v
    stats = side_ratio_stats(plates, values=vals)
    assert stats.median == pytest.approx(0.5)      # rs[10//2] = rs[5]
    assert stats.p10 == pytest.approx(0.1)         # rs[10//10] = rs[1]
    assert stats.count == 10


def test_alignment_mean_of_a_perfectly_aligned_pair_is_one():
    n = np.array([[0.0, 0.0, 1.0]] * 2)
    e1 = np.array([[1.0, 0.0, 0.0]] * 2)
    p = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    anis = np.array([1.0, 1.0])
    mean, pairs = alignment_mean(p, n, e1, anis, [np.array([1]), np.array([0])], spacing=1.0)
    assert mean == pytest.approx(1.0, abs=1e-12)
    assert pairs == 2                              # ORDERED pairs: both directions counted


def test_alignment_mean_at_the_asymptotic_direction_is_minus_one():
    """phi = 15 deg is a maximum of U = -cos(12 phi): cos(180 deg) = -1."""
    n = np.array([[0.0, 0.0, 1.0]] * 2)
    e1 = np.array([[1.0, 0.0, 0.0]] * 2)
    a = math.radians(15.0)
    p = np.array([[0.0, 0.0, 0.0], [math.cos(a), math.sin(a), 0.0]])
    anis = np.array([1.0, 1.0])
    mean, _ = alignment_mean(p, n, e1, anis, [np.array([1]), np.array([])], spacing=1.0)
    assert mean == pytest.approx(-1.0, abs=1e-9)


def test_alignment_mean_excludes_agents_below_the_anisotropy_gate():
    """algorithm.md 4: population is agents with Anisotropy >= 0.5."""
    n = np.array([[0.0, 0.0, 1.0]] * 2)
    e1 = np.array([[1.0, 0.0, 0.0]] * 2)
    p = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    mean, pairs = alignment_mean(p, n, e1, np.array([0.4, 0.4]),
                                [np.array([1]), np.array([0])], spacing=1.0)
    assert pairs == 0 and mean == 0.0


def test_alignment_mean_reports_zero_pairs_rather_than_a_fake_zero():
    """STATUS: on a sphere the harness prints 'alignment 0.00 over 0 pairs'. That is an ABSENT
    population, not a working metric -- the pair count is what distinguishes them."""
    n = np.array([[0.0, 0.0, 1.0]])
    mean, pairs = alignment_mean(np.zeros((1, 3)), n, np.array([[1.0, 0.0, 0.0]]),
                                 np.array([0.0]), [np.array([], dtype=int)], spacing=1.0)
    assert (mean, pairs) == (0.0, 0)


def test_valence_tally_counts_ring_lengths():
    plates = [_P(np.zeros((6, 3))), _P(np.zeros((6, 3))), _P(np.zeros((5, 3)))]
    assert valence_tally(plates) == {5: 1, 6: 2}
