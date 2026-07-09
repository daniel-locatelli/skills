# Icons

Grasshopper needs icons at two levels: **component icons** (24×24 bitmaps on the canvas and palette) and **package icons** (64×64 PNGs in the Yak manifest). This reference covers both — design rules, programmatic generation, and wiring them into the build.

---

## Design rules

These rules come from the official Grasshopper icon guide and David Rutten's essay on icon design. Follow them.

### Canvas icons (24×24)

| Property | Value |
|---|---|
| **Size** | Exactly 24×24 px |
| **Format** | PNG, RGBA (transparency OK) |
| **Safe area** | 2 px empty border on all four sides — draw within the 20×20 interior |
| **Drop shadow** | 2 px Gaussian blur, black at 25% opacity (65/255), offset 1 px right + 1 px down |
| **Outlines** | Dark gray or dark shade of the fill — **not** black. Silhouette edges only; leave internal creases alone |

### David Rutten's guidelines (memorize these)

1. Use colour, but limit to 1–2 hues per icon. Different icons should look different in peripheral vision.
2. No photorealism. Flat shapes with subtle vertical gradients beat detailed renders.
3. No perspective unless it is the point of the image.
4. No near-vertical or near-horizontal lines — they anti-alias badly at 24 px.
5. Align geometry to the pixel grid. Make a new image for every size; never just scale one down.
6. No black outlines — use a darker shade of the fill colour.
7. Faint shadows for depth, never sharp outlines.
8. Large fills get subtle gradients, not solid colour.
9. No text in icons.
10. Don't imply transparency unless it is the point.
11. Add a faint (5–10% opacity) 1 px edge around high-contrast transitions for uber-anti-aliasing.
12. Don't stack icons too close — leave empty pixels at the edges (the 2 px border handles this).

Icons are **navigation aids**, not feature descriptions. They must be memorable and recognizable, not representative. A pink sphere could mean "paste" as long as it is distinct from the other icons.

### Package icons (Yak)

For the Yak `manifest.yml` `icon` field: PNG, square, 64×64 recommended (128×128 also common), transparent background preferred. See `[[yak-packaging.md]]` for manifest details.

---

## Quick start: composing icons from Lucide / Iconify

The fastest way to get presentable component icons is to pull from an existing icon library. **Lucide** icons are already designed at 24×24, and the **Iconify API** gives access to 200k+ icons across 150+ families (Lucide, Phosphor, Tabler, Material Design, etc.) — all fetchable as SVGs via a single HTTP endpoint.

**Recommended families for GH components:**

| Family | Iconify prefix | Style | Notes |
|---|---|---|---|
| Lucide | `lucide` | 24×24 stroked, clean | Best default — matches GH's line weight |
| Phosphor | `ph` | Multiple weights (thin/light/regular/bold/fill/duotone) | Good variety |
| Tabler | `tabler` | 24×24 stroked, rounded | Similar to Lucide |
| Material Design Icons | `mdi` | 24×24 filled | Denser shapes |

### Pipeline: Iconify API → SVG → PNG

A Python script can fetch icons, tint them to a GH-appropriate colour, apply the standard drop shadow, and produce build-ready 24×24 PNGs:

```python
"""
Fetch icons from Iconify and convert to GH-ready 24×24 PNGs.

Run:  pip install Pillow cairosvg requests
      python generate_icons.py
"""

import os
import io
import requests
import cairosvg
from PIL import Image, ImageFilter

SCALE = 4
HI = 24 * SCALE       # 96 — render resolution
FINAL = 24
OUT = os.path.dirname(os.path.abspath(__file__))

# GH-appropriate icon colour — dark gray, not black (per Rutten's rules)
ICON_COLOR = "%23404040"  # URL-encoded #404040

# ── Icon manifest ───────────────────────────────────────────
# Map component names to Iconify icon identifiers.
# Browse icons at https://icon-sets.iconify.design/

ICONS = {
    "Midpoint":    "lucide/locate",
    "Length":      "lucide/ruler",
    "Divide":     "lucide/scissors",
    "Offset":     "lucide/copy",
    "Intersect":  "lucide/crosshair",
}

def fetch_svg(prefix_name, size=HI, color=ICON_COLOR):
    """Fetch an SVG from the Iconify API at the given size and colour."""
    url = f"https://api.iconify.design/{prefix_name}.svg?width={size}&height={size}&color={color}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.content

def svg_to_png(svg_bytes):
    """Convert SVG bytes to a Pillow RGBA Image."""
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=HI, output_height=HI)
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

def add_shadow(img):
    """GH-standard drop shadow: 2 px blur, 25% black, offset (1,1)."""
    s = lambda v: int(v * SCALE)
    alpha = img.split()[3]
    shadow = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (HI, HI), (0, 0, 0, 65))
    shadow.paste(shadow_layer, mask=alpha)
    offset = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    offset.paste(shadow, (s(1), s(1)))
    offset = offset.filter(ImageFilter.GaussianBlur(radius=s(2)))
    return Image.alpha_composite(offset, img)

def generate(name, prefix_name):
    img = svg_to_png(fetch_svg(prefix_name))
    img = add_shadow(img)
    img = img.resize((FINAL, FINAL), Image.LANCZOS)
    path = os.path.join(OUT, f"{name}.png")
    img.save(path)
    print(f"  {name}.png  ←  {prefix_name}")

if __name__ == "__main__":
    print("Generating GH icons from Iconify...")
    for name, icon_id in ICONS.items():
        generate(name, icon_id)
    print(f"\nDone! Icons saved to: {OUT}")
```

