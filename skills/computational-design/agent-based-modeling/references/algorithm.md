# Algorithm — agent-based hexagonal plates on a doubly-curved surface

The **normative specification** of the strategy: enough to implement it from scratch, natively, in any language
against any geometry kernel. `core/AbmCore.cs` is the reference implementation, not the definition — where this
document and the C# disagree, this document is right and the C# has a bug (both are noted below where they
currently differ). Tags → `sources.md`.

Host adaptation: implement this specification in your platform's own idioms. What must match across hosts is the
behaviour semantics, the update discipline, parameter meanings, the plate derivation with its guards, the
alignment field including its sign, the units/tolerance rule (§2) and the acceptance criteria (§8). Data
structures, spatial-query implementation, triangulation library, curvature evaluation and geometry types are
yours to choose. Do not transliterate the C#.

## 1. Model

| Element | Definition | Source |
|---|---|---|
| Agent | a point **on** the surface: `(u,v)`, `P`, unit normal `N`, Gaussian curvature `K`, principal curvatures `K1,K2` + direction `E1` + `Anisotropy`, neighbour set. The plate is *derived*, never stored. | S14 p.181; G18 §4.3 |
| Environment | the surface contract of §5. | G18 §3.2.5 |
| Step | **synchronous (Jacobi)**: every agent's behaviour vector is computed against the positions at the *start* of the iteration; only then are all agents moved. Sum → `× Speed` → project onto the tangent plane (using the **pre-step** normal) → cap at `MaxStepFactor·s` → move → re-project onto the surface. | G18 §3.2.4–3.2.5; position-based update after Schwinn/Siriwardena/Menges 2023 (PolyAgent) |
| Termination | `maxDisplacement < ConvergenceFactor·Spacing` (default 1e-3), where `maxDisplacement` is the **realised 3D displacement after re-projection**, not the intended step length — a step that gets projected back onto the surface counts as smaller. Or `Iterations`. | G18 fig. 11 / §3.5.3 |
| Materialisation | triangulation (§3.1) → tangent-plane intersection per triangle (§3.2) → each interior agent's plate = ring of TPI points around it (§3.3). | S14 p.181, T08, LLW15 §3.2 |

A Jacobi update is required, not incidental: a sequential (Gauss–Seidel) sweep converges to a different packing.

### Behaviours (all continuous in distance, zero at their cutoff)

`s` = `Spacing`, `r` = `NeighbourRadiusFactor·s` (default 1.5·s = first hexagonal ring only; the second ring sits at 1.73·s).
The neighbour set is **exactly** the agents within `r` in 3D — the data structure that finds them is free, the
result set is not.

| Behaviour | Vector on agent *a* from neighbour *b* at distance `d` | Weight | Origin |
|---|---|---|---|
| Separation | `dir · (s − d)` for `d < s` (linear spring, full strength `s` at contact, **zero at the target spacing**) | `SeparationWeight` 1.0 | R87 SEP; ABxM `GradientSeparation` |
| Cohesion | `−dir · (d − s)(r − d)/(r − s)` for `s ≤ d < r` (pull toward sparse neighbours, zero at `s` and at `r`) | `CohesionWeight` 0.3 | ABxM `Attraction`; G18 LGCS |
| Containment | for **each** domain edge that is a real boundary (not a seam, not a pole) within `s/2`: `(s/2 − d_edge)` away from the edge | `ContainmentWeight` 1.0 | S14 containment |
| Alignment | `perp · (AlignmentWeight · s · anis · sin(12φ) · (1 − d/r) / 12)` — see the sign convention below | `AlignmentWeight` 0.3 | LLW15 §4.1; WLP08 Prop. 5 |
| Centroid (optional) | toward the centroid of the Delaunay 1-ring (Laplacian smoothing), interior agents only. Costs a full triangulation per iteration, and uses the **Voronoi** dual (no TPI). | `CentroidWeight` 0 | G18 PC / ABxM `MoveToCentroid` in spirit |

**Alignment sign convention (normative).** `e₂ = N × E₁` (right-handed with `N`). `t` = the neighbour offset
`b.P − a.P` projected into `a`'s tangent plane. `φ = atan2(t·e₂, t·E₁)`, measured from `E₁` toward `e₂`. The
potential being descended is `U = −cos(12φ)`, so the force is a sideways push `perp = N × t̂`, along which moving
`a` decreases `φ`. Get this sign backwards and the field becomes a repeller that drives the packing *onto* the
asymptotic directions — the exact failure this behaviour exists to fix, and one that no convergence test detects.

**Alignment is not pair-antisymmetric.** It is evaluated in `a`'s own frame with `a`'s anisotropy; `b` computes an
independent and generally unequal push in its own frame. The natural vectorised formulation — visit each pair
once, apply `+f` to `i` and `−f` to `j` — is therefore **wrong**: it silently halves and corrupts the field.
Separation and cohesion *are* antisymmetric. Evaluate alignment in both directions of every pair.

**Containment foot point (normative).** The foot point is the **iso-parametric** point on the domain edge at the
agent's other parameter — for the `u = u₀` edge, `S(u₀, a.v)` — and the force acts along the 3D direction from
that point to the agent. It is *not* the closest point on the boundary curve. On a curved patch the two differ in
both magnitude and direction, and the boundary ring determines which plates count as interior, so this changes
every interior-plate statistic. (A true closest-point rule is defensible and arguably better; it is not what the
acceptance numbers in §8 were measured with. Change it deliberately, and re-measure.)

### Seeding

