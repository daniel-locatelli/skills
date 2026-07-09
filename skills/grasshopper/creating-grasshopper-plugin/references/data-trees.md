# Data Trees: GH_Structure&lt;T&gt;, GH_Path, and Branch Iteration

## What a Data Tree Is

A Grasshopper **data tree** is a path-keyed collection of branches. Concretely, it is an
instance of `GH_Structure<T>` from the `Grasshopper.Kernel.Data` namespace.

Verified against the SDK API at
`mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_Data_GH_Structure_1.htm`
(fetched 2026-05-17).

**Anatomy of a tree:**

- A **branch** is a `List<T>` of values — all of the same GH wrapper type (e.g. `GH_Curve`).
- A **path** (`GH_Path`) is the address of a branch. It is a tuple of integers — for example
  `{0}`, `{1;2}`, or `{0;0;3}`. Paths are immutable value-like objects.
- Each path addresses exactly one branch; each branch has exactly one path.

Namespace: `Grasshopper.Kernel.Data`. Both `GH_Structure<T>` and `GH_Path` live there.

**Compare to a flat list:**

| Concept | Flat list | Data tree |
|---|---|---|
| Container type | `List<T>` | `GH_Structure<T>` |
| Address | integer index | `GH_Path` (tuple of ints) |
| Nesting | single level | arbitrarily deep paths |
| Iteration | `foreach (T item in list)` | iterate `Paths`, then `Branches[i]` |

A flat list `[A, B, C]` maps to a tree with one branch at path `{0}`. A tree
`{0}:[A,B]` + `{1}:[C,D]` has two branches; a flat list cannot represent that distinction —
when branch membership matters, only the tree encodes it.

---

## When Item-Access Auto-Iterates

Declaring `access = GH_ParamAccess.item` on an input causes Grasshopper to **iterate over all
leaves** of whatever tree arrives on that wire, calling `SolveInstance` once per leaf. You
never see the tree; you only see individual values.

This is the correct default for the overwhelming majority of components.

**Example:** A component declared as:

```csharp
pManager.AddCurveParameter("Curve", "C", "Input curve", GH_ParamAccess.item);
```

…receives a tree with two branches `{0} → [curve0, curve1]` and `{1} → [curve2]`. Grasshopper
calls `SolveInstance` three times:

| Call | `DA.GetData(0, ref c)` gives you |
|---|---|
| 1 | `curve0` |
| 2 | `curve1` |
| 3 | `curve2` |

The output tree is assembled automatically with matching paths. You write code for a single
item; Grasshopper handles the iteration.

**Implication:** Most components should declare `.item`. Auto-iteration preserves path
correspondence: each `DA.SetData` result is placed in the same branch the input leaf came from.
Do not declare `.tree` "just to be safe" — it disables auto-iteration and forces manual tree
handling. Only deviate when branch structure actually matters (see next section).

---

## When to Declare `.tree`

Declare `GH_ParamAccess.tree` only when **your component's logic depends on branch structure**
— that is, when the component needs to know which items are in the same branch or needs to
produce output with a branch structure derived from the input.

**Classic case: match curves per branch to points per branch.**

Under `.item` access, GH auto-iterates each input independently, losing branch grouping.
When pairing must happen at the branch level (branch-0 curves with branch-0 points), declare
both inputs `.tree` and iterate paths explicitly:

```csharp
// RegisterInputParams
protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
{
    pManager.AddCurveParameter("Curves", "C", "Curves, one branch per group",
        GH_ParamAccess.tree);
    pManager.AddPointParameter("Points", "P", "Points, matching branch structure",
        GH_ParamAccess.tree);
}

// RegisterOutputParams
protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager pManager)
{
    pManager.AddCurveParameter("Result", "R", "Processed curves",
        GH_ParamAccess.tree);
}

// SolveInstance
protected override void SolveInstance(IGH_DataAccess DA)
{
    GH_Structure<GH_Curve> curveTree = new GH_Structure<GH_Curve>();
    GH_Structure<GH_Point> pointTree = new GH_Structure<GH_Point>();

    if (!DA.GetDataTree(0, out curveTree)) return;
    if (!DA.GetDataTree(1, out pointTree)) return;

    var output = new GH_Structure<GH_Curve>();

    foreach (GH_Path path in curveTree.Paths)
    {
        List<GH_Curve> curveBranch = curveTree[path];
        List<GH_Point> pointBranch = pointTree[path];

        if (pointBranch == null) continue; // no matching points for this branch

        for (int i = 0; i < curveBranch.Count; i++)
        {
            Curve curve = curveBranch[i]?.Value;
            Point3d pt = pointBranch[i].Value;
            if (curve == null) continue;

            // ...process curve with matching point...
            Curve moved = curve.DuplicateCurve();
            moved.Translate(pt - curve.PointAtStart);
            output.Append(new GH_Curve(moved), path);
        }
    }

    DA.SetDataTree(0, output);
}
```

