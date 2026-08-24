# `compas_timber` ABM host

A Python/COMPAS host for the agent-based modelling strategy: relax agents on a doubly
curved surface, derive tangent-plane-intersection plates, and (Levels 2–3) turn each plate
into a `compas_timber.elements.Plate` in a `TimberModel` and export BTLx.

It implements `../../references/algorithm.md`, which is **normative**. It shares **no code**
with `core/AbmCore.cs` — that is the point of it. Two independent implementations of the same
specification disagreeing is information; a port agreeing with its original is not.

## What it needs

**Level 1 (geometry) needs numpy and scipy, and nothing else.** `abm/` imports no COMPAS at
all, and `run.py --no-timber` stops before the fabrication stage. That separation is
deliberate: **a geometry regression must never be maskable by a fabrication-library failure.**

**Levels 2–3 (timber plates, BTLx) additionally need `compas_timber`**, which brings COMPAS
and, for the solid check, a Brep backend:

```
pip install numpy scipy compas_timber
```

| | needed by | verified at |
|---|---|---|
| numpy, scipy | `abm/`, `run.py`, `viz.py` — everything at Level 1 | 2.4.2 / 1.17.1 |
| `compas_timber` + COMPAS | `timber.py`, `btlx.py` — Levels 2–3 only | `v2.2.0-195-gd6dd441af6`, COMPAS 2.15.1 |
| Python | all of it | 3.14.6 |
| pytest | `tests/` | 9.0.2 |
| `xmlschema` | *optional*, BTLx schema validation only — see **BTLx** below | any |

**Read the verified column as a pin, not a floor.** This host has only ever been run against
`compas_timber` at `d6dd441af6`, not against a release tag, and several of its workarounds
(the `<Shape>` block, the tolerance round trip, the `MIN_SIDE` order) are written against
behaviour observed at exactly that commit. On a newer `compas_timber` the geometry tests
should be unaffected — they import none of it — while `tests/test_timber.py` and
`tests/test_btlx.py` are the ones to run first, since a workaround that upstream has since
fixed will fail there and that is the intended signal.

## Running it

```powershell
python run.py --surface monge --agents 150 --seed hex --no-timber          # Level 1
python run.py --surface monge --agents 150 --seed hex --thickness 0.02     # + Level 2
python run.py --surface sphere --agents 150 --seed random --no-timber      # closed surface
python run.py --surface tube --agents 150 --seed random --tube-barrel 0.35 --no-timber
python -m pytest tests/ -q                                                 # 156 tests, ~5 min
python -m pytest tests/ -q -m "not slow"                                   # 126 of them, ~66 s
```

Give every run its own `--json` path. Parallel runs sharing one clobber each other; this
already bit the .NET harness.

## Units

**The model unit is the metre** in the solver, matching the reference's `L = 20`,
`spacing ≈ 1.92`. The conversion to millimetre happens exactly **once**, at the `timber.py`
boundary (`Tolerance(unit="MM")`), and nowhere else.

Every geometric tolerance is relative to `spacing` (§2). The only permitted absolute
constant is the plane-solve determinant `1e-9`, which is dimensionless because the normals
are unit vectors.

## Choices this host makes, that another host could make differently

- **Order statistics are raw nearest rank** — `rs[n // 2]`, `rs[n // 10]` — not
  interpolated. §4 requires the raw rank and requires a host to say which it used; numpy's
  `percentile` would report slightly different numbers on the same plates.
- **`orient_ccw` propagates orientation across shared edges** rather than applying §3.1's
  per-triangle `cross·N` test, which is not sufficient (algorithm.md §3.1).
- **Curvature on `TubeSurface` comes from `fd_principal`** — point and normal only, no second
  derivatives — so the portable §5.1 fallback is exercised on at least one surface, since it
  is what a host on an unhelpful kernel will have to use.

(What this host does *not* do at all is under **Host limits** below.)

## Looking at a run

```powershell
python run.py --surface monge --agents 150 --seed hex --thickness 0.02 `
     --geometry-json egg.json --mesh egg.stl