**`Count` is nominal, not the realised agent count.** For `Layout.Hexagonal` the lattice is generated and then
filtered, so the run ends up with fewer agents than asked for — measured **131 for `Count = 150`** on the
egg-crate. Every per-agent statistic must be reported against the realised count.

`Layout.Hexagonal` (open patches only — a uv lattice is meaningless across a seam or pole):

```
d      = sqrt(du·dv / (0.8660254 · max(1, Count)))        # lattice pitch, in PARAMETER-DOMAIN area
ang    = HexAngle is NaN ? DominantPrincipalAngle() : radians(HexAngle)
basis  = (d·cos ang, d·sin ang) and (d·cos(ang+60°), d·sin(ang+60°))
centre = domain midpoint ((u0+u1)/2, (v0+v1)/2)
margin = 0.4·d
for each lattice point p = centre + i·basis1 + j·basis2:
    reject if p is within `margin` of any domain edge      # tested on the UN-jittered point
    u = p.u + uniform(-0.5, 0.5)·d·HexJitter               # square box, in RAW uv, applied AFTER the test
    v = p.v + uniform(-0.5, 0.5)·d·HexJitter               # so an agent may land outside and be clamped
```

Note the pitch `d` is derived from **parameter-domain** area `du·dv`, while `Spacing` is derived from **surface**
area (§6) — ≈12 % apart on the egg-crate (plan 400 vs surface 479). The packing is therefore seeded denser than
its own target spacing and separation expands it; the fast convergence (~51 iterations) is partly a product of
this mismatch. Both facts are reference behaviour, not design intent; a host that "fixes" either will not
reproduce §8.

**`DominantPrincipalAngle()`** — the auto seed angle, and the single most consequential quantity in the strategy:

```
sc = ss = 0
for i, j in 0..16:                                        # 17x17 offset grid
    u = u0 + (u1-u0)·(i+0.5)/17 ;  v = v0 + (v1-v0)·(j+0.5)/17
    (k1, k2, e1) = principal_at(u, v)        ; skip if unavailable
    w = anisotropy(k1,k2) · (|k1| + |k2|)    ; skip if w <= 0
    hu = 1e-4·(u1-u0) ; hv = 1e-4·(v1-v0)
    Pu, Pv = central differences of point_at, CLAMPED to the domain    # note: differs from the
                                                                       # unclamped stencil used for curvature
    E = Pu·Pu ; F = Pu·Pv ; G = Pv·Pv ; det = E·G - F·F ; skip if det < 1e-18
    r1 = e1·Pu ; r2 = e1·Pv
    alpha = (G·r1 - F·r2)/det ; beta = (E·r2 - F·r1)/det   # e1 expressed in the uv basis
    theta = atan2(beta, alpha)
    sc += w·cos(12·theta) ; ss += w·sin(12·theta)
return (sc == 0 and ss == 0) ? 0 : atan2(ss, sc)/12        # mod 30 degrees
```

The angle is a **uv** angle, because the lattice is laid out in uv. Recovering it needs the first fundamental
form `[E F; F G]` — an orthonormal frame at the point has already discarded `E`, `F` and `G`, so a host contract
that offers only a frame and a 3D principal direction **cannot compute this**. The parametric derivatives
`(Su, Sv)` are therefore part of the surface contract (§5). On the egg-crate the answer is **15°**.
(The reference's `Parameters.HexAngle` docstring used to say "6-fold mean" while the code was 12-fold; the
docstring was wrong and is fixed. 12-fold is correct — see the why-note below.)

Ambiguity to be aware of: the lattice is laid out in **raw uv** while the open-patch Delaunay runs in uv
normalised to `[0,1]²`. On a square domain these agree; on a non-square domain "HexAngle in uv degrees" is
ambiguous between the two metrics. Raw uv is normative.

`Layout.Random` (and any surface with a seam or pole): uniform per unit **area** by rejection sampling against
`|Pu×Pv|`, not uniform in uv (poles and stretched patches would be over-sampled). The maximum area element is
estimated on a 24×24 grid, and the sampling loop is guarded at `Count·1000` attempts.

**RNG streams are not portable.** Seed *n* in .NET and seed *n* in numpy select different point sets. Never
compare hosts seed-for-seed; compare distributions over several seeds (§8).

