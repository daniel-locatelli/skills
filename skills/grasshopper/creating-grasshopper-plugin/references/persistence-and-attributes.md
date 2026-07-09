# Persistence and Custom Attributes

## When You Need This

Most components do not touch persistence or custom attributes. You need this reference when
any of the following apply:

1. **Persistent input values.** The user right-clicks a parameter and chooses "Set One/Multiple
   &lt;Type&gt;" to bake a value into the param. That value must survive file close and reopen.
   Without `GH_PersistentParam<T>`, the baked value is lost — the param reverts to
   volatile/empty on next load.

2. **Custom UI (non-default attributes).** The standard capsule draws input/output grips only.
   If you need buttons, toggles, or any other canvas widget, subclass `GH_ComponentAttributes`
   and override `Layout` and `Render`.

3. **Component-state serialisation.** Per-instance settings that are not expressed as input
   parameters (a mode enum, a filter string) must be written to and read from the `.gh` file
   explicitly. Override `Write(GH_IWriter)` and `Read(GH_IReader)` on the component class.

**Spec note:** "Often skipped, then needed; teaching just-in-time is cheaper than retrofitting
later." See "Common Failures" for the cost of deferral.

---

## `GH_PersistentParam<T>`

**Namespace:** `Grasshopper.Kernel`  
**Base class:** `GH_Param<T>` (where `T : class, IGH_Goo`)  
**SDK API:** verified at `mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_PersistentParam_1.htm`
(2026-05-17)

The abstract base class for all built-in `Param_*` types. It maintains a `PersistentData`
(`GH_Structure<T>`) store and handles its own serialisation automatically. Subclass it only
when building a **custom parameter type** that wraps a custom `IGH_Goo`. If you use existing
`Param_*` types, they already handle persistence — no subclassing needed.

**Key members:** `PersistentData` (the stored structure), `PersistentDataCount`, and
`SetPersistentData(…)` (preferred setter — triggers undo recording, change events, and
solution expiry automatically). `CollectVolatileData_Custom()` is called by the solver to
push persistent data into the volatile store when no wire is connected.

If you override `Read`/`Write` in a subclass, you **must** call `base.Read`/`base.Write` or
the `PersistentData` store will not survive save/reopen.

### Minimal example

```csharp
public class Param_MyString : GH_PersistentParam<GH_String>
{
    public Param_MyString()
        : base("My String", "MyStr", "A custom string param.", "MyPlugin", "Params") { }

    public override Guid ComponentGuid => new Guid("YOUR-NEW-GUID-HERE");

    protected override GH_String InstantiateT() => new GH_String();

    public override GH_Exposure Exposure => GH_Exposure.primary;
}
```

Grasshopper discovers the parameter via `GH_AssemblyInfo` — no extra registration step.

---

## Custom `GH_ComponentAttributes`

**Namespace:** `Grasshopper.Kernel.Attributes`  
**Base class:** `GH_Attributes<IGH_Component>`  
**SDK API:** verified at `mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_Attributes_GH_ComponentAttributes.htm`
(2026-05-17)

Subclass to draw non-default UI on the canvas. Key overridable members:

- `Layout()` — recalculates `Bounds` and sub-region rectangles. Always call `base.Layout()`
  first; then expand `Bounds` to contain your added region.
- `Render(GH_Canvas, Graphics, GH_CanvasChannel)` — draws the component. Call
  `base.Render()` first, then draw in the `Objects` channel only.
- `RespondToMouseDown(GH_Canvas, GH_CanvasMouseEvent)` — handle clicks. Return
  `GH_ObjectResponse.Handled` to consume the event; call `base.RespondToMouseDown()` for
  all unhandled cases.

Wire up by overriding `CreateAttributes()` on your component:

```csharp
public override void CreateAttributes() => m_attributes = new MyButtonAttributes(this);
```

### Minimal example — button below the capsule