Other cases where `.tree` is justified: modifying branch structure (graft/flatten/shift),
cross-branch operations, or output paths that cannot be derived from a simple per-item mapping.

Do not declare `.tree` when the component processes one item at a time (use `.item`) or needs
the full list per branch but no cross-branch logic (use `.list`).

---

## Reading a Tree Manually

When a parameter is declared `.tree`, retrieve it in `SolveInstance` with `DA.GetDataTree`.

Verified against the `IGH_DataAccess` interface at
`mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_IGH_DataAccess.htm`
(fetched 2026-05-17).

### Signature

```csharp
// by index:
bool GetDataTree<T>(int index, out GH_Structure<T> tree) where T : IGH_Goo;

// by name:
bool GetDataTree<T>(string name, out GH_Structure<T> tree) where T : IGH_Goo;
```

Note: `GetDataTree` uses **`out`**, not `ref`. Declare the variable; pass it as `out`.

### Minimal pattern

```csharp
GH_Structure<GH_Curve> tree = new GH_Structure<GH_Curve>();
if (!DA.GetDataTree(0, out tree)) return;
```

Initialising before the call is conventional; the `out` contract overwrites it regardless.
Always check the return value and return early on `false`.

### Iterating paths and branches

`GH_Structure<T>` exposes `tree.Paths` (`IList<GH_Path>`) and `tree.Branches`
(`IList<List<T>>`), both in the same order. Index by path using the indexer:

```csharp
foreach (GH_Path path in tree.Paths)
{
    List<GH_Curve> branch = tree[path];
    foreach (GH_Curve ghCurve in branch)
    {
        Curve curve = ghCurve?.Value;
        if (curve == null) continue;
        // work with curve...
    }
}
```

### Unwrapping GH wrappers

Every GH wrapper type exposes its underlying value via `.Value`. Common ones:

| GH wrapper | `.Value` type |
|---|---|
| `GH_Curve` | `Curve` |
| `GH_Point` | `Point3d` |
| `GH_Number` | `double` |
| `GH_Brep` | `Brep` |
| `GH_Mesh` | `Mesh` |

Always null-check before accessing `.Value` — branches can contain null entries when upstream
data is missing:

```csharp
Curve curve = ghCurve?.Value;
if (curve == null) continue;
```

---

## Writing a Tree

Build a `GH_Structure<T>` and set it on the output with `DA.SetDataTree`.

### Signature

```csharp
// IGH_DataAccess.SetDataTree — verified 2026-05-17
void SetDataTree(int index, IGH_Structure structure);
```

`GH_Structure<T>` implements `IGH_Structure`, so pass your `GH_Structure<T>` directly.

### Key methods

- `Append(T item, GH_Path path)` — creates the branch at `path` if absent, then appends.
  This is the workhorse for building output trees one item at a time.
- `EnsurePath(GH_Path path)` — creates the branch and returns the `List<T>` for bulk appending.

The "When to declare `.tree`" example above shows the full read-iterate-write pattern.

---

## Path Operations

`GH_Path` is in `Grasshopper.Kernel.Data`. Verified against the SDK API at
`mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_Data_GH_Path.htm`
(fetched 2026-05-17).

### Constructors

```csharp
new GH_Path()            // empty path — zero elements; rarely useful
new GH_Path(0)           // single-element path: {0}
new GH_Path(0, 1)        // two-element path: {0;1}
new GH_Path(new int[] { 0, 2, 5 })   // arbitrary path: {0;2;5}
new GH_Path(existingPath)            // copy constructor
```

### Key methods

| Method | Signature | Notes |
|---|---|---|
| `AppendElement` | `GH_Path AppendElement(int index)` | Returns a **new** path; `this` is unchanged |
| `CullElement` | `GH_Path CullElement()` | Returns a new path with the last element removed |
| `Indices` | `int[] Indices { get; set; }` | Raw integer array; treat as read-only |
| `Length` | `int Length { get; }` | Number of dimensions (elements) in the path |
| `Valid` | `bool Valid { get; }` | True if non-empty and no negative indices |
| `ToString()` | `string ToString()` | Returns `"{0;1;2}"` style string |
| `IsAncestor` | `bool IsAncestor(GH_Path other)` | True if `this` is a prefix of `other` |

**`AppendElement` is non-mutating:**

```csharp
GH_Path parent = new GH_Path(0);        // {0}
GH_Path child  = parent.AppendElement(3); // {0;3}
// parent is still {0}
```

This is a common source of bugs — see "Common failures."

---

## Common Failures

### The central failure: treating a tree-typed input as a flat list