**Why these exact forms (lessons from the harness, 2026-08-21/22):**
- A separation force that does **not** vanish at `s` (e.g. `(r − d)/r`) has its equilibrium at the cutoff radius, so the packing is compressed against the boundary and ~12 neighbours push at once: the per-step gain exceeds the explicit-integrator stability limit and `maxDisp` saturates at the step cap forever. Velocity/damping makes it worse. Positional update + forces that are zero at `s` and continuous at `r` converge monotonically.
- Containment by the *nearest* edge only flips between two edges at a corner every step (0.03·s flip-flop, never converges). Sum all edges.
- Centroid-of-TPI-plate (G18 PC literally) is discontinuous (vertices jump at fallbacks / bow-ties) and destroys convergence; centroid of the Voronoi cell is unbounded next to the hull. Neighbour-ring centroid is bounded and continuous. It regularises *shape*, not *valence*, and fights separation, so it is off by default.
- Valence (5/7-gon defects) is set by the seed: uniform random → ~75–85 % hexagons after relaxation; jittered hexagonal seed (`HexJitter` 0.15) → ~90–95 %. BUGA19 did the same (regular arrangement at the folds). DistMesh's 1.2× compression trick gives only a few % more.
- `Spacing ≤ 0` = automatic `sqrt(Area/(0.866·Count))` (surface area sampled on a 48×48 uv grid); the *area-consistent* spacing matters more than any weight — too small and agents float apart (mean neighbours ≪ 6), too large and they compress against the boundary.
- **Orientation decides the bow-tie shape, not |K|** (see §3). A hex lattice seeded along the uv axes put plate edges exactly along the asymptotic directions of the egg-crate saddles: hyperbolic side ratio median 0.02 — kites and arrowheads, not butterflies. Auto `HexAngle` alone lifts it to 0.40.
- **The alignment field must be 12-fold, not 6-fold.** Where |κ₁| = |κ₂| (every symmetric saddle) the numerically "larger" principal direction swaps between E1 and E2 from agent to agent; in a 6-fold field E1 and E2 (90° ≡ 30° mod 60°) are opposite targets, so a 6-fold behaviour fights itself (non-convergence, 5/7 defects multiply, mean cos(6φ) ≈ 0.1). In the 12-fold field (mod 30°) both principal directions are fixed points and the asymptotic directions of a symmetric saddle (45° off) are the maxima. Weight 0.3–0.6 converges; 1.0 over-constrains random seeds (defects).
- **Alignment does nothing once the seed is already aligned.** Measured: with the hex seed at the auto angle, `AlignmentWeight = 0` reproduces the reference side ratio (0.40 / p10 0.33) *exactly*. Its value shows on random seeds (median 0.12 → 0.23, and converged vs. not converged in 1000 iterations) and on a misaligned hex seed. Any test of the alignment behaviour must use one of those.
- **Closed surfaces** (sphere, tube): no containment on seam/pole edges, and the plates must not use uv (the sphere's poles and seam are not a chart). With that, 12 pentagons (± 5/7 pairs) appear by themselves.

## 2. Units and tolerances

**State the model unit and keep the whole pipeline in it.** The reference was tuned on a domain of `L = 20` with
`Spacing ≈ 1.9`, and several of its guards are *absolute* constants with physical dimensions:

| Guard | Value | Dimension | Where |
|---|---|---|---|
| plane-intersection determinant | `1e-9` | dimensionless (unit normals) | §3.2 |
| circumcentre denominator | `1e-18`·`Spacing⁴` (reference: bare `1e-18`) | length⁴ | §3.2 |
| convexity turn threshold | `1e-12`·`Spacing²` | length² | §3.3 |
| vector normalisation | `1e-12` | length | everywhere |
| degenerate neighbour distance | `1e-9` | length | §1 behaviours |

At millimetre scale (`Spacing ≈ 1900`) or at metre scale for a small pavilion, these behave differently — the
convexity test in particular gates the headline acceptance criterion. **Normative rule: every geometric tolerance
is expressed relative to `Spacing`, scaled by its own dimension** — the convexity threshold as `ε·Spacing²`, the
circumcentre denominator as `ε·Spacing⁴`, normalisation and the degenerate neighbour distance as `ε·Spacing` —
with the dimensionless determinant test left absolute. Scale each one by the power its dimension column gives,
not by `Spacing` flat; the circumcentre denominator is the one this is easiest to get wrong, because `1e-18` reads
as "machine zero" and is in fact a length⁴. The reference writes it bare (`AbmCore.cs:975`), which is correct only
at the metre scale it was tuned at: at millimetre scale a bare `1e-18` is 10¹² times too strict and the guard
never fires. A host that keeps the absolute constants must document the unit it is valid in. Where the solver's
units differ from the fabrication stage's, state the conversion point explicitly.

Thresholds on quantities in **parameter** space are not covered by this rule and must not be scaled by `Spacing`:
the first-fundamental-form determinant in §1's `DominantPrincipalAngle()` grid is a `(length/uv-unit)⁴` (or, read
with an unnormalised stencil, `(length·uv-step)⁴`) — either way it depends on the
surface's parameterisation and not on the model unit. Left absolute deliberately.

## 3. Plates: tangent-plane intersection (TPI)

### 3.1 Triangulation

**Every triangle is CCW about its agents' normals.** This is not cosmetic: hole-finding walks directed edges and
finds a hole as an edge whose reverse is missing; the fan walk follows next/prev; the convexity test reads turn
signs about `N`. All three break silently on mixed orientation, and the symptom is "plates < agents" with no
error. Most library triangulators (Qhull among them) return simplices in arbitrary orientation, so **re-orient
explicitly** after triangulating — but the rule is **for the mesh, not for the triangle**: make each connected
component self-consistent by propagating orientation across shared edges (a triangle adjacent to an already
oriented one must traverse their shared edge in the opposite direction), then set that component's global sign by
aggregate agreement with the agents' normals. Invariant to assert: every interior edge carries exactly two
oppositely-directed half-edges.

The per-triangle test — flip when `((b−a) × (c−a)) · N < 0` — is a reasonable *seed* for that propagation and is
not a substitute for it. Where a triangle is strongly tilted relative to the agent's tangent plane, which is the
ordinary state of affairs on the egg-crate's ~43° flanks and not an exotic case, the sign of `cross·N` disagrees
with the triangle's winding, so applying the test triangle by triangle leaves a mesh that is manifold but
inconsistently oriented — which is exactly what the three walks above cannot survive. Measured on the Python host,
egg-crate hex seed, 248 triangles over 131 agents: **6** duplicated half-edges taking `N` from the first agent,
**20** taking the sum of the three, **0** with edge propagation.

*(Until 2026-08-23 this section gave the per-triangle test as the rule itself. No measured number moved, because
neither existing host applies it: the reference keeps open-patch triangles CCW **in uv** and seam/pole triangles
CCW in each agent's own tangent frame, both globally consistent by construction. "CCW in uv" is exact but only
available on an open patch, which is why the reference needs two mechanisms; edge propagation plus a global sign
is one mechanism that covers both, which is what a host without a uv fallback needs.)*

