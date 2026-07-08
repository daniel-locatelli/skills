# Threading and the Main Thread

## Rhino 8 Parallel Solver

**Summary:** `SolveInstance` may be called from worker threads for components that opt in to
task-capable execution. This is a Rhino 8 / Grasshopper 8 behaviour. Every example written
before this era assumed single-threaded sequential execution — those examples are not wrong
for standard `GH_Component`, but they are misleading as a mental model for the Rhino 8 world.

### Standard Grasshopper execution (all versions)

Standard Grasshopper executes components **sequentially**, one at a time, on the UI thread.
`SolveInstance` for component A finishes before `SolveInstance` for component B starts.
There is no concurrent execution between components in the standard solver.

Primary source — discourse.mcneel.com topic 98982 ("C# custom component SolveInstance()
behavior", verified 2026-05-17). Post by `Dani_Abalde` (community score 30.4):

> "Nothing happens at the same time in software, except (virtually) when the process is
> running in parallel in different threads. But GH doesn't do that, it just does it inside
> some components, but not between them. Components run one by one, ensuring all expired
> objects are recomputed and running source components first."

### Parallel execution inside a single component (Rhino 6+ opt-in)

A component can opt in to **task-capable execution** by implementing the
`IGH_TaskCapableComponent` interface (or by subclassing `GH_TaskCapableComponent<T>`).
When opted in, Grasshopper calls `SolveInstance` **twice** per solve cycle:

1. **Pre-solve pass** (`InPreSolve == true`): collect inputs, start `Task<T>` worker(s).
   Do not call `DA.SetData` here.
2. **Post-solve pass** (`InPreSolve == false`): wait for task results, call `DA.SetData`.

The worker tasks run on `ThreadPool` threads — not the UI thread. The `IGH_DataAccess`
interface (`DA`) is **not thread-safe** and must not be called from inside a worker task.

Primary source — developer.rhino3d.com/guides/grasshopper/programming-task-capable-component/
(verified 2026-05-17):

> "Independent tasks should not be directly accessing `IGH_DataAccess`, as that interface
> is not thread safe."

Primary source — discourse.mcneel.com topic 80496 ("Parallelising DA.SetData",
verified 2026-05-17). Post by `stevebaer` (McNeel admin, like_count 60):

> "DA is not thread safe."

### Pre-Rhino-8 examples are misleading

A search for "GH_Component SolveInstance threading" returns many examples that:

- Call `RhinoDoc.ActiveDoc` inside a `Parallel.For` or `Task.Run` body.
- Directly assign to output inside a worker thread via closure over `DA`.
- Do not handle cancellation.

These examples were written when the parallel solver did not exist, or were written for the
standard `GH_Component` (no task-capable interface) where the single-thread assumption holds.
Treat them as starting points only; apply the patterns in this reference before shipping.

---

## Main-Thread-Only APIs

The following APIs must not be called from a `ThreadPool` or `Task.Run` worker thread.
All are safe to call from the UI thread — i.e. inside a standard `GH_Component.SolveInstance`
body that does **not** use task-capable execution, or inside the post-solve pass of a
task-capable component.

| API | Why unsafe on worker thread | Safe alternative |
|---|---|---|
| `RhinoDoc.ActiveDoc` | Returns the UI-thread active document; accessing it from a worker thread can cause null reads or race conditions during document switching. | Pass `RhinoDoc.ActiveDoc` as a local variable before entering the worker, or access it only in the UI-thread pass. |
| `RhinoApp.RunScript(…)` | Executes a Rhino command on the UI thread; calling from a worker thread is undefined behaviour. | Schedule via `RhinoApp.InvokeOnUiThread` or restructure to avoid script execution in workers. |
| `RhinoDoc` write operations (`doc.Objects.Add`, `doc.Objects.Delete`, etc.) | Document mutation APIs are not thread-safe; concurrent mutations corrupt the document state. | Perform mutations only on the UI thread, via `RhinoApp.InvokeOnUiThread` or by scheduling them after the solve. |
| Grasshopper UI (`GH_Canvas`, `GH_Document.ScheduleSolution`, attribute rendering) | Grasshopper's UI dispatch runs on the UI thread. | Do not modify canvas or attributes from workers. |
| `IGH_DataAccess` (`DA.GetData`, `DA.SetData`, etc.) | Confirmed not thread-safe. | Use only in the pre-solve or post-solve pass, never inside a `Task.Run` body. |

### Accessing the GH document vs. the Rhino document

Inside `SolveInstance`, two distinct "document" objects are available:

- **`RhinoDoc.ActiveDoc`** — the Rhino document. Contains geometry, layers, materials.
  Accessing it from a worker thread is unsafe (see table above). If you need a tolerance or
  unit value, read it on the UI thread before launching workers, store it in a local variable,
  and capture it in the task lambda.
- **`this.OnPingDocument()`** — the **Grasshopper** document (`GH_Document`). Returns the
  `GH_Document` that owns this component. Use this when you need GH document state (e.g.
  `ScheduleSolution`, `UndoServer`, `SolutionDepth`). Do not confuse with `RhinoDoc`.

Primary source — discourse.mcneel.com topic 72659, post by `DavidRutten` (McNeel admin,
verified 2026-05-17):

> "GH_Document ghDoc = this.OnPingDocument();"

### Prefer parameters over document fetching

The safest pattern: receive doc-level values (tolerance, unit system) via input parameters
rather than calling `RhinoDoc.ActiveDoc` inside `SolveInstance`. When direct document access
is unavoidable, call it once at the top of `SolveInstance` on the UI thread, store the result
in a local variable, and capture the local variable in any worker lambdas. See
`[[geometry-units-and-tolerance.md]]` for the canonical `RhinoDoc.ActiveDoc` usage pattern.

---

## Marking a Component Thread-Safe (Task-Capable Opt-In)

To opt in to multi-threaded solving, implement `IGH_TaskCapableComponent` or subclass
`GH_TaskCapableComponent<T>`. The key members provided by the base class are:

| Member | Type | Description |
|---|---|---|
| `InPreSolve` | `bool` property | `true` during the first (worker-launch) pass; `false` during the second (output-set) pass. |
| `CancelToken` | `CancellationToken` | Propagated to worker tasks so they can be cancelled when GH aborts the solve. |
| `TaskList` | `List<Task<T>>` | Accumulate worker tasks here during the pre-solve pass; retrieve results during the post-solve pass. |

Verified against developer.rhino3d.com/guides/grasshopper/programming-task-capable-component/
(fetched 2026-05-17).

### Minimal task-capable skeleton

```csharp
public class MyHeavyComponent : GH_TaskCapableComponent<MyHeavyComponent.SolveResults>
{
    public class SolveResults { public double Value { get; set; } }

    public MyHeavyComponent()
        : base("HeavyCalc", "HC", "Slow computation.", "MyPlugin", "Analysis") { }

    // RegisterInputParams / RegisterOutputParams — same as GH_Component.

    private static SolveResults Compute(double input) =>
        new SolveResults { Value = input * input };

    protected override void SolveInstance(IGH_DataAccess DA)
    {
        if (InPreSolve)
        {
            double n = 0;
            if (!DA.GetData(0, ref n)) return;
            TaskList.Add(Task.Run(() => Compute(n), CancelToken));
            return;
        }
        if (!GetSolveResults(DA, out SolveResults result)) return;
        DA.SetData(0, result.Value);
    }
}
```

> **Warning — zero-input components:** `GH_TaskCapableComponent<T>` silently fails when
> `RegisterInputParams` registers zero input parameters. Tasks get scheduled via `TaskList.Add`
> in the pre-solve pass, but the post-solve pass never completes — `GetSolveResults` is never
> called. Outputs are empty, with no errors or warnings. This affects any component that
> fetches external data without user-provided inputs (API status checkers, list-all-items
> endpoints). Use the manual async pattern (next section) instead.
>
> Confirmed in a production plugin: a "List Clients" component went from 1 input to 0 inputs.
> It stopped producing data with no error. A sibling component with 1 input using the same base
> class continued working. Replacing `GH_TaskCapableComponent<T>` with `GH_Component` + manual
> async restored output.

### Opting out — staying on the main thread

A standard `GH_Component` subclass (no `IGH_TaskCapableComponent`) always executes
`SolveInstance` on the UI thread. This is the default. You do not need to do anything special
to opt out; simply do not implement `IGH_TaskCapableComponent`.

If you start with a `GH_TaskCapableComponent<T>` and later need to revert, change the base
class back to `GH_Component` and remove the task-related members.

---

## Manual Async Alternative (Plain `GH_Component`)

When `GH_TaskCapableComponent<T>` is not suitable — zero-input components (see warning above),
persistent polling, or cases where the two-phase pattern adds unnecessary complexity — subclass
`GH_Component` directly and manage async work manually.

**Pattern:** In `SolveInstance`, if a fetch is needed and not already in progress, launch
`Task.Run`. The background task writes results to a field, then calls
`RhinoApp.InvokeOnUiThread(() => ExpireSolution(true))`. The next solve cycle reads the
cached result and emits outputs.

### Minimal manual-async skeleton

```csharp
public class MyAsyncComponent : GH_Component
{
    private MyResult _result;
    private volatile bool _isFetching;

    public MyAsyncComponent()
        : base("AsyncFetch", "AF", "Fetches data in background.", "MyPlugin", "Network") { }

    // RegisterInputParams / RegisterOutputParams — same as any GH_Component.

    protected override void SolveInstance(IGH_DataAccess DA)
    {
        // Emit whatever we have (null on first run, cached after fetch completes).
        if (_result != null)
            DA.SetData(0, _result.Value);

        if (_isFetching) return;          // don't launch a second fetch
        _isFetching = true;

        Task.Run(async () =>
        {
            try
            {
                _result = await FetchAsync();
            }
            catch (Exception ex)
            {
                Rhino.RhinoApp.WriteLine($"Fetch error: {ex.Message}");
            }
            finally
            {
                _isFetching = false;
                RhinoApp.InvokeOnUiThread(new Action(() =>
                {
                    if (OnPingDocument() != null)
                        ExpireSolution(true);
                }));
            }
        });
    }

    private static async Task<MyResult> FetchAsync() { /* HTTP call */ }
}
```

### Thread-safety notes

- **`volatile bool _isFetching`:** Guards against concurrent fetches. The `volatile` keyword
  ensures visibility across threads.
- **`OnPingDocument() != null`:** The component may have been removed from the canvas between
  task completion and the UI-thread callback. Without this guard, `ExpireSolution` operates on
  a detached component.
- **Reference-type field assignment:** `_result = await FetchAsync()` is an atomic reference
  assignment in .NET. The `InvokeOnUiThread` call creates a happens-before relationship,
  ensuring the UI thread sees the updated field when the next solve runs.
- **No built-in `CancellationToken`:** Unlike `GH_TaskCapableComponent<T>`, this pattern has
  no `CancelToken`. For long-running or cancellable work, manage your own
  `CancellationTokenSource` and cancel it in a `RemovedFromDocument` override.

### Trade-offs vs `GH_TaskCapableComponent<T>`

| | `GH_TaskCapableComponent<T>` | Manual async |
|---|---|---|
| **Input count** | Requires ≥ 1 input parameter | Works with any input count |
| **Cancellation** | Built-in `CancelToken` | Manual `CancellationTokenSource` |
| **Complexity** | Two-phase pre-solve / post-solve | Single-phase with field caching |
| **Parallel solver** | Integrated with GH parallel solver | Not integrated |

---

## Cancellation

`GH_TaskCapableComponent<T>` exposes a `CancelToken` (`CancellationToken`) that Grasshopper
sets when it wants to abort the current solve (e.g. the user triggers a re-solve before the
previous one finishes). Always pass `CancelToken` to `Task.Run` and to any long-running
operation that accepts a `CancellationToken`:

```csharp
Task<SolveResults> task = Task.Run(() => ComputeHeavy(input), CancelToken);
```

For long loops inside the compute method, check `CancellationToken.IsCancellationRequested`
periodically and throw `OperationCanceledException` to exit cleanly:

```csharp
private static SolveResults ComputeHeavy(double input, CancellationToken ct)
{
    for (int i = 0; i < 1_000_000; i++)
    {
        ct.ThrowIfCancellationRequested();
        // ... do work ...
    }
    return new SolveResults { Value = input };
}
```

Standard `GH_Component` (not task-capable) has no `CancelToken`. Keep `SolveInstance` short
and return promptly — do not run unbounded loops.

---

## `RhinoApp.WriteLine` from Worker Threads

`RhinoApp.WriteLine` is used throughout the Grasshopper developer community for print-style
debugging from inside `SolveInstance`. It appears in worker-thread contexts in forum examples
without reported crashes (discourse.mcneel.com topic 112085, verified 2026-05-17 — multiple
code samples call it inside `Task.Run` bodies without documented failure).

**Practical status:** Treat as de-facto safe for debug-logging from worker threads; output
ordering is not guaranteed (parallel tasks may interleave). For production diagnostics, prefer
`AddRuntimeMessage` (called on the UI thread after the solve) or `Debug.WriteLine`.

---

## Common Failures

No `[threading-and-the-main-thread]` findings in the RED baseline (trivial single-item
`SolveInstance`). The failures below are drawn from spec §5 and primary-source forum evidence.

### Failure 1: Calling `RhinoDoc.ActiveDoc` inside a `Task.Run` body

**WRONG:**

```csharp
// Called inside a task-capable component's pre-solve pass.
protected override void SolveInstance(IGH_DataAccess DA)
{
    if (InPreSolve)
    {
        Curve curve = null;
        if (!DA.GetData(0, ref curve)) return;

        Task<Point3d> task = Task.Run(() =>
        {
            // BUG: accessing ActiveDoc from a worker thread
            double tol = RhinoDoc.ActiveDoc.ModelAbsoluteTolerance;
            return curve.PointAtNormalizedLength(0.5);
        }, CancelToken);
        TaskList.Add(task);
        return;
    }
    // ...
}
```

**Why it fails:** `RhinoDoc.ActiveDoc` reads a UI-thread property from a worker thread. In
the common case it returns a valid object, giving the false impression that it works. Under
document-switching or rapid re-solve scenarios it can return null or an unexpected document,
producing silent incorrect results.

**RIGHT:** Read `RhinoDoc.ActiveDoc` once on the UI thread before any `Task.Run`, capture the
needed value (e.g. `tol`) in a local variable, and close over the local variable in the task
lambda.

```csharp
if (InPreSolve)
{
    var doc = RhinoDoc.ActiveDoc;
    if (doc == null) return;
    double tol = doc.ModelAbsoluteTolerance;  // captured by value

    Curve curve = null;
    if (!DA.GetData(0, ref curve)) return;

    Task<Point3d> task = Task.Run(() =>
    {
        // Safe: tol is a captured local double, not a property access.
        return curve.PointAtNormalizedLength(0.5);
    }, CancelToken);
    TaskList.Add(task);
    return;
}
```

### Failure 2: Calling `DA.SetData` from inside a worker task

**WRONG:**

```csharp
Task.Run(() =>
{
    Point3d result = ComputeMidpoint(curve);
    DA.SetData(0, result);  // BUG: DA is not thread-safe
});
```

**Why it fails:** `IGH_DataAccess` is confirmed not thread-safe (Steve Baer, McNeel admin,
discourse topic 80496). Calling it from a worker thread produces undefined behaviour — silent
data loss, incorrect output, or runtime exceptions.

**RIGHT:** Use the task-capable two-phase pattern. Compute in the worker; call `DA.SetData`
only in the post-solve pass (when `InPreSolve == false`), which runs on the UI thread.

### Failure 3: Copying a pre-Rhino-8 example that accesses `ActiveDoc` inside `Parallel.For`

Pre-Rhino-8 forum examples often use `Parallel.For` with `RhinoDoc.ActiveDoc` calls inside
the loop body. These are safe only because `SolveInstance` was always on the UI thread when
those examples were written — once adapted to a task-capable component they become unsafe.
Apply the Failure 1 "RIGHT" pattern: isolate the `ActiveDoc` read before the parallel region.

### Failure 4: Using `GH_TaskCapableComponent<T>` with zero input parameters

**WRONG:**

```csharp
// Component with no inputs — silently produces empty outputs.
public class ApiStatusComponent : GH_TaskCapableComponent<ApiStatusComponent.SolveResults>
{
    public class SolveResults { public string Status { get; set; } }

    protected override void RegisterInputParams(GH_InputParamManager pManager) { }
    protected override void RegisterOutputParams(GH_OutputParamManager pManager)
    {
        pManager.AddTextParameter("Status", "S", "API status", GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess DA)
    {
        if (InPreSolve)
        {
            TaskList.Add(Task.Run(() => new SolveResults { Status = "OK" }, CancelToken));
            return;
        }
        // GetSolveResults is NEVER called — post-solve pass does not execute.
        if (!GetSolveResults(DA, out SolveResults result)) return;
        DA.SetData(0, result.Status);
    }
}
```

**Why it fails:** With zero registered inputs, `GH_TaskCapableComponent<T>` runs the pre-solve
pass (tasks are added to `TaskList`) but the post-solve pass never executes. `GetSolveResults`
is never called. All outputs are empty. No errors, no warnings. The component appears to solve
normally. This is not a bug in user code — it is a limitation of the base class.

A common misdiagnosis is blaming a leftover `DA.GetData` guard or assuming the task was not
added correctly. The real cause is the zero-input count itself.

**RIGHT:** Use the manual async pattern (see "Manual Async Alternative" section above):

```csharp
public class ApiStatusComponent : GH_Component
{
    private string _status;
    private volatile bool _isFetching;

    public ApiStatusComponent()
        : base("API Status", "API", "Checks API status.", "MyPlugin", "Network") { }

    protected override void RegisterInputParams(GH_InputParamManager pManager) { }
    protected override void RegisterOutputParams(GH_OutputParamManager pManager)
    {
        pManager.AddTextParameter("Status", "S", "API status", GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess DA)
    {
        if (_status != null)
            DA.SetData(0, _status);

        if (_isFetching) return;
        _isFetching = true;

        Task.Run(async () =>
        {
            try { _status = await CheckApiAsync(); }
            finally
            {
                _isFetching = false;
                RhinoApp.InvokeOnUiThread(new Action(() =>
                {
                    if (OnPingDocument() != null)
                        ExpireSolution(true);
                }));
            }
        });
    }
}
```

---

## Cross-links

See also:
- `[[geometry-units-and-tolerance.md]]` for accessing `RhinoDoc.ActiveDoc` safely (read once,
  store in a local) and for `ModelAbsoluteTolerance` / `ModelUnitSystem` usage.
- `[[component-lifecycle.md]]` for `GH_Component` subclass structure and the role of
  `SolveInstance` in the component lifecycle.
- `[[params-and-registration.md]]` for `DA.GetData` / `DA.SetData` usage patterns.