This is the spec-noted stumbling block for AI agents: **when asked to handle a `GH_Structure<T>`
input, agents default to declaring `.item` access and iterating as if the structure were a
flat sequence, losing branch grouping silently.**

The failure surfaces when:

1. The component is supposed to process data branch-by-branch (pair curves in branch 0 with
   points in branch 0, curves in branch 1 with points in branch 1, etc.).
2. The agent declares both inputs as `.item` and lets GH auto-iterate.
3. GH iterates leaves in undefined order across branches, mixing branch-0 items with
   branch-1 items.
4. The result is wrong but the component does not error; it silently produces mismatched output.

**WRONG — loses branch structure:**

```csharp
// Input registration
pManager.AddCurveParameter("Curves", "C", "Curves", GH_ParamAccess.item);  // WRONG
pManager.AddPointParameter("Points", "P", "Points", GH_ParamAccess.item);  // WRONG

// SolveInstance — called once per leaf pair (GH auto-iterates both inputs)
protected override void SolveInstance(IGH_DataAccess DA)
{
    Curve curve = null;
    Point3d pt = Point3d.Unset;
    if (!DA.GetData(0, ref curve)) return;
    if (!DA.GetData(1, ref pt)) return;

    // At this point you have ONE curve and ONE point.
    // If the input trees have 2 branches {0}:[c0,c1] and {1}:[c2,c3],
    // GH pairs them by longest-list matching across the FLATTENED sequence.
    // Branch structure is completely lost.
    Curve moved = curve.DuplicateCurve();
    moved.Translate(pt - curve.PointAtStart);
    DA.SetData(0, moved);  // output has wrong branch structure
}
```

The mistake is subtle: the code compiles, the component runs, and for simple inputs (one branch
each) it appears to work. The bug is invisible until the user feeds multi-branch trees.

**RIGHT — preserves branch structure:**

```csharp
// Input registration
pManager.AddCurveParameter("Curves", "C", "Curves", GH_ParamAccess.tree);  // CORRECT
pManager.AddPointParameter("Points", "P", "Points", GH_ParamAccess.tree);  // CORRECT

// SolveInstance — called once; you control iteration
protected override void SolveInstance(IGH_DataAccess DA)
{
    GH_Structure<GH_Curve> curveTree = new GH_Structure<GH_Curve>();
    GH_Structure<GH_Point> pointTree = new GH_Structure<GH_Point>();
    if (!DA.GetDataTree(0, out curveTree)) return;
    if (!DA.GetDataTree(1, out pointTree)) return;

    var output = new GH_Structure<GH_Curve>();

    foreach (GH_Path path in curveTree.Paths)
    {
        List<GH_Curve> curveBranch = curveTree[path];
        List<GH_Point> pointBranch = pointTree[path];  // same path — explicit pairing
        if (pointBranch == null) continue;

        int count = Math.Min(curveBranch.Count, pointBranch.Count);
        for (int i = 0; i < count; i++)
        {
            Curve curve = curveBranch[i]?.Value;
            Point3d pt = pointBranch[i].Value;
            if (curve == null) continue;

            Curve moved = curve.DuplicateCurve();
            moved.Translate(pt - curve.PointAtStart);
            output.Append(new GH_Curve(moved), path);  // same path — structure preserved
        }
    }

    DA.SetDataTree(0, output);
}
```

The corrected version explicitly pairs branches at the same path, preserves branch grouping
in the output, and fails gracefully when a path is present in one tree but not the other.

---

### Failure: forgetting that AppendElement is non-mutating

```csharp
// WRONG — AppendElement returns a new path; the result is discarded
GH_Path path = new GH_Path(0);
path.AppendElement(itemIndex);         // path is still {0}
output.Append(item, path);             // all items land in {0}

// CORRECT
GH_Path childPath = path.AppendElement(itemIndex);  // capture the return value
output.Append(item, childPath);        // items land in {0;0}, {0;1}, {0;2}…
```

The bug: all items end up in the same branch because the deepened path was never assigned.
The symptom: output is flat (one branch) instead of grafted.

---

### Other quick failures

**Mismatched access declaration and retrieval method:** declaring `.tree` but calling
`DA.GetData` returns only the first item or fails. Match declaration to retrieval: `.tree`
requires `DA.GetDataTree`. See `[[params-and-registration.md]]` for the pairing table.

**Building output but never setting it:** constructing a `GH_Structure<T>` but omitting the
`DA.SetDataTree(0, output)` call produces a component with empty output and no error message.

---

## Cross-links

See also:
- `[[params-and-registration.md]]` for access mode declaration (`GH_ParamAccess.item` vs.
  `.list` vs. `.tree`) and the full declaration–retrieval method pairing table.
- `[[component-lifecycle.md]]` for where `RegisterInputParams` and `SolveInstance` fit in
  the component class and for the `.gha` project scaffolding prerequisites.