```csharp
public class MyButtonAttributes : GH_ComponentAttributes
{
    private RectangleF _btnBounds;

    public MyButtonAttributes(IGH_Component owner) : base(owner) { }

    protected override void Layout()
    {
        base.Layout();                    // sets Bounds from Pivot — call first
        RectangleF b = Bounds;
        b.Height += 24;
        Bounds = b;
        _btnBounds = new RectangleF(Bounds.X + 4, Bounds.Bottom - 22, Bounds.Width - 8, 18);
    }

    protected override void Render(GH_Canvas canvas, Graphics graphics, GH_CanvasChannel ch)
    {
        base.Render(canvas, graphics, ch);
        if (ch != GH_CanvasChannel.Objects) return;
        GH_Capsule btn = GH_Capsule.CreateTextCapsule(_btnBounds, _btnBounds,
            GH_Palette.Black, "Run", 2, 0);
        btn.Render(graphics, Selected, Owner.Locked, false);
        btn.Dispose();
    }

    public override GH_ObjectResponse RespondToMouseDown(GH_Canvas sender, GH_CanvasMouseEvent e)
    {
        if (e.Button == System.Windows.Forms.MouseButtons.Left && _btnBounds.Contains(e.CanvasLocation))
        {
            Owner.ExpireSolution(true);
            return GH_ObjectResponse.Handled;
        }
        return base.RespondToMouseDown(sender, e);
    }
}
```

**Warning:** `Layout()` is called on every resize. Derive all sub-region rectangles from
`Bounds` *after* `base.Layout()` — never cache them, or the body height they hang off,
across calls (the full-name display toggle changes it). If your custom region
extends outside `Bounds`, GH's hit-testing and zoom-to-fit will be wrong.

Primary source: discourse.mcneel.com topic 107479, post by OBucklin (verified 2026-05-17).

### Custom-painted buttons with GDI+ (beyond `GH_Capsule`)

`GH_Capsule` provides a fixed set of `GH_Palette` options. For more control over button
appearance — gradient fill, custom borders, rounded corners — draw manually using
`LinearGradientBrush`, `GraphicsPath`, and `Pen`, rendered inside `Render()` on
`GH_CanvasChannel.Objects`.

**`CreateRoundedRect` helper:** A `GraphicsPath` with four `AddArc` calls plus `CloseFigure`:

```csharp
private static GraphicsPath CreateRoundedRect(RectangleF rect, float radius)
{
    float d = radius * 2;
    var path = new GraphicsPath();
    path.AddArc(rect.X, rect.Y, d, d, 180, 90);
    path.AddArc(rect.Right - d, rect.Y, d, d, 270, 90);
    path.AddArc(rect.Right - d, rect.Bottom - d, d, d, 0, 90);
    path.AddArc(rect.X, rect.Bottom - d, d, d, 90, 90);
    path.CloseFigure();
    return path;
}
```

**Gradient-filled button rendering** (inside `Render`, after `base.Render`, in `Objects`
channel):

```csharp
private bool _buttonPressed;

private void RenderButton(Graphics graphics)
{
    Color topColor = _buttonPressed
        ? Color.FromArgb(170, 170, 170)    // lighter when pressed
        : Color.FromArgb(130, 130, 130);
    Color bottomColor = _buttonPressed
        ? Color.FromArgb(110, 110, 110)
        : Color.FromArgb(50, 50, 50);

    using (var path = CreateRoundedRect(_btnBounds, 3f))
    {
        using (var fill = new LinearGradientBrush(_btnBounds, topColor, bottomColor, 90f))
            graphics.FillPath(fill, path);
        using (var border = new Pen(Color.FromArgb(30, 30, 30), 1f))
            graphics.DrawPath(border, path);
    }

    using (var font = GH_FontServer.NewFont("Verdana", 6f, FontStyle.Regular))
    using (var brush = new SolidBrush(Color.White))
    using (var fmt = new StringFormat
        { LineAlignment = StringAlignment.Center, Alignment = StringAlignment.Center })
    {
        graphics.DrawString("Run", font, brush, _btnBounds, fmt);
    }
}
```

**Click feedback with `Timer`:** Set a `_buttonPressed` flag in `RespondToMouseDown`, clear it
after ~100 ms via a `System.Windows.Forms.Timer`, and call `canvas.Refresh()` on both
transitions to trigger repaint:

```csharp
public override GH_ObjectResponse RespondToMouseDown(GH_Canvas sender, GH_CanvasMouseEvent e)
{
    if (e.Button == MouseButtons.Left && _btnBounds.Contains(e.CanvasLocation))
    {
        _buttonPressed = true;
        sender.Refresh();

        var timer = new Timer { Interval = 100 };
        timer.Tick += (s, ev) =>
        {
            timer.Stop();
            timer.Dispose();
            _buttonPressed = false;
            sender.Refresh();    // repaint back to normal state
        };
        timer.Start();

        Owner.ExpireSolution(true);
        return GH_ObjectResponse.Handled;
    }
    return base.RespondToMouseDown(sender, e);
}
```

**Note:** The visual result is functional. Tune gradient colors and timer duration to taste.

---

