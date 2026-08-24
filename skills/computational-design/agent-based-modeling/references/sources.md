# Sources — agent-based hexagonal plate tessellation

Tags used in SKILL.md / algorithm.md: **S14**, **G18**, **B17**, **LLW15**, **WLP08**, **T08**, **Z12**, **BUGA19**, **R87**.
The **Librarian** column holds local reference-library ids and will mean nothing outside it; every
entry is identified by its DOI or URL, which is the column to use.

## Primary (the ICD Stuttgart line — where the strategy comes from)

| Tag | Reference | DOI / URL | Librarian |
|---|---|---|---|
| S14 | Schwinn T., Krieg O.D., Menges A. (2014) *Behavioral Strategies: Synthesizing design computation and robotic fabrication of lightweight timber plate structures*. ACADIA 2014 "Design Agency", pp. 177–188. **Most explicit algorithm description**: plate agent = point + tangent plane; Delaunay in (u,v) + 3D edge flip (Troche) → TPI; containment / curvature-gradient / planarity / plate behaviours, *prioritised* combination; circumcircle validity rule for TPI points. | 10.52842/conf.acadia.2014.177 — PDF: papers.cumincad.org/data/works/att/acadia14_177.content.pdf | 3257 |
| G18 | Groenewolt A., Schwinn T., Nguyen L., Menges A. (2018) *An interactive agent-based framework for materialization-informed architectural design*. Swarm Intelligence 12:155–186. ABxM framework: behaviours store movement vectors, **summed**, scaled by a global factor, applied synchronously, agent pulled back to the surface; R-tree neighbour search; convergence = max displacement below threshold; behaviour catalogue (LGCS, LPSE, PC, PTA, EAE, ELE, MNEL). | 10.1007/s11721-017-0151-8 | 20817 |
| B17 | Baharlou E. (2017) *Generative agent-based architectural design computation* (ICD Research Reports 01, ed. Menges). Two-level agent morphology (plane + polygonal base), adhesion/repulsion on circumscribed circles, naked agents at the boundary, Dupin-duality validity test, inhibitory IF/THEN layers (connection angle, polygonal radius, internal angle). | ISBN 978-3-9819457-0-6 | 20787 |
| BUGA19 | Alvarez M., Wagner H.J., Groenewolt A., Krieg O.D., Kyjanek O., Sonntag D., Bechert S., Aldinger L., Menges A., Knippers J. (2019) *The BUGA Wood Pavilion*. ACADIA 2019, pp. 490–499. 376 cassettes; agents near fold lines constrained to a regular arrangement, apex agents free. | 10.52842/conf.acadia.2019.490 — PDF: papers.cumincad.org/data/works/att/acadia19_490.pdf | 3439 |
| — | Krieg O.D. et al. (2015) *Biomimetic Lightweight Timber Plate Shells*. AAG 2014, pp. 209–225. | 10.1007/978-3-319-11418-7_8 | — |
| — | Schwinn T., Menges A. (2015) *Fabrication Agency: Landesgartenschau Exhibition Hall*. AD 85(5):92–99. | 10.1002/ad.1960 | — |
| — | Schwinn T. (2021) PhD *A systematic approach for developing agent-based architectural design models of segmented shells*, Univ. Stuttgart. | 10.18419/OPUS-11633 | — |
| — | Schwinn T., Siriwardena L., Menges A. (2023) *Integrative Agent-Based Architectural Design Modelling for Segmented Timber Shells*. AAG 2023 — PolyAgent / VertexAgent, **position-based (Cartesian) update, "faster convergence than previous force-based approaches"**. | 10.1515/9783111162683-014 | — |
| — | Baharlou E., Menges A. (2015) *Toward a Behavioral Design System: An Agent-Based Approach for Polygonal Surface Structures*. ACADIA 2015. | papers.cumincad.org/data/works/att/acadia15_161.pdf | — |

## Geometry of planar hexagonal meshes (why bow-ties)

