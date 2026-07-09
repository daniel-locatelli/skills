# Yak Packaging and Distribution

## What Yak Is

Yak is Rhino's official package manager. It lets plugin authors publish `.yak` packages to
the Rhino Package Server at `yak.rhino3d.com`, which is federated into the **PackageManager**
panel inside Rhino. End users install packages with one click — no manual file copying, no
restart (in most cases), no registry editing.

A `.yak` file is a ZIP archive containing your built `.gha` assembly, an icon, and a
`manifest.yml` describing the package. The Yak CLI builds that archive and pushes it.

**Canonical developer guide:**
- Overview: `https://developer.rhino3d.com/guides/yak/`
- Creating a Grasshopper plugin package: `https://developer.rhino3d.com/guides/yak/creating-a-grasshopper-plugin-package/`
- CLI reference: `https://developer.rhino3d.com/guides/yak/yak-cli-reference/`

---

## `manifest.yml`

Every Yak package requires a `manifest.yml` in the top-level directory of the build
folder — alongside your built `.gha` and icon. The canonical minimal manifest for a
Grasshopper plugin targeting Rhino 8 on Windows:

```yaml
---
name: curve-utils
version: 1.0.0
authors:
  - Your Name Here
description: >
  CurveUtils provides midpoint and other curve-analysis components
  for Grasshopper in Rhino 8.
url: https://github.com/your-org/curve-utils
icon: icon.png
keywords:
  - curve
  - geometry
  - grasshopper
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Lowercase, no spaces. Must be globally unique on the server. |
| `version` | string | Semantic versioning — `MAJOR.MINOR.PATCH`. |
| `authors` | list of strings | One entry per author. |
| `description` | string | Shown in the Package Manager UI. Block scalar (`>`) is fine for long text. |
| `url` | string | Project or support page. Cannot be empty. |
| `icon` | string | Filename of the icon file — almost always `icon.png`. |
| `keywords` | list of strings | Used for search. Minimum: one keyword. |

### Generating a skeleton manifest

Before hand-editing, run `yak spec` inside your build output folder. Yak inspects the
`.gha` assembly and auto-fills `name`, `version`, and `authors` from the assembly metadata.
Edit the generated file to add `description`, `url`, and `keywords`.

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" spec
```

This is the fastest way to avoid typos in the fields that must match the assembly.

---

## Icon Requirements

- **Format:** PNG only.
- **Shape:** Square. Non-square images are accepted by the CLI but display incorrectly in
  the Package Manager.
- **Dimensions:** Recommended 64×64 px. 128×128 is also widely used. Larger images are
  scaled down; tiny images look blurry at high DPI.
- **Background:** Transparent background is fine and preferred for dark/light theme
  compatibility.
- **Filename:** Must match the `icon` field in `manifest.yml`. Convention is `icon.png`.

Place the icon file in the same directory as the `.gha` and `manifest.yml` before running
`yak build`. This is the **package icon** (64×64) — distinct from the 24×24 component icons
embedded in the assembly. See `[[icons.md]]` for design rules and generation.

---

## `yak build`