- **Open patch** (`Topology` all false): Delaunay (Bowyer–Watson) in normalised `(u,v)`, then **3D edge flip**
  (S14/T08): flip every interior edge whose opposite diagonal is shorter in 3D, if the flipped pair stays a
  convex CCW quad in uv; repeat to convergence (≤ 20 passes). uv-Delaunay is not 3D-Delaunay on a stretched
  patch. The pass is order-dependent — at most one flip per triangle per pass, ties broken strictly (`<`), and
  the iteration order is the triangle container's — so the resulting mesh is a function of container ordering.
- **Seam/pole** (`Topology.IsNonTrivial`): every agent Delaunay-triangulates its 3D neighbourhood (radius
  **2·s**, and only neighbours whose normal satisfies `N_j · N_a > 0`) projected onto its own tangent plane, and
  keeps the triangles incident to itself; a triangle is accepted when **all three** of its agents produced it
  (consistent restricted Delaunay). Guard the local triangulation against fewer than 4 points and against
  collinear/cocircular sets — most library Delaunay implementations raise there.
  Where the three projections disagree (near-cocircular quads) nobody is unanimous and a small hole remains:
  walk every open-edge loop of **≤ 8 edges** and ear-clip it by shortest 3D diagonal (same criterion as the
  flip). Longer loops are real boundaries (cylinder-like surfaces) and stay open.

  Two limits of the hole filler to respect: it assumes each vertex has at most one outgoing open edge, so a pinch
  vertex shared by two holes silently loses one; and a short loop is not necessarily a hole — a boundary notch,
  or any trimmed patch, can present a loop of ≤ 8 edges that must **not** be filled. Only fill loops strictly
  interior to the domain.

  **Do not use the unanimity path on an open patch.** Boundary agents see a half-disc neighbourhood and generate
  long hull triangles their interior partners never produce, so unanimity fails along the whole outer ring;
  "unanimous" has no defined meaning for an agent without a full ring. The two paths also disagree by
  construction — empty-circumcircle versus shortest-3D-diagonal pick different diagonals systematically in the
  anisotropic valleys.

### 3.2 The TPI point, its guards and their precedence

For each triangle `(a,b,c)` solve `n_i · x = n_i · p_i` (3×3). Then, **in this order** — the branches are
mutually exclusive, which is easy to get wrong:

```
cc       = circumcentre(a.P, b.P, c.P)      # fall back to the centroid if denom < 1e-18·spacing^4
                                            # (length^4, so scaled by spacing^4 per §2; the
                                            #  reference writes it bare, correct only at metre scale)
R        = |cc - a.P|
centroid = (a.P + b.P + c.P)/3
illShaped = (spacing > 0) and (R > 2·spacing)          # near-collinear; only happens along the boundary

if illShaped:
    cc = centroid                                       # bounded fallback (LLW15 centroid rule)
    if solved and |x - centroid| > 2·spacing: solved = false     # keep a bounded TPI point, drop a far one
    # NOTE: the circumcircle validity test is SKIPPED entirely in this branch
elif solved:
    # S14 validity: project x onto the triangle plane; outside the circumcircle -> degenerate (near-parabolic)
    xp = x - tn·((x - a.P)·tn)      where tn = unit((b.P-a.P) x (c.P-a.P))
    if |xp - cc| > R: solved = false
if not solved: x = cc ; fallbackCount += 1
```

The plane solve fails when `|det| < 1e-9` (dimensionless, unit normals). Near `K = 0` the three planes are almost
parallel, the system is ill-conditioned and the point flies off (Z12) — the parabolic band always needs this
fallback. Two kernel traps worth naming, because they are not hypothetical: a three-plane intersection routine
may return "no intersection" at a much coarser angular tolerance than you expect (check whether its tolerance
argument is absolute or relative), and it may not handle **anti-parallel** planes at all — pre-test
`|n_i · n_j|` yourself rather than relying on a null return.

**`FallbackCount` semantics:** an ill-shaped triangle whose TPI point stayed within `2·spacing` of the centroid
is **not** counted; an ill-shaped one whose point was dropped is. Without this the "25–35 % of triangles" figure
in §8 is not reproducible.

### 3.3 From triangles to plates

An agent is **interior** when it has ≥ 3 incident triangles and every incident edge is shared by exactly two of
them. For an interior agent, walk the fan triangle→triangle by shared edges (combinatorial order, so a folded
ring stays folded) and take the TPI point of each: that ring is the plate. A fan walk that fails to close
**silently drops the plate** — count and report these; they are the usual cause of `plates < agents` on a closed
surface.

