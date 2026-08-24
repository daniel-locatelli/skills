# Console harness (host-agnostic)

```
dotnet run -c Release -- --h 3 --periods 2 --hex            # recommended test: egg-crate surface, hexagonal seed (auto angle)
dotnet run -c Release -- --h 3 --periods 2 --seed 3          # random seed (area-weighted), alignment on
dotnet run -c Release -- --surface sphere --R 10 --count 150 # closed surface: seam + poles, pentagons, Euler check
dotnet run -c Release -- --h 3 --periods 2 --hex --hexangle 0 --walign 0   # the "wrong" orientation (kites, side ratio ~0)
ABM_TRACE=1 dotnet run -- ...                                # per-50-iteration trace of the worst mover
ABM_PROBE=1 dotnet run -- ...                                # principal curvature probe for the first agents
python render.py out.json out.png                            # plan, out-axo.png, out-kneg.png / out-kpos.png catalogues
```
Flags: `--surface monge|sphere --L --h --periods --R --count --iterations --spacing (0=auto) --wsep --wcoh --wcont --wcen
--walign (0.3) --hexangle (NaN=auto) --speed --seed --hex --boundary --svg <file>`.
Report lines: `spacing/area/seedAngle`, convergence, plates + sides histogram, class tallies, mean neighbours,
**side ratio** per class (shortest/longest plate side: ideal aligned bow-tie 0.5, edge along an asymptotic direction 0),
TPI fallbacks per class, alignment quality (mean cos 12φ), closed-surface Euler line, numeric-vs-analytic K check.
Outputs: `<svg>` (editorial-style figure, diagram-design palette, fonts via Google Fonts @import; front hemisphere only for
closed surfaces), `<svg>.json` (agents, normals, e1·anisotropy, plates with agent index / boundary flag / convexity / K,
triangles with fallback flag, K<0 cells, closed flag).
PNG of the SVG without extra dependencies:
`chrome --headless=new --disable-gpu --hide-scrollbars --window-size=960,1040 --screenshot=figure.png file:///.../out.svg`
(the diagram-design skill uses Python Playwright for the same step; `pip install playwright` if you prefer that path).