### Choosing icons

Browse the full catalogue at `https://icon-sets.iconify.design/`. Pick icons that are **visually distinct** from each other — remember Rutten's rule: icons are navigation aids, not feature descriptions. A curve component and a surface component need different silhouettes, not a curve and a surface.

### When to use custom Pillow drawing instead

Use the Iconify pipeline for most components. Switch to custom Pillow drawing (below) when:

- No existing icon captures the concept (domain-specific geometry operations).
- You need to compose multiple shapes (e.g. a mesh with an upload arrow).
- The plugin's visual identity requires a unified custom style.

---

## Custom icons with Python (PIL/Pillow)

An AI agent cannot open Xara or Photoshop. The practical approach is a Python script using Pillow that renders at 4× resolution (96×96) and downscales with LANCZOS. This produces crisp, anti-aliased 24×24 icons that follow every GH design rule.

### Script skeleton

```python
from PIL import Image, ImageDraw, ImageFilter
import os

SCALE = 4
HI = 24 * SCALE       # 96 — working resolution
FINAL = 24
OUT = os.path.dirname(os.path.abspath(__file__))

# ── Helpers ─────────────────────────────────────────────────

def s(v):
    """Scale a coordinate from 24-space to working resolution."""
    return int(v * SCALE)

def sp(pts):
    """Scale a list of (x, y) tuples."""
    return [(s(x), s(y)) for x, y in pts]

def new():
    """New transparent 96×96 canvas."""
    return Image.new("RGBA", (HI, HI), (0, 0, 0, 0))

def add_shadow(img):
    """GH-standard drop shadow: 2 px blur, 25% black, offset (1,1)."""
    alpha = img.split()[3]
    shadow = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (HI, HI), (0, 0, 0, 65))
    shadow.paste(shadow_layer, mask=alpha)
    offset = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    offset.paste(shadow, (s(1), s(1)))
    offset = offset.filter(ImageFilter.GaussianBlur(radius=s(2)))
    return Image.alpha_composite(offset, img)

def gradient_fill(draw, pts, color_top, color_bot, bbox=None):
    """Fill a polygon with a vertical gradient."""
    temp = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    td = ImageDraw.Draw(temp)
    td.polygon(pts, fill=color_top)
    if bbox is None:
        ys = [p[1] for p in pts]
        y_min, y_max = min(ys), max(ys)
    else:
        y_min, y_max = bbox[1], bbox[3]
    height = max(y_max - y_min, 1)
    for y in range(y_min, y_max + 1):
        t = (y - y_min) / height
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        td.line([(0, y), (HI, y)], fill=(r, g, b, 255))
    mask = Image.new("L", (HI, HI), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(pts, fill=255)
    result = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    result.paste(temp, mask=mask)
    return result

def finalize(img, name):
    """Apply shadow, downscale to 24×24, save."""
    img = add_shadow(img)
    img = img.resize((FINAL, FINAL), Image.LANCZOS)
    img.save(os.path.join(OUT, f"{name}.png"))
    print(f"  {name}.png")
```

### Writing an icon function

Think in 24-space coordinates. Use `s()` and `sp()` to scale to working resolution. Draw filled shapes with gradients, add silhouette outlines only, then call `finalize()`.

```python
# ── Standardised widths (in 24-space) ───────────────────────
W_SILHOUETTE = 0.6    # outer edges
W_INTERNAL   = 0.4    # internal detail lines
W_GROUND     = 0.7    # ground / axis lines

OUTLINE      = (10, 10, 10)       # near-black for silhouettes
BODY_L       = (55, 55, 55)       # lighter shade — gradient top
BODY_D       = (18, 18, 18)       # darker shade — gradient bottom
WHITE        = (220, 220, 220)    # highlight / feature colour

def icon_example():
    """Mountain with snow cap."""
    img = new()
    d = ImageDraw.Draw(img)

    # Main shape — filled polygon with vertical gradient
    mtn = sp([(2, 21), (11, 4), (22, 21)])
    mgrad = gradient_fill(d, mtn, BODY_L, BODY_D)
    img = Image.alpha_composite(img, mgrad)
    d = ImageDraw.Draw(img)
    d.polygon(mtn, outline=OUTLINE, width=s(W_SILHOUETTE))

    # Feature — small contrasting shape
    snow = sp([(11, 4), (8.5, 9), (13.5, 9)])
    d.polygon(snow, fill=WHITE, outline=OUTLINE, width=s(W_INTERNAL))

    # Ground line
    d.line([s(2), s(21), s(22), s(21)], fill=OUTLINE, width=s(W_GROUND))

    finalize(img, "Example")
```

