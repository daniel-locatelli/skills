# Params and Registration: GH_ParamAccess, Param_* Types, and DA Access Patterns

## Two Independent Dimensions

Every Grasshopper input or output parameter has **two orthogonal properties** that authors
frequently conflate:

1. **Parameter type** — which `Param_*` class (or `AddXxxParameter` method) maps to your
   C# data type. This determines what the wire carries: a `Curve`, a `double`, a `Brep`, etc.

2. **Access mode** — `GH_ParamAccess.item`, `.list`, or `.tree`. This determines how
   Grasshopper feeds your component with that data: one value at a time, a whole list at once,
   or the full tree structure.

Getting the type wrong causes a compile error or a cast failure at runtime.  
Getting the access mode wrong causes silent data-mismatch bugs or wrong iteration behaviour.  
They must be chosen independently.

---

## Parameter Type Table

Verified against `GH_InputParamManager` methods at
`mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_Component_GH_InputParamManager.htm`
(fetched 2026-05-17).

### Geometry

| RhinoCommon / GH type | pManager method | C# receive type in `DA.GetData` |
|---|---|---|
| `Curve` (any curve) | `AddCurveParameter` | `Curve` |
| `Brep` | `AddBrepParameter` | `Brep` |
| `Mesh` | `AddMeshParameter` | `Mesh` |
| `Surface` (trimmed/untrimmed) | `AddSurfaceParameter` | `Surface` |
| `SubD` | `AddSubDParameter` | `SubD` |
| `Point3d` | `AddPointParameter` | `Point3d` |
| `Vector3d` | `AddVectorParameter` | `Vector3d` |
| `Plane` | `AddPlaneParameter` | `Plane` |
| `Line` | `AddLineParameter` | `Line` |
| `Circle` | `AddCircleParameter` | `Circle` |
| `Arc` | `AddArcParameter` | `Arc` |
| `Rectangle3d` | `AddRectangleParameter` | `Rectangle3d` |
| `Box` | `AddBoxParameter` | `Box` |
| `IGH_GeometricGoo` (any geometry) | `AddGeometryParameter` | `IGH_GeometricGoo` |

### Numerics and Primitives

| Type | pManager method | C# receive type |
|---|---|---|
| `double` | `AddNumberParameter` | `double` |
| `int` | `AddIntegerParameter` | `int` |
| `double` (angle, in radians) | `AddAngleParameter` | `double` |
| `bool` | `AddBooleanParameter` | `bool` |
| `string` | `AddTextParameter` | `string` |
| `System.Drawing.Color` | `AddColourParameter` | `System.Drawing.Color` |
| `Interval` | `AddIntervalParameter` | `Interval` |
| `Complex` | `AddComplexNumberParameter` | `Complex` |
| `DateTime` | `AddTimeParameter` | `DateTime` |
| `Transform` | `AddTransformParameter` | `Transform` |
| `Matrix` | `AddMatrixParameter` | `Matrix` |

For untyped / any-object data, use `AddGenericParameter` — the C# receive type is `IGH_Goo`;
unwrap the underlying value with `.Value`.

### Caveats

- **`Param_Number` is `double`, not `int`** — use `AddIntegerParameter` if you need an integer.
  Registering with `AddNumberParameter` and then calling `DA.GetData<int>` will cause a
  type-mismatch error.
- **`Curve` is the abstract base** — `LineCurve`, `NurbsCurve`, `PolyCurve`, `ArcCurve`, etc.
  all inherit from `Curve`. Use `AddCurveParameter` unless you specifically need to accept only
  one subtype (rare; normally the component accepts any curve).
- **`AddGeometryParameter` is coarser than `AddBrepParameter`** — use the specific method when
  you know the expected type; the generic version requires the caller to supply the right
  geometry type and gives no type-mismatch feedback in the GH canvas.
- **No "length" parameter type** — `Param_Number` (`AddNumberParameter`) is dimensionless.
  When a number represents a length, document that it is in model units and handle unit
  conversion if needed. See `[[geometry-units-and-tolerance.md]]`.

---

## Access Modes

Verified against the `GH_ParamAccess` enum at
`mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_ParamAccess.htm`
(fetched 2026-05-17).

| Enum member | Integer value | Description (from API) |
|---|---|---|
| `GH_ParamAccess.item` | 0 | "Every data item is to be treated individually." |
| `GH_ParamAccess.list` | 1 | "All data branches will be treated at the same time." |
| `GH_ParamAccess.tree` | 2 | "The entire data structure will be treated at once." |

