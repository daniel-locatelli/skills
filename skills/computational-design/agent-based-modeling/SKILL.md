---
name: agent-based-modeling
description: Use when a design task needs agents relaxing on a surface or in a region to produce a tessellation, packing, or plate/panel layout — hexagonal or polygonal plate shells (ICD Stuttgart / Landesgartenschau / BUGA style), curvature-adaptive panelisation, "agent-based" or "behavioural" form finding, boids-style relaxation on NURBS, bow-tie / butterfly plates on saddles, closed surfaces (spheres, tubes) that need pentagons — in any host (Grasshopper, web, Revit, Blender).
---

# Agent-based modeling (ABM) for surface tessellation

## Overview

Agents are points constrained to a surface; simple summed behaviours relax them into a near-hexagonal
packing; geometry is *derived* from the converged agents. The strategy is host-agnostic: the core is
specified in `references/algorithm.md` — the normative document — with `core/AbmCore.cs` as one
reference implementation of it. **Implement the strategy natively in each host, do not transliterate
the reference**: what must match is behaviour semantics, the Jacobi update, parameter meanings, the TPI
plate derivation with its guards, the alignment sign convention and the acceptance criteria. Data
structures, spatial queries, triangulation library, curvature evaluation and geometry types are the
host's own — use what the platform already does well, and never reimplement a kernel facility. The
acceptance contract is `algorithm.md` §8, and its four classes are the standing rule for reading any
number in this skill — see *Acceptance* below before asserting one.

Three host recipes ship: `hosts/grasshopper/` (Rhino/Grasshopper via Cordyceps), `hosts/dotnet/` (the
console harness you tune in) and `hosts/compas_timber/` (Python/COMPAS, through to timber plates and
BTLx). The last of these shares **no code** with `core/AbmCore.cs`, which is the point of it: two
independent implementations of one specification agreeing is evidence, and a port agreeing with its
original is not.

**Core principle:** convergence and plate quality come from *continuous forces that vanish at the target
spacing*, from *an area-consistent spacing*, and from *orienting the packing with the principal curvature
directions* — not from weights. Plate shape comes from the **tangent-plane intersection** (TPI), not
from Voronoi.

## When to use / not

- Use: plate/panel layouts that must adapt to local curvature, packings with fabrication constraints
  expressed as behaviours, interactive "drag an agent and the system re-settles" workflows, closed
  surfaces where the tessellation must wrap (sphere: 12 pentagons appear by themselves).
- Don't: a regular grid/UV subdivision is enough; you need exact planar quads (use PQ-mesh / conjugate
  nets); you only need convex cells on a synclastic surface (surface Voronoi is simpler).

## Workflow

1. **Host adapter**: implement `ISurfaceHost` (`Domain`, `Topology`, `PointAt`, `NormalAt`,
   `GaussianAt`, `ClosestUV`). `Topology` flags seams (`ClosedU/V`) and poles (`Singular*`): those
   edges get no containment and the plates are built without uv. Nothing else touches host types.
   Grasshopper recipe: `hosts/grasshopper/` (`AbmHexPlates.cs` adapter + `build-canvas.ps1 [-Sphere]`
   via Cordyceps); console recipe: `hosts/dotnet/`; Python/COMPAS recipe, with the fabrication stage:
   `hosts/compas_timber/`.
2. **Tune in the console harness first** (`dotnet run -- --h 3 --periods 2 --hex`, `--surface sphere`,
   then `render.py`): seconds per run, plan/axo/per-plate catalogue PNGs. Only then go to the CAD host.
3. **Check the report before looking at pictures**: `converged=True`; `sides` dominated by 6;
   `elliptic: concave=0`; `hyperbolic: convex=0`; hyperbolic **side ratio median 0.38–0.46** (kites and
   zero-length sides mean the packing is misoriented — a misaligned seed reads 0.07); closed surface:
   plates = agents. Euler = 2 is an *identity*, not evidence — see algorithm.md §8(c).
