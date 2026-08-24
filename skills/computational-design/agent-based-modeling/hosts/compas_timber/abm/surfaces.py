"""Surface contract (algorithm.md 5) and the two analytic test surfaces (9).

Kernel-neutral by construction: nothing in this module imports COMPAS. `derivatives_at`
is a first-class requirement of the contract, not a convenience -- the auto hex-seed angle
needs the first fundamental form, and an orthonormal frame has already discarded E, F and G.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Tuple

import numpy as np

Vec = np.ndarray


@dataclass(frozen=True)
class Domain:
    u0: float
    u1: float
    v0: float
    v1: float

    @property
    def du(self) -> float:
        return self.u1 - self.u0

    @property
    def dv(self) -> float:
        return self.v1 - self.v0

    @property
    def mid(self) -> Tuple[float, float]:
        return (0.5 * (self.u0 + self.u1), 0.5 * (self.v0 + self.v1))


@dataclass(frozen=True)
class Topology:
    """Per direction: closed (seam) / singular (pole) / real boundary.

    Real boundaries get containment; seams and poles do not (algorithm.md 1, 5).
    """

    closed_u: bool = False
    closed_v: bool = False
    singular_u0: bool = False
    singular_u1: bool = False
    singular_v0: bool = False
    singular_v1: bool = False

    @property
    def boundary_u0(self) -> bool:
        return not (self.closed_u or self.singular_u0)

    @property
    def boundary_u1(self) -> bool:
        return not (self.closed_u or self.singular_u1)

    @property
    def boundary_v0(self) -> bool:
        return not (self.closed_v or self.singular_v0)

    @property
    def boundary_v1(self) -> bool:
        return not (self.closed_v or self.singular_v1)

    @property
    def is_non_trivial(self) -> bool:
        return any(
            (
                self.closed_u,
                self.closed_v,
                self.singular_u0,
                self.singular_u1,
                self.singular_v0,
                self.singular_v1,
            )
        )

    @property
    def is_closed_surface(self) -> bool:
        return not (
            self.boundary_u0 or self.boundary_u1 or self.boundary_v0 or self.boundary_v1
        )


class Surface(Protocol):
    domain: Domain
    topology: Topology

    def point_at(self, u: float, v: float) -> Vec: ...

    def normal_at(self, u: float, v: float) -> Vec: ...

    def derivatives_at(self, u: float, v: float) -> Tuple[Vec, Vec]: ...

    def gaussian_at(self, u: float, v: float) -> float: ...

    def principal_at(self, u: float, v: float) -> Tuple[float, float, Vec]: ...

    def closest_uv(self, p: Vec, hint_u: float, hint_v: float) -> Tuple[float, float]: ...

    def area(self, n: int = 48) -> float: ...


def anisotropy(k1: float, k2: float) -> float:
    """|k1 - k2| / (|k1| + |k2|), clamped to 1, zero when both vanish (algorithm.md 4)."""
    denom = abs(k1) + abs(k2)
    if denom <= 0.0:
        return 0.0
    return min(1.0, abs(k1 - k2) / denom)


def _shape_operator(e_, f_, g_, l_, m_, nn):
    """S = I^-1 . II, with I^-1 = 1/det [[G, -F], [-F, E]]."""
    det_i = e_ * g_ - f_ * f_
    if abs(det_i) < 1e-18:
        return None
    return np.array(
        [
            [(g_ * l_ - f_ * m_) / det_i, (g_ * m_ - f_ * nn) / det_i],
            [(e_ * m_ - f_ * l_) / det_i, (e_ * nn - f_ * m_) / det_i],
        ]
    )


def _eig2(shape):
    """Closed-form eigen-decomposition of a real 2x2 with real eigenvalues.

    Returned as (k1, k2, (alpha, beta)) with |k1| >= |k2| and (alpha, beta) the
    eigenvector of k1. Closed form rather than np.linalg.eig because the solver evaluates
    this once per agent per iteration -- of the order of 10^5 times in a single run.

    The shape operator is self-adjoint with respect to the first fundamental form, not
    with respect to the identity, so it is generally NOT symmetric and eigh is wrong here.
    Its eigenvalues are real all the same (they are the principal curvatures), so the
    discriminant is clamped at zero against rounding rather than treated as a failure.
    """
    a11, a12 = float(shape[0, 0]), float(shape[0, 1])
    a21, a22 = float(shape[1, 0]), float(shape[1, 1])
    tr = a11 + a22
    det = a11 * a22 - a12 * a21
    disc = math.sqrt(max(0.0, tr * tr - 4.0 * det))
    lo, hi = 0.5 * (tr - disc), 0.5 * (tr + disc)
    k1, k2 = (hi, lo) if abs(hi) >= abs(lo) else (lo, hi)
    # The off-diagonal test is RELATIVE (section 2), and that is not a refinement. On any
    # surface whose parametrisation is already principal -- every surface of revolution:
    # tube, cone, dome, vault -- the off-diagonals are rounding noise at 1e-17 rather than
    # exact zeros. An absolute test takes the `(a12, k1 - a11)` branch, where BOTH
    # components are noise, and builds an eigenvector whose norm is below the 1e-14 floor
    # in _principal_from_shape. That returns the zero vector, `anisotropy` is then forced
    # to 0, and the 12-fold alignment field goes silently inert on exactly the surfaces
    # whose anisotropy it exists to exploit.
    scale = max(abs(a11), abs(a12), abs(a21), abs(a22))
    off = 1e-12 * scale
    if abs(a12) > off:
        vec = (a12, k1 - a11)
    elif abs(a21) > off:
        vec = (k1 - a22, a21)
    else:                                     # diagonal: u and v are already principal
        vec = (1.0, 0.0) if abs(a11 - k1) <= abs(a22 - k1) else (0.0, 1.0)
    return k1, k2, vec


def _principal_from_shape(shape, su, sv, n):
    """|k1| >= |k2|, e1 = alpha.Su + beta.Sv.

    E1 is re-tangentialised and re-normalised afterwards (algorithm.md 4) -- a kernel's
    principal direction is not guaranteed to be exactly tangent.
    """
    k1, k2, (alpha, beta) = _eig2(shape)
    e1 = alpha * su + beta * sv
    e1 = e1 - n * float(e1 @ n)
    nrm = float(np.linalg.norm(e1))
    if nrm < 1e-14:
        return k1, k2, np.zeros(3)
    return k1, k2, e1 / nrm


def _principal_from_forms(su, sv, suu, suv, svv, n):
    e_, f_, g_ = float(su @ su), float(su @ sv), float(sv @ sv)
    l_, m_, nn = float(suu @ n), float(suv @ n), float(svv @ n)
    shape = _shape_operator(e_, f_, g_, l_, m_, nn)
    if shape is None:
        return 0.0, 0.0, np.zeros(3)
    return _principal_from_shape(shape, su, sv, n)


def fd_principal(surface: Surface, u: float, v: float, h_rel: float = 1e-4):
    """Principal curvatures from point_at/normal_at alone (algorithm.md 5.1).

    The portable fallback for a kernel that exposes neither second derivatives nor
    principal directions -- a common situation, and worth checking before committing to a
    kernel. Uses L = -Su.Nu, M = -(Su.Nv + Sv.Nu)/2, Nn = -Sv.Nv.
    """
    d = surface.domain
    hu, hv = h_rel * d.du, h_rel * d.dv
    su = (surface.point_at(u + hu, v) - surface.point_at(u - hu, v)) / (2.0 * hu)
    sv = (surface.point_at(u, v + hv) - surface.point_at(u, v - hv)) / (2.0 * hv)
    nu = (surface.normal_at(u + hu, v) - surface.normal_at(u - hu, v)) / (2.0 * hu)
    nv = (surface.normal_at(u, v + hv) - surface.normal_at(u, v - hv)) / (2.0 * hv)
    n = surface.normal_at(u, v)
    e_, f_, g_ = float(su @ su), float(su @ sv), float(sv @ sv)
    l_ = -float(su @ nu)
    m_ = -0.5 * (float(su @ nv) + float(sv @ nu))
    nn = -float(sv @ nv)
    shape = _shape_operator(e_, f_, g_, l_, m_, nn)
    if shape is None:
        return 0.0, 0.0, np.zeros(3)
    return _principal_from_shape(shape, su, sv, n)


def _grid_area(surface: Surface, n: int) -> float:
    """|Su x Sv| integrated on an n x n cell-centred grid (algorithm.md 5)."""
    d = surface.domain
    cell = (d.du / n) * (d.dv / n)
    total = 0.0
    for i in range(n):
        u = d.u0 + d.du * (i + 0.5) / n
        for j in range(n):
            v = d.v0 + d.dv * (j + 0.5) / n
            su, sv = surface.derivatives_at(u, v)
            total += float(np.linalg.norm(np.cross(su, sv))) * cell
    return total


class MongeSurface:
    """z = h.cos(w x).cos(w y), w = periods.pi/length, on [-L/2, L/2]^2 (algorithm.md 9).

    `projection` selects the closest-point rule:

    "closest"   normative (algorithm.md 5): the true closest point on the surface, by
                Newton on |S(u,v) - p|^2 from the agent's current parameter.
    "vertical"  the reference harness's flagged approximation (Program.cs:31),
                u = clamp(p.x), v = clamp(p.y). On the egg-crate's ~43 degree flanks it
                stretches the re-projected tangential step by ~1/cos(slope) = 1.37,
                concentrated exactly where the side ratio is measured. Kept so that any
                divergence from section 8 is attributable instead of mysterious.
    """

    def __init__(
        self,
        h: float = 3.0,
        periods: float = 2.0,
        length: float = 20.0,
        projection: str = "closest",
    ):
        if projection not in ("closest", "vertical"):
            raise ValueError("projection must be 'closest' or 'vertical'")
        self.h = float(h)
        self.periods = float(periods)
        self.length = float(length)
        self.projection = projection
        self.w = self.periods * math.pi / self.length
        half = 0.5 * self.length
        self.domain = Domain(-half, half, -half, half)
        self.topology = Topology()                       # all real boundaries

    # --- height field -------------------------------------------------------------
    def _f(self, u, v):
        return self.h * math.cos(self.w * u) * math.cos(self.w * v)

    def _fx(self, u, v):
        return -self.h * self.w * math.sin(self.w * u) * math.cos(self.w * v)

    def _fy(self, u, v):
        return -self.h * self.w * math.cos(self.w * u) * math.sin(self.w * v)

    def _fxx(self, u, v):
        return -self.h * self.w ** 2 * math.cos(self.w * u) * math.cos(self.w * v)

    def _fyy(self, u, v):
        return -self.h * self.w ** 2 * math.cos(self.w * u) * math.cos(self.w * v)

    def _fxy(self, u, v):
        return self.h * self.w ** 2 * math.sin(self.w * u) * math.sin(self.w * v)

    def _second_derivatives(self, u, v):
        return (
            np.array([0.0, 0.0, self._fxx(u, v)]),
            np.array([0.0, 0.0, self._fxy(u, v)]),
            np.array([0.0, 0.0, self._fyy(u, v)]),
        )

    # --- contract -----------------------------------------------------------------
    def point_at(self, u, v):
        return np.array([u, v, self._f(u, v)])

    def derivatives_at(self, u, v):
        return (
            np.array([1.0, 0.0, self._fx(u, v)]),
            np.array([0.0, 1.0, self._fy(u, v)]),
        )

    def normal_at(self, u, v):
        n = np.array([-self._fx(u, v), -self._fy(u, v), 1.0])
        return n / float(np.linalg.norm(n))

    def gaussian_at(self, u, v):
        fx, fy = self._fx(u, v), self._fy(u, v)
        fxx, fyy, fxy = self._fxx(u, v), self._fyy(u, v), self._fxy(u, v)
        return (fxx * fyy - fxy * fxy) / (1.0 + fx * fx + fy * fy) ** 2

    def principal_at(self, u, v):
        su, sv = self.derivatives_at(u, v)
        suu, suv, svv = self._second_derivatives(u, v)
        return _principal_from_forms(su, sv, suu, suv, svv, self.normal_at(u, v))

    def closest_uv(self, p, hint_u, hint_v):
        d = self.domain
        if self.projection == "vertical":
            return (
                min(max(float(p[0]), d.u0), d.u1),
                min(max(float(p[1]), d.v0), d.v1),
            )
        p = np.asarray(p, dtype=float)
        u, v = float(hint_u), float(hint_v)
        for _ in range(8):
            q = self.point_at(u, v) - p
            su, sv = self.derivatives_at(u, v)
            grad = np.array([float(q @ su), float(q @ sv)])
            if float(np.linalg.norm(grad)) < 1e-14:
                break
            suu, suv, svv = self._second_derivatives(u, v)
            hess = np.array(
                [
                    [float(su @ su) + float(q @ suu), float(su @ sv) + float(q @ suv)],
                    [float(su @ sv) + float(q @ suv), float(sv @ sv) + float(q @ svv)],
                ]
            )
            try:
                step = np.linalg.solve(hess, grad)
            except np.linalg.LinAlgError:
                step = grad
            u = min(max(u - float(step[0]), d.u0), d.u1)
            v = min(max(v - float(step[1]), d.v0), d.v1)
        return u, v

    def area(self, n: int = 48) -> float:
        return _grid_area(self, n)


class SphereSurface:
    """Radius-R sphere: u in [0, 2pi) closed (seam), v in [-pi/2, pi/2] singular at both ends."""

    def __init__(self, radius: float = 10.0):
        self.radius = float(radius)
        self.domain = Domain(0.0, 2.0 * math.pi, -0.5 * math.pi, 0.5 * math.pi)
        self.topology = Topology(closed_u=True, singular_v0=True, singular_v1=True)

    def point_at(self, u, v):
        r = self.radius
        return np.array(
            [
                r * math.cos(v) * math.cos(u),
                r * math.cos(v) * math.sin(u),
                r * math.sin(v),
            ]
        )

    def derivatives_at(self, u, v):
        r = self.radius
        su = np.array([-r * math.cos(v) * math.sin(u), r * math.cos(v) * math.cos(u), 0.0])
        sv = np.array(
            [-r * math.sin(v) * math.cos(u), -r * math.sin(v) * math.sin(u), r * math.cos(v)]
        )
        return su, sv

    def normal_at(self, u, v):
        return self.point_at(u, v) / self.radius

    def gaussian_at(self, u, v):
        return 1.0 / (self.radius * self.radius)

    def principal_at(self, u, v):
        """Umbilic: every tangent direction is principal.

        The choice of Su is arbitrary but deterministic. `anisotropy` is 0 here, so the
        alignment field is inert and the choice never reaches a behaviour -- which is why
        the sphere reports "alignment 0.00 over 0 pairs".
        """
        k = 1.0 / self.radius
        su, _ = self.derivatives_at(u, v)
        nrm = float(np.linalg.norm(su))
        e1 = su / nrm if nrm > 1e-14 else np.array([1.0, 0.0, 0.0])
        return k, k, e1

    def closest_uv(self, p, hint_u, hint_v):
        """Wraps the seam naturally via atan2 normalised to [0, 2pi) and asin.

        Seam handling is the host's job (algorithm.md 5); the solver's clamp is only a
        guard and must never be relied on to implement wrapping.
        """
        p = np.asarray(p, dtype=float)
        nrm = float(np.linalg.norm(p))
        if nrm < 1e-14:
            return float(hint_u), float(hint_v)
        q = p / nrm
        u = math.atan2(float(q[1]), float(q[0])) % (2.0 * math.pi)
        v = math.asin(min(1.0, max(-1.0, float(q[2]))))
        return u, v

    def area(self, n: int = 48) -> float:
        return 4.0 * math.pi * self.radius * self.radius


class TubeSurface:
    """A tube of radius `radius(v)` about the z axis: u closed (seam), v a real boundary.

    Exists to make one caveat testable rather than only stated. At `barrel = 0` this is a
    RIGHT CIRCULAR CYLINDER, which is **developable**: `k2 = 0` and `K = 0` everywhere. Every
    plate therefore lands in the parabolic band, the three tangent planes around a triangle
    are near-parallel, and the TPI solve is ill-conditioned wherever it is not outright
    degenerate -- so the fallback rate goes to nearly 100 % and every shape statistic derived
    from those rings means nothing.

    **The developable tube tests seam wrapping and the boundary/seam mix. It does not test
    plate geometry, and a near-100 % fallback rate on it is not a regression.** Give it a
    non-zero `barrel` for meaningful plates: `radius(v) = radius * (1 + barrel * sin(pi *
    (v - v0) / height))` is doubly curved everywhere except the two ends.

    Curvature comes from `fd_principal` -- point and normal only, no second derivatives --
    which algorithm.md 5.1 blesses as the portable fallback and which is worth exercising on
    at least one surface, since it is what a host on an unhelpful kernel will have to use.
    """

    def __init__(self, radius: float = 5.0, height: float = 20.0, barrel: float = 0.0):
        self.radius = float(radius)
        self.height = float(height)
        self.barrel = float(barrel)
        self.domain = Domain(0.0, 2.0 * math.pi, 0.0, self.height)
        self.topology = Topology(closed_u=True)

    @property
    def is_developable(self) -> bool:
        return self.barrel == 0.0

    def _r(self, v: float) -> float:
        return self.radius * (1.0 + self.barrel * math.sin(math.pi * v / self.height))

    def _dr(self, v: float) -> float:
        return (
            self.radius * self.barrel * (math.pi / self.height) * math.cos(math.pi * v / self.height)
        )

    def point_at(self, u, v):
        r = self._r(v)
        return np.array([r * math.cos(u), r * math.sin(u), v])

    def derivatives_at(self, u, v):
        r, dr = self._r(v), self._dr(v)
        su = np.array([-r * math.sin(u), r * math.cos(u), 0.0])
        sv = np.array([dr * math.cos(u), dr * math.sin(u), 1.0])
        return su, sv

    def normal_at(self, u, v):
        su, sv = self.derivatives_at(u, v)
        n = np.cross(su, sv)
        nrm = float(np.linalg.norm(n))
        return n / nrm if nrm > 1e-14 else np.array([math.cos(u), math.sin(u), 0.0])

    def gaussian_at(self, u, v):
        k1, k2, _ = fd_principal(self, u, v)
        return k1 * k2

    def principal_at(self, u, v):
        return fd_principal(self, u, v)

    def closest_uv(self, p, hint_u, hint_v):
        """Angle exactly, height clamped -- an approximation on a barrelled tube.

        `u` wraps naturally through atan2, which is the whole point of the seam here. `v` is
        the vertical drop rather than the true closest point, which is the same class of
        approximation as `MongeSurface(projection="vertical")` and was measured there to
        perturb the path and not the equilibrium.
        """
        p = np.asarray(p, dtype=float)
        u = math.atan2(float(p[1]), float(p[0])) % (2.0 * math.pi)
        v = min(self.height, max(0.0, float(p[2])))
        del hint_u, hint_v
        return u, v

    def area(self, n: int = 48) -> float:
        if self.is_developable:
            return 2.0 * math.pi * self.radius * self.height
        return _grid_area(self, n)