### When to use `.item`

**Default choice.** Declare `.item` when your component processes one value per call.
Grasshopper auto-iterates: if the input wire carries 10 curves, `SolveInstance` is called 10
times, once per curve. You write code for a single item; GH handles the loop.

Most components should use `.item`. Only deviate when there is a specific reason.

### When to use `.list`

Declare `.list` only when your component genuinely needs the **entire collection at once**:
sorting, indexing, comparing elements to each other, culling, deduplication.

If you declare `.list`, `SolveInstance` is called once per branch, receiving the whole branch
as a list. You must retrieve the data with `DA.GetDataList`. You lose GH's auto-iteration;
you are responsible for iterating across branches if the input tree has more than one branch.

Verified pattern from `developer.rhino3d.com/guides/grasshopper/list-components/`
(fetched 2026-05-17):

```csharp
protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
{
    pManager.AddGeometryParameter("Geometry", "G", "Geometry to cull", GH_ParamAccess.list);
    pManager.AddIntegerParameter("Count", "C", "Number to cull", GH_ParamAccess.item, 1);
}
```

Note: the two parameters on the same component can have different access modes.

### When to use `.tree`

Declare `.tree` only when your component's logic depends on **branch structure**: pairing
items across branches, reconstructing paths, or doing cross-branch operations.

If you declare `.tree`, `SolveInstance` is called once and you receive the full
`GH_Structure<T>`. All iteration is your responsibility. See `[[data-trees.md]]`.

---

## `DA.GetData*` / `DA.SetData*` Patterns

### Item access (`.item`)

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    Curve curve = null;
    if (!DA.GetData(0, ref curve)) return;

    Point3d midpoint = curve.PointAtNormalizedLength(0.5);
    DA.SetData(0, midpoint);
}
```

Key rules:
- Declare the receiver before passing it as `ref`. Do not rely on a post-`GetData` null check
  to guard against a missing value — see "Common failures" below.
- Always check the return value of `DA.GetData`. Return immediately on `false`.
  Grasshopper has already set a warning on the component; do not attempt to use the value.
- `DA.SetData(outputIndex, value)` writes to output slot `outputIndex`.

### List access (`.list`)

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    List<IGH_GeometricGoo> geometry = new List<IGH_GeometricGoo>();
    int count = 0;

    if (!DA.GetDataList(0, geometry)) return;
    if (!DA.GetData(1, ref count)) return;

    // process geometry list...

    DA.SetDataList(0, geometry);
}
```

Key rules:
- Use `DA.GetDataList` (not `DA.GetData`) for `.list`-access inputs. Using `DA.GetData` on a
  list input will fail silently or return only the first element.
- Declare `new List<T>()` before calling `GetDataList` — the method appends to the list.
- `DA.SetDataList(outputIndex, collection)` writes a collection to an output declared `.list`.

