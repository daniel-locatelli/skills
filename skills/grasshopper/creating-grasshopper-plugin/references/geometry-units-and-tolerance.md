# Geometry, Units, and Tolerance

## The Two Model-Level Constants

Every Rhino document carries two properties that control all geometric operations. Both vary
per document — there is no process-wide default.

Verified against the RhinoCommon API at `developer.rhino3d.com/api/rhinocommon/Rhino.RhinoDoc`
and `developer.rhino3d.com/api/rhinocommon/Rhino.UnitSystem` (fetched 2026-05-17).

### `RhinoDoc.ActiveDoc.ModelUnitSystem`

**Type:** `Rhino.UnitSystem` (enum)  
**Kind:** Instance property on `RhinoDoc`

Holds the document's current length unit system. Common enum members:

| `UnitSystem` member | Enum value |
|---|---|
| `Millimeters` | 2 |
| `Centimeters` | 3 |
| `Meters` | 4 |
| `Inches` | 8 |
| `Feet` | 9 |
| `None` | 0 (scale factor 1.0) |
| `Unset` | 255 (not designated) |

A component that assumes metres when the document is in millimetres will produce coordinates
off by a factor of 1 000. The mismatch is silent — there is no runtime exception.

### `RhinoDoc.ActiveDoc.ModelAbsoluteTolerance`

**Type:** `double`  
**Kind:** Instance property on `RhinoDoc`  
**Description:** "Model space absolute tolerance"

This is the document's tolerance for geometric operations: coincidence tests, curve closure
checks, planarity tests, intersection, and similar. The user sets it in Rhino's document
properties. Typical values:

| Unit system | Typical default tolerance |
|---|---|
| Metres | 0.001 (1 mm) |
| Millimetres | 0.01 (10 µm) |
| Inches | 0.001 |
| Feet | 0.001 |

These are convention, not hard constraints — a user can change them. Access the live value;
never hardcode a tolerance.

In `SolveInstance`, `RhinoDoc.ActiveDoc` is the standard pattern (GH does not pass a doc
parameter). Access it once at the top, store in a local variable, and check for null before
use. See `[[threading-and-the-main-thread.md]]` for thread-safety details.

---

## Why Hardcoded Tolerances Are Wrong

A fixed literal like `1e-6` appears frequently in forum examples. It is not portable.

`1e-6` is fine in a metres document (tolerance ~0.001) — it's just very tight. In a
millimetres document (tolerance ~0.01), `1e-6` is ten thousand times tighter than the document
expects: geometry Rhino considers coincident will not pass the test. In feet or inches the
mismatch is similar. The literal that appears to work in the author's environment silently
fails in every other unit system.

**Corrected pattern:**

```csharp
RhinoDoc doc = RhinoDoc.ActiveDoc;
if (doc == null) return;
double tol = doc.ModelAbsoluteTolerance;

bool coincident = pt1.DistanceTo(pt2) < tol;
```

`ModelAbsoluteTolerance` is the same value Rhino uses internally for `Point3d.EpsilonEquals`,
`Curve.IsPlanar`, intersection operations, and all tolerance-sensitive geometry methods.
Matching it makes your component behave consistently with the rest of the document.

---

## Reading Units When Needed

Most components do not need to know the unit system — they receive geometry and return
geometry, and the coordinates are already in model units. Unit awareness is only required
when:

1. A number input represents a fixed real-world distance (e.g. "extrude by 10 mm").
2. The component computes a result in a specific unit and must display it as a number.

For these cases, use `RhinoMath.UnitScale(from, to)` to get the scale factor between two unit
systems.

Verified against the RhinoCommon API at `developer.rhino3d.com/api/rhinocommon/Rhino.RhinoMath`
(fetched 2026-05-17).

### `RhinoMath.UnitScale(UnitSystem from, UnitSystem to)`

**Return type:** `double`  
**Description:** "Compute the scale factor for changing the measurements unit systems."

```csharp
double scale = RhinoMath.UnitScale(UnitSystem.Millimeters, UnitSystem.Meters);
// scale == 0.001 — multiply a millimetre value by 0.001 to get metres
```

### Worked example: "extrude by 10 mm regardless of model units"

```csharp
RhinoDoc doc = RhinoDoc.ActiveDoc;
if (doc == null) return;

// Convert a fixed 10 mm value into whatever unit the document uses.
double scale = RhinoMath.UnitScale(UnitSystem.Millimeters, doc.ModelUnitSystem);
double distanceModelUnits = 10.0 * scale;
// In a mm document: scale = 1.0.  In a metres document: scale = 0.001 (→ 0.01 m = 10 mm).
```

---

## Closed-Curve and Coplanarity Checks

Tolerance-sensitive boolean tests on curves must use the document tolerance, not a literal.

Verified against the RhinoCommon API at `developer.rhino3d.com/api/rhinocommon/Rhino.Geometry.Curve`
(fetched 2026-05-17).

### `Curve.IsClosed`

**Type:** `bool` property (no tolerance parameter). Exact geometric check — start/end
coincide by construction (circle, closed NurbsCurve). No tolerance argument; the result is
exact.

```csharp
if (!curve.IsClosed)
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Input curve must be closed.");
    return;
}
```