## `Read`/`Write` with `IGH_Chunk`

Override `Write(GH_IWriter)` and `Read(GH_IReader)` on your `GH_Component` subclass to
persist per-instance state. Both interfaces are in `GH_IO.Serialization`.

**Two absolute rules:**
1. `return base.Write(writer);` is always the last line of `Write`. The base serialises
   the component's name, position, wires, and every parameter state. Skipping it corrupts
   the file.
2. `return base.Read(reader);` is always the last line of `Read`.

**`GH_IWriter` essentials:** `SetString(name, value)`, `SetInt32`, `SetDouble`,
`SetBoolean`, `SetVersion`, `CreateChunk(name)` / `CreateChunk(name, index)`.  
**`GH_IReader` essentials:** `TryGetString(name, ref value)` (returns `false` if absent,
no throw), `TryGetInt32`, `TryGetDouble`, `TryGetBoolean`, `TryGetVersion`,
`FindChunk(name)` (returns `null` if absent — always null-check).

SDK API verified at `mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/M_Grasshopper_Kernel_GH_Component_Write.htm`
and `T_GH_IO_Serialization_GH_IReader.htm` (2026-05-17).

### Minimal example

```csharp
public class MyModeComponent : GH_Component
{
    private string _mode = "Automatic";   // per-instance state

    // constructor, Register*, SolveInstance ...

    public override bool Write(GH_IWriter writer)
    {
        writer.SetString("Mode", _mode);
        return base.Write(writer);        // always last
    }

    public override bool Read(GH_IReader reader)
    {
        if (!reader.TryGetString("Mode", ref _mode))
            _mode = "Automatic";          // default for files that predate this field
        return base.Read(reader);         // always last
    }
}
```

Primary source: discourse.mcneel.com topic 86211, post by David Rutten (McNeel admin,
verified 2026-05-17).

---

## Naming Conventions

Chunk and item names are the keys GH_IO uses when reading a file. A renamed key causes
silent data loss for every file saved before the rename.

1. **Use PascalCase literals** — `"Mode"`, `"FilterRadius"`. Easy to search; consistent with
   GH's own internal key names.
2. **Never reuse a name for a different type.** If `"Mode"` was a `string` in v1 and you
   change it to an `int`, `GetString` throws on old files. Retire the old name; introduce a
   new one.
3. **Never rename a chunk.** `FindChunk("NewName")` returns `null` on files that contain
   `"OldName"`. Data is lost silently.
4. **Version the format explicitly.** Write a `System.Version` item in every `Write` call:
   `writer.SetVersion("Version", new System.Version(2, 0));`. In `Read`, use
   `TryGetVersion` to detect old files and supply defaults for keys that did not yet exist.
   The serialisation version is independent of the plugin assembly version — bump it only
   when the set of written keys changes.

---

## Common Failures

No `[persistence-and-attributes]` findings in the RED baseline — the `CurveUtils` scenario
has no persistent state. Failures below are from the spec note and primary-source evidence.

### Failure 1: Skipping persistence, then retrofitting it

A developer ships a component with a mode toggle. No `Write`/`Read` overrides. Users save
files. On reopen, the toggle resets to default — all user state is silently lost.

**Retrofit cost:** every file saved by the old version is already missing the chunk. Data
is unrecoverable. A new release must be shipped that accepts "defaults everywhere" for old
files. If users have automation relying on the remembered mode, it breaks.

**Up-front cost:** one override, ~ten lines of code. Rule: if a component field varies
between instances, add `Write`/`Read` before the first commit that introduces the field.

### Failure 2: Skipping `base.Write` / `base.Read`

Returning `true` instead of `base.Write(writer)` omits the component's position, nick
name, and all parameter states from the file. The component appears to save but loads
broken — wrong position, disconnected wires, lost nick name.

### Failure 3: Using throwing `GetString` instead of `TryGetString`

```csharp
// WRONG — throws on files that predate this key
_mode = reader.GetString("Mode");
```

Grasshopper silently swallows exceptions thrown inside `Read` (confirmed by David Rutten,
discourse topic 102121, 2026-05-17): the partial state is dropped and the component loads
in whatever state the partially-completed `Read` left it. Use `TryGetString` (and all
`Try*` variants) for every field so missing keys are handled as defaults, not exceptions.

---

## Cross-links

See also: `[[component-lifecycle.md]]` for where `Write`, `Read`, and `CreateAttributes`
overrides fit in the `GH_Component` subclass, and for `GH_AssemblyInfo` registration.