| Tag | Reference | DOI / URL | Librarian |
|---|---|---|---|
| LLW15 | Li Y., Liu Y., Wang W. (2015) *Planar Hexagonal Meshing for Architecture*. IEEE TVCG 21(1):95–106. Dupin indicatrix → face is convex at elliptic points, concave (bow-tie) at hyperbolic points; "ideal" triangles; pentagon/heptagon (N5−N7=12) defects; centroid dual for parabolic triangles; hybrid PH–PQ. | — | 20819 |
| WLP08 | Wang W., Liu Y., Yan D., Chan B., Ling R., Sun F. (2008) *Hexagonal meshes with planar faces*. HKU CS TR-2008-13. Prop. 1 (vertices O(h²) from a Dupin conic), Prop. 4/5 (validity conditions for K>0 / K<0), negatively curved surfaces cannot be tiled by convex planar polygons with valence-3 vertices. | cs.hku.hk/data/techreps/document/TR-2008-13.pdf | — |
| — | Wang W., Liu Y. (2009) *A note on planar hexagonal meshes*. IMA Vol. 151, pp. 221–233. | 10.1007/978-1-4419-0999-2_9 | — |
| T08 | Troche C. (2008) *Planar hexagonal meshes by tangent plane intersection*. AAG 2008, pp. 57–60. The TPI construction and the shortest-Cartesian-distance edge flip. | (no open PDF) | — |
| Z12 | Zimmer H., Campen M., Herkrath R., Kobbelt L. (2012) *Variational Tangent Plane Intersection for Planar Polygonal Meshing*. AAG 2012, pp. 319–332. TPI as a 3×3 system, singular for near-parallel planes (K→0 / tiny triangles); VTPI frees the normals. | 10.1007/978-3-7091-1251-9_26 — preprint graphics.rwth-aachen.de/media/papers/zimmer_aag12_preprint_annotated.pdf | — |
| — | Pottmann H., Eigensatz M., Vaxman A., Wallner J. (2015) *Architectural geometry*. Computers & Graphics 47:145–164. | 10.1016/j.cag.2014.11.002 | — |
| — | Pottmann H., Asperl A., Hofer M., Kilian A. (2007) *Architectural Geometry*. Bentley Institute Press. | — | — |
| — | Cutler B., Whiting E. (2007) *Constrained planar remeshing for architecture*. Graphics Interface 2007, pp. 11–18. | — | — |

## Agent systems

| Tag | Reference | DOI / URL |
|---|---|---|
| R87 | Reynolds C.W. (1987) *Flocks, herds and schools: a distributed behavioral model*. SIGGRAPH 21(4):25–34. Separation / alignment / cohesion. | 10.1145/37401.37406 |
| — | Reynolds C.W. (1999) *Steering behaviors for autonomous characters*. GDC 1999, pp. 763–782. Prioritised (not weighted-sum) combination. | red3d.com/cwr/steer/ |
| — | Shiffman D. (2012) *The Nature of Code*, ch. 6 (autonomous agents). | natureofcode.com |
| — | Persson P.-O., Strang G. (2004) *A simple mesh generator in MATLAB*. SIAM Review 46(2):329–345. DistMesh: repulsive-only springs with target length 1.2·h on a Delaunay graph — the regular-packing trick. | 10.1137/S0036144503429121 |

## Open-source code

| What | Where | Notes |
|---|---|---|
| **ABxM.Core** 1.7.0 (MIT, C#, .NET 4.8, Rhino 7/GH) | DaRUS doi:10.18419/DARUS-2994; food4rhino.com/en/app/abxmcore | Behavior / Agent / AgentSystem / Environment / Solver base classes; Boid (force), Cartesian (position), matrix, mesh, network systems. |
| **ABxM.PlateStructures** 1.1.2 (MIT) | DaRUS doi:10.18419/DARUS-3438 | `PlateAgent : Boid`, `EdgeAgent`, `TpiPlateGenerator` / `VoronoiPlateGenerator` / `SlicingPlateGenerator`, behaviours listed in algorithm.md §behaviours; tutorial `.gh` files. Used for Landesgartenschau 2014, BUGA 2019, LCRL roof 2023. |
| Culebra (GPL-3) | github.com/elQuixote/Culebra | flocking/wander/path/mesh-crawling; no plates. |
| Quelea | github.com/lxfschr/Quelea | particles/boids with surface flow, containment; no plates. |
| ICD project pages | icd.uni-stuttgart.de/projects/landesgartenschau-exhibition-hall/ · …/buga-wood-pavilion-2019/ · …/icditke-research-pavilion-2011/ · …/research/research-tools/abxm-framework/ | photos of convex-on-dome / bow-tie-on-saddle plates. |

## Reference implementation in this skill

`core/AbmCore.cs` (plain C#) + `hosts/dotnet` (console harness, analytic surfaces) + `hosts/grasshopper` (Rhino 8 C# Script via Cordyceps). Exact behaviours, defaults and the deviations from the papers are in `algorithm.md`.