### `Curve.IsPlanar(double tolerance)`

**Signatures:**
- `IsPlanar()` — uses a default internal tolerance
- `IsPlanar(double tolerance)` — explicit tolerance

**Return type:** `bool`  
**Description:** "Test a curve for planarity."

Always pass the document tolerance explicitly. The zero-argument overload uses an internal
constant that may not match the document's tolerance, producing inconsistent results when the
user switches unit systems.

```csharp
RhinoDoc doc = RhinoDoc.ActiveDoc;
if (doc == null) return;
double tol = doc.ModelAbsoluteTolerance;

if (!curve.IsPlanar(tol))
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Input curve must be planar.");
    return;
}
```

When you need closure-within-tolerance (for curves whose endpoints have a small numerical gap
from upstream operations), use `curve.IsClosedWithinTolerance(tol)` instead. Use `IsClosed`
for structurally closed curves; use `IsClosedWithinTolerance` for "close enough" cases.

---

## `Param_Number` vs. Implicit Length

There is no "length parameter" type in the Grasshopper SDK. `Param_Number`
(`pManager.AddNumberParameter`) carries a dimensionless `double`. It has no unit annotation
and no automatic conversion.

Verified — `AddNumberParameter` table row in `[[params-and-registration.md]]`:

> `Param_Number` is `double`, not `int`. … There is no "length param" type.

### Convention

When a component accepts a number that represents a length, the convention is:

1. The number is interpreted as being **in current model units**.
2. Document this in the parameter's description string.
3. If the component must accept a fixed real-world unit (e.g. always millimetres), use
   `RhinoMath.UnitScale` to convert at the top of `SolveInstance` (see the previous section).

```csharp
// Convention: "Distance" is in model units — document it in the description
pManager.AddNumberParameter(
    "Distance", "D",
    "Extrusion distance in model units.",
    GH_ParamAccess.item, 1.0);
```

The default value `1.0` is also in model units, so a 1-unit default in a metres document means
1 m, and in a millimetres document means 1 mm.

`Param_Number` carries no unit annotation, performs no automatic conversion, and does not
validate sign or range. Those responsibilities belong to the component's `SolveInstance`.

---

## Common Failures

No `[geometry-units-and-tolerance]` findings in the RED baseline — the baseline scenario
does not exercise tolerance or unit-conversion surfaces. The examples below address the
central failure mode from spec §5: **hardcoded tolerances + unit assumptions**.

### Failure 1: Hardcoded tolerance literal

**WRONG:**

```csharp
// Hardcoded — breaks in millimetre documents
if (curve.GetLength() < 1e-6)
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Curve is too short.");
    return;
}
```

**RIGHT:** replace `1e-6` with `doc.ModelAbsoluteTolerance` (same pattern as the corrected
example in the section above).

### Failure 2: Unit assumption in a length input

**WRONG:**

```csharp
// Assumes metres — correct only when the document is in metres
double radius = 0.05;  // "50 mm" — only true in a metres document
Sphere sphere = new Sphere(Point3d.Origin, radius);
```

**Why it fails:** In a millimetres document, `radius = 0.05` means 0.05 mm — a sphere 0.1 mm
in diameter instead of 100 mm. The geometry is off by a factor of 1 000.

**RIGHT:**

```csharp
// Convert 50 mm into model units, whatever they are
RhinoDoc doc = RhinoDoc.ActiveDoc;
if (doc == null) return;
double scale = RhinoMath.UnitScale(UnitSystem.Millimeters, doc.ModelUnitSystem);
double radius = 50.0 * scale;
Sphere sphere = new Sphere(Point3d.Origin, radius);
```

### Failure 3: Using `IsPlanar()` without a tolerance argument

**WRONG:**

```csharp
if (!curve.IsPlanar())
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Must be planar.");
    return;
}
```

**Why it fails:** The zero-argument overload uses an internal constant. In a millimetres
document that constant may be far tighter than the document tolerance, causing nearly-planar
curves (acceptable to the user) to fail the test.

**RIGHT:**

```csharp
RhinoDoc doc = RhinoDoc.ActiveDoc;
if (doc == null) return;

if (!curve.IsPlanar(doc.ModelAbsoluteTolerance))
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Must be planar.");
    return;
}
```

### Failure 4: `RhinoMath.ZeroTolerance` as a general-purpose tolerance

`RhinoMath.ZeroTolerance` is 2⁻³² ≈ 2.3×10⁻¹⁰ — an engineering near-zero for floating-point
comparisons, not a document-driven geometric tolerance. Using it for coincidence tests
(`pt1.DistanceTo(pt2) < RhinoMath.ZeroTolerance`) is tighter than `1e-6` and will reject
coincident points in any practical model. Use `ModelAbsoluteTolerance` for geometric
coincidence; reserve `ZeroTolerance` for explicit near-zero floating-point checks.

---

## Cross-links

See also:
- `[[params-and-registration.md]]` for `Param_Number` as a dimensionless `double` and the
  full parameter type table.
- `[[threading-and-the-main-thread.md]]` for accessing `RhinoDoc.ActiveDoc` safely from
  `SolveInstance` under Rhino 8's parallel solver.
