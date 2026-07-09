# Icons

Revit ribbon buttons take icons at two sizes: **32×32** (`PushButtonData.LargeImage`,
shown when the button is large) and **16×16** (`PushButtonData.Image`, shown when the
button is small/stacked). This reference covers Revit ribbon design rules, generating
the PNGs from an icon library, and wiring them onto buttons. *Loading* the PNGs at
runtime is already handled by the template — see `[[ui-and-interaction.md]]` and
`Infrastructure/ImageUtils.cs`.

---

## Sizes & the native-render rule

| Use | Size | Property |
|---|---|---|
| Large button | 32×32 px | `PushButtonData.LargeImage` |
| Small / stacked button | 16×16 px | `PushButtonData.Image` |

- **Two PNGs per command.** Provide both; Revit picks one based on how the button is shown.
- **High-DPI:** Revit upsamples ribbon images on high-DPI displays, so a crisp,
  pixel-aligned 32px source matters (there is no separate `@2x` asset — just the 32px image).
- **Render each size natively. Never downscale the 32px PNG to make the 16px.**
  Rasterizing the source vector directly at 16px hits the 16px pixel grid cleanly;
  shrinking a 32px raster blurs it.
- **Simplification is a separate problem.** A glyph with fine detail is unreadable at
  16px no matter how you rasterize it — the detail physically can't fit in 16 pixels.
  The only fix is a *simpler glyph* for the small size (the generator supports this).

---

## Design rules — Autodesk ribbon style

Revit ribbon icons should sit comfortably beside Autodesk's native buttons. These are
conventions for fitting that visual context, not a published pixel spec.

- **Flat and line-based.** Favor clean outlined glyphs over photoreal or heavily shaded
  art. Avoid the gradient-fill + drop-shadow style used for Grasshopper canvas icons — it
  looks out of place on the Revit ribbon.
- **Restrained palette.** One or two hues. Use a dark gray (e.g. `#404040`) rather than
  pure black for strokes; pure black reads heavy at ribbon scale.
- **Pixel-grid alignment.** Align strokes to the grid and keep stroke weight even,
  especially at 16px.
- **Breathing room.** Leave a 1–2 px transparent margin so the glyph doesn't touch the
  button edge.
- **Transparent background, always.** PNG with an alpha channel. A white or colored box
  behind the glyph is the #1 sign of a broken icon (see Common failures).
- **Distinct silhouettes.** Icons are navigation aids — each command should be
  recognizable in peripheral vision. Two commands need two different shapes, not the same
  shape recolored.
- **No text.** Letters are illegible at 16–32 px.

---

## Generating icons — Iconify → PNG

Pull line glyphs from an existing library for fast, consistent results. **Lucide** matches
the flat ribbon style well; **Tabler** and **Phosphor** are good alternates. The **Iconify
API** serves 200k+ icons across these families.

The Iconify API returns **SVG only** — no PNG endpoint, no stroke-width override. So the
script fetches each glyph as SVG (tinted via the `color` parameter) and rasterizes it
locally to PNG at each size.

### Rasterizer: `resvg-py` (not cairosvg, not reportlab)

- `cairosvg` needs a native libcairo runtime — painful to install on Windows.
- `svglib` + `reportlab` (`renderPM`) installs cleanly but **drops the alpha channel**
  (RGB output → white-boxed icons).
- **`resvg-py`** installs from a wheel with no system libraries and returns **RGBA** PNGs
  with full transparency at the exact requested size. Use it.

```
pip install resvg-py Pillow
```

### The generator

Save this as `Resources\generate_icons.py`, edit the `ICONS` map, and run it:

```python
"""
Generate Revit ribbon icons from the Iconify API.

Fetches an SVG per command, tints it dark gray, and rasterizes a 32x32
(LargeImage) and a 16x16 (Image) transparent PNG next to this script.

Setup (Windows-friendly, no system libraries):
    pip install resvg-py Pillow

Run from the project root:
    python Resources\\generate_icons.py
"""
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

OUT = os.path.dirname(os.path.abspath(__file__))      # write next to this script
COLOR = "#404040"                                      # dark gray, not pure black
UA = {"User-Agent": "Mozilla/5.0 (revit-icon-gen)"}    # Iconify 403s the default UA

# command name -> Iconify id.
#   "Name": "lucide/ruler"                 same glyph at both sizes
#   "Name": {"32": "...", "16": "..."}     simpler glyph for the small (16px) button
# Browse ids at https://icon-sets.iconify.design/   (lucide / tabler / ph)
ICONS = {
    "MyCommand": "lucide/wand-sparkles",
}


def fetch_svg(icon_id, size):
    query = urllib.parse.urlencode({"width": size, "height": size, "color": COLOR})
    url = f"https://api.iconify.design/{icon_id}.svg?{query}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Iconify returned {resp.status} for {icon_id}")
        return resp.read().decode("utf-8")


def render_png(svg_text, path):
    import resvg_py
    with open(path, "wb") as f:
        f.write(bytes(resvg_py.svg_to_bytes(svg_string=svg_text)))


def verify(path, size):
    """Optional self-check; skipped if Pillow isn't installed."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path)
    assert im.size == (size, size), f"{path}: {im.size}, expected {size}x{size}"
    assert im.mode == "RGBA", f"{path}: mode {im.mode}, expected RGBA (no transparency)"


def generate(name, spec):
    for size in (32, 16):
        icon_id = spec[str(size)] if isinstance(spec, dict) else spec
        path = os.path.join(OUT, f"{name}{size}.png")
        render_png(fetch_svg(icon_id, size), path)
        verify(path, size)
        print(f"  {name}{size}.png  <-  {icon_id}")


if __name__ == "__main__":
    try:
        import resvg_py  # noqa: F401
    except ImportError:
        sys.exit("Missing rasterizer. Run:  pip install resvg-py Pillow")
    try:
        for name, spec in ICONS.items():
            generate(name, spec)
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach api.iconify.design ({e}). Check your connection.")
    print(f"Done. PNGs written to {OUT}")
```