Run from the directory that contains the built `.gha` and `manifest.yml` (typically the
project's `bin\Release\net7.0-windows\` folder after `dotnet build -c Release`):

```powershell
# Windows — Rhino 8 installs Yak.exe here by default
& "C:\Program Files\Rhino 8\System\Yak.exe" build
```

For a platform-specific package (Rhino 8, Windows only — which is the expected case for
`net7.0-windows` compiled `.gha` files):

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" build --platform win
```

**Output:** A `.yak` file with a distribution tag appended to the filename, for example:

```
curve-utils-1.0.0-rh8-win.yak
```

The distribution tag (e.g. `rh8-win`) is inferred by Yak from the assembly's referenced
RhinoCommon / Grasshopper NuGet versions. You do not specify it manually; it is appended
automatically. Inspect the filename after the build to confirm the tag is what you expect.

**Verify:** Yak produces exit code 0 on success. If `manifest.yml` has missing fields or
the icon file is absent, the build fails with a descriptive error.

---

## `yak push`

Uploads the built `.yak` file to the Rhino Package Server.

**This is a public, destructive operation.** Once pushed, a given `name@version` cannot be
overwritten — only yanked (made invisible to new installs, but still fetchable by existing
users). Only run `yak push` when you intend to make the package available to all Rhino users.

### Step 1 — Log in (once per machine)

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" login
```

This opens a browser window to authenticate with your Rhino account. Credentials are stored
locally; you will not need to log in again until the token expires.

**CI / automation:** Set the `YAK_TOKEN` environment variable to a non-expiring API key
(obtained via `yak login --ci`). The CLI reads the token from the environment automatically.

### Step 2 — Push

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" push curve-utils-1.0.0-rh8-win.yak
```

Supply the exact filename produced by `yak build`. Do not glob or abbreviate — different
distribution tags are separate packages on the server.

To push to a private repository instead of the public server:

```powershell
& "C:\Program Files\Rhino 8\System\Yak.exe" push --source=https://your.server.com curve-utils-1.0.0-rh8-win.yak
```

---

## Versioning

Three version strings must stay in sync at release time:

| File | Field | Example |
|---|---|---|
| `manifest.yml` | `version` | `1.0.0` |
| Assembly attribute / `.csproj` | `<Version>` or `[assembly: AssemblyVersion]` | `1.0.0` |
| Git tag | — | `v1.0.0` |

If these diverge, `yak spec` will generate a manifest version that does not match what you
intend to push, and the distribution tag Yak infers may point at the wrong Rhino target.

### Bumping rules (Grasshopper plugins)

| Change | Bump |
|---|---|
| Targeting a new major Rhino version (e.g. Rhino 8 → 9) | **MAJOR** |
| New components or new features in existing components | **MINOR** |
| Bug fixes, documentation-only changes, icon updates | **PATCH** |

**Pre-release versions** follow the SemVer pre-release convention and are excluded from
search results by default. Use `yak search --prerelease <name>` to find them. Append
`-beta.1`, `-rc.1`, etc. to the version string in `manifest.yml`.

---

## Common Failures

"Distribution is mechanically easy but full of 'fix this one field' gotchas."
(Spec note — plan Task 14.)

### Failure 1: Missing icon at build time

The `manifest.yml` declares `icon: icon.png` but the `icon.png` file is not in the build
output directory. `yak build` fails:

```
Error: icon 'icon.png' not found
```

**Fix:** Add a `<None Include="icon.png"><CopyToOutputDirectory>Always</CopyToOutputDirectory></None>`
item to your `.csproj`, or manually copy the icon before running `yak build`.

### Failure 2: Wrong Yak.exe path

On machines with multiple Rhino installs or a non-default install directory, the hardcoded
`C:\Program Files\Rhino 8\System\Yak.exe` path does not exist. The call fails silently
in some shells or throws `CommandNotFoundException`.

**Fix:** Verify the path first. Alternatively, add `C:\Program Files\Rhino 8\System\` to
`$env:PATH` so `yak` can be called without the full path.

### Failure 3: Version mismatch between manifest.yml and assembly

Yak reads the assembly metadata and the `manifest.yml` independently. If the csproj
`<Version>` is `1.0.0` but `manifest.yml` says `1.1.0`, the distribution tag is inferred
from the assembly (correct), but the published version string shown in the Package Manager
comes from `manifest.yml` (wrong). Users see version `1.1.0` but the code is `1.0.0`.

**Fix:** Always bump both `manifest.yml` and the csproj `<Version>` in the same commit.
Use `yak spec` to regenerate the manifest version from the assembly before each release.

### Failure 4: Account authentication required before push

Running `yak push` without logging in produces an authentication error. The error message
is clear, but agents that batch the build-and-push step will terminate early without
pushing.

**Fix:** Run `yak login` (interactive) or set `YAK_TOKEN` (CI) before calling `yak push`.

### Failure 5: Wrong distribution tag blocks installation

Yak appends a distribution tag (`rh6_18`, `rh7_0`, `rh8_0`, etc.) based on the
RhinoCommon version the assembly was compiled against. If you compile against Rhino 8 SDK
NuGet packages but try to use the resulting package on Rhino 7, it will not appear in the
Rhino 7 Package Manager — the tag filters it out. There is no workaround; you must rebuild
against the target SDK.

**The inverse is equally true:** a `rh6*`-tagged package is not installable in Rhino 7
(confirmed by the Yak dev guide). Each Rhino target requires a separate build-and-push.
For a Rhino 8 plugin compiled against `net7.0-windows`, the tag will be `rh8-win`.

### Failure 6: `name` field must be unique and lowercase

`name` in `manifest.yml` becomes the package's permanent identifier on the server. It must
be globally unique across all packages and must be lowercase with no spaces (use hyphens).

Attempting to push a package whose `name` collides with an existing package from a
different author fails with a permission error. Reserve the name early by doing a test push
with a pre-release version.

### Failure 7: Attempting to re-push an existing version

You cannot overwrite `name@version` on the server. Attempting to push `curve-utils@1.0.0`
a second time fails:

```
Error: version 1.0.0 already exists for curve-utils
```

**Fix:** Bump the version in `manifest.yml` and the csproj, rebuild, re-push.

---

## Cross-links

See also: `[[component-lifecycle.md]]` for assembly metadata (`GH_AssemblyInfo`, GUID,
`AssemblyVersion`) that must match the manifest and for the Rhino.Templates csproj
`<Version>` property that drives the `yak spec` output.
