# Retrieval Recipe: developer.rhino3d.com URL Index

## Purpose

Consult dev guides when you need **canonical, version-pinned facts** about the Grasshopper
SDK or RhinoCommon API: csproj properties, type signatures, deployment paths, template
behaviour. The forum has too much noise on these surfaces; the dev guide is the authoritative
source.

If the dev guide comes up empty (guides in progress, GH-specific types not documented there),
escalate to forum search — see `[[search-discourse.md]]`.

---

## URL Map

| Topic | URL template |
|---|---|
| RhinoCommon API | `https://developer.rhino3d.com/api/rhinocommon/<Namespace>.<Type>` |
| Grasshopper SDK guides | `https://developer.rhino3d.com/guides/grasshopper/<slug>/` |
| Grasshopper SDK API | `https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/<page>.htm` |
| Rhino dev guides | `https://developer.rhino3d.com/guides/rhinocommon/` |
| Samples (GitHub) | `https://github.com/mcneel/rhino-developer-samples` |

**Verified real-example fetches (2026-05-17):**

| URL | Result |
|---|---|
| `https://developer.rhino3d.com/api/rhinocommon/Rhino.Geometry.Curve` | 200 — "Curve class" page |
| `https://developer.rhino3d.com/guides/grasshopper/your-first-component-windows/` | 200 — "Your First Component (Windows)" guide |
| `https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_Component.htm` | 200 — `GH_Component` class reference |
| `https://developer.rhino3d.com/guides/rhinocommon/` | 200 — "RhinoCommon Guides" index |
| `https://github.com/mcneel/rhino-developer-samples` | 200 — McNeel developer samples repo |

---

## Important Divergence: GitHub Pages vs. developer.rhino3d.com

The **Grasshopper SDK API reference** is NOT hosted on `developer.rhino3d.com`. It lives on
GitHub Pages at:

```
https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/
```

`developer.rhino3d.com/api/grasshopper` (without trailing slash) issues a **301 redirect** to
that GitHub Pages host. Agents should use the GitHub Pages URL directly rather than relying
on the redirect.

The **RhinoCommon API** reference, by contrast, **is** hosted on `developer.rhino3d.com`:

```
https://developer.rhino3d.com/api/rhinocommon/<Namespace>.<Type>
```

These are two different hosts serving two different APIs. Do not mix their URL patterns.

---

## WebFetch Usage Patterns

### Fetching the RhinoCommon API

Use the `<Namespace>.<Type>` path directly. Namespaces use dot notation; types are
PascalCase. Examples:

```
WebFetch: https://developer.rhino3d.com/api/rhinocommon/Rhino.Geometry.Curve
WebFetch: https://developer.rhino3d.com/api/rhinocommon/Rhino.Geometry.Point3d
WebFetch: https://developer.rhino3d.com/api/rhinocommon/Rhino.RhinoDoc
```

The page is rendered HTML — method signatures, property tables, and inheritance chains are
all present in the fetched content. No pagination for individual type pages.

### Fetching a Grasshopper SDK guide

The guide index at `https://developer.rhino3d.com/guides/grasshopper/` lists all guides as
a flat HTML page — fetch it once to get the slug list, then fetch the specific guide by slug.

```
WebFetch: https://developer.rhino3d.com/guides/grasshopper/
```

Each guide slug is a kebab-case string, e.g. `simple-component`, `grasshopper-data-types`,
`your-first-component-windows`. Construct the URL as:

```
WebFetch: https://developer.rhino3d.com/guides/grasshopper/simple-component/
```

The guide index is a single page (not paginated). One fetch retrieves all guide links.

### Fetching the Grasshopper SDK API

The GH API is a `.htm`-based documentation site. The index page at
`https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/` issues a meta-refresh
redirect to a frame-based entry page that does not contain substantive content directly.

To reach a specific type, use the `html/` subdirectory with the naming convention
`T_<Namespace_with_underscores>_<Type>.htm`:

```
WebFetch: https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_Component.htm
WebFetch: https://mcneel.github.io/grasshopper-api-docs/api/grasshopper/html/T_Grasshopper_Kernel_GH_Structure_1.htm
```

If you do not know the exact `.htm` filename, fetch a guide on `developer.rhino3d.com`
first — the guides often link directly to the relevant GH API type pages.

### Dev guides vs. rendered HTML

All pages on `developer.rhino3d.com` are rendered HTML. `WebFetch` converts them to
markdown. Code examples are in `<pre>`/`<code>` blocks. Method signatures on API pages are
in tables. Both are reliably readable from fetched content — no need to locate raw markdown
source.

---

## Anti-Patterns

These are URLs agents commonly guess that do **not** work as expected:

| Guessed URL | Actual behaviour | Correct alternative |
|---|---|---|
| `https://developer.rhino3d.com/api/grasshopper/` | Meta-refresh redirect; index page has no content | Use the GitHub Pages URL directly; navigate to type via `html/T_*.htm` path |
| `https://developer.rhino3d.com/api/rhinocommon/Grasshopper.Kernel.GH_Component` | "Nothing found" — GH types are NOT in the RhinoCommon API | Use `mcneel.github.io/grasshopper-api-docs/…/html/T_Grasshopper_Kernel_GH_Component.htm` |
| `https://developer.rhino3d.com/api/grasshopper/GH_Component` | 404 | Use the GitHub Pages `html/T_*.htm` path |

**Verified (2026-05-17):**
- `https://developer.rhino3d.com/api/grasshopper/` → 301 to GitHub Pages; that index page
  redirects again to a `.htm` file that returns 404. Index page has no browsable content.
- `https://developer.rhino3d.com/api/rhinocommon/Grasshopper.Kernel.GH_Component` →
  renders "Nothing found" — GH types are absent from the RhinoCommon API reference.
- `https://developer.rhino3d.com/api/grasshopper/GH_Component` → 404.

The root cause of all three: agents assume GH SDK types are in the RhinoCommon API docs, or
that the GH API follows the same URL scheme as the RhinoCommon API. Neither is true.

---

## See Also

- `[[search-discourse.md]]` — when dev guides come up empty or the surface is volatile
  (post-build target behavior, NuGet package versions, threading changes between Rhino
  releases). The forum has the live ground-truth; the dev guide has the canonical reference.