4. **Capture** the host viewport (done-test of the recipe) and keep dated notes of what
   changed in the tuning.

## Quick reference (defaults that converge)

| Parameter | Value | Note |
|---|---|---|
| Spacing | 0 (auto = √(A/(0.866·N)), **surface** area) | plan area under-estimates on curved patches |
| Speed | 0.2 (≤ 0.3) | positional update, no velocity/damping |
| Separation / Cohesion / Containment | 1.0 / 0.3 / 1.0 | separation **zero at spacing**, cohesion zero at spacing and at 1.5·spacing; containment only on real boundary edges |
| Alignment | 0.3 | 12-fold field against the principal cross field (lattice axis along either principal direction); faded by anisotropy, so inert on spheres |
| NeighbourRadiusFactor | 1.5 | first hex ring only |
| InitialLayout / HexAngle | Hexagonal (jittered), angle auto | auto = dominant principal direction; a lattice edge along an *asymptotic* direction gives zero-length plate sides. Closed/seamed surfaces: area-weighted random |
| Iterations / ConvergenceFactor | 1000 / 1e-3·spacing | hex seed ~60 its, random ~600, sphere ~600 |

### Acceptance, in four classes — read the class before reading the number

Nominal 150 agents; the hex seed realises ~131, so **report realised counts**. Which class a
statement is in matters more than its value. The failure this guards against is specific and it is
not hypothetical: **an acceptance number that a correct implementation fails**, written once from a
single run of a single implementation and then asserted as though it were forced. Ask what kind of
claim a number is before you assert it, and band anything that is not forced.

| class | what it means | examples |
|---|---|---|
| **Invariant** — assert exactly | forced by construction or by topology; a violation is a bug, always | closed surface: plates = agents; `pentagons − heptagons = 12`; elliptic concave = 0 and hyperbolic convex = 0 (hex seed on `periods=2` — algorithm.md §8(a) says when it does not hold) |
| **Banded statistic** — assert with a band, **per configuration** | a correct implementation lands in a range that depends on the seed and the surface; a single number here is a bug in the *spec* | egg-crate hex: ≤ 200 iterations, ≥ 90 % hexagons, hyperbolic side ratio median **0.38–0.46**, p10 ≥ 0.32. Random: ≤ 900 iterations, ≥ 75 %, side ratio 0.20–0.28. Do-nothing detector: `maxDisplacement` falls **≥ 40× (hex), ≥ 100× (random)** — the unqualified "2 orders of magnitude" is failed by the reference itself |
| **Identity** — report, never read as evidence | satisfied by a jittered seed with **zero iterations run** | Euler's formula, the valence-defect sum, triangle counts. algorithm.md §8(c) |
| **Not portable** — never compare across hosts | RNG streams, container-ordering-dependent iteration counts, and anything derived from either | seed-for-seed agent positions; *which* pentagon count the sphere lands on (12/14/13 are all correct — the **difference** p5 − p7 = 12 is the assertable part) |

Two tests that actually discriminate: `HexAngle = 0` must **fail** (0.07, alignment mean −0.40),
and alignment must be tested on a *random* seed, where it moves the median 0.12 → 0.23 — on an
aligned hex seed `AlignmentWeight = 0` changes nothing (algorithm.md §8).
The surface contract, and curvature without a CAD kernel: algorithm.md §5.

Plates: Delaunay in uv → 3D edge flip (shortest Cartesian diagonal) — or, with seams/poles, per-agent
tangent-plane Delaunay with unanimous triangles + small-hole filling — → TPI per triangle → S14 validity
(projected point outside the circumcircle ⇒ Voronoi vertex) → fan walk → `IsConvex`, `TouchesBoundary`,
`Classify` (elliptic / parabolic band / hyperbolic). Full derivation, sources and the deviations from
the papers: `references/algorithm.md`, `references/sources.md`.

## Common mistakes (each one cost a debugging round)

