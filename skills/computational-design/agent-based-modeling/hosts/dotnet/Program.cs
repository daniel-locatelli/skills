// Host-agnostic test harness: runs the portable ABM core on an analytic Monge-patch surface
// z = h cos(pi x/L) cos(pi y/L) (dome in the centre, saddles toward the corners) and writes
// stats + an SVG top view (green = convex plate, red = concave plate, grey dots = agents).
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Globalization;
using System.Collections.Generic;
using Abm;

public class MongeSurfaceHost : ISurfaceHost
{
    readonly double L, h, w;   // z = h cos(w x) cos(w y), w = periods*pi/L. periods=1: dome + saddle corners; 2: egg-crate (domes, valleys, flat saddles)
    public MongeSurfaceHost(double L, double h, double periods = 1) { this.L = L; this.h = h; w = periods * Math.PI / L; }
    double F(double x, double y) => h * Math.Cos(w * x) * Math.Cos(w * y);
    double Fx(double x, double y) => -h * w * Math.Sin(w * x) * Math.Cos(w * y);
    double Fy(double x, double y) => -h * w * Math.Cos(w * x) * Math.Sin(w * y);
    double Fxx(double x, double y) => -h * w * w * Math.Cos(w * x) * Math.Cos(w * y);
    double Fyy(double x, double y) => Fxx(x, y);
    double Fxy(double x, double y) => h * w * w * Math.Sin(w * x) * Math.Sin(w * y);
    public void Domain(out double u0, out double u1, out double v0, out double v1) { u0 = -L / 2; u1 = L / 2; v0 = -L / 2; v1 = L / 2; }
    public SurfaceTopology Topology => SurfaceTopology.Open;
    public Vec3 PointAt(double u, double v) => new Vec3(u, v, F(u, v));
    public Vec3 NormalAt(double u, double v) => new Vec3(-Fx(u, v), -Fy(u, v), 1).Unit();
    public double GaussianAt(double u, double v)
    {
        double fx = Fx(u, v), fy = Fy(u, v);
        return (Fxx(u, v) * Fyy(u, v) - Fxy(u, v) * Fxy(u, v)) / Math.Pow(1 + fx * fx + fy * fy, 2);
    }
    public bool ClosestUV(Vec3 p, out double u, out double v) { u = Math.Clamp(p.X, -L / 2, L / 2); v = Math.Clamp(p.Y, -L / 2, L / 2); return true; }
}

/// <summary>Closed test surface: sphere of radius R, u = longitude [0, 2pi) (seam), v = latitude [-pi/2, pi/2] (poles).
/// Exercises SurfaceTopology (no containment, uv-free triangulation) and the 12 pentagons a closed hexagonal tessellation needs.</summary>
public class SphereHost : ISurfaceHost, IPrincipalCurvatureHost
{
    readonly double R;
    public SphereHost(double r) { R = r; }
    public void Domain(out double u0, out double u1, out double v0, out double v1) { u0 = 0; u1 = 2 * Math.PI; v0 = -Math.PI / 2; v1 = Math.PI / 2; }
    public SurfaceTopology Topology => new SurfaceTopology { ClosedU = true, SingularV0 = true, SingularV1 = true };
    public Vec3 PointAt(double u, double v) => new Vec3(R * Math.Cos(v) * Math.Cos(u), R * Math.Cos(v) * Math.Sin(u), R * Math.Sin(v));
    public Vec3 NormalAt(double u, double v) => PointAt(u, v).Unit();
    public double GaussianAt(double u, double v) => 1.0 / (R * R);
    public bool ClosestUV(Vec3 p, out double u, out double v)
    {
        double len = p.Length; if (len < 1e-12) { u = 0; v = 0; return false; }
        v = Math.Asin(Math.Clamp(p.Z / len, -1, 1)); u = Math.Atan2(p.Y, p.X); if (u < 0) u += 2 * Math.PI;
        return true;
    }
    public bool PrincipalAt(double u, double v, out double k1, out double k2, out Vec3 e1) { k1 = k2 = 1.0 / R; e1 = Vec3.Zero; return true; }   // umbilic everywhere
}

