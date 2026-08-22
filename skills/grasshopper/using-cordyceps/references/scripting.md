# Cordyceps: scripting pitfalls

Measured findings for `gh_script` (C# / Python 3 script components) and `rhino_scene script`
(Rhino Python). Read before configuring a script component or driving Rhino Python.

## C# Script source: body-only *or* full file — but never `using` after a type

Two source forms are accepted by the GH 8 C# Script (`b6ba1144-02d6-4a2d-b53c-ec62e290eeb7`), both via
`gh_script set` and `gh_script configure` (verified 2026-08-21, Cordyceps 1.4.x, Rhino 8):

1. **Body only** — using directives, then bare statements; declared inputs/outputs are variables.
2. **Full file** — `// #! csharp`, usings, `public class Script_Instance : GH_ScriptInstance { private void
   RunScript(<typed inputs>, ref object <outputs>) {...} }` **plus any helper classes / namespaces after it**.
   Cordyceps re-derives the component's inputs from the `RunScript` signature on every `set` (dropping a
   parameter from the signature silently removes the input and its wire).

The silent-`<null>` failure mode is real but its cause is a **compile error the component swallows**:
any `using` directive that appears *after* a type declaration (CS1529) — e.g. when you concatenate a second
file that starts with its own usings — compiles to nothing: `out` = `""`, every output a single null, runtime
level "Blank", no message. Strip the usings of appended files (or put them all at the top). A wrong body form
or a missing symbol, by contrast, *does* show its errors in `out`.

Bisect recipe when outputs are null and `out` is empty: `gh_script set` a probe that only does
`report = "probe"` with the same signature → works? then append your helper code in chunks until it breaks.

## Other script gotchas

- **`gh_script configure` reports output types as "Generic Data"** in its response, even though it correctly applies the type hint to the live component (since v1.4.4). Trust the declared type, not the response label.
- **`gh_script configure` resets all wires.** Use `gh_script set` for code-only updates — it preserves wires for parameters whose names didn't change, and returns `lostConnections` for any that did, which is directly consumable by `gh_wire connect`.
- **`object` is rejected as a C# Script input type.** Use a concrete type from the upstream Type System guide.
- **Python 3 Script output type hints are item-access only, and a stale hint survives reconfigure.** Returning a list from a `Brep`-hinted output fails with `type conversion failed from PyObject to Brep`; `access: "list"` in `gh_script configure` is not honored. Worse, once a typed hint is set it sticks to the param — reconfiguring to hint-free does not clear it (even outputting `[]` keeps failing). Only deleting and re-adding the component clears it. Reliable shape: one item per typed output.
- **Custom Preview rejects untyped script outputs.** A hint-free (Generic Data) output wraps values in `GH_ObjectWrapper`, and Custom Preview fails with `Data conversion failed from Goo to Geometry` even when the wrapped value is a `Rhino.Geometry.Brep`. Give the script output a concrete geometry type hint (see previous bullet: one item per output) — then previews collect it fine; multiple wires into one `G` input merge as usual.
- **`rhino_scene script` returns `success:true` no matter what the script did.** It only queues the command string; it
  never sees the outcome. A *failing* `-_RunPythonScript` therefore parks a **modal error dialog** in Rhino — blocking the
  UI until a human dismisses it — while your tool call looks clean. (Cost: a `RhinoView.Visible` typo, an invisible modal,
  and a user who had to close it by hand.) Never read `success:true` as evidence the script ran: have the script write a
  witness file and test for it. Both forms work when the script is correct — inline `( … )` and `"<file.py>"`, and the call is **synchronous** (measured: a script sleeping 4s blocked the HTTP call for 4.2s), so on success the effect has already landed when the call returns — no polling needed. `Assert-CordycepsScript` in `cordyceps.psm1` wraps all of this.