| Mistake | Symptom | Fix |
|---|---|---|
| Separation ∝ (radius − d) with radius 1.8·s | `maxDisp` saturates at the step cap, never converges; 5/7-gons everywhere | force zero at `s`, radius 1.5·s, drop velocity |
| Containment from the *nearest* edge only | one corner agent flip-flops ~0.03·s forever | sum all edges within `s/2` |
| Spacing from plan area, or a fixed number | mean neighbours ≪ 6, voids, or compression against the boundary | auto spacing from sampled surface area |
| Hex seed lattice aligned with the uv axes regardless of curvature | bow-ties with near-zero sides / kites / arrowheads ("don't look like bow-ties"): an edge lies along an asymptotic direction | `HexAngle` auto (dominant principal direction) + Alignment 0.3; judge with the side-ratio metric |
| Alignment as a 6-fold field toward "E1" | never converges, 5/7 defects grow: where |κ₁| = |κ₂| E1/E2 swap and are opposite targets mod 60° | 12-fold field (mod 30°): both principal directions are fixed points |
| Treating a sphere/tube as an open uv patch | gap along the seam, agents piled at the poles, plates missing, no pentagons | `Topology` flags → no containment there, uv-free triangulation; pentagons come from the relaxation |
| Reading a **right circular cylinder** as a plate test | 100 % TPI fallbacks, 100 % hexagons, side ratio 0.87 — all of it meaningless | it is **developable**: `K = 0` everywhere, every plate lands in the parabolic band and the three tangent planes are near-parallel, so nothing is a TPI hexagon. The tube tests seam wrapping and the boundary/seam mix, **not plate geometry**. Barrel or taper it for plates; do not read the developable case as a regression |
| An **absolute** tolerance on a shape-operator off-diagonal | the alignment field goes silently inert on every surface of revolution — dome, tube, cone, vault — with no symptom but bad plates | those parametrisations are *already* principal, so the off-diagonals are rounding noise, not zeros. Scale the test by the matrix magnitude, per §2's relative-tolerance rule |
| Lloyd/centroid on TPI or hull cells | non-convergence | ring centroid, interior only, default off |
| Voronoi cells as plates | everything convex, no bow-ties | TPI; bow-ties follow the Dupin indicatrix (K<0 ⇒ hyperbola ⇒ non-convex hexagon) |
| Explaining bow-ties by "Gauss-map orientation flip" / crossed edges | wrong; TPI bow-ties are simple non-convex polygons, and their plan-form is scale-free | see algorithm.md §2 |
| Judging plates in the K≈0 band or next to the hull | "K>0 but concave", spikes to infinity | classify the band, flag/drop boundary plates, centroid fallback for ill-shaped triangles |
| Handing a TPI ring straight to a fabrication kernel as a planar outline | the plate builder rejects it, or accepts it and the part is wrong, on a surface where nothing looks unusual | a ring is planar **only** where every vertex came from the three-plane solve; a §3.2 fallback vertex is a circumcentre or centroid and lies in no tangent plane. 29 % of egg-crate triangles take that path, leaving 50 of 85 interior plates off by up to 11 % of spacing. **Planarise before use** — total-least-squares plane, not the agent's tangent plane — and report the residual and the corner movement it cost (up to 7 % of spacing) |
| Test surface `cos·cos` with one period | saddles are steep and |K| tiny there | `periods=2` egg-crate |
| GH C# Script: appending the core *with its `using` lines* after the adapter | compiles silently, all outputs null | strip `using` lines (CS1529 is swallowed) |
| GH capture with the default preview on | dull-red surface z-fights with the plates; Colour Swatch cannot be set via Cordyceps (stays white) | hide previews, Panel "R,G,B" → Colour param → Custom Preview (`capture.ps1`) |

## Red flags

- "Converged" claimed without `maxDisp` number; "looks hexagonal" without the `sides` histogram;
  "bow-ties" claimed without the side-ratio median.
- Inventing anisotropic scalings, blends or adaptive radii before the plain model converges.
- Citing "ICD does X" without one of: S14, G18, B17, ABxM source (`references/sources.md`).