```powershell
python Resources\generate_icons.py
```

It writes `{Command}32.png` and `{Command}16.png` into `Resources\`. The `.csproj`
already embeds `Resources\*.png` (see `[[project-setup-and-build.md]]`), so a rebuild
picks them up.

### Choosing glyphs

Browse `https://icon-sets.iconify.design/` and pick shapes that are visually distinct from
one another. For a command whose detailed glyph turns to mush at 16px, give it a simpler
16px id:

```python
ICONS = {
    "PlaceWall": "lucide/brick-wall",                              # same glyph both sizes
    "TagRooms":  {"32": "lucide/scan-text", "16": "lucide/tag"},   # simpler at 16px
}
```

---

## Wiring icons onto buttons

Loading is already implemented — `Infrastructure/ImageUtils.cs` reads a PNG from the
embedded-resource stream into a frozen `BitmapImage` (the reliable approach; naive pack
URIs often fail — see `[[ui-and-interaction.md]]`). `ImageUtils.Load` takes the assembly
that embeds the PNGs plus the resource-name suffix — pass `Assembly.GetExecutingAssembly()`
from the add-in. (Passing the assembly explicitly, rather than calling
`GetExecutingAssembly()` inside the helper, keeps it working if you later move `ImageUtils`
into a shared library whose assembly doesn't contain the icons.)

```csharp
var asm = Assembly.GetExecutingAssembly();
var data = new PushButtonData(
    "MyCommand", "My\nCommand",
    asm.Location, "MyRevitAddin.Commands.MyCommand");
var btn = (PushButton)panel.AddItem(data);
btn.LargeImage = ImageUtils.Load(asm, "MyCommand32.png"); // 32x32
btn.Image      = ImageUtils.Load(asm, "MyCommand16.png"); // 16x16
```

### Naming convention

The template's single starter button uses generic `icon32.png` / `icon16.png`. For an
add-in with several commands, name per command — `{Command}32.png` / `{Command}16.png` —
so each button loads its own pair. The string passed to `ImageUtils.Load` only needs to
match the end of the embedded resource name.

### Match sizes to the ribbon layout

Not every command needs both sizes:

- A **large** `PushButton` on a panel uses the 32px `LargeImage`.
- Commands added as **stacked small buttons** (`panel.AddStackedItems(...)`) render only
  the 16px `Image`.

So a command that will only ever appear as a small stacked button needs just a 16px PNG —
generating a 32px for it is wasted. Decide the layout first, then generate the sizes
you'll use.

---

## Common failures

**White (or colored) box behind the glyph.** The rasterizer dropped the alpha channel —
`reportlab`/`renderPM` does this. Use `resvg-py`, which outputs RGBA.

**`403 Forbidden` from the Iconify API.** The request lacked a `User-Agent` header; the API
rejects the default `urllib` agent. The generator sets one.

**Icon doesn't appear (no error).** `ImageUtils.Load` returned `null` because no embedded
resource name ends with the string you passed. Confirm the PNG lives under `Resources\`
(the `.csproj` globs `Resources\*.png` as `EmbeddedResource`) and that the name matches:

```powershell
# against your built DLL, e.g. in a scratch C# snippet / LINQPad:
# Assembly.LoadFrom("MyRevitAddin.dll").GetManifestResourceNames()
```

**Blurry 16px.** Produced by downscaling the 32px PNG instead of rasterizing the SVG
natively at 16px. If a natively-rendered 16px is still mush, the glyph is too detailed —
give it a simpler 16px id in the `ICONS` map.

**Stretched or clipped icon.** The PNG isn't square at the expected size. Revit does not
resize; feed it exactly 32×32 and 16×16.

---

## When no library glyph fits

For a domain-specific concept no library covers, draw a simple shape directly with
Pillow's `ImageDraw` (render at high resolution — e.g. 4× — then downscale with
`Image.LANCZOS` for clean anti-aliasing) and save as a transparent RGBA PNG at 32×32 and
16×16. Keep it to a recognizable silhouette; detailed custom art rarely survives ribbon
scale.

---

See also:
- `[[ui-and-interaction.md]]` — ribbon/panel/button anatomy, the `ImageUtils` loader, the pack-URI pitfall.
- `[[project-setup-and-build.md]]` — the `Resources\*.png` embed rule.
