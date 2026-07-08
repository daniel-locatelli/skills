# AI-Assisted Development & MCP for Revit

Two distinct things, don't conflate them:
- **Dev-time AI** — using an AI agent (Claude Code, etc.) to *write the add-in's C# code*. This whole
  skill exists to ground that: it counters the stale-training-data failures (`.NET 8`, `ForgeTypeId`,
  `ElementId.Value`, transaction/API-context discipline) that otherwise produce non-compiling code.
- **Runtime AI / MCP** — an AI agent *driving Revit live* through a Model Context Protocol server that
  exposes Revit operations as tools. This is the new, fast-moving frontier covered below.

## MCP for Revit — the landscape (2026/2027)

**Model Context Protocol (MCP)** lets an LLM client (Claude Desktop/Code, Cursor, Copilot, ChatGPT)
call well-defined *tools* over a standard protocol. For Revit it turns "the AI suggests a change" into
"the AI **executes** a change" with traceability — which is exactly what makes it usable in
professional BIM workflows (vs. copy-paste-from-chat).

- **Revit 2027 ships a built-in MCP server.** It runs in the background whenever a project is open;
  any MCP client connects via a one-time settings config. It exposes **live model data** (elements,
  parameters, geometry, spatial data, project metadata) — not exports or screenshots. Caveats that
  matter: it still **makes analytical mistakes** (e.g. misreading configurations), **burns context
  fast** on large models, and **requires professional review** of anything it produces.
- **Third-party Revit MCP servers (available now, Revit 2023–2027):**
  - `mcp-servers-for-revit/revit-mcp` — ~130+ tools, broad version support.
  - `LuDattilo/revit-mcp-server` — 80+ tools.
  - `Demolinator/revit-mcp-server` — pyRevit-based (~45 tools), works with any MCP client.
- **DevCon 2026 reference talk** — "Revit API + MCP: Build an AI Agent That Actually Works in
  Production BIM Workflows" (Enrique Meneses, APS YouTube). Demonstrates exposing Revit tools (grids,
  levels, walls, columns, structural framing) plus data extraction (quantifications, element counts,
  issue lists) and even Autodesk Construction Cloud access — with deterministic, auditable execution.
  Live demos: Claude auto-modeling a structural layout from a PDF plan; quantity extraction +
  visibility-graphics overrides by prompt; Claude+ACC listing projects/issues and generating reports.
  Companion: "MCP Workshop: Build a Production-Ready AI Agent with Autodesk APS."
- **Dev-time verification application:** beyond the runtime/agent uses above, `revit-mcp`'s arbitrary-C#
  execution can drive a closed build→run→read-back→iterate loop that verifies a plugin under development
  against the live model — see `mcp-verified-dev-loop.md`.

## Deploying & triaging the third-party `revit-mcp` family (it is NOT one add-in)

The popular `revit-mcp` server is **three separately-built, separately-deployed pieces** — a fact
the "install the revit-mcp add-in" framing hides, and the #1 source of wasted hours:

1. **`revit-mcp`** (Node/TypeScript) — the MCP server Claude Code launches via `.mcp.json`. This is
   the *only* piece that determines **which tools appear in `/mcp`**.