public static class Program
{
    static double Arg(string[] a, string k, double d) { int i = Array.IndexOf(a, "--" + k); return i >= 0 && i + 1 < a.Length ? double.Parse(a[i + 1], CultureInfo.InvariantCulture) : d; }
    public static int Main(string[] args)
    {
        double L = Arg(args, "L", 20), h = Arg(args, "h", 5), periods = Arg(args, "periods", 1), R = Arg(args, "R", 10);
        string surface = args.SkipWhile(s => s != "--surface").Skip(1).FirstOrDefault() ?? "monge";
        var p = new Parameters
        {
            Count = (int)Arg(args, "count", 150), Iterations = (int)Arg(args, "iterations", 1000),
            Spacing = Arg(args, "spacing", 0), SeparationWeight = Arg(args, "wsep", 1.0), CohesionWeight = Arg(args, "wcoh", 0.3),
            ContainmentWeight = Arg(args, "wcont", 1.0), CentroidWeight = Arg(args, "wcen", 0.0), AlignmentWeight = Arg(args, "walign", 0.3), HexAngle = Arg(args, "hexangle", double.NaN),
            InitialLayout = args.Contains("--hex") ? Layout.Hexagonal : Layout.Random, Speed = Arg(args, "speed", 0.2), Seed = (int)Arg(args, "seed", 1),
        };
        string svgPath = args.SkipWhile(s => s != "--svg").Skip(1).FirstOrDefault() ?? "out.svg";

        ISurfaceHost host = surface == "sphere" ? (ISurfaceHost)new SphereHost(R) : new MongeSurfaceHost(L, h, periods);
        if (surface == "sphere") L = 2.2 * R;   // plan-view extent for the figures
        var solver = new Solver(host, p);
        var sw = System.Diagnostics.Stopwatch.StartNew();
        if (Environment.GetEnvironmentVariable("ABM_TRACE") == "1")
            solver.OnIteration = it => { if (it % 50 == 49 || it < 5) { var m = solver.Agents[solver.LastMaxAgent]; Console.WriteLine($"  it={it + 1} maxDisp={solver.LastMaxDisplacement:0.####} agent={m.Index} P={m.P} N={m.N} K={m.K:0.###} nbrs={m.Neighbours.Count} dists=[{string.Join(",", m.Neighbours.Select(j => (solver.Agents[j].P - m.P).Length.ToString("0.##")))}]"); } };
        solver.Run();
        var plates = TangentPlanePlates.Build(solver.Agents, host, p.Spacing);
        sw.Stop();
        bool keepBoundary = args.Contains("--boundary");
        int boundaryPlates = plates.Plates.Count(x => x.TouchesBoundary);
        if (!keepBoundary) plates.Plates.RemoveAll(x => x.TouchesBoundary);

        var t = plates.Tally();
        var sides = plates.Plates.GroupBy(x => x.Vertices.Count).OrderBy(g => g.Key).Select(g => g.Key + ":" + g.Count());
        Console.WriteLine($"spacing={p.Spacing:0.###} area={Solver.EstimateArea(host):0.#} seedAngle={solver.SeedAngle:0.#}");
        Console.WriteLine($"agents={solver.Agents.Count} iterations={solver.IterationsRun} converged={solver.Converged} maxDisp={solver.LastMaxDisplacement:0.####} ms={sw.ElapsedMilliseconds}");
        Console.WriteLine($"plates={plates.Plates.Count} (+{boundaryPlates} boundary plates{(keepBoundary ? ", kept" : ", dropped; --boundary keeps them")}) tpiFallbacks={plates.FallbackCount} edgeFlips={plates.EdgeFlips} sides=[{string.Join(" ", sides)}]");
        Console.WriteLine($"elliptic(K>0): convex={t[0, 1]} concave={t[0, 0]}   hyperbolic(K<0): convex={t[2, 1]} concave={t[2, 0]}   parabolic band: convex={t[1, 1]} concave={t[1, 0]}");
        double nbrMean = solver.Agents.Average(a => a.Neighbours.Count);
        Console.WriteLine($"mean neighbours={nbrMean:0.00}");
        // Shape quality: min/max side ratio per plate (ideal TPI bow-tie on an aligned hex ring = 0.5; misaligned by 15 deg = 0.19).
        // Metric definitions live in the core (Abm.Metrics) so every host reports the same population; see algorithm.md 4.
        foreach (var cls in new[] { CurvatureClass.Elliptic, CurvatureClass.Hyperbolic })
        {
            var st = Metrics.SideRatios(plates, cls, includeBoundary: keepBoundary);
            if (st.Count > 0) Console.WriteLine($"side ratio {cls}: median={st.Median:0.00} p10={st.P10:0.00} min={st.Min:0.00} (n={st.Count})");
        }
        if (host.Topology.IsClosedSurface)
        {
            int V = plates.Triangles.Count, E2 = plates.Triangles.Count * 3, F = plates.Plates.Count;   // dual: V=tris, E=3T/2, F=plates
            int p5 = plates.Plates.Count(x => x.Vertices.Count == 5), p7 = plates.Plates.Count(x => x.Vertices.Count == 7);
            Console.WriteLine($"closed surface: plates={F} of {solver.Agents.Count} agents (all interior if equal), triangles={V}, Euler V-E+F={V - E2 / 2 + F} (2 for a sphere), pentagons-heptagons={p5 - p7} (12 for a sphere)");
        }
        // Diagnostics: where do the TPI fallbacks sit (by the curvature class of the triangle's agents), and how well is the
        // packing aligned with the principal directions (mean cos(12 phi) over neighbour pairs with anisotropy > 0.5; 1 = perfect).
        {
            double kmax = solver.Agents.Max(a => Math.Abs(a.K));
            int[] fbByClass = new int[3], triByClass = new int[3];
            for (int i = 0; i < plates.Triangles.Count; i++)
            {
                var tr = plates.Triangles[i];
                double km = (solver.Agents[tr.A].K + solver.Agents[tr.B].K + solver.Agents[tr.C].K) / 3;
                int c = Math.Abs(km) <= 0.1 * kmax ? 1 : (km > 0 ? 0 : 2);
                triByClass[c]++; if (plates.TriangleIsFallback[i]) fbByClass[c]++;
            }
            Console.WriteLine($"tpi fallbacks by class: elliptic {fbByClass[0]}/{triByClass[0]}  band {fbByClass[1]}/{triByClass[1]}  hyperbolic {fbByClass[2]}/{triByClass[2]}");
            int npairs; double amean = Metrics.AlignmentMean(solver.Agents, out npairs);
            if (npairs > 0) Console.WriteLine($"alignment: mean cos(12phi)={amean:0.00} over {npairs} pairs (anisotropy>=0.5)");
            if (Environment.GetEnvironmentVariable("ABM_PROBE") == "1")
                foreach (var a in solver.Agents.Take(6)) Console.WriteLine($"  probe agent {a.Index}: uv=({a.U:0.##},{a.V:0.##}) K={a.K:0.####} k1={a.K1:0.####} k2={a.K2:0.####} k1k2={a.K1 * a.K2:0.####} anis={a.Anisotropy:0.00} e1={a.E1}");
        }
        if (!(host is IPrincipalCurvatureHost))
        {
            double err = 0; foreach (var a in solver.Agents) { double k1, k2; Vec3 e1; if (SurfaceCurvature.Estimate(host, a.U, a.V, out k1, out k2, out e1)) err = Math.Max(err, Math.Abs(k1 * k2 - a.K)); }
            Console.WriteLine($"numeric K check: max |k1*k2 - K| = {err:0.#####}");
        }

        WriteSvg(svgPath, L, solver.Agents, plates, host);
        WriteJson(Path.ChangeExtension(svgPath, ".json"), L, solver.Agents, plates, host);
        Console.WriteLine("svg=" + Path.GetFullPath(svgPath));
        return 0;
    }

    static void WriteJson(string path, double L, List<Agent> agents, PlateSet plates, ISurfaceHost host)
    {
        var ci = CultureInfo.InvariantCulture; var sb = new StringBuilder();
        Func<Vec3, string> V = v => "[" + v.X.ToString("R", ci) + "," + v.Y.ToString("R", ci) + "," + v.Z.ToString("R", ci) + "]";
        sb.Append("{\"L\":" + L.ToString("R", ci) + ",\"agents\":[");
        sb.Append(string.Join(",", agents.Select(a => V(a.P))));
        sb.Append("],\"plates\":[");
        sb.Append(string.Join(",", plates.Plates.Select(p => "{\"a\":" + p.AgentIndex + ",\"boundary\":" + (p.TouchesBoundary ? "true" : "false") + ",\"convex\":" + (p.IsConvex ? "true" : "false") + ",\"K\":" + p.GaussianCurvature.ToString("R", ci) + ",\"v\":[" + string.Join(",", p.Vertices.Select(V)) + "]}")));
        sb.Append("],\"normals\":[");
        sb.Append(string.Join(",", agents.Select(a => V(a.N))));
        sb.Append("],\"e1\":[");
        sb.Append(string.Join(",", agents.Select(a => V(a.E1 * a.Anisotropy))));
        sb.Append("],\"closed\":" + (host.Topology.IsClosedSurface ? "true" : "false") + ",\"dummy\":[");
        sb.Append("],\"tris\":[");
        sb.Append(string.Join(",", plates.Triangles.Select((t, i) => "[" + t.A + "," + t.B + "," + t.C + "," + (plates.TriangleIsFallback[i] ? 1 : 0) + "]")));
        sb.Append("],\"kneg\":[");
        var cells = new List<string>();
        for (int i = 0; i < 80; i++) for (int j = 0; j < 80; j++)
        { double x = -L / 2 + L * (i + 0.5) / 80, y = -L / 2 + L * (j + 0.5) / 80; if (host is MongeSurfaceHost && host.GaussianAt(x, y) < 0) cells.Add("[" + i + "," + j + "]"); }
        sb.Append(string.Join(",", cells));
        sb.Append("]}");
        File.WriteAllText(path, sb.ToString());
    }

    /// <summary>Plan-view figure in the "editorial" style of the diagram-design skill: paper background, inline presentation
    /// attributes only (survives extraction), Geist/Instrument Serif via @import, muted ink for convex plates, one accent for
    /// concave plates, hairline parabolic band, legend strip. Export to PNG: chrome --headless=new --screenshot (see README).</summary>
    static void WriteSvg(string path, double L, List<Agent> agents, PlateSet plates, ISurfaceHost host)
    {
        var ci = CultureInfo.InvariantCulture;
        int W = 960, H = 1040, M = 40; double S = (W - 2 * M) / L;
        Func<double, string> X = x => ((x + L / 2) * S + M).ToString("0.#", ci);
        Func<double, string> Y = y => ((L / 2 - y) * S + M).ToString("0.#", ci);
        string ink = "#2d3142", muted = "#4f5d75", accent = "#eb6c36", paper = "#f5f5f5";
        var t = plates.Tally();
        var sb = new StringBuilder();
        sb.AppendLine($"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' width='{W}' height='{H}' role='img' aria-labelledby='abm-title abm-desc'>");
        sb.AppendLine("<title id='abm-title'>Agent-based hexagonal plates — plan</title>");
        sb.AppendLine($"<desc id='abm-desc'>{agents.Count} agents relaxed on z = h cos(wx) cos(wy); plates by tangent-plane intersection; convex plates muted, concave (bow-tie) plates in accent.</desc>");
        sb.AppendLine("<defs><style>@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&amp;family=Geist:wght@400;500;600&amp;family=Geist+Mono:wght@400;500;600&amp;display=swap');</style>");
        sb.AppendLine("<pattern id='dots' width='22' height='22' patternUnits='userSpaceOnUse'><circle cx='11' cy='11' r='0.9' fill='rgba(45,49,66,0.10)'/></pattern></defs>");
        sb.AppendLine($"<rect width='{W}' height='{H}' fill='{paper}'/>");
        sb.AppendLine($"<rect x='{M}' y='{M}' width='{W - 2 * M}' height='{W - 2 * M}' fill='url(#dots)' opacity='0.55'/>");
        sb.AppendLine($"<text x='{M}' y='24' font-family=\"'Geist Mono', monospace\" font-size='8' font-weight='500' letter-spacing='0.18em' fill='{muted}'>AGENT-BASED MODELING · TANGENT-PLANE INTERSECTION · PLAN</text>");
        // parabolic band: hairline contour of K=0 by sampling sign changes on a grid
        int g = 80; var neg = new bool[g, g];
        for (int i = 0; i < g; i++) for (int jj = 0; jj < g; jj++)
            neg[i, jj] = host is MongeSurfaceHost && host.GaussianAt(-L / 2 + L * (i + 0.5) / g, -L / 2 + L * (jj + 0.5) / g) < 0;
        for (int i = 0; i < g; i++) for (int jj = 0; jj < g; jj++)
        {
            double x = -L / 2 + L * (i + 0.5) / g, y = -L / 2 + L * (jj + 0.5) / g;
            if (neg[i, jj]) sb.AppendLine($"<rect x='{X(x - L / (2 * g))}' y='{Y(y + L / (2 * g))}' width='{(S * L / g).ToString("0.##", ci)}' height='{(S * L / g).ToString("0.##", ci)}' fill='rgba(45,49,66,0.04)'/>");
        }
        bool closed = host.Topology.IsClosedSurface;
        foreach (var pl in plates.Plates)
        {
            if (closed && agents[pl.AgentIndex].N.Z < 0) continue;   // plan of a closed surface: front hemisphere only
            var pts = string.Join(" ", pl.Vertices.Select(v => X(v.X) + "," + Y(v.Y)));
            if (pl.IsConvex) sb.AppendLine($"<polygon points='{pts}' fill='rgba(79,93,117,0.12)' stroke='{muted}' stroke-width='1' stroke-linejoin='round'/>");
            else sb.AppendLine($"<polygon points='{pts}' fill='rgba(235,108,54,0.15)' stroke='{accent}' stroke-width='1.2' stroke-linejoin='round'/>");
        }
        foreach (var a in agents) { if (closed && a.N.Z < 0) continue; sb.AppendLine($"<circle cx='{X(a.P.X)}' cy='{Y(a.P.Y)}' r='1.6' fill='{ink}'/>"); }
        // legend strip
        int ly = W + 12;
        sb.AppendLine($"<line x1='{M}' y1='{ly}' x2='{W - M}' y2='{ly}' stroke='rgba(45,49,66,0.12)' stroke-width='1'/>");
        sb.AppendLine($"<text x='{M}' y='{ly + 20}' font-family=\"'Geist Mono', monospace\" font-size='8' font-weight='500' letter-spacing='0.18em' fill='{muted}'>LEGEND</text>");
        sb.AppendLine($"<rect x='{M}' y='{ly + 30}' width='12' height='12' fill='rgba(79,93,117,0.12)' stroke='{muted}' stroke-width='1'/><text x='{M + 18}' y='{ly + 40}' font-family=\"Geist, sans-serif\" font-size='12' fill='{ink}'>convex plate (elliptic {t[0, 1]}, band {t[1, 1]})</text>");
        sb.AppendLine($"<rect x='{M + 300}' y='{ly + 30}' width='12' height='12' fill='rgba(235,108,54,0.15)' stroke='{accent}' stroke-width='1.2'/><text x='{M + 318}' y='{ly + 40}' font-family=\"Geist, sans-serif\" font-size='12' fill='{ink}'>concave / bow-tie plate (hyperbolic {t[2, 0]}, band {t[1, 0]})</text>");
        sb.AppendLine($"<rect x='{M + 660}' y='{ly + 30}' width='12' height='12' fill='rgba(45,49,66,0.04)' stroke='rgba(45,49,66,0.25)' stroke-width='0.8'/><text x='{M + 678}' y='{ly + 40}' font-family=\"Geist, sans-serif\" font-size='12' fill='{ink}'>K &lt; 0 region</text>");
        sb.AppendLine($"<text x='{M}' y='{ly + 64}' font-family=\"'Geist Mono', monospace\" font-size='9' fill='{muted}'>agents {agents.Count} · plates {plates.Plates.Count} · fallbacks {plates.FallbackCount} · flips {plates.EdgeFlips}</text>");
        sb.AppendLine("</svg>");
        File.WriteAllText(path, sb.ToString());
    }
}