### Tree access (`.tree`)

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    GH_Structure<GH_Curve> tree = new GH_Structure<GH_Curve>();
    if (!DA.GetDataTree(0, out tree)) return;

    var output = new GH_Structure<GH_Point>();
    foreach (GH_Path path in tree.Paths)
    {
        List<GH_Curve> branch = tree[path];
        foreach (GH_Curve ghCurve in branch)
        {
            Curve curve = ghCurve?.Value;
            if (curve == null) continue;
            Point3d mid = curve.PointAtNormalizedLength(0.5);
            output.Append(new GH_Point(mid), path);
        }
    }
    DA.SetDataTree(0, output);
}
```

Note: `DA.GetDataTree` uses `out`, not `ref`. See `[[data-trees.md]]` for full tree internals.

---

## Optional Params

Verified from `discourse.mcneel.com` topics 50837 and 82035 (fetched 2026-05-17).

Mark a param optional by indexing `pManager` immediately after registration:

```csharp
protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
{
    pManager.AddCurveParameter("Curve", "C", "Input curve", GH_ParamAccess.item);
    // index 0 above is required; index 1 below is optional

    pManager.AddNumberParameter("Offset", "O", "Offset distance (optional)", GH_ParamAccess.item);
    pManager[1].Optional = true;
}
```

`pManager[n]` returns the parameter at index `n`. Setting `.Optional = true` tells Grasshopper
not to block the component from running when that input is disconnected.

**Critical difference in SolveInstance for optional inputs:**

```csharp
protected override void SolveInstance(IGH_DataAccess DA)
{
    Curve curve = null;
    if (!DA.GetData(0, ref curve)) return;   // required: early return is correct

    double offset = 0.0;
    DA.GetData(1, ref offset);               // optional: do NOT return early on false
    // offset remains 0.0 if disconnected — use as default
}
```

Required input: return early on `false`. Optional input: call `DA.GetData` but do not return
on `false` — let the local variable hold its default value and allow `SolveInstance` to proceed.

`Params.Input[n].Optional = true` is equivalent; `pManager[n]` is preferred inside
`RegisterInputParams` because `pManager` is already in scope.

---

## Common Failures

These failures come from the `[params-and-registration]` RED baseline finding
(`tests/baseline/curve-utils.md`). Both agents exhibited the same root misunderstanding about
`DA.GetData`'s nullability contract, in different surface forms.

### Failure: `DA.GetData` nullability contract misunderstood

**What Opus wrote** (`runs/2026-05-17-opus-4-5.md` lines 69–70):

```csharp
// Opus
Curve curve = null;
if (!DA.GetData(0, ref curve) || curve == null) return;
```

**What Sonnet wrote** (`runs/2026-05-17-sonnet-4-6.md` lines 57–58):

```csharp
// Sonnet
Curve? curve = null;
if (!DA.GetData(0, ref curve)) return;
```

Both agents were attempting the same thing: ensure that `curve` is non-null before using it.
But both patterns are wrong in different ways.

**Why Opus's pattern is wrong:** the compound condition `!DA.GetData(...) || curve == null`
has a logic error. The `curve == null` branch is **unreachable when `GetData` returns `true`**:
a successful `GetData` has already assigned a non-null value. The redundant null check is dead
code that misleads readers.

**Why Sonnet's pattern is wrong:** `Curve? curve` is a nullable reference-type annotation.
It requires `<Nullable>enable</Nullable>` in the csproj. Rhino.Templates does **not** include
this by default; without it `Curve?` triggers warning **CS8632**.

**The correct minimal pattern:**

```csharp
Curve curve = null;
if (!DA.GetData(0, ref curve)) return;

// curve is guaranteed non-null here — DA.GetData returned true
Point3d midpoint = curve.PointAtNormalizedLength(0.5);
DA.SetData(0, midpoint);
```

The contract: when `DA.GetData` returns `true`, the `ref` output is a valid non-null value.
When it returns `false`, a component warning is already logged; return immediately — nothing more to check.

**What this pattern does NOT need:**

```csharp
// Unnecessary null checks after a successful GetData:
if (curve == null) return;    // unreachable — remove it
if (!curve.IsValid) ...       // only needed if you have a specific validity contract
```

To opt into nullable annotations project-wide, add `<Nullable>enable</Nullable>` to the
csproj `<PropertyGroup>` and update all existing code. For most plugins, leaving nullable
disabled is simpler. See `[[component-lifecycle.md]]` for the csproj defaults note.

---

### Failure: using wrong access-mode retrieval method

Calling `DA.GetData` on a `.list`-access input returns only the first item (or fails silently).

```csharp
// WRONG: input registered as list, but retrieved as item
pManager.AddCurveParameter("Curves", "C", "Curves", GH_ParamAccess.list);
// ...
Curve curve = null;
DA.GetData(0, ref curve);   // only retrieves first element or fails
```

```csharp
// CORRECT
List<Curve> curves = new List<Curve>();
if (!DA.GetDataList(0, curves)) return;
```

The access-mode declaration in `RegisterInputParams` and the retrieval method in
`SolveInstance` must match:

| Declaration | Retrieval method |
|---|---|
| `GH_ParamAccess.item` | `DA.GetData(index, ref value)` |
| `GH_ParamAccess.list` | `DA.GetDataList(index, list)` |
| `GH_ParamAccess.tree` | `DA.GetDataTree(index, out tree)` |

---

## Cross-links

See also:
- `[[data-trees.md]]` for `.tree` access mode internals: `GH_Structure<T>`, `GH_Path`, branch
  iteration, and when item-access auto-iteration applies vs. when tree access is needed.
- `[[component-lifecycle.md]]` for where `RegisterInputParams` fits in the lifecycle and for
  the csproj nullable defaults that affect `DA.GetData` receiver declarations.
- `[[geometry-units-and-tolerance.md]]` for `Param_Number` as a dimensionless `double` and the
  convention for length parameters in model units.