2. **`revit-mcp-plugin`** (in-Revit C# add-in, `IExternalApplication`) — the **socket listener/host**.
   Installed in `…\Addins\<year>\` + a `revit_mcp_plugin\` payload folder. It loads at Revit startup
   and you switch its **service On** from its ribbon Settings panel.
3. **`revit-mcp-commandset`** (a **separate** C# assembly, `RevitMCPCommandSet.dll`) — the **actual
   command implementations** (`create_line_based_element`, `get_current_view_info`, …). The host
   loads it **dynamically at runtime** from `…\Addins\<year>\revit_mcp_plugin\Commands\`.

> **Tools showing in `/mcp` does NOT mean Revit can execute them.** That only proves piece 1. The
> tool list lives in the Node server; execution needs pieces 2 and 3 present *and wired*. Triage by
> the **exact error string** the failing tool call returns:

| Error returned by the tool call | Which piece is broken | Fix |
|---|---|---|
| `connect to revit client failed` | Piece 2 not running — Revit closed, no document, listener service off, or `revit-mcp-plugin` not installed for this Revit version | Open a doc in the **right Revit version**, install `revit-mcp-plugin` into that version's `Addins`, switch the service On |
| `Method 'X' not found` | Pieces 1+2 fine; **piece 3 not registered** (the command set's commands aren't in `commandRegistry.json`) | Register/enable the command set — **no DLL rebuild needed** (see below) |
| (call succeeds) | All three wired | — |

**`commandRegistry.json` vs `command.json` — the trap behind "Method not found":** the host reads
**`…\revit_mcp_plugin\Commands\commandRegistry.json`** (a `FrameworkConfig`: a `commands[]` of
`{commandName, assemblyPath, enabled, supportedRevitVersions}`), resolving each `assemblyPath`
relative to the `Commands\` dir with a `{VERSION}` placeholder substituted. A freshly-built command
set ships its **own** `command.json` (a *catalog*, different schema) but leaves `commandRegistry.json`
**empty (`{"commands":[]}`)** — so every call is `Method not found` until the registry is populated.
Populate it via the plugin's **"Command Set Settings" ribbon UI** (it scans the command set and writes
the entries), or write `commandRegistry.json` directly. Either way the host re-reads it at
**service start**, so restart Revit (or restart the service) after editing. **This is config, not a
code/DLL problem** — the RED-baseline failure mode is an agent "fixing" a stale DLL or adding a
handler when the DLL was fine and only the registry was empty.

**The writable third-party path runs on Revit 2026 / .NET 8 today — not 2027.** `revit-mcp-plugin`
and `revit-mcp-commandset` ship build configs only up to **R25**, and Revit 2027's *built-in* MCP is
**read-only**. There is no .NET 10 / 2027 community build. To get a **writable** agent loop now, build
both for **2026**: add an `R26` configuration that is a copy of the `R25` one (2025 and 2026 are both
`net8.0-windows`; only `RevitVersion` changes) — the SDK-style csproj already keys NuGet versions and
the post-build deploy on `$(RevitVersion)`, so it installs into the 2026 `Addins\…\Commands\` folder
automatically. Both halves must reference the **same `RevitMCPSDK` major** (e.g. `2026.*`) or the
host's `IRevitCommand` type identity won't match across `Assembly.LoadFrom` and commands silently fail
to register.

**Building these command sets for 2026+ hits the `ElementId.IntegerValue` removal.** The community
command set still uses the pre-2024 `ElementId.IntegerValue` (Int32) in dozens of call sites; it no
longer exists (it's `ElementId.Value`, Int64). Lowest-diff migration: add one extension method and
replace `.IntegerValue` → `.GetIntegerValue()` everywhere — preserving the original `int` return type
so nothing downstream changes:

```csharp
public static class ElementIdCompat   // brought in via a global using
{
    public static int GetIntegerValue(this ElementId id) => (int)id.Value;
}
```

## How a Revit MCP server is architected (if you build one)

The server is a **thin façade over the Revit API** — it decouples the LLM from API specifics and
exposes a small, well-named tool surface (`get_elements`, `create_walls`, `set_parameter`,
`override_visibility`, …). The non-obvious, load-bearing constraint:

> **Every tool handler must execute inside Revit's valid API context** (main thread). The MCP transport
> (an HTTP/stdio listener) runs on a background thread, so each tool invocation must marshal the actual
> API work through an **`ExternalEvent`** (or the async-ExternalEvent pattern in `architecture.md`).
> This is the *same* discipline as a modeless dialog — the MCP listener is just another "outside the
> API context" caller.

So a Revit-MCP add-in composes three things this skill already covers:
1. An **`IExternalApplication`** that, on startup, spins up the MCP listener (an embedded server) and
   creates one or more `ExternalEvent`/`IExternalEventHandler` bridges.
2. **Tool handlers** that translate MCP tool-call args → Revit API calls, run inside the
   ExternalEvent's `Execute(uiapp)`, wrap edits in a `Transaction`, and return structured results
   (JSON-serializable DTOs) back to the agent.
3. A **Revit-agnostic core** (see `architecture.md`) doing the real logic, so the same tools can later
   be repackaged for headless **APS Design Automation**.

Determinism/safety practices for production MCP tools: validate and clamp inputs; make tools
**idempotent** (re-running must not duplicate elements); wrap edits in named transactions so the user
can undo; suppress warnings via `IFailuresPreprocessor` so no modal dialog blocks the agent; log every
tool call (audit trail); and **keep a human in the loop** for review — the models do make mistakes.

## Dev-time: getting better Revit code out of an AI agent

- **Ground the agent** with current API facts — this skill is exactly that. Community equivalents:
  custom GPTs ("Revit API Expert") grounded on the API docs, and the `revitapidocs.com` reference.
- **Verify version-sensitive APIs** every time (the table in `SKILL.md`): `ForgeTypeId`/`UnitTypeId`,
  `ElementId.Value`, `net8.0-windows`, `TransactionMode.Manual`. These are where ungrounded models
  most reliably emit broken code.
- **Inspect with RevitLookup** when generated code returns surprising results — confirm the actual
  element/parameter the agent assumed exists.

## Sources
- Revit 2027 built-in MCP server — blog.bimsmith.com "Revit 2027: What the Built-In MCP Server Actually Does in Practice".
- DevCon 2026 talk (APS YouTube, @autodeskplatformservices) "Revit API + MCP …" (Enrique Meneses).
- Open-source servers — github.com/mcp-servers-for-revit/revit-mcp, github.com/LuDattilo/revit-mcp-server, github.com/Demolinator/revit-mcp-server.
- API-context/ExternalEvent discipline — see `ui-and-interaction.md` and `architecture.md`; The Building Coder on valid API context.
