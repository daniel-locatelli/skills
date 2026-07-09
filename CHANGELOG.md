# Changelog

## 1.1.0 — 2026-07-09

Categories are now the host application, not the discipline: `skills/aec/` split into `skills/revit/` and `skills/grasshopper/`. The path now says which platform a skill targets even when its name doesn't — making room for upcoming skills like the MCP-driven test loops for Grasshopper and Revit. Skill names and content are unchanged; installs by skill name are unaffected.

## 1.0.0 — 2026-07-08

Initial consolidated release. Skills migrated from their standalone GitLab repos:

- `creating-revit-plugin` (renamed from `create-revit-plugin` to match the gerund naming of the other skills) — from [gitlab.com/daniellocatelli/creating-revit-plugin](https://gitlab.com/daniellocatelli/creating-revit-plugin). Covers Revit 2027 (.NET 10) and 2025/2026 (.NET 8); includes a buildable Revit 2027 scaffold in `template/`.
- `creating-grasshopper-plugin` — from [gitlab.com/daniellocatelli/creating-grasshopper-plugin](https://gitlab.com/daniellocatelli/creating-grasshopper-plugin) (was v1.0.0 there). Compiled `.gha` for Rhino 8.