python ..\dotnet\render.py egg.json egg.png      # an interpreter with PIL
```

**Neither route adds a dependency to the environment the solver runs in.** No PIL, no
matplotlib and no viewer: rendering is a separate interpreter's job, and `render.py` is run
with one that has PIL.

- **`--geometry-json`** writes the schema `hosts/dotnet/render.py` already consumes, so the
  same script draws both hosts and the two sets of PNGs are directly comparable. Four images:
  plan, `-axo`, and a `-kneg`/`-kpos` catalogue of every plate seen along its own normal —
  the catalogue is the one that settles "do these look like bow-ties". Green convex, red
  non-convex, amber where the TPI guard fired, thin grey for the dropped boundary plates,
  pink where `K < 0`. It imports nothing but numpy, so `--no-timber --geometry-json` is a
  Level 1 picture that touches no COMPAS.
- **`--mesh`** tesselates the built solids to `.stl` or `.obj` — the Breps in millimetres,
  not a re-plot of the numpy rings, so it carries the thickness and the rejections. Opens in
  Windows 3D Viewer, Blender, Rhino or FreeCAD. Note viewers carry no units: a 2.4 m plate
  reads as 2400.

Baking into Rhino through the Cordyceps MCP server would be the third route and is **not
built** — this host touches no Rhino.

On the egg-crate the pink `K < 0` bands and the red plates land exactly on top of each
other, which is the classification agreeing with the surface rather than with itself. On the
developable tube every plate is a clean green convex hexagon at 100 % hexagons and a side
ratio of 0.87 — the best-looking numbers on any surface here, and all 280 rings are
circumcentre polygons rather than TPI hexagons. **The prettiest picture is the worthless
one, and no number in the report says so.** That is what the pictures are for.

## Host limits, stated plainly

Each of these is a deliberate v1 boundary, not an oversight.

- **`centroid_weight` is not implemented** and raises rather than being silently ignored.
  It costs a full triangulation per iteration, regularises shape rather than valence, and
  fights separation; §6 has it off by default.
- **NURBS surfaces are out of v1.** `Surface` is a protocol, so a NURBS host is a matter of
  implementing six methods — but not through COMPAS's OCC backend as it stands: no NURBS
  surface plugin was installed in the verified environment (`NurbsSurface.from_points` raises
  `PluginNotInstalledError`), and on the abstract class both `curvature_at` and `normal_at`
  are bare `raise NotImplementedError`, with no principal curvatures and no D2 derivatives
  exposed. `fd_principal` — point and normal only — is the portable answer and is exercised
  by `TubeSurface`.
- **Joinery is out of scope.** `connect_adjacent_plates()` and `compute_topologies()` are
  never called. The former no longer exists on this HEAD in any case.
- **Boundary plates are dropped, not trimmed or extended.** The normative order is build →
  drop → classify, and classification's `max|K|` is recomputed over the surviving set, so
  the drop moves the band. 34 of 119 plates go this way on the egg-crate.
- **The edge-flip pass is a function of the triangle container's ordering.** That is
  reference behaviour and one legitimate source of small cross-host differences; it shows
  up as iteration counts 2–23 higher than the C#'s on identical configurations.
- **Only the seam is wrapped, not the parameter-space distance.** Neighbour queries are in
  3D (`cKDTree` on positions), which is the normative result set and sidesteps the question.

## The tube caveat — a developable surface is not a plate test

**A right circular cylinder is developable.** `k2 = 0` and `K = 0` everywhere, so every
plate lands in the parabolic band, the three tangent planes around each triangle are
near-parallel, and the TPI solve is ill-conditioned wherever it is not outright degenerate.
Measured, `--surface tube --agents 150 --seed random`:

| | developable (`--tube-barrel 0`) | barrelled (`--tube-barrel 0.35`) |
|---|---|---|
| TPI fallbacks | **280 of 280 = 100 %** | 92 of 279 = 33 % |
| interior plates | 95, all parabolic | 94, all elliptic |
| side ratio median | 0.87 | 0.11 |

The developable column is not a regression and not a bug. **The tube tests seam wrapping
and the boundary/seam mix; it does not test plate geometry.** Every ring on it is a
circumcentre polygon from the §3.2 fallback, not a TPI hexagon, so its 100 % hexagon share
and its 0.87 side ratio are statistics about the fallback and mean nothing about the
strategy. Use a barrelled or tapered tube if you want plates.

**But the barrelled tube is not yet a calibrated test surface either, and this host does not
claim it is.** 63 of its 94 elliptic plates come out concave, which the strategy's own
"elliptic concave = 0" would flag, and the side-ratio median of 0.11 reads like the
misaligned-seed symptom. It is not the alignment field — that is live here at 0.44 over 866
pairs, and the plates barely moved when it was switched on. What this leaves is an open
question about highly anisotropic elliptic points, recorded rather than resolved: this
host's acceptance surfaces are the egg-crate and the sphere.

### What the tube found: a defect in this host, on every surface of revolution

Adding it was worth it before a single plate was drawn. On any surface whose parametrisation
is **already principal** — every surface of revolution: tube, cone, dome, vault — the shape
operator's off-diagonals are rounding noise at ~1e-17 rather than exact zeros. `_eig2`
tested them against an absolute `1e-300`, took the `(a12, k1 − a11)` branch, and built an
eigenvector from two quantities that are both noise; `_principal_from_shape` then found its
norm under the 1e-14 floor and returned the **zero vector**. `anisotropy` is forced to 0
whenever `e1` is zero, so the 12-fold alignment field went **silently inert** on exactly the
class of surface whose anisotropy it exists to exploit — the misaligned-packing failure mode
the strategy warns about, with no symptom except bad plates.

The egg-crate never hit it (its parametrisation is not principal), the sphere never hit it
(umbilic, so anisotropy is 0 either way), and the *developable* tube never hit it (exact
symbolic zeros take the correct branch). Only the barrelled tube exposes it. The fix is to
scale the off-diagonal test by the matrix magnitude, which is what §2's "every geometric
tolerance is relative" required in the first place.
Regression: `test_a_principal_parametrisation_still_yields_a_usable_principal_direction`.

## The bands this host asserts, and the measurements behind them

Every band below is a *banded statistic* in `algorithm.md` §8's four-class sense: a correct
implementation lands in a range that depends on the seed and the surface, so a single number
here would be a bug in the specification rather than a criterion. Each is stated with what was
measured, over five seeds, in both this host and the C# reference.

| band | asserted | measured |
|---|---|---|
| do-nothing detector | **≥ 40× hex, ≥ 100× random** | 57–72× here over five seeds, 67× in the C#. A single unqualified "two orders of magnitude" is failed by *both* implementations on a hex seed: at the auto angle it starts near equilibrium, ~0.066·spacing, and every run stops at 1e-3·spacing. |
| hexagon share, hex seed | **90–96 %** | 81 hexagons of 85 interior plates = 95.29 %, on all five seeds, with the rest of the row reproducing the C# exactly. An upper bound of 95 % excludes the configuration it describes. |
| sphere pentagon count | **≥ 12; the distribution is reported, not asserted** | 14, 13, 12, 14, 12, 13 over six seeds — exactly 12 in only 2 of 6 — while `p5 − p7 = 12` holds in all six and in the C#. The split between pentagons and heptagons is an RNG-stream property and RNG streams are not portable; §8(c) says only the difference may be asserted. |
| ring planarity | **planar only where the TPI solve succeeded** | A fallback vertex is a circumcentre or centroid and lies in neither tangent plane; 29 % of egg-crate triangles take that path, leaving 50 of 85 interior plates off the tangent plane by up to 11 % of spacing. |

## Level 2 — the timber stage

Every interior plate either builds or is rejected by a **named, pre-declared** criterion.
The four are `MIN_SIDE`, `NON_PLANAR`, `SELF_INTERSECTING` and `BUILD_FAILED`, checked in
that fixed order so a ring failing two of them is always attributed to the same one.
`MIN_SIDE` is `0.05·spacing` and is passed in rather than hard-coded — a length that is only
meaningful relative to spacing has no business being a constant inside `build_model`.

Measured over three seeds each, thickness 20 mm:

| configuration | interior plates | elements | rejected |
|---|---|---|---|
| egg-crate, hex | 85 | **85** | 0 |
| egg-crate, random | 95–97 | 84–87 | 10–12, all `MIN_SIDE`/`SELF_INTERSECTING` |
| sphere, random | 150 | 144–150 | 0–6, all `MIN_SIDE` |

**Planarisation is mandatory, not a refinement** (algorithm.md §3.3). `planarise` fits the
total-least-squares plane — orientation-independent, so a ring standing on the egg-crate's
43° flanks is fitted as well as a flat one — and moves every vertex along that plane's
normal only, so the in-plane footprint survives. It costs a corner movement of up to 7 % of
spacing and is reported on every run as `timber.planarity_residual_mm`; the result clears
compas_timber's 3.3e-10 planarity budget by two and a half orders of magnitude.

Two upstream behaviours the stage is shaped around, both found by running code:

- `PlateGeometry` derives its frame from three **consecutive** vertices, because its search
  for a third non-colinear point never breaks out of its loop. `rotate_to_sharpest_corner`
  therefore chooses the ring's start index to maximise that triple's conditioning. (The
  plan's name for it describes the wrong end of the measure — the winner is usually the
  flattest corner, not the sharpest — and is kept so plan, test and code agree.)
- A true bow-tie is accepted silently and yields a Brep reporting `is_solid=True` with a
  **negative** volume and `is_valid=False`. `is_valid_solid` guards on validity and volume;
  a host guarding on the obvious `is_solid` passes it straight through.

`run.py` publishes the diagnostics as the payload's `timber` block and keeps the model out
of it under `timber_model` — the model is not JSON-serialisable, and `--json` failing at the
very end of a two-minute run is a bad way to find that out.

## Level 3 — BTLx

```powershell
python run.py --surface monge --agents 150 --seed hex --thickness 0.02 --btlx out.btlx
python btlx.py out.btlx       # validate an existing file
```

Measured: the 85-part egg-crate export validates against the **real BTLx 2.0.0 xsd with 0
errors**, reads back as 85 parts at 20.0 mm, and every part comes back with two contour
features where one was written. `Version="2.0.0"` is what compas_timber's writer pins
(`fabrication/btlx.py:56`) and each BTLx schema accepts exactly one `Version`, so 2.0.0 is
the schema — confirmed, per the `working-with-btlx` skill's standing rule, not remembered.

Two deliberate constraints:

- **The xsd is not vendored, and has no default path.** BTLx schemas are vendor files with
  no redistribution rights — design2machine's site is the only official channel — so
  shipping one would redistribute it. Set `BTLX_SCHEMA_DIR` to the directory holding
  `BTLx_2_0_0.xsd`. Without it the validation test **skips** rather than passing, so the
  suite still runs on a machine without the archive and "not checked" never reads as clean.
- **`xmlschema` is not a dependency of this host.** Validation is optional and nothing else
  needs it, so rather than adding it to the environment the solver runs in, the validator
  lives in its own throwaway venv and `btlx.py` shells out to it:

  ```powershell
  $VALIDATOR = "$env:LOCALAPPDATA\abm-btlx-validator"      # or set ABM_BTLX_VALIDATOR
  python -m venv $VALIDATOR
  & "$VALIDATOR\Scripts\python.exe" -m pip install xmlschema
  ```

`validated` in the payload's `btlx` block is three-valued. "0 errors" and "not checked"
must never look the same, and they would if a missing schema quietly reported a clean file.

**`export_btlx` clears the element geometry cache, and that is a workaround.** Building the
optional `<Shape>` block raises `AttributeError: 'Plane' object has no attribute 'frame_at'`
on COMPAS 2.15.1 — a planar `OccBrepFace.surface` is a `Plane` and
`fabrication/btlx.py:654` calls `frame_at(0.5, 0.5)` on it. The writer attempts the block
only `if element._geometry`, so whether an export crashes depends on whether anything
touched `.geometry` earlier in the process; our own Level 2 solid check touches it on every
plate, so every export would. `<Shape>` is `minOccurs="0"` in the xsd, so dropping it is
schema-legal and costs only the display mesh.
`test_the_shape_block_is_what_breaks_the_writer_measured_not_assumed` pins the crash so the
workaround can be removed the day upstream fixes it.

## Divergences from the C# reference

Three were expected. Measured over a five-seed calibration sweep, only two survive:

1. **Closest-point projection vs the reference's vertical drop — NEGLIGIBLE.** A single step
   differs by up to 4.1 % of spacing, but at convergence the two packings differ by 0.0045 %
   and every reported statistic is identical to every printed digit. Relaxation is a
   fixed-point iteration; the projection rule perturbs the path, not the equilibrium. **Do
   not attribute a discrepancy to it.** `MongeSurface(projection="vertical")` is kept as the
   evidence for that.
2. **numpy's RNG stream differs from .NET's — CONFIRMED**, and it accounts for the whole
   disagreement on random seeds. Compare distributions over several seeds, never seed for
   seed.
3. **Qhull / edge-flip ordering — CONFIRMED, small.** Visible only in iteration counts.

All four hex configurations reproduce the C# on agents, plates, side-ratio median and p10,
alignment mean and convexity.

## Layout

```
abm/            pure numpy/scipy; no COMPAS, no Rhino
  surfaces.py   Domain, Topology, the Surface protocol, MongeSurface, SphereSurface,
                TubeSurface (the developable caveat, and fd_principal exercised)
  seeding.py    auto spacing, the 12-fold dominant angle, hex and area-weighted random
  solver.py     Parameters, AgentState, behaviours, the Jacobi step
  plates.py     both triangulation paths, orientation, TPI, the fan walk, convexity
  metrics.py    the two normative metrics -- kept apart because their POPULATIONS differ
timber.py       plate rings -> Plate / TimberModel (Level 2)
btlx.py         BTLx write, schema validation, read-back (Level 3)
run.py          CLI harness and diagnostics
```

`tests/test_acceptance.py`, the four end-to-end tests in `tests/test_timber.py` and most of
`tests/test_btlx.py` carry the `slow` marker; `-m "not slow"` skips the full relaxations.
The whole suite is 156 tests and about six minutes.

Note the **first** OCP call costs ~0.4 s and plate solids then compute at ~2.3 ms each. Do
not read that first call as a hang.
