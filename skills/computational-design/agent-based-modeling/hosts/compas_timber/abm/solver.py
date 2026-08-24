"""Agent relaxation (algorithm.md 1).

The update is synchronous (Jacobi) and that is a requirement, not an incidental: every
behaviour vector is computed against the positions at the START of the iteration, and only
then does anything move. A sequential (Gauss-Seidel) sweep converges to a different packing.

All five behaviours are continuous in distance and zero at their cutoff. Separation in
particular vanishes at the target spacing rather than at the neighbour radius -- a force
that does not has its equilibrium at the cutoff, roughly twelve neighbours push at once,
the per-step gain exceeds the explicit-integrator stability limit, and maxDisp saturates
at the step cap forever.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from scipy.spatial import cKDTree

from .seeding import auto_spacing, hex_seed, random_seed
from .surfaces import Surface, anisotropy


@dataclass
class Parameters:
    """Defaults from algorithm.md 6. Meanings are invariant across hosts; spellings are local.

    `iterations` defaults to 1000, not the core's 500: 500 is too low for the sphere, which
    needs 601 at 150 agents. Both existing harnesses use 1000.
    """

    count: int = 100
    iterations: int = 1000
    spacing: float = 0.0                      # 0 = auto, from SURFACE area
    speed: float = 0.2
    separation_weight: float = 1.0
    cohesion_weight: float = 0.3
    containment_weight: float = 1.0
    alignment_weight: float = 0.3
    centroid_weight: float = 0.0
    hex_angle: Optional[float] = None         # radians; None = auto (12-fold mean)
    hex_jitter: float = 0.15
    neighbour_radius_factor: float = 1.5
    convergence_factor: float = 1e-3
    max_step_factor: float = 0.5
    layout: str = "random"                    # "random" | "hex"
    rng_seed: int = 1
    evaluate_principal_frame: bool = True
    band_fraction: float = 0.1


@dataclass
class AgentState:
    """Struct of arrays. The plate is derived, never stored (algorithm.md 1)."""

    uv: np.ndarray                            # (N, 2)
    p: np.ndarray                             # (N, 3)
    n: np.ndarray                             # (N, 3) unit
    k: np.ndarray                             # (N,) Gaussian curvature at P
    k1: np.ndarray                            # (N,) |k1| >= |k2|
    k2: np.ndarray
    e1: np.ndarray                            # (N, 3) unit tangent, direction of k1
    anis: np.ndarray                          # (N,) in [0, 1]

    def __len__(self) -> int:
        return len(self.p)


@dataclass
class SolverResult:
    agents: AgentState
    iterations_run: int
    converged: bool
    max_disp_history: List[float]
    spacing: float
    seed_jitter_spread: float
    neighbours: List[np.ndarray] = field(default_factory=list)


# --- behaviours, as pure functions of distance -----------------------------------------
# Every scalar below is the coefficient of `dir`, the unit vector pointing FROM the
# neighbour TO the agent. Positive is away from the neighbour.


def separation(d: float, s: float) -> float:
    """Linear spring, full strength s at contact, ZERO at the target spacing."""
    return (s - d) if d < s else 0.0


def cohesion(d: float, s: float, r: float) -> float:
    """Pull toward sparse neighbours; zero at s and at r, negative in between."""
    if d < s or d >= r or r <= s:
        return 0.0
    return -(d - s) * (r - d) / (r - s)


def alignment_force(
    n: np.ndarray,
    e1: np.ndarray,
    anis: float,
    t: np.ndarray,
    d: float,
    r: float,
    weight: float,
    s: float,
) -> np.ndarray:
    """The 12-fold principal-direction field (algorithm.md 1), sign convention normative.

    e2 = N x E1 (right-handed with N); phi = atan2(t.e2, t.E1), measured from E1 toward e2,
    where t is the neighbour offset projected into this agent's tangent plane. The potential
    being descended is U = -cos(12.phi), so the force is a sideways push along
    perp = N x t_hat, along which moving the agent decreases phi.

    12-fold, not 6-fold: where |k1| = |k2| -- every symmetric saddle -- the numerically
    larger principal direction swaps between E1 and E2 from agent to agent, and in a 6-fold
    field those are opposite targets, so the behaviour fights itself. In the 12-fold field
    both principal directions are fixed points and the asymptotic directions of a symmetric
    saddle are the maxima.
    """
    if weight <= 0.0 or anis <= 0.0:
        return np.zeros(3)
    tn = float(np.linalg.norm(t))
    if tn <= 0.0:
        return np.zeros(3)
    that = t / tn
    e2 = np.cross(n, e1)
    phi = math.atan2(float(that @ e2), float(that @ e1))
    perp = np.cross(n, that)
    fall = 1.0 - d / r
    return perp * (weight * s * anis * math.sin(12.0 * phi) * fall / 12.0)


class Solver:
    def __init__(self, surface: Surface, params: Parameters):
        self.surface = surface
        self.p = params
        if params.spacing <= 0.0:
            params.spacing = auto_spacing(surface, params.count)
        self.agents: Optional[AgentState] = None
        self._seed_jitter_spread = 0.0

    # --- placement ---------------------------------------------------------------------
    def place(self, uv: np.ndarray) -> AgentState:
        """Evaluate every agent's frame at its parameter.

        The principal frame is evaluated on every placement INDEPENDENTLY of
        `alignment_weight` (algorithm.md 4): gating it on the weight makes the alignment
        mean unmeasurable with the field off, which is exactly the before/after comparison
        section 8 needs. `evaluate_principal_frame` is the opt-out for a host that neither
        uses the field nor reports the metric.
        """
        uv = np.asarray(uv, dtype=float).reshape(-1, 2)
        n_agents = len(uv)
        pos = np.empty((n_agents, 3))
        nrm = np.empty((n_agents, 3))
        gauss = np.empty(n_agents)
        k1 = np.zeros(n_agents)
        k2 = np.zeros(n_agents)
        e1 = np.zeros((n_agents, 3))
        anis = np.zeros(n_agents)
        for i, (u, v) in enumerate(uv):
            pos[i] = self.surface.point_at(u, v)
            nrm[i] = self.surface.normal_at(u, v)
            gauss[i] = self.surface.gaussian_at(u, v)
            if self.p.evaluate_principal_frame:
                a, b, e = self.surface.principal_at(u, v)
                k1[i], k2[i], e1[i] = a, b, e
                anis[i] = anisotropy(a, b) if float(np.linalg.norm(e)) > 0.0 else 0.0
        self.agents = AgentState(uv=uv, p=pos, n=nrm, k=gauss, k1=k1, k2=k2, e1=e1, anis=anis)
        return self.agents

    # --- queries -----------------------------------------------------------------------
    def neighbours(self, positions: Optional[np.ndarray] = None) -> List[np.ndarray]:
        """Exactly the agents within r = neighbour_radius_factor . spacing, in 3D.

        The result set is invariant across hosts; the structure that computes it is free.
        A KD-tree is this platform's natural choice. Indices are sorted so that a run is
        reproducible independently of the tree's internal ordering.
        """
        pos = self.agents.p if positions is None else positions
        r = self.p.neighbour_radius_factor * self.p.spacing
        tree = cKDTree(pos)
        out = []
        for i, ids in enumerate(tree.query_ball_point(pos, r)):
            keep = [j for j in ids if j != i and float(np.linalg.norm(pos[j] - pos[i])) < r]
            out.append(np.array(sorted(keep), dtype=int))
        return out

    def containment_vector(self, i: int, positions: Optional[np.ndarray] = None) -> np.ndarray:
        """Sum over EVERY real-boundary domain edge within s/2 (algorithm.md 1).

        The foot point is the ISO-PARAMETRIC point on the edge at the agent's other
        parameter -- for the u = u0 edge, S(u0, a.v) -- and the force acts along the 3D
        direction from that point to the agent. It is not the closest point on the boundary
        curve; on a curved patch the two differ in both magnitude and direction, and the
        boundary ring determines which plates count as interior.

        Summing all edges is also required: containment by the nearest edge only flips
        between two edges at a corner every step and never converges.
        """
        pos = self.agents.p if positions is None else positions
        s = self.p.spacing
        half = 0.5 * s
        d = self.surface.domain
        topo = self.surface.topology
        u, v = self.agents.uv[i]
        p_i = pos[i]
        total = np.zeros(3)
        edges = (
            (topo.boundary_u0, (d.u0, v)),
            (topo.boundary_u1, (d.u1, v)),
            (topo.boundary_v0, (u, d.v0)),
            (topo.boundary_v1, (u, d.v1)),
        )
        for is_real, (fu, fv) in edges:
            if not is_real:
                continue                                   # seams and poles get no containment
            away = p_i - self.surface.point_at(fu, fv)
            dist = float(np.linalg.norm(away))
            if dist >= half or dist <= 0.0:
                continue
            total = total + (away / dist) * (half - dist)
        return total * self.p.containment_weight

    # --- the step ----------------------------------------------------------------------
    def step(self) -> float:
        """One synchronous (Jacobi) iteration. Returns the realised max 3D displacement.

        Sum -> x speed -> project onto the tangent plane using the PRE-STEP normal -> cap
        at max_step_factor . spacing -> move -> re-project onto the surface. The value
        returned is |p_new - p_old| after re-projection, not the intended step length: a
        step that gets projected back onto the surface counts as smaller.
        """
        a = self.agents
        s = self.p.spacing
        r = self.p.neighbour_radius_factor * s
        pos0 = a.p.copy()
        n0 = a.n.copy()
        degenerate = 1e-9 * s
        nb = self.neighbours(pos0)
        forces = np.zeros_like(pos0)
        for i in range(len(pos0)):
            acc = np.zeros(3)
            for j in nb[i]:
                offset = pos0[j] - pos0[i]
                dist = float(np.linalg.norm(offset))
                if dist < degenerate:
                    continue
                away = -offset / dist
                acc = acc + away * (
                    self.p.separation_weight * separation(dist, s)
                    + self.p.cohesion_weight * cohesion(dist, s, r)
                )
                if self.p.alignment_weight > 0.0 and a.anis[i] > 0.0:
                    tangential = offset - n0[i] * float(offset @ n0[i])
                    acc = acc + alignment_force(
                        n0[i], a.e1[i], float(a.anis[i]), tangential, dist, r,
                        self.p.alignment_weight, s,
                    )
            acc = acc + self.containment_vector(i, pos0)
            forces[i] = acc

        cap = self.p.max_step_factor * s
        moved = np.empty_like(pos0)
        new_uv = np.empty_like(a.uv)
        for i in range(len(pos0)):
            stepv = forces[i] * self.p.speed
            stepv = stepv - n0[i] * float(stepv @ n0[i])       # PRE-step normal
            length = float(np.linalg.norm(stepv))
            if length > cap:
                stepv = stepv * (cap / length)
            target = pos0[i] + stepv
            u, v = self.surface.closest_uv(target, a.uv[i][0], a.uv[i][1])
            new_uv[i] = (u, v)
            moved[i] = self.surface.point_at(u, v)

        self.place(new_uv)
        return float(np.max(np.linalg.norm(moved - pos0, axis=1))) if len(pos0) else 0.0

    # --- the run -----------------------------------------------------------------------
    def seed(self) -> np.ndarray:
        rng = np.random.default_rng(self.p.rng_seed)
        if self.p.layout == "hex":
            if self.surface.topology.is_non_trivial:
                raise ValueError(
                    "a uv lattice is meaningless across a seam or a pole; use layout='random'"
                )
            uv = hex_seed(
                self.surface, self.p.count, self.p.hex_angle, self.p.hex_jitter, rng
            )
            pitch = math.sqrt(
                abs(self.surface.domain.du * self.surface.domain.dv)
                / (0.8660254 * max(1, self.p.count))
            )
            self._seed_jitter_spread = pitch * self.p.hex_jitter
            return uv
        if self.p.layout != "random":
            raise ValueError("layout must be 'hex' or 'random'")
        self._seed_jitter_spread = float("inf")
        return random_seed(self.surface, self.p.count, rng)

    def run(self) -> SolverResult:
        if self.p.centroid_weight != 0.0:
            raise NotImplementedError(
                "centroid_weight is not implemented in v1: it costs a full triangulation "
                "per iteration, regularises shape rather than valence, and fights "
                "separation, so algorithm.md 6 has it off by default. See README.md."
            )
        self.place(self.seed())
        history: List[float] = []
        converged = False
        iterations = 0
        threshold = self.p.convergence_factor * self.p.spacing
        for _ in range(self.p.iterations):
            disp = self.step()
            history.append(disp)
            iterations += 1
            if disp < threshold:
                converged = True
                break
        return SolverResult(
            agents=self.agents,
            iterations_run=iterations,
            converged=converged,
            max_disp_history=history,
            spacing=self.p.spacing,
            seed_jitter_spread=self._seed_jitter_spread,
            neighbours=self.neighbours(),
        )
