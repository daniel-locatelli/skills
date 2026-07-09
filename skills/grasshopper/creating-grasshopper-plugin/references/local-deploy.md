# Local Deploy for Development

## What Local Deploy Is

Local deploy is the build-copy-restart loop that gets your plugin into Grasshopper for testing during development. It is separate from Yak packaging (`yak build` / `yak push`), which is for distribution. Do not conflate the two.

The cycle:

1. `dotnet build`
2. Copy build output to `%APPDATA%\Grasshopper\Libraries\<PluginName>\`
3. Restart Rhino
4. Test in Grasshopper

---

## Deploy Target Path

Grasshopper scans `%APPDATA%\Grasshopper\Libraries\` at Rhino startup. Place your plugin in a subfolder named after your plugin to avoid file collisions with other plugins:

```
%APPDATA%\Grasshopper\Libraries\CurveUtils\
    CurveUtils.gha
    System.Text.Json.dll        (example dependency)
    SomeProjectRef.dll          (example project reference)
```

The subfolder is not required by Grasshopper (it scans recursively), but it keeps the Libraries directory clean and makes uninstalling trivial: delete the folder.

---

## Build Output Folder

The build output path depends on the target framework and configuration:

| Target | Output folder |
|---|---|
| Rhino 8 (`net7.0-windows`) | `bin\Debug\net7.0-windows\` |
| Rhino 8 (`net8.0-windows`) | `bin\Debug\net8.0-windows\` |
| Rhino 7 (`net48`) | `bin\Debug\net48\` |

The Rhino.Templates csproj uses `net7.0-windows` by default. If the csproj multi-targets, pick the output folder that matches your installed Rhino version.

Release builds use `bin\Release\<tfm>\` instead. For the dev loop, Debug is fine.

---

## Build + Deploy Commands (PowerShell)

```powershell
# Build
dotnet build CurveUtils.csproj -c Debug

# Deploy — copy entire output folder contents
$dest = "$env:APPDATA\Grasshopper\Libraries\CurveUtils"
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Force $dest | Out-Null }
Copy-Item -Path "bin\Debug\net7.0-windows\*" -Destination $dest -Recurse -Force
```

Adjust the source path if your target framework or configuration differs. For a solution with multiple projects, build the solution and copy from the plugin project's output folder.

---

## Restart Rhino

Grasshopper loads `.gha` assemblies once at Rhino startup. There is no hot-reload. After copying new files to the Libraries folder:

- **Close Rhino entirely** (not just the Grasshopper window).
- Reopen Rhino and launch Grasshopper.

Closing only the Grasshopper canvas does nothing — the assembly remains loaded in the Rhino process.

---

## Copy Everything, Not Just the .gha

The most common local-deploy failure: copying only the `.gha` and leaving its dependencies behind.

A plugin that references NuGet packages (beyond the Grasshopper/RhinoCommon SDK packages, which are already loaded by Rhino) or other project assemblies needs those DLLs next to the `.gha` at runtime. If they are missing, Grasshopper loads the component but the first `SolveInstance` call throws `System.IO.FileNotFoundException` or `System.TypeLoadException`.

**Always copy the full contents of the build output directory**, not just the `.gha` file. The `Copy-Item -Path "bin\Debug\net7.0-windows\*"` command above does this.

### What can be excluded

The build output may contain files that are not needed at runtime:

- `*.pdb` — debug symbols; harmless to include, not required.
- `*.deps.json`, `*.runtimeconfig.json` — .NET host files; not used by Grasshopper's loader but harmless.
- `ref\` subfolder — reference assemblies; not needed at runtime.

When in doubt, copy everything. The overhead is negligible.

---

## Template Auto-Copy vs. Manual Deploy

The Rhino.Templates csproj includes a post-build target that copies the `.gha` to `%APPDATA%\Grasshopper\Libraries\` after each build. See `[[component-lifecycle.md]]` (Post-Build Deploy section) for details.

This auto-copy has a limitation: it copies only the `.gha` file, not its dependencies. For a minimal plugin with no extra NuGet packages beyond the SDK, this is sufficient. For anything else, use the manual deploy commands above.

If you find the auto-copy and manual deploy conflicting (e.g., a bare `.gha` in the Libraries root and a full folder in a subfolder), either:

- Remove the post-build target from the csproj and rely on manual deploy, or
- Modify the post-build target to copy the full output directory to a subfolder.

---

## Common Failures

### Failure 1: FileNotFoundException on first solve

**Symptom:** Component appears in the Grasshopper palette (the `.gha` loaded), but wiring inputs and triggering a solve produces a red component with `FileNotFoundException` naming a dependency DLL.

**Cause:** Only the `.gha` was copied; its runtime dependencies were left in the build output folder.

**Fix:** Copy the entire build output directory contents to the deploy folder, not just the `.gha`.

### Failure 2: Old version still running after rebuild

**Symptom:** You rebuilt and recopied, but Grasshopper still runs the old behavior.

**Cause:** Rhino was not restarted. The old assembly is still loaded in memory.

**Fix:** Close Rhino entirely, not just the Grasshopper window. Reopen and test.

### Failure 3: Wrong target framework output

**Symptom:** The `.gha` does not appear in Grasshopper's palette at all, or Rhino logs a load error.

**Cause:** You copied from the wrong TFM output folder (e.g., `net48` output into a Rhino 8 install, or vice versa).

**Fix:** Check which Rhino version you are running and copy from the matching output folder. Rhino 8 expects `net7.0-windows` (or `net8.0-windows`); Rhino 7 expects `net48`.

---

## Cross-links

See also:
- `[[component-lifecycle.md]]` for the template's post-build auto-copy behavior and how to verify the `.gha` was produced.
- `[[yak-packaging.md]]` for distribution packaging — a separate concern from local deploy.