### Running the generator

```powershell
pip install Pillow          # once
python Icons\generate_icons.py
```

This writes PNGs into the `Icons\` folder. Verify each icon is exactly 24×24 RGBA.

---

## Wiring icons into the build

### 1. Embed as assembly resources

In the `.csproj`, embed all PNGs from the `Icons\` folder:

```xml
<ItemGroup>
  <EmbeddedResource Include="Icons\*.png" />
</ItemGroup>
```

This compiles each PNG into the assembly with the resource name `{RootNamespace}.Icons.{Filename}` — for example, `CurveUtils.Icons.Midpoint.png`.

### 2. Icon loader utility

Add a static helper that loads icons by component name:

```csharp
using System.Drawing;
using System.Reflection;

namespace CurveUtils
{
    internal static class IconLoader
    {
        internal static Bitmap Load(string name)
        {
            var assembly = Assembly.GetExecutingAssembly();
            var resourceName = $"CurveUtils.Icons.{name}.png";
            using (var stream = assembly.GetManifestResourceStream(resourceName))
            {
                return stream != null ? new Bitmap(stream) : null;
            }
        }
    }
}
```

Replace `CurveUtils` with your project's root namespace.

### 3. Override `Icon` on each component

```csharp
public class MidpointComponent : GH_Component
{
    // ... constructor, params, SolveInstance ...

    protected override Bitmap Icon => IconLoader.Load("Midpoint");

    public override Guid ComponentGuid =>
        new Guid("..."); // freshly generated
}
```

The string `"Midpoint"` matches the filename `Icons\Midpoint.png` — no extension, no path.

### 4. `GH_AssemblyInfo.Icon`

The assembly info icon appears in Grasshopper's plugin manager. It uses the same loader:

```csharp
public class CurveUtilsInfo : GH_AssemblyInfo
{
    public override string Name => "CurveUtils";
    public override Bitmap Icon => IconLoader.Load("CurveUtils");
    // ... other overrides ...
}
```

`null` is acceptable during development but should be replaced before distribution.

---

## Naming convention

| File | Matches |
|---|---|
| `Icons\{ComponentName}.png` | `IconLoader.Load("{ComponentName}")` |
| `Icons\{PluginName}.png` | `GH_AssemblyInfo.Icon` via `IconLoader.Load("{PluginName}")` |

Use PascalCase. One PNG per component, plus one for the assembly.

---

## Common failures

### Failure 1: Resource not found at runtime

`IconLoader.Load("Midpoint")` returns `null` — no icon on the canvas.

**Cause:** The resource name doesn't match. Embedded resource names are `{DefaultNamespace}.{FolderPath}.{Filename}` where folder separators become dots.

**Fix:** Verify with:

```powershell
dotnet build
# In a test or scratch file:
# Assembly.GetExecutingAssembly().GetManifestResourceNames()
```

Check that the namespace in the `$"..."` interpolation matches `<RootNamespace>` in the csproj.

### Failure 2: Icons not embedded — shown as `null`

The PNGs exist on disk but aren't compiled into the assembly.

**Cause:** Missing `<EmbeddedResource>` in the csproj. By default, PNGs are not included.

**Fix:** Add the `<EmbeddedResource Include="Icons\*.png" />` item group.

### Failure 3: Bitmap wrong size

Component icons must be exactly 24×24. Grasshopper does **not** resize them — wrong dimensions produce stretched or clipped icons.

**Fix:** If generating with the Python pipeline, verify `FINAL = 24` and that `finalize()` calls `.resize((FINAL, FINAL), Image.LANCZOS)`.

### Failure 4: Confusing `Icon` override with Yak package icon

The `protected override Bitmap Icon` on `GH_Component` is a **24×24 in-memory bitmap** loaded from an embedded resource. The `icon` field in `manifest.yml` is a **64×64 PNG file on disk** placed next to the `.gha` before `yak build`. They are separate artifacts with different purposes.

---

See also:
- `[[component-lifecycle.md]]` for the full `GH_Component` and `GH_AssemblyInfo` anatomy.
- `[[yak-packaging.md]]` for packaging the 64×64 icon into a `.yak` distribution.