**The ring is planar by construction only where every one of its vertices came from the three-plane solve.** That
vertex lies in the agent's own tangent plane because that plane is one of the three. A vertex produced by §3.2's
fallback is a circumcentre or a centroid and lies in **neither** — and §3.2 puts 29 % of the egg-crate's triangles
on that path (§8's band is 25–35 %), so this is the common case and not an edge case. Measured on the egg-crate hex seed
(131 agents, 248 triangles, `Spacing` 1.9207): **50 of the 85 interior plates carry at least one fallback vertex**,
and the ring deviates from the tangent plane by up to **0.208 = 11 % of `Spacing`** (median 0.057). The control is
the sphere at `R = 10` on a random seed, which takes no fallback anywhere and is planar to < 1e-9·`Spacing`, which
locates the defect in the fallback and not in TPI.

So **planarisation before use as an outline is mandatory, not a refinement**. A fabrication kernel wants a planar
outline on a tight budget — `compas_timber`'s is 3.3e-10 — and a host that trusts an unqualified "planar by
construction" will hand it a ring that is off by 11 % of `Spacing` and get a failure it has no reason to expect.
Fit the plane by total least squares over the ring rather than reusing the agent's tangent plane: measured, that
is the better plane by a third (worst residual 135.5 mm against 208 mm on the same rings) and it is sufficient on
its own — 0 rings needed rejecting across egg-crate hex and random and the sphere control, and the planarised ring
clears the 3.3e-10 budget by two and a half orders of magnitude. **Record what it cost** — a corner moves by up to
7 % of `Spacing`, invisible in a viewport and decisive on a CNC — and **name the guard that produced each vertex**,
so a ring that needs planarising can be told from one that does not.

`TouchesBoundary` = any ring triangle has a hull agent **or is ill-shaped**. Both conditions, not just hull
adjacency — "interior plate" throughout this document means `not TouchesBoundary` in this full sense. Such plates
are unbounded in reality (ABxM extends them to the boundary by plane–boundary intersection; we flag and drop them
by default).

**"Hull agent" means an agent on the convex hull of the triangulation** — one incident to a boundary edge, an edge
belonging to exactly one triangle — and not the outer *band* of agents, which is the easy misreading and sizes the
set far too generously. Measured on the egg-crate hex seed it is **12 of 131** agents, and those 12 produce no
plate at all: they fail the interior test above, so they never reach the `TouchesBoundary` question. The drop from
131 agents to 85 interior plates is all three effects together: those 12 agents yield no plate, and of the 119
plates that do exist 34 are flagged `TouchesBoundary` — largely by the ill-shaped condition firing on the long
thin triangles just inside the hull, not by hull adjacency alone.
The interior plate set is what every side-ratio number in §8 is measured over, so getting its size right matters.

**Convexity (normative).** All turns the same sign about `N`, with the turn threshold **relative to spacing**
(`ε·Spacing²`, `ε = 1e-12`), **and** the ring must be simple (non-self-intersecting). A self-intersecting ring is
never a plate. Once the turns agree in sign the total turning is exactly `2πk` with `k ≥ 1`, and the ring is simple
iff `k = 1`, so the simplicity half needs no segment-intersection test — accumulate the signed turn angles and
require `|turning| < 3π`. Two degenerate cases follow from the same rule: a ring whose every turn fell below the
threshold is collinear, not convex, and a turn that is a *reversal* (below the threshold but with the two edges
antiparallel) is the ring doubling back on itself, so it is never convex.
(The reference implemented only the turn-sign half, with an absolute `1e-12` threshold and `true` for an all-skipped
ring, so it reported a doubly-folded ring as convex; it now implements this rule in full. The change moves no
measured number — the six egg-crate and two sphere configurations of §8, plus two further random seeds, reproduce
exactly, i.e. none of them produced a folded ring in the first place.)

### Why bow-ties where K < 0 (and not with Voronoi)

A plane close and parallel to the tangent plane at `p` cuts the surface in a curve that is, to first order, the **Dupin indicatrix** `κ₁x² + κ₂y² = ±1`: an ellipse where `K = κ₁κ₂ > 0`, a pair of hyperbolas where `K < 0`, two lines where `K = 0`. The TPI hexagon around `p` is cut from `T_p` by the six neighbouring tangent planes and is therefore approximately inscribed in that conic: **convex at elliptic points, non-convex (bow-tie/butterfly) at hyperbolic points** (WLP08 Prop. 1; LLW15 §3.1; S14 p.181; G18 §4.3). A negatively curved surface *cannot* be tiled by convex planar polygons with valence-3 vertices (WLP08). Voronoi cells on the surface are always convex — that is why the ICD systems use TPI and why a Voronoi/"clipping" plate generator only works on synclastic surfaces (B17 §6.3, G18 §4.3).

**Orientation (WLP08 Prop. 5, LLW15 §4.1).** The shape of the TPI hexagon depends on how the ring is oriented relative to the principal/asymptotic directions. Computed on the exact egg-crate saddle (`κ₁ = −κ₂`), regular ring of radius `s`, shortest/longest side:

| ring axis relative to **the asymptotic directions** | 0° (edge along an asymptote) | 5° | 10° | 15° (axis along a principal direction) |
|---|---|---|---|---|
| side ratio | **0.00** | 0.18 | 0.35 | **0.50** (two halves of a regular hexagon: the "ideal bow-tie") |

Read the angle from the **asymptote**: the 10° column is a 5° *misorientation* from the principal direction, not
10°. Independent of `s` (0.8–1.9) — the plan-form is scale-free; only the dihedral angles scale with κ·s. With
10 % jitter on the ring the aligned case keeps ~0.35–0.4, random orientation ~0.2–0.27; `HexJitter` is 0.15, so a
correct implementation can legitimately land near 0.38–0.40 rather than 0.50. Hence: seed/align the packing so
that a lattice axis follows a principal direction, and judge with the side-ratio metric, not by eye. Elliptic
anisotropic points (`κ₂ ≪ κ₁`, the valleys) want an affinely stretched ring for an affine-regular hexagon
(LLW15); a regular ring there gives uneven but convex plates — accepted.

Two facts worth remembering: (i) bow-ties need K < 0 and *regular, aligned* triangles, not strong curvature. (ii) Near `K = 0` the three planes are almost parallel and the parabolic band always needs a fallback (and, in the ICD papers, agents are steered out of it by a curvature-gradient behaviour and plates are planarised afterwards).

### Classification

`Classify(plate, bandFraction = 0.1)`: `|K| ≤ bandFraction · max|K|` → *parabolic band* (shape not meaningful),
else *elliptic* (K > 0) / *hyperbolic* (K < 0). `K` is the **agent's** Gaussian curvature, not a triangle average.

Two things that decide the number and are easy to get wrong:
- `max|K|` is taken over the **current plate set**, recomputed on every call. The boundary drop happens *before*
  classification, so dropping boundary plates changes the band threshold and moves plates between classes.
  Normative order: build plates → drop boundary plates → classify.
- A *third* `max|K|`, over all **agents**, is used by the TPI-fallback-by-class diagnostic. Do not confuse them.

## 4. Metrics (normative definitions)

Both headline metrics are quoted to two decimals in §8, so their populations are part of the specification.
They differ from each other — this is the single easiest thing to get wrong.

**Side ratio.** Per plate, `min(edge length) / max(edge length)`, `0` if the longest edge is zero. Reported
**per curvature class**; the headline number is **hyperbolic**. Population: the plate set **after** the boundary
drop (i.e. `not TouchesBoundary`, including the ill-shaped condition), classified per §3. Order statistics on the
ascending list use **raw nearest-rank, no interpolation**: `median = rs[n/2]`, `p10 = rs[n/10]` (integer
division). A host using an interpolating percentile will report slightly different numbers; say which you used.

**Alignment mean.** `mean(cos 12φ)` over **ordered agent→neighbour pairs**: for every agent with
`Anisotropy ≥ 0.5`, for every neighbour in its radius-`r` list, `φ` measured in **that agent's** frame per the
§1 sign convention. Population is **agents, not plates** — no boundary drop, no parabolic-band exclusion, hull
agents included. Note that since `Anisotropy = |κ₁−κ₂|/(|κ₁|+|κ₂|)` → 1 as `κ₂` → 0, this population is
*concentrated in* the parabolic band that the side-ratio metric excludes. The two metrics look at almost
disjoint parts of the surface.

The principal frame (`κ₁, κ₂, E₁, Anisotropy`) must be evaluated **independently of `AlignmentWeight`**:
gating it on the weight makes the alignment mean unmeasurable with the field off, which is exactly the
before/after comparison §8 needs. The reference did gate it; it no longer does (`Parameters.EvaluatePrincipalFrame`,
default on, is the opt-out for a host that neither uses the field nor reports the metric).

Both metrics have a reference implementation in the core (`Abm.Metrics.SideRatios` / `Abm.Metrics.AlignmentMean`),
not in the harness — a host reporting different numbers on the same configuration has a different population,
which is the failure this section exists to prevent. `φ` is skipped where the tangent projection of the
neighbour vector is degenerate (< 1e-9), since the angle is undefined there.

`Anisotropy = |κ₁ − κ₂| / (|κ₁| + |κ₂|)`, clamped to 1, zero when both are zero. `E₁` is re-tangentialised
(`e₁ − N(e₁·N)`) and re-normalised after evaluation — a kernel's principal direction is not guaranteed exactly
tangent.

## 5. The surface contract

Kernel-neutral. A host must provide, for a parametric patch `S(u,v)`:

| Capability | Notes |
|---|---|
| `domain` | `u0, u1, v0, v1` |
| `topology` | per direction: closed (seam) / singular (pole) / real boundary. Sphere = closed in u + singular at both v ends; cylinder = closed in u; torus = closed in both; trimmed patch = all real boundaries. Real boundaries get containment; seams and poles do not. |
| `point_at(u,v)` | |
| `normal_at(u,v)` | unit |
| `derivatives_at(u,v)` | `(Su, Sv)`. **Required** — the auto seed angle needs the first fundamental form (§1). |
| `gaussian_at(u,v)` | kept separate from `κ₁κ₂`: classification bands are relative to `max|K|`, so a different K evaluation moves plates between classes. |
| `principal_at(u,v)` | `(κ₁, κ₂, e₁)`. Use the kernel's own if it has one; otherwise §5.1. |
| `closest_uv(p, hint)` | see below |
| area | `|Su×Sv|`; the reference sums bilinear patches on a 48×48 grid. |

**`closest_uv` is the closest point on the surface**, returned as an in-domain parameter. Newton /
projected-gradient on `|S(u,v) − p|²` from the agent's current `(u,v)` converges in 3–5 steps because steps are
≤ 0.5·spacing. **Seam handling is the host's job**: `closest_uv` wraps across a seam and returns an in-domain
parameter (a sphere host does this naturally via `atan2` normalised to `[0,2π)` and `asin`); the solver clamps
only as a guard, and that clamp must never be relied on to implement wrapping — clamping at a seam piles agents
against both ends of it. Finite-difference stencils near a seam must wrap too.

*Reference approximation, flagged:* the harness's Monge host returns `(clamp(p.x), clamp(p.y))` — a **vertical
drop**, not the closest point. On the egg-crate the slope reaches ~43°, so the re-projected tangential step is
stretched by ≈ 1/cos(slope) ≈ 1.37, concentrated on the steep flanks — which is where the side ratio is measured.
A host implementing a true closest point is more correct and will differ from §8 slightly for this reason.

### 5.1 Curvature without a kernel curvature API

With `Su, Sv` (first) and `Suu, Suv, Svv` (second): `N = (Su×Sv)/|Su×Sv|`, `E = Su·Su, F = Su·Sv, G = Sv·Sv`,
`L = Suu·N, M = Suv·N, Nn = Svv·N`, **`K = (L·Nn − M²)/(E·G − F²)`**. For a height field `z = f(x,y)` this reduces
to `K = (f_xx f_yy − f_xy²)/(1 + f_x² + f_y²)²`.
Principal curvatures/directions: shape operator `S = I⁻¹·II` (2×2), eigenvalues κ₁, κ₂, eigenvector (α,β) →
`e₁ = α·Su + β·Sv`. All of it can be built from `point_at` and `normal_at` alone by central differences
(`h = 1e-4·domain`; `L = −Su·Nu` etc.), which is the portable fallback for any kernel that exposes neither second
derivatives nor principal directions — a common situation, and worth checking before committing to a kernel.
Analytic derivatives are not required: only the sign of K, the |K| ranking and the principal *directions* are
used. Mesh hosts: barycentric closest point + per-vertex curvature (libigl / compas `principal_curvature`).

## 6. Defaults and what they mean

| Parameter | Default | Meaning / how to pick |
|---|---|---|
| `Count` | 100 | **nominal**; hexagonal seed realises fewer (131 of 150 on the egg-crate). Plates ≈ realised − hull − boundary ring (closed surface: = realised) |
| `Spacing` | 0 = auto | `sqrt(A/(0.866·Count))` from **surface** area; written back into the parameter object once computed, and **not** recomputed after the seed rejects agents — so an equilibrium packing sits ≈ `Spacing·sqrt(Count/realised)` apart, ~7 % above `Spacing` at the default. Do not assert mean neighbour distance against `Spacing` without this correction. |
| `Iterations` | 500 in the core, **1000 in both harnesses** | hexagonal seed converges in ~50–200, random in ~400–900, sphere ~200–600 (601 at 150 agents). 500 is too low for the sphere; use 1000. |
| `Speed` | 0.2 | ≤ 0.3 stable; smaller = slower, not better |
| `SeparationWeight / CohesionWeight / ContainmentWeight` | 1.0 / 0.3 / 1.0 | keep the ratio; cohesion > 0.6 gains nothing |
| `AlignmentWeight` | 0.3 | 0 = off; 0.3–0.6 improves random-seed bow-ties; inert where anisotropy = 0 (sphere) and inert on an already-aligned hex seed |
| `HexAngle` | NaN = auto | degrees in **raw** uv; set explicitly to test "wrong" orientations |
| `HexJitter` | 0.15 | fraction of the lattice pitch, uniform square box in raw uv |
| `CentroidWeight` | 0 | optional shape smoothing; costs a triangulation per iteration |
| `NeighbourRadiusFactor` | 1.5 | 1.8+ includes the second ring → overcrowding |
| `InitialLayout` | Random | `Hexagonal` for production-quality valence (open patches) |
| `ConvergenceFactor` | 1e-3 | of Spacing, on realised post-reprojection displacement |
| `bandFraction` | 0.1 | of `max|K|` over the post-drop plate set |

Cost: neighbours O(n²) per step in the reference (fine to ~1000 agents; G18 uses an R-tree beyond that); Delaunay
O(n²) only at the end (or every step if `CentroidWeight > 0`); local triangulation O(n·k²) once. Principal
curvature by finite differences = 8 host evaluations per agent per step.

## 7. Deviations from the papers (be honest about them)

- Weighted **sum** of behaviours (G18), not the prioritised sequence of S14.
- Position-based update (2023 PolyAgent), not S14/G18's force–velocity boids.
- Principal-direction alignment as a local 12-fold pair behaviour + global seed orientation, not LLW15's global direction field / remeshing.
- No curvature-gradient steering out of parabolic zones (S14); instead TPI fallback + classification.
- Boundary plates are flagged/dropped, not extended to the boundary (ABxM `BoundaryPlateExtension`).
- No post-planarisation / fabrication behaviours (edge length, dihedral angle, plate radius — G18 PTA/EAE/ELE/MNEL, B17 layers). They slot into the behaviour sum as further terms.

## 8. Acceptance — what "working" looks like

Criteria fall into four classes. Only the first two are assertable across hosts; treating an identity as evidence
is how a broken implementation passes a green suite.

**(a) Invariants — must hold exactly, on the stated surface and seed**
- Egg-crate `h=3 periods=2`, hexagonal seed, auto angle: **0 convex hyperbolic** and **0 concave elliptic**
  plates, outside the parabolic band and the boundary set, with a spacing-relative convexity tolerance.
  *Conditional on surface and seed*: the random seed produces 0–2 concave elliptic and up to 1 convex hyperbolic
  plate, and the `periods=1, h=5` surface produces 4 convex hyperbolic under the *hexagonal* seed and 1–2 under the
  random seed (its saddles have tiny |K| — §9 warns it is a poor bow-tie test). Do not assert this unconditionally.
- Every interior edge carries exactly two oppositely-directed half-edges.

**(b) Statistics — must fall inside the band** (egg-crate, nominal `Count = 150`)

| Quantity | Random seed (align 0.3) | Hexagonal seed, auto angle |
|---|---|---|
| realised agents | 150 | 125–135 (measured 131) |
| interior plates | ~88 | ~85 |
| `converged` | True, ≤ 900 iterations | True, ≤ 200 (measured 51–56) |
| hexagon share (interior plates) | 75–85 % | **90–96 %** (measured 81 of 85 = 95.29 %, all five seeds) |
| hyperbolic side ratio (median / p10) | 0.20–0.28 / ~0.06 | **0.38–0.46 / ≥ 0.32** (measured 0.40–0.41 / 0.33 over 5 seeds) |
| alignment mean cos(12φ) | ~0.31 (−0.22 with the field off) | ~0.65 (0.61 with the field off) |
| TPI fallbacks | 25–35 % of triangles | same |

Sphere `R = 10`, random seed: converged (174–457 its at 60 agents, 601 at 150); plates = agents; all convex;
side-ratio median ≈ 0.6; **0** TPI fallbacks.

The hex-seed hexagon share was **90–95 %** in every revision of this document up to 2026-08-23, and a correct
implementation fails it: 81 hexagons of 85 interior plates is 95.29 %, on all five seeds, to the digit, with the
rest of that column reproducing the reference exactly. The cause is arithmetic and not disagreement — 95.29 %
quoted as "95 %" and then read back as an inclusive upper bound loses the 0.29 %. It is banded at 90–96 % here;
stating it as `≥ 90 %` with no upper bound is equally defensible, since there is no failure mode that a hexagon
share which is too *high* would catch. This is the same error class as A1's do-nothing detector and A7's pentagon
count — **an acceptance number that a correct implementation fails** — and the third instance of it in this
specification. When a band is missed by a fraction of a percent, measure the reference before moving anything.

**(c) Identities — report, never assert as evidence.** On a closed surface `Euler V−E+F = 2` is forced by the
triangulation closing; `Σ(6 − valence) = 12` follows from `3F = 2E` and `χ = 2`; `triangles = 2N − 4` likewise;
mean interior valence ≈ 6 is pinned by Euler regardless of where the points are — a jittered hex seed with **zero
iterations run** passes all of them. `pentagons − heptagons = 12` *is* falsifiable (a square or octagon breaks it
while the identity holds) and may be asserted; **"exactly 12 pentagons" may not**, and a criterion of the form
"exactly 12 in ≥ *k* of *n* seeds" is the same statement wearing a quantifier and may not be asserted either.
`p5 − p7 = 12` is the Euler defect and is forced; how the defect *splits* between pentagons and heptagons is a
property of the RNG stream, and RNG streams are not portable (§1, (d) below). Measured in two hosts over 6 sphere
seeds each:

| | seeds giving exactly 12 pentagons | `p5 − p7 = 12` |
|---|---|---|
| reference (C#), 60 agents | 5 of 6 (the sixth gave 14 p5 + 2 p7) | 6 of 6 |
| Python host, 150 agents (p5 = 14, 13, 12, 14, 12, 13) | **2 of 6** | 6 of 6 |

A "≥ 4 of 6" criterion would therefore have passed on the reference it was written from and failed on a correct
second implementation, while the identity held in all twelve runs. Report the distribution — it is evidence about
the *seeder* — and assert only the difference.

**(d) Not portable — never assert across hosts.** Wall-clock cost (the reference runs in < 0.1 s; a host built on
boxed geometry types will be one to two orders slower and that is not a defect). RNG streams, hence seed-for-seed
comparison of any kind.

**Discriminating tests.** A suite built only from (a) and (b) can still pass with a behaviour missing. Two
configurations, both measured, that actually fail when something is wrong:

| Test | Config | Correct | Broken |
|---|---|---|---|
| Seed orientation | hex, `HexAngle = 0`, alignment on | median 0.40 | **0.07**, alignment mean **−0.40** |
| Alignment behaviour | random seed, align 0.3 vs 0 | 0.23, alignment **+0.31**, converges | **0.12**, alignment **−0.22**, does **not** converge in 1000 its |

The first does not self-correct: a misaligned seed sits on a *maximum* of the 12-fold potential and 1000
iterations of an active field do not rescue it. The second is the only configuration that exercises alignment at
all.

**The do-nothing detector — banded by seed, not an invariant.** `maxDisplacement` must fall by at least **40×**
(hexagonal seed) or **100×** (random seed) between the first iteration and the last, and the spread of neighbour
distances must drop below the seed's jitter spread. Measured on the reference, egg-crate `h=3 periods=2`,
`Count = 150`, five seeds each: hexagonal **61–67×** (first 0.117–0.127, last 0.0019, 51–56 iterations), random
**316–460×** (first 0.60–0.87, last 0.0019, 556–602 iterations); the Python host measures 57–61× and 367–501× on
the same configurations. The gap between the two seeds is structural, not an artefact of either language: a
jittered hexagonal seed at the auto angle starts close to equilibrium — a first displacement of only ~0.06·`Spacing`
— while every run terminates at `ConvergenceFactor·Spacing` = 1e-3·`Spacing`. Two orders of magnitude are not on
offer there. It is a **banded statistic** in the sense of (b), and the band differs by seed exactly as the
side-ratio band does.

Keep the detector. It is the only criterion here that catches a solver which runs but does nothing — every
identity in (c) passes without it, which is (c)'s own point — and only its threshold was ever wrong. Until
2026-08-23 it read "≥ 2 orders of magnitude" unconditionally, which **the reference itself fails** on the
hexagonal seed at 67×. That is the same class of error as asserting mean neighbour distance against `Spacing`,
which §6's `Spacing` row warns off for the same reason: an acceptance number that a *correct* implementation
fails. It survived three adversarial reviews of the derived spec because nobody ran it against the reference.
Run every threshold written here against the reference before writing it.

## 9. Test surfaces

`z = h·cos(w x)·cos(w y)`, `w = periods·π/L`, on `[−L/2, L/2]²`.
- `periods = 1, h = 10, L = 20`: dome in the centre, steep saddles at the corners (|K| tiny there — poor bow-tie test; the harness default `h = 5, periods = 1` produces convex hyperbolic plates for this reason).
- `periods = 2, h = 3, L = 20` (**recommended, and what §8 is measured on**): dome, four valleys at mid-edges (K>0), four flat strongly anticlastic saddles at (±L/4, ±L/4) with |K| equal to the dome's. Principal directions at the saddles are the diagonals, asymptotic directions the axes — which is exactly why a uv-aligned hex seed fails there.
- Sphere `R = 10`: the closed-surface test (seam + poles, pentagons, Euler).
