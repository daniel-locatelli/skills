// Portable core of the agent-based hexagonal-plate strategy. Plain C#: no host (Rhino/Revit/Unity) types.
// Hosts implement ISurfaceHost and call Solver + TangentPlanePlates. Port 1:1 to other languages for other hosts.
//
// Model (see ../references/algorithm.md for sources):
//   agent   = point on the base surface carrying the surface tangent plane (Schwinn/Krieg/Menges 2014)
//   step    = sum of behaviour vectors -> scale -> damp -> move -> re-project onto surface (Groenewolt et al. 2018 §3.2.5)
//   plates  = tangent-plane intersection on the Delaunay triangulation of the agents (Troche 2008); convex where K>0,
//             bow-tie where K<0 because TPI hexagons follow the Dupin indicatrix (Wang/Liu/Pottmann 2008; Li/Liu/Wang 2015)
using System;
using System.Linq;
using System.Collections.Generic;

namespace Abm
{
    public struct Vec3
    {
        public double X, Y, Z;
        public Vec3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static Vec3 operator +(Vec3 a, Vec3 b) => new Vec3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        public static Vec3 operator -(Vec3 a, Vec3 b) => new Vec3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static Vec3 operator *(Vec3 a, double s) => new Vec3(a.X * s, a.Y * s, a.Z * s);
        public static Vec3 operator *(double s, Vec3 a) => a * s;
        public static double Dot(Vec3 a, Vec3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        public static Vec3 Cross(Vec3 a, Vec3 b) => new Vec3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public Vec3 Unit() { var l = Length; return l > 1e-12 ? this * (1.0 / l) : new Vec3(0, 0, 0); }
        public static readonly Vec3 Zero = new Vec3(0, 0, 0);
        public override string ToString() => string.Format("({0:0.###},{1:0.###},{2:0.###})", X, Y, Z);
    }

    /// <summary>Topology of the uv domain. Open rectangular patches: all false (= <see cref="Open"/>).
    /// Closed = the two opposite edges are the same curve (seam, e.g. u of a cylinder/sphere/torus);
    /// Singular = the edge collapses to a point (pole of a sphere). Such edges are not boundaries: no containment
    /// there, and plates are built without uv (local tangent-plane triangulation), so the tessellation closes over them.</summary>
    public struct SurfaceTopology
    {
        public bool ClosedU, ClosedV;
        public bool SingularU0, SingularU1, SingularV0, SingularV1;
        public static readonly SurfaceTopology Open = new SurfaceTopology();
        public bool BoundaryU0 => !(ClosedU || SingularU0);
        public bool BoundaryU1 => !(ClosedU || SingularU1);
        public bool BoundaryV0 => !(ClosedV || SingularV0);
        public bool BoundaryV1 => !(ClosedV || SingularV1);
        /// <summary>True if any edge is a seam or a pole (uv is then not a chart of the whole surface).</summary>
        public bool IsNonTrivial => ClosedU || ClosedV || SingularU0 || SingularU1 || SingularV0 || SingularV1;
        /// <summary>True if the surface has no boundary at all (sphere, torus, closed tube).</summary>
        public bool IsClosedSurface => !BoundaryU0 && !BoundaryU1 && !BoundaryV0 && !BoundaryV1;
    }

    /// <summary>What the strategy needs from a host surface. Implement once per CAD/BIM host.</summary>
    public interface ISurfaceHost
    {
        void Domain(out double u0, out double u1, out double v0, out double v1);
        /// <summary>Seams and poles of the uv domain (see <see cref="SurfaceTopology"/>); return SurfaceTopology.Open for a plain patch.</summary>
        SurfaceTopology Topology { get; }
        Vec3 PointAt(double u, double v);
        Vec3 NormalAt(double u, double v);
        double GaussianAt(double u, double v);
        /// <summary>Parameters of the surface point closest to p (clamped to the domain for trimmed/finite patches).</summary>
        bool ClosestUV(Vec3 p, out double u, out double v);
    }

    /// <summary>Optional: hosts that can evaluate principal curvatures exactly (RhinoCommon SurfaceCurvature, analytic surfaces).
    /// Otherwise the core estimates them from PointAt/NormalAt by central differences (<see cref="SurfaceCurvature.Estimate"/>).</summary>
    public interface IPrincipalCurvatureHost
    {
        /// <summary>k1 = principal curvature of largest |k|, e1 = its unit direction (tangent), k2 the other one.</summary>
        bool PrincipalAt(double u, double v, out double k1, out double k2, out Vec3 e1);
    }

    /// <summary>Principal curvatures/directions from the shape operator, evaluated numerically (host-agnostic).</summary>
    public static class SurfaceCurvature
    {
        /// <summary>Central differences in uv: first fundamental form from Pu,Pv, second from -Pu·Nu etc.;
        /// shape operator S = I⁻¹·II, eigen-decomposed. Returns false near singular points (|Pu×Pv| ≈ 0).</summary>
        public static bool Estimate(ISurfaceHost host, double u, double v, out double k1, out double k2, out Vec3 e1)
        {
            double u0, u1, v0, v1; host.Domain(out u0, out u1, out v0, out v1);
            double hu = 1e-4 * (u1 - u0), hv = 1e-4 * (v1 - v0);
            var pu = (host.PointAt(u + hu, v) - host.PointAt(u - hu, v)) * (0.5 / hu);
            var pv = (host.PointAt(u, v + hv) - host.PointAt(u, v - hv)) * (0.5 / hv);
            var nu = (host.NormalAt(u + hu, v) - host.NormalAt(u - hu, v)) * (0.5 / hu);
            var nv = (host.NormalAt(u, v + hv) - host.NormalAt(u, v - hv)) * (0.5 / hv);
            double E = Vec3.Dot(pu, pu), F = Vec3.Dot(pu, pv), G = Vec3.Dot(pv, pv);
            double L = -Vec3.Dot(pu, nu), M = -0.5 * (Vec3.Dot(pu, nv) + Vec3.Dot(pv, nu)), N = -Vec3.Dot(pv, nv);
            double det = E * G - F * F;
            k1 = k2 = 0; e1 = Vec3.Zero;
            if (det <= 1e-18 * (E * G + 1e-300)) return false;
            // S = I^-1 II  (2x2, real eigenvalues)
            double s11 = (G * L - F * M) / det, s12 = (G * M - F * N) / det;
            double s21 = (E * M - F * L) / det, s22 = (E * N - F * M) / det;
            double tr = s11 + s22, dt = s11 * s22 - s12 * s21;
            double disc = Math.Max(0, tr * tr / 4 - dt);
            double sq = Math.Sqrt(disc);
            double ka = tr / 2 + sq, kb = tr / 2 - sq;
            if (Math.Abs(ka) < Math.Abs(kb)) { var tmp = ka; ka = kb; kb = tmp; }
            k1 = ka; k2 = kb;
            // eigenvector of ka: (S - ka I) x = 0
            double a, b;
            if (Math.Abs(s12) > 1e-14 || Math.Abs(s11 - ka) > 1e-14) { a = s12; b = ka - s11; }
            else { a = ka - s22; b = s21; }
            if (Math.Abs(a) < 1e-14 && Math.Abs(b) < 1e-14) { a = 1; b = 0; }   // umbilic: any direction
            e1 = (pu * a + pv * b).Unit();
            return true;
        }

        /// <summary>How well-defined the principal directions are: |k1-k2|/(|k1|+|k2|), 0 at umbilics (sphere), 1 on a saddle
        /// with k1 = -k2 or on a cylinder. Used to fade the alignment behaviour out where directions are meaningless.</summary>
        public static double Anisotropy(double k1, double k2)
        {
            double d = Math.Abs(k1) + Math.Abs(k2);
            return d < 1e-12 ? 0 : Math.Min(1, Math.Abs(k1 - k2) / d);
        }
    }

    public enum Layout { Random, Hexagonal }

    public class Parameters
    {
        public int Count = 100;
        public int Iterations = 500;
        /// <summary>Target centre-to-centre distance between neighbouring agents (≈ plate size).
        /// ≤ 0 = automatic: sqrt(area / (0.866 · Count)), the spacing of a hexagonal packing of Count agents on the surface.</summary>
        public double Spacing = 0;
        /// <summary>Separation: linear repulsion from neighbours closer than Spacing (Reynolds 1987 SEP; ABxM GradientSeparation).</summary>
        public double SeparationWeight = 1.0;
        /// <summary>Cohesion: weak pull toward neighbours between Spacing and the neighbour radius (closes voids; ABxM Attraction).</summary>
        public double CohesionWeight = 0.3;
        /// <summary>Centroid: pull each interior agent toward the centroid of its Delaunay neighbours (Laplacian smoothing;
        /// G18 "PC" / ABxM MoveToCentroid in spirit). Regularises the packing toward hexagons; one triangulation per iteration when > 0.</summary>
        public double CentroidWeight = 0.0;
        /// <summary>Containment: repel from the surface boundary so plates do not collapse onto it (S14 containment).</summary>
        public double ContainmentWeight = 1.0;
        /// <summary>Alignment: rotate each neighbour pair so that a lattice axis follows a principal curvature direction (12-fold field =
        /// hexagonal 60° symmetry × principal cross 90° symmetry; LLW15 §4.1 principal alignment; WLP08 Prop. 5: no edge along an asymptotic direction). TPI hexagons are symmetric (butterflies with a 2:1 side ratio
        /// where K&lt;0, affine-regular where K&gt;0) only when the hexagonal packing is aligned with the principal directions; a
        /// packing rotated by 15° gives 5:1 side ratios (kites). Faded by <see cref="SurfaceCurvature.Anisotropy"/>, so it is
        /// inactive on spheres/umbilics.</summary>
        public double AlignmentWeight = 0.3;
        /// <summary>Evaluate each agent's principal frame (K1, K2, E1, Anisotropy) on every placement, independently of
        /// <see cref="AlignmentWeight"/>. On by default: the alignment metric reads the frame, so gating it on the weight
        /// would make "alignment on vs off" unmeasurable. Turn it off only to save the curvature evaluation in a host that
        /// runs with the field off and does not report the metric.</summary>
        public bool EvaluatePrincipalFrame = true;
        /// <summary>Fraction of the summed behaviour vector applied per step (G18 §3.2.5 "global scaling factor").
        /// Positional (Cartesian) update, no velocity. Stable for ≲0.3 on a hexagonal packing; 0.2 is the default.</summary>
        public double Speed = 0.2;
        public int Seed = 1;
        /// <summary>Initial layout: Random (uniform in uv) or Hexagonal (jittered hex lattice in uv sized to Count;
        /// the relaxation then only has to fix the metric distortion, so valence defects are rare).</summary>
        public Layout InitialLayout = Layout.Random;
        /// <summary>Jitter of the hexagonal layout as a fraction of its lattice spacing.</summary>
        public double HexJitter = 0.15;
        /// <summary>Orientation of the hexagonal seed lattice in uv (degrees, neighbour direction from the u axis).
        /// NaN = automatic: the dominant principal curvature direction of the surface (anisotropy-weighted 12-fold mean, matching
        /// the alignment field's periodicity), so that
        /// plate edges avoid the asymptotic directions (WLP08 Prop. 5). An edge along an asymptotic direction gives a zero-length
        /// plate side; a lattice axis along a principal direction gives the symmetric 2:1 butterfly (side ratio 0.5).</summary>
        public double HexAngle = double.NaN;
        /// <summary>Neighbour search radius as a multiple of Spacing. 1.5 = first hexagonal ring only (second ring is at 1.73).</summary>
        public double NeighbourRadiusFactor = 1.5;
        /// <summary>Stop when the max displacement in a step falls below Spacing * this.</summary>
        public double ConvergenceFactor = 1e-3;
        /// <summary>Safety cap on per-step movement, as a fraction of Spacing (only active in the first chaotic iterations).</summary>
        public double MaxStepFactor = 0.5;
    }

    public class Agent
    {
        public int Index;
        public double U, V;
        public Vec3 P, N;
        public double K; // Gaussian curvature at P
        /// <summary>Principal curvatures (|K1| ≥ |K2|), direction of K1 (unit, tangent) and anisotropy in [0,1]; only
        /// evaluated when AlignmentWeight &gt; 0.</summary>
        public double K1, K2, Anisotropy;
        public Vec3 E1;
        public List<int> Neighbours = new List<int>();
    }

    /// <summary>
    /// Agent relaxation on a surface. Each iteration: behaviours -> one movement vector (summed, scaled,
    /// damped, projected to the tangent plane, capped) -> move -> re-project onto the surface.
    /// Synchronous update: all vectors are computed before any agent moves.
    /// </summary>
    public class Solver
    {
        public readonly List<Agent> Agents = new List<Agent>();
        public int IterationsRun { get; private set; }
        public double LastMaxDisplacement { get; private set; }
        public bool Converged { get; private set; }
        /// <summary>Index of the agent that moved most in the last iteration (diagnostics).</summary>
        public int LastMaxAgent { get; private set; }
        /// <summary>Optional per-iteration hook (iteration index) for tracing/animation. Null by default.</summary>
        public Action<int> OnIteration;

        private readonly ISurfaceHost _host;
        private readonly IPrincipalCurvatureHost _pc;
        private readonly Parameters _p;
        private readonly SurfaceTopology _topo;
        private double _u0, _u1, _v0, _v1;

        public Solver(ISurfaceHost host, Parameters p)
        {
            _host = host; _pc = host as IPrincipalCurvatureHost; _p = p;
            _topo = host.Topology;
            _host.Domain(out _u0, out _u1, out _v0, out _v1);
            if (_p.Spacing <= 0) _p.Spacing = Math.Sqrt(EstimateArea(host) / (0.8660254 * Math.Max(1, _p.Count)));
            Seed();
        }

        /// <summary>Surface area by summing bilinear patches on an n×n uv grid (host-agnostic).</summary>
        public static double EstimateArea(ISurfaceHost host, int n = 48)
        {
            double u0, u1, v0, v1; host.Domain(out u0, out u1, out v0, out v1);
            var pts = new Vec3[n + 1, n + 1];
            for (int i = 0; i <= n; i++) for (int j = 0; j <= n; j++)
                pts[i, j] = host.PointAt(u0 + (u1 - u0) * i / n, v0 + (v1 - v0) * j / n);
            double area = 0;
            for (int i = 0; i < n; i++) for (int j = 0; j < n; j++)
            {
                var a = pts[i, j]; var b = pts[i + 1, j]; var c = pts[i + 1, j + 1]; var d = pts[i, j + 1];
                area += 0.5 * Vec3.Cross(b - a, c - a).Length + 0.5 * Vec3.Cross(c - a, d - a).Length;
            }
            return area;
        }

        private void Seed()
        {
            var rnd = new Random(_p.Seed);
            if (_p.InitialLayout == Layout.Hexagonal && !_topo.IsNonTrivial)   // a uv lattice is meaningless across seams/poles
            {
                double du = _u1 - _u0, dv = _v1 - _v0;
                double d = Math.Sqrt(du * dv / (0.8660254 * Math.Max(1, _p.Count)));   // uv lattice spacing for ~Count points
                double ang = double.IsNaN(_p.HexAngle) ? DominantPrincipalAngle() : _p.HexAngle * Math.PI / 180;
                SeedAngle = ang * 180 / Math.PI;
                double ax = d * Math.Cos(ang), ay = d * Math.Sin(ang);
                double bx = d * Math.Cos(ang + Math.PI / 3), by = d * Math.Sin(ang + Math.PI / 3);
                double cu = (_u0 + _u1) / 2, cv = (_v0 + _v1) / 2, margin = 0.4 * d;
                int m = (int)Math.Ceiling(Math.Sqrt(du * du + dv * dv) / (2 * d * 0.8660254)) + 2;
                for (int i = -m; i <= m; i++) for (int j = -m; j <= m; j++)
                {
                    double u = cu + i * ax + j * bx, v = cv + i * ay + j * by;
                    if (u < _u0 + margin || u > _u1 - margin || v < _v0 + margin || v > _v1 - margin) continue;
                    var a = new Agent { Index = Agents.Count };
                    a.U = u + (rnd.NextDouble() - 0.5) * d * _p.HexJitter;
                    a.V = v + (rnd.NextDouble() - 0.5) * d * _p.HexJitter;
                    Place(a);
                    Agents.Add(a);
                }
                return;
            }
            // Random: uniform per unit *area* (rejection sampling on |Pu×Pv|), not per unit uv — uv is badly stretched at
            // poles and on any non-uniformly parametrised patch.
            double maxDa = 0; int g = 24;
            for (int i = 0; i <= g; i++) for (int j = 0; j <= g; j++)
                maxDa = Math.Max(maxDa, AreaElement(_u0 + (_u1 - _u0) * i / g, _v0 + (_v1 - _v0) * j / g));
            int guard = 0;
            while (Agents.Count < _p.Count && guard++ < _p.Count * 1000)
            {
                double u = _u0 + rnd.NextDouble() * (_u1 - _u0), v = _v0 + rnd.NextDouble() * (_v1 - _v0);
                if (maxDa > 0 && rnd.NextDouble() * maxDa > AreaElement(u, v)) continue;
                var a = new Agent { Index = Agents.Count, U = u, V = v };
                Place(a);
                Agents.Add(a);
            }
        }

        /// <summary>Orientation (degrees, in uv) actually used for the hexagonal seed lattice (diagnostics).</summary>
        public double SeedAngle { get; private set; } = double.NaN;

        /// <summary>Dominant principal direction of the surface as an angle in uv (radians, mod 30°): anisotropy-weighted
        /// circular mean of 12·angle over a uv grid (12-fold: invariant to the E1/E2 swap, see the alignment behaviour). Maps each E1 to parameter space by solving [E F; F G](α,β) = (E1·Pu, E1·Pv).</summary>
        private double DominantPrincipalAngle()
        {
            int g = 16; double sc = 0, ss = 0;
            for (int i = 0; i <= g; i++) for (int j = 0; j <= g; j++)
            {
                double u = _u0 + (_u1 - _u0) * (i + 0.5) / (g + 1), v = _v0 + (_v1 - _v0) * (j + 0.5) / (g + 1);
                double k1, k2; Vec3 e1;
                bool ok = _pc != null ? _pc.PrincipalAt(u, v, out k1, out k2, out e1) : SurfaceCurvature.Estimate(_host, u, v, out k1, out k2, out e1);
                if (!ok) continue;
                double w = SurfaceCurvature.Anisotropy(k1, k2) * (Math.Abs(k1) + Math.Abs(k2));
                if (w <= 0) continue;
                double hu = 1e-4 * (_u1 - _u0), hv = 1e-4 * (_v1 - _v0);
                var pu = (_host.PointAt(Math.Min(_u1, u + hu), v) - _host.PointAt(Math.Max(_u0, u - hu), v)) * (1.0 / (Math.Min(_u1, u + hu) - Math.Max(_u0, u - hu)));
                var pv = (_host.PointAt(u, Math.Min(_v1, v + hv)) - _host.PointAt(u, Math.Max(_v0, v - hv))) * (1.0 / (Math.Min(_v1, v + hv) - Math.Max(_v0, v - hv)));
                double E = Vec3.Dot(pu, pu), F = Vec3.Dot(pu, pv), G = Vec3.Dot(pv, pv), det = E * G - F * F;
                if (det < 1e-18) continue;
                double r1 = Vec3.Dot(e1, pu), r2 = Vec3.Dot(e1, pv);
                double al = (G * r1 - F * r2) / det, be = (E * r2 - F * r1) / det;   // uv-space direction of E1
                double th = Math.Atan2(be, al);
                sc += w * Math.Cos(12 * th); ss += w * Math.Sin(12 * th);
            }
            return (sc == 0 && ss == 0) ? 0 : Math.Atan2(ss, sc) / 12;
        }

        /// <summary>|Pu × Pv| by central differences (area per unit uv).</summary>
        private double AreaElement(double u, double v)
        {
            double hu = 1e-4 * (_u1 - _u0), hv = 1e-4 * (_v1 - _v0);
            double ua = Math.Max(_u0, u - hu), ub = Math.Min(_u1, u + hu), va = Math.Max(_v0, v - hv), vb = Math.Min(_v1, v + hv);
            var pu = (_host.PointAt(ub, v) - _host.PointAt(ua, v)) * (1.0 / (ub - ua));
            var pv = (_host.PointAt(u, vb) - _host.PointAt(u, va)) * (1.0 / (vb - va));
            return Vec3.Cross(pu, pv).Length;
        }

        private void Place(Agent a)
        {
            a.U = Clamp(a.U, _u0, _u1);
            a.V = Clamp(a.V, _v0, _v1);
            a.P = _host.PointAt(a.U, a.V);
            a.N = _host.NormalAt(a.U, a.V);
            a.K = _host.GaussianAt(a.U, a.V);
            // The principal frame is evaluated unconditionally, not only when the alignment field is on: the alignment
            // metric reads it, so gating it on AlignmentWeight would make the field's own before/after test impossible
            // (algorithm.md §4). Hosts that never need it can opt out with Parameters.EvaluatePrincipalFrame = false.
            if (_p.EvaluatePrincipalFrame)
            {
                double k1, k2; Vec3 e1;
                bool ok = _pc != null ? _pc.PrincipalAt(a.U, a.V, out k1, out k2, out e1)
                                      : SurfaceCurvature.Estimate(_host, a.U, a.V, out k1, out k2, out e1);
                if (ok)
                {
                    e1 = e1 - a.N * Vec3.Dot(e1, a.N);   // make sure it is tangent
                    a.K1 = k1; a.K2 = k2; a.E1 = e1.Unit(); a.Anisotropy = SurfaceCurvature.Anisotropy(k1, k2);
                }
                else { a.K1 = a.K2 = 0; a.E1 = Vec3.Zero; a.Anisotropy = 0; }
            }
        }

        public void Run()
        {
            double radius = _p.Spacing * _p.NeighbourRadiusFactor;
            double maxStep = _p.Spacing * _p.MaxStepFactor;
            double tol = _p.Spacing * _p.ConvergenceFactor;
            IterationsRun = 0; Converged = false;
            for (int it = 0; it < _p.Iterations; it++)
            {
                UpdateNeighbours(radius);
                Vec3?[] centroids = null;
                if (_p.CentroidWeight > 0) centroids = RingCentroids();
                var moves = new Vec3[Agents.Count];
                for (int i = 0; i < Agents.Count; i++)
                {
                    moves[i] = Behaviours(Agents[i], radius);
                    if (centroids != null && centroids[i].HasValue)
                        moves[i] += (centroids[i].Value - Agents[i].P) * _p.CentroidWeight;
                }

                double maxDisp = 0;
                for (int i = 0; i < Agents.Count; i++)
                {
                    var a = Agents[i];
                    var step = moves[i] * _p.Speed;                 // positional update (ABxM PolyAgent / Cartesian system)
                    step = step - a.N * Vec3.Dot(step, a.N);        // slide along the tangent plane
                    double l = step.Length;
                    if (l > maxStep) step = step * (maxStep / l);
                    var target = a.P + step;
                    double u, v;
                    if (_host.ClosestUV(target, out u, out v)) { a.U = u; a.V = v; }   // surface constraint
                    var old = a.P;
                    Place(a);
                    double disp = (a.P - old).Length;
                    if (disp > maxDisp) { maxDisp = disp; LastMaxAgent = i; }
                }
                IterationsRun = it + 1;
                LastMaxDisplacement = maxDisp;
                if (OnIteration != null) OnIteration(it);
                if (maxDisp < tol) { Converged = true; break; }
            }
            UpdateNeighbours(radius);
        }

        /// <summary>Centroid of the Delaunay 1-ring of each interior agent (null for hull agents). Bounded and continuous
        /// in the positions, unlike the centroid of a TPI plate (vertices jump at fallbacks) or of a hull Voronoi cell.</summary>
        private Vec3?[] RingCentroids()
        {
            var c = new Vec3?[Agents.Count];
            var set = TangentPlanePlates.Build(Agents, _host, _p.Spacing, useTpi: false);
            var ring = new Dictionary<int, HashSet<int>>();
            foreach (var pl in set.Plates) ring[pl.AgentIndex] = new HashSet<int>();
            foreach (var t in set.Triangles)
            {
                int[] v = { t.A, t.B, t.C };
                foreach (int i in v) { HashSet<int> r; if (ring.TryGetValue(i, out r)) foreach (int j in v) if (j != i) r.Add(j); }
            }
            foreach (var kv in ring)
            {
                if (kv.Value.Count < 3) continue;
                var sum = Vec3.Zero;
                foreach (int j in kv.Value) sum += Agents[j].P;
                c[kv.Key] = sum * (1.0 / kv.Value.Count);
            }
            return c;
        }

        private void UpdateNeighbours(double radius)
        {
            double r2 = radius * radius;
            foreach (var a in Agents) a.Neighbours.Clear();
            for (int i = 0; i < Agents.Count; i++)
                for (int j = i + 1; j < Agents.Count; j++)
                {
                    var d = Agents[i].P - Agents[j].P;
                    if (Vec3.Dot(d, d) <= r2) { Agents[i].Neighbours.Add(j); Agents[j].Neighbours.Add(i); }
                }
        }

        /// <summary>Sum of behaviour vectors for one agent (in model units). Add new behaviours here.
        /// Every term is continuous in distance and zero at its cutoff, so the synchronous update converges monotonically.</summary>
        private Vec3 Behaviours(Agent a, double radius)
        {
            double s = _p.Spacing;
            var sum = Vec3.Zero;
            foreach (int j in a.Neighbours)
            {
                var b = Agents[j];
                var d = a.P - b.P;
                double dist = d.Length;
                if (dist < 1e-9) { d = new Vec3(1e-3, 0, 0); dist = 1e-3; }
                var dir = d * (1.0 / dist);
                if (dist < s)
                    // Separation: linear spring, full strength (= s) at contact, zero at the target spacing.
                    sum += dir * ((s - dist) * _p.SeparationWeight);
                else
                    // Cohesion: pull toward neighbours beyond the target spacing; zero at s and again at the radius (continuous).
                    sum -= dir * ((dist - s) * (radius - dist) / (radius - s) * _p.CohesionWeight);

                // Alignment: 12-fold orientational field (hexagonal lattice, 60-periodic, against the principal cross field, 90-periodic:
                // lcm = 30 deg). phi = angle of the neighbour in a's tangent plane from E1; the pair is rotated (a moves sideways, b does
                // the same in its own frame) so that phi -> k*30 deg, i.e. a lattice axis along either principal direction; the asymptotic
                // directions of a symmetric saddle (45 deg off) are the maxima. 6-fold would make E1/E2 (which swap freely where |k1|=|k2|)
                // opposite targets. Potential -cos(12 phi) => sideways push ~ sin(12 phi); zero at the radius (continuous).
                if (_p.AlignmentWeight > 0 && a.Anisotropy > 0)
                {
                    var t = (b.P - a.P); t = t - a.N * Vec3.Dot(t, a.N);
                    double tl = t.Length;
                    if (tl > 1e-9)
                    {
                        var e2 = Vec3.Cross(a.N, a.E1);
                        double phi = Math.Atan2(Vec3.Dot(t, e2), Vec3.Dot(t, a.E1));
                        var perp = Vec3.Cross(a.N, t * (1.0 / tl));          // moving a along +perp decreases phi
                        double fall = Math.Max(0, 1 - dist / radius);
                        sum += perp * (_p.AlignmentWeight * s * a.Anisotropy * Math.Sin(12 * phi) * fall / 12);
                    }
                }
            }
            // Containment: every domain edge within half a spacing acts as a wall (all edges summed, so a corner
            // does not flip between two nearest edges from step to step).
            double reach = s * 0.5;
            foreach (var edge in BoundaryPoints(a))
            {
                var e = a.P - edge; double de = e.Length;
                if (de < reach && de > 1e-9)
                    sum += e * (1.0 / de) * ((reach - de) * _p.ContainmentWeight);
            }
            return sum;
        }

        /// <summary>Foot points on the domain edges that are real boundaries (not seams, not poles), evaluated on the surface.</summary>
        private IEnumerable<Vec3> BoundaryPoints(Agent a)
        {
            if (_topo.BoundaryU0) yield return _host.PointAt(_u0, a.V);
            if (_topo.BoundaryU1) yield return _host.PointAt(_u1, a.V);
            if (_topo.BoundaryV0) yield return _host.PointAt(a.U, _v0);
            if (_topo.BoundaryV1) yield return _host.PointAt(a.U, _v1);
        }

        private static double Clamp(double x, double lo, double hi) => x < lo ? lo : (x > hi ? hi : x);
    }

    /// <summary>Bowyer–Watson Delaunay triangulation in 2D (used in normalised uv space).</summary>
    public static class Delaunay2D
    {
        public struct Tri { public int A, B, C; public Tri(int a, int b, int c) { A = a; B = b; C = c; } }

        public static List<Tri> Triangulate(IList<double> xs, IList<double> ys)
        {
            int n = xs.Count;
            var px = new List<double>(xs); var py = new List<double>(ys);
            double minX = px.Min(), maxX = px.Max(), minY = py.Min(), maxY = py.Max();
            double dx = maxX - minX, dy = maxY - minY, dm = Math.Max(dx, dy) * 20 + 1;
            double mx = (minX + maxX) / 2, my = (minY + maxY) / 2;
            px.Add(mx - dm); py.Add(my - dm);
            px.Add(mx); py.Add(my + dm);
            px.Add(mx + dm); py.Add(my - dm);
            var tris = new List<Tri> { new Tri(n, n + 1, n + 2) };

            for (int i = 0; i < n; i++)
            {
                var bad = new List<int>();
                for (int t = 0; t < tris.Count; t++)
                    if (InCircumcircle(px, py, tris[t], px[i], py[i])) bad.Add(t);
                var edges = new List<KeyValuePair<int, int>>();
                foreach (int t in bad)
                {
                    var tr = tris[t];
                    edges.Add(new KeyValuePair<int, int>(tr.A, tr.B));
                    edges.Add(new KeyValuePair<int, int>(tr.B, tr.C));
                    edges.Add(new KeyValuePair<int, int>(tr.C, tr.A));
                }
                var boundary = edges.GroupBy(e => Key(e.Key, e.Value)).Where(g => g.Count() == 1).Select(g => g.First()).ToList();
                for (int k = bad.Count - 1; k >= 0; k--) tris.RemoveAt(bad[k]);
                foreach (var e in boundary) tris.Add(new Tri(e.Key, e.Value, i));
            }
            tris.RemoveAll(t => t.A >= n || t.B >= n || t.C >= n);
            for (int t = 0; t < tris.Count; t++)
            {
                var tr = tris[t];
                double cross = (px[tr.B] - px[tr.A]) * (py[tr.C] - py[tr.A]) - (py[tr.B] - py[tr.A]) * (px[tr.C] - px[tr.A]);
                if (cross < 0) tris[t] = new Tri(tr.A, tr.C, tr.B);
            }
            return tris;
        }

        public static long Key(int a, int b) => a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;

        private static bool InCircumcircle(List<double> px, List<double> py, Tri t, double x, double y)
        {
            double ax = px[t.A] - x, ay = py[t.A] - y;
            double bx = px[t.B] - x, by = py[t.B] - y;
            double cx = px[t.C] - x, cy = py[t.C] - y;
            double det = (ax * ax + ay * ay) * (bx * cy - cx * by)
                       - (bx * bx + by * by) * (ax * cy - cx * ay)
                       + (cx * cx + cy * cy) * (ax * by - bx * ay);
            double orient = (px[t.B] - px[t.A]) * (py[t.C] - py[t.A]) - (py[t.B] - py[t.A]) * (px[t.C] - px[t.A]);
            return orient > 0 ? det > 0 : det < 0;
        }
    }

    public class Plate
    {
        public int AgentIndex;
        public List<Vec3> Vertices = new List<Vec3>();
        public bool IsConvex;
        public double GaussianCurvature;
        /// <summary>True if any vertex of the plate is dual to a triangle that has a hull (boundary) agent or is ill-shaped
        /// (circumradius > 2·spacing, which only happens along the boundary): such plates are unbounded in reality and their
        /// TPI/Voronoi vertices are arbitrary (ABxM clips them against the surface boundary instead).</summary>
        public bool TouchesBoundary;
    }

    public enum CurvatureClass { Elliptic, Parabolic, Hyperbolic }

    public class PlateSet
    {
        public List<Plate> Plates = new List<Plate>();

        /// <summary>Classify a plate by its agent's Gaussian curvature relative to the strongest |K| in the set:
        /// |K| ≤ bandFraction·max|K| (default 10 %) counts as the parabolic band, where TPI degenerates and shapes are not meaningful.</summary>
        public CurvatureClass Classify(Plate p, double bandFraction = 0.1)
        {
            double kmax = 0; foreach (var q in Plates) kmax = Math.Max(kmax, Math.Abs(q.GaussianCurvature));
            if (Math.Abs(p.GaussianCurvature) <= bandFraction * kmax) return CurvatureClass.Parabolic;
            return p.GaussianCurvature > 0 ? CurvatureClass.Elliptic : CurvatureClass.Hyperbolic;
        }

        /// <summary>Counts [class][convex?1:0] for reporting: elliptic-convex, elliptic-concave, hyperbolic-convex, ... </summary>
        public int[,] Tally(double bandFraction = 0.1, bool includeBoundary = false)
        {
            var t = new int[3, 2];
            foreach (var p in Plates) if (includeBoundary || !p.TouchesBoundary) t[(int)Classify(p, bandFraction), p.IsConvex ? 1 : 0]++;
            return t;
        }
        /// <summary>Triangles whose TPI point was invalid (near-parallel planes / outside circumcircle) and got clamped.</summary>
        public int FallbackCount;
        public List<Delaunay2D.Tri> Triangles = new List<Delaunay2D.Tri>();
        /// <summary>One entry per triangle: the plate vertex dual to it, and whether it is a Voronoi fallback.</summary>
        public Vec3[] TriangleVertex = new Vec3[0];
        public bool[] TriangleIsFallback = new bool[0];
        /// <summary>Edges flipped after the uv-Delaunay to honour 3D distances (diagnostics).</summary>
        public int EdgeFlips;
    }

    /// <summary>Order statistics of a side-ratio population (raw nearest-rank, no interpolation — algorithm.md §4).</summary>
    public struct SideRatioStats
    {
        public int Count;
        public double Median, P10, Min;
    }

    /// <summary>
    /// The two headline metrics of algorithm.md §4, as a reference implementation. They are quoted to two decimals
    /// in §8, so their populations are part of the specification — and they are almost disjoint:
    /// the side ratio lives on plates outside the parabolic band, while alignment lives on the anisotropic agents,
    /// which concentrate *inside* it.
    /// </summary>
    public static class Metrics
    {
        /// <summary>Agents below this anisotropy are excluded from the alignment mean (their principal frame is arbitrary).</summary>
        public const double MinAnisotropy = 0.5;

        /// <summary>min(edge length) / max(edge length) of a plate's closed ring; 0 if the longest edge is zero.</summary>
        public static double SideRatio(Plate p)
        {
            int n = p.Vertices.Count;
            if (n < 2) return 0;
            double lo = double.MaxValue, hi = 0;
            for (int i = 0; i < n; i++)
            {
                double e = (p.Vertices[(i + 1) % n] - p.Vertices[i]).Length;
                if (e < lo) lo = e;
                if (e > hi) hi = e;
            }
            return hi > 0 ? lo / hi : 0;
        }

        /// <summary>
        /// Side-ratio order statistics for one curvature class. Population: the plates of <paramref name="set"/> that
        /// survive the boundary drop, classified per §3. The normative order is build → drop boundary plates from the
        /// set → classify, because <see cref="PlateSet.Classify"/> takes max|K| over whatever is still in the set;
        /// <paramref name="includeBoundary"/> only mirrors <see cref="PlateSet.Tally"/> for a caller that kept them.
        /// Ranks are raw nearest-rank on the ascending list (median = rs[n/2], p10 = rs[n/10], integer division).
        /// </summary>
        public static SideRatioStats SideRatios(PlateSet set, CurvatureClass cls, double bandFraction = 0.1, bool includeBoundary = false)
        {
            var rs = new List<double>();
            foreach (var p in set.Plates)
                if ((includeBoundary || !p.TouchesBoundary) && set.Classify(p, bandFraction) == cls) rs.Add(SideRatio(p));
            rs.Sort();
            var s = new SideRatioStats { Count = rs.Count };
            if (rs.Count > 0) { s.Median = rs[rs.Count / 2]; s.P10 = rs[rs.Count / 10]; s.Min = rs[0]; }
            return s;
        }

        /// <summary>
        /// mean(cos 12φ) over ordered agent→neighbour pairs, 1 = a lattice axis on a principal direction everywhere.
        /// Population: agents (not plates) with Anisotropy ≥ <paramref name="minAnisotropy"/>, each paired with every
        /// neighbour in its radius list — no boundary drop, no band exclusion. φ is measured in the *agent's* frame
        /// (E1, N × E1), the same convention the alignment behaviour uses. Requires a solver run (neighbour lists) and
        /// a populated principal frame. Returns 0 with pairs = 0 if the population is empty.
        /// </summary>
        public static double AlignmentMean(IList<Agent> agents, out int pairs, double minAnisotropy = MinAnisotropy)
        {
            double sum = 0; pairs = 0;
            foreach (var a in agents)
            {
                if (a.Anisotropy < minAnisotropy) continue;
                var e2 = Vec3.Cross(a.N, a.E1);
                foreach (int j in a.Neighbours)
                {
                    var t = agents[j].P - a.P; t = t - a.N * Vec3.Dot(t, a.N);
                    if (t.Length < 1e-9) continue;
                    double phi = Math.Atan2(Vec3.Dot(t, e2), Vec3.Dot(t, a.E1));
                    sum += Math.Cos(12 * phi); pairs++;
                }
            }
            return pairs > 0 ? sum / pairs : 0;
        }
    }

    /// <summary>
    /// Tangent-plane intersection (TPI) materialisation: Delaunay-triangulate the agents (in uv),
    /// replace every triangle by the point where its three agents' tangent planes meet, and read
    /// each interior agent's plate as the ring of those points around it. Plates are planar by
    /// construction. Where K &lt; 0 the ring folds over the agent and the polygon is non-convex (bow-tie).
    /// Degenerate TPI points (S14 rule): if the point projected onto the triangle's plane falls outside the
    /// triangle's circumcircle, the circumcentre (Voronoi vertex) is used instead — plates degrade to Voronoi cells there.
    /// </summary>
    public static class TangentPlanePlates
    {
        /// <param name="spacing">Nominal agent spacing; fallback vertices farther than 2*spacing from the triangle use its centroid
        /// (LLW15 §5.2) instead of the circumcentre so ill-shaped boundary triangles cannot throw vertices to infinity. 0 = no cap.</param>
        /// <param name="useTpi">true: tangent-plane intersection (materialisation); false: Voronoi dual (circumcentres),
        /// continuous in the agent positions and therefore the one to use inside the relaxation loop.</param>
        public static PlateSet Build(IList<Agent> agents, ISurfaceHost host, double spacing = 0, bool useTpi = true)
        {
            var result = new PlateSet();
            int n = agents.Count;
            if (n < 3) return result;

            List<Delaunay2D.Tri> tris;
            if (host.Topology.IsNonTrivial)
            {
                // uv is not a chart across seams/poles: triangulate from 3D neighbourhoods instead (no uv involved).
                tris = LocalTriangulate(agents, spacing > 0 ? 2.0 * spacing : 0);
                result.EdgeFlips = 0;
            }
            else
            {
                double u0, u1, v0, v1; host.Domain(out u0, out u1, out v0, out v1);
                var xs = agents.Select(a => (a.U - u0) / (u1 - u0)).ToList();
                var ys = agents.Select(a => (a.V - v0) / (v1 - v0)).ToList();
                tris = Delaunay2D.Triangulate(xs, ys);
                result.EdgeFlips = FlipToShortestDiagonal(tris, agents, xs, ys);   // Troche 2008 / S14: 3D edge flip by shortest Cartesian diagonal
            }
            result.Triangles = tris;

            var tpi = new Vec3[tris.Count];
            var isFb = new bool[tris.Count];
            var isIll = new bool[tris.Count];
            var incident = new List<int>[n];
            for (int i = 0; i < n; i++) incident[i] = new List<int>();
            for (int t = 0; t < tris.Count; t++)
            {
                var tr = tris[t];
                var a = agents[tr.A]; var b = agents[tr.B]; var c = agents[tr.C];
                Vec3 x = Vec3.Zero; bool ok = useTpi && IntersectPlanes(a.P, a.N, b.P, b.N, c.P, c.N, out x);
                var cc = Circumcentre(a.P, b.P, c.P);
                double R = (cc - a.P).Length;
                var centroid = (a.P + b.P + c.P) * (1.0 / 3.0);
                bool illShaped = spacing > 0 && R > 2 * spacing;    // near-collinear triangle: its circumcircle test is meaningless
                if (illShaped)
                {
                    cc = centroid;                                                       // bounded fallback (LLW15 centroid rule)
                    if (ok && (x - centroid).Length > 2 * spacing) ok = false;           // keep a bounded TPI point, drop a far one
                }
                else if (ok)
                {
                    // S14 validity: project x onto the triangle plane; outside the circumcircle → invalid
                    var tn = Vec3.Cross(b.P - a.P, c.P - a.P).Unit();
                    var xp = x - tn * Vec3.Dot(x - a.P, tn);
                    double dr = (xp - cc).Length;
                    if (dr > R) ok = false;   // degenerate (near-parabolic): fall back to the Voronoi vertex
                }
                if (!ok) x = cc;
                if (!ok) { result.FallbackCount++; isFb[t] = true; }
                isIll[t] = illShaped;
                tpi[t] = x;
                incident[tr.A].Add(t); incident[tr.B].Add(t); incident[tr.C].Add(t);
            }

            result.TriangleVertex = tpi; result.TriangleIsFallback = isFb;
            var edgeTris = new Dictionary<long, List<int>>();
            for (int t = 0; t < tris.Count; t++)
            {
                var tr = tris[t];
                AddEdgeTri(edgeTris, tr.A, tr.B, t); AddEdgeTri(edgeTris, tr.B, tr.C, t); AddEdgeTri(edgeTris, tr.C, tr.A, t);
            }

            var onHull = new bool[n];
            foreach (var kv in edgeTris)
                if (kv.Value.Count == 1) { onHull[(int)(kv.Key >> 32)] = true; onHull[(int)(kv.Key & 0xffffffff)] = true; }

            for (int i = 0; i < n; i++)
            {
                var fan = incident[i];
                if (fan.Count < 3) continue;
                bool interior = true;
                foreach (int t in fan)
                {
                    var tr = tris[t];
                    foreach (int j in new[] { tr.A, tr.B, tr.C })
                        if (j != i && edgeTris[Delaunay2D.Key(i, j)].Count != 2) { interior = false; break; }
                    if (!interior) break;
                }
                if (!interior) continue;

                // Combinatorial ring: walk the fan triangle-to-triangle around agent i (keeps a folded ring folded).
                var ring = WalkFan(i, fan, tris);
                if (ring == null) continue;
                var a = agents[i];
                var plate = new Plate { AgentIndex = i, GaussianCurvature = a.K };
                foreach (int t in ring)
                {
                    plate.Vertices.Add(tpi[t]);
                    var tr = tris[t];
                    if (onHull[tr.A] || onHull[tr.B] || onHull[tr.C] || isIll[t]) plate.TouchesBoundary = true;
                }
                plate.IsConvex = IsConvexPolygon(plate.Vertices, a.N, spacing);
                result.Plates.Add(plate);
            }
            return result;
        }

        /// <summary>
        /// Triangulation without uv (closed surfaces, seams, poles): every agent Delaunay-triangulates its 3D neighbourhood
        /// (within <paramref name="radius"/>, default 2·spacing = first and second ring) projected onto its own tangent plane and
        /// keeps the triangles incident to itself; a triangle is accepted when all three of its agents produced it (consistent
        /// restricted Delaunay). Triangles are CCW about the agents' normals. Inconsistent spots (rare after relaxation) become holes,
        /// i.e. their agents are treated like hull agents.
        /// </summary>
        public static List<Delaunay2D.Tri> LocalTriangulate(IList<Agent> agents, double radius)
        {
            int n = agents.Count;
            if (radius <= 0)
            {   // no spacing given: use 2 x median nearest-neighbour distance
                var nn = new List<double>();
                for (int i = 0; i < n; i++)
                {
                    double best = double.MaxValue;
                    for (int j = 0; j < n; j++) if (j != i) best = Math.Min(best, (agents[i].P - agents[j].P).Length);
                    nn.Add(best);
                }
                nn.Sort(); radius = 2.0 * nn[nn.Count / 2];
            }
            double r2 = radius * radius;
            var votes = new Dictionary<string, KeyValuePair<Delaunay2D.Tri, int>>();
            for (int i = 0; i < n; i++)
            {
                var a = agents[i];
                var local = new List<int> { i };
                for (int j = 0; j < n; j++)
                {
                    if (j == i) continue;
                    var d = agents[j].P - a.P;
                    if (Vec3.Dot(d, d) <= r2 && Vec3.Dot(agents[j].N, a.N) > 0) local.Add(j);   // same side only (thin tubes)
                }
                if (local.Count < 3) continue;
                var ex = Vec3.Cross(a.N, Math.Abs(a.N.X) < 0.9 ? new Vec3(1, 0, 0) : new Vec3(0, 1, 0)).Unit();
                var ey = Vec3.Cross(a.N, ex);
                var xs = new List<double>(); var ys = new List<double>();
                foreach (int j in local) { var d = agents[j].P - a.P; xs.Add(Vec3.Dot(d, ex)); ys.Add(Vec3.Dot(d, ey)); }
                foreach (var t in Delaunay2D.Triangulate(xs, ys))
                {
                    if (t.A != 0 && t.B != 0 && t.C != 0) continue;
                    var g = new Delaunay2D.Tri(local[t.A], local[t.B], local[t.C]);   // CCW about a.N (ex,ey,N right-handed)
                    int[] k = { g.A, g.B, g.C }; Array.Sort(k);
                    string key = k[0] + "," + k[1] + "," + k[2];
                    KeyValuePair<Delaunay2D.Tri, int> cur;
                    votes[key] = votes.TryGetValue(key, out cur) ? new KeyValuePair<Delaunay2D.Tri, int>(cur.Key, cur.Value + 1)
                                                                 : new KeyValuePair<Delaunay2D.Tri, int>(g, 1);
                }
            }
            var accepted = votes.Values.Where(v => v.Value == 3).Select(v => v.Key).ToList();
            FillSmallHoles(accepted, agents, 8);
            return accepted;
        }

        /// <summary>
        /// Where the three local triangulations disagree (near-cocircular quads: each agent's projection picks a different
        /// diagonal) no triangle is unanimous and a small hole remains. Fill every open loop of at most <paramref name="maxLoop"/>
        /// edges by ear clipping with the shortest 3D diagonal (the same criterion as the edge flip). Larger loops are real
        /// boundaries (open surfaces with a seam, e.g. a cylinder) and are left alone.
        /// </summary>
        public static int FillSmallHoles(List<Delaunay2D.Tri> tris, IList<Agent> agents, int maxLoop)
        {
            int added = 0;
            for (int round = 0; round < 4; round++)
            {
                var directed = new HashSet<long>();
                foreach (var t in tris) { directed.Add(DKey(t.A, t.B)); directed.Add(DKey(t.B, t.C)); directed.Add(DKey(t.C, t.A)); }
                var open = new Dictionary<int, int>();   // u -> v for directed edges whose reverse is missing (hole on the right)
                foreach (var t in tris)
                    foreach (var e in new[] { new[] { t.A, t.B }, new[] { t.B, t.C }, new[] { t.C, t.A } })
                        if (!directed.Contains(DKey(e[1], e[0]))) open[e[0]] = e[1];
                if (open.Count == 0) return added;
                var used = new HashSet<int>(); int addedThisRound = 0;
                foreach (var start in open.Keys.ToList())
                {
                    if (used.Contains(start)) continue;
                    var loop = new List<int>(); int cur = start; bool ok = true;
                    for (int g = 0; g <= maxLoop; g++)
                    {
                        loop.Add(cur);
                        int nx; if (!open.TryGetValue(cur, out nx)) { ok = false; break; }
                        cur = nx;
                        if (cur == start) break;
                        if (loop.Count > maxLoop) { ok = false; break; }
                    }
                    if (!ok || cur != start || loop.Count < 3) continue;
                    foreach (int v in loop) used.Add(v);
                    // The open edges run with the hole on their right; the hole polygon itself is their reverse (CCW about the normal).
                    loop.Reverse();
                    var poly = new List<int>(loop);
                    while (poly.Count > 3)
                    {
                        int best = -1; double bestLen = double.MaxValue;
                        for (int i = 0; i < poly.Count; i++)
                        {
                            int pv = poly[(i + poly.Count - 1) % poly.Count], nx = poly[(i + 1) % poly.Count];
                            double l = (agents[pv].P - agents[nx].P).Length;
                            if (l < bestLen) { bestLen = l; best = i; }
                        }
                        int a = poly[(best + poly.Count - 1) % poly.Count], b = poly[best], c = poly[(best + 1) % poly.Count];
                        tris.Add(new Delaunay2D.Tri(a, b, c)); added++; addedThisRound++;
                        poly.RemoveAt(best);
                    }
                    tris.Add(new Delaunay2D.Tri(poly[0], poly[1], poly[2])); added++; addedThisRound++;
                }
                if (addedThisRound == 0) return added;
            }
            return added;
        }

        private static long DKey(int a, int b) => ((long)a << 32) | (uint)b;

        /// <summary>
        /// uv-Delaunay is not 3D-Delaunay on a curved patch. Flip every interior edge whose opposite diagonal is shorter
        /// in 3D (S14: "edge flipping of the 3D mesh based on shortest Cartesian distance", after Troche 2008), as long
        /// as the flipped pair stays a valid (convex, CCW in uv) quad. Repeats until no edge flips (capped).
        /// </summary>
        public static int FlipToShortestDiagonal(List<Delaunay2D.Tri> tris, IList<Agent> agents, IList<double> xs, IList<double> ys)
        {
            int total = 0;
            for (int pass = 0; pass < 20; pass++)
            {
                var edgeTris = new Dictionary<long, List<int>>();
                for (int t = 0; t < tris.Count; t++)
                {
                    var tr = tris[t];
                    AddEdgeTri(edgeTris, tr.A, tr.B, t); AddEdgeTri(edgeTris, tr.B, tr.C, t); AddEdgeTri(edgeTris, tr.C, tr.A, t);
                }
                var touched = new HashSet<int>();
                int flips = 0;
                foreach (var kv in edgeTris)
                {
                    if (kv.Value.Count != 2) continue;
                    int t1 = kv.Value[0], t2 = kv.Value[1];
                    if (touched.Contains(t1) || touched.Contains(t2)) continue;
                    int a = (int)(kv.Key >> 32), b = (int)(kv.Key & 0xffffffff);
                    int c = Opposite(tris[t1], a, b), d = Opposite(tris[t2], a, b);
                    if ((agents[c].P - agents[d].P).Length >= (agents[a].P - agents[b].P).Length) continue;
                    // orientation of the two candidate triangles (c,d,?) in uv must both be CCW -> quad is convex
                    // candidate triangles: (a, c, d)? Determine by keeping orientation consistent with t1: t1 = (a,b,c) CCW-ordered somehow.
                    var n1 = new Delaunay2D.Tri(a, d, c); var n2 = new Delaunay2D.Tri(b, c, d);
                    if (Orient(n1, xs, ys) <= 0) n1 = new Delaunay2D.Tri(a, c, d);
                    if (Orient(n2, xs, ys) <= 0) n2 = new Delaunay2D.Tri(b, d, c);
                    if (Orient(n1, xs, ys) <= 0 || Orient(n2, xs, ys) <= 0) continue;   // non-convex quad in uv
                    // the two new triangles must lie on opposite sides of the new diagonal: a and b separated by line c-d
                    if (Side(c, d, a, xs, ys) * Side(c, d, b, xs, ys) >= 0) continue;
                    tris[t1] = n1; tris[t2] = n2; touched.Add(t1); touched.Add(t2); flips++;
                }
                total += flips;
                if (flips == 0) break;
            }
            return total;
        }

        private static int Opposite(Delaunay2D.Tri t, int a, int b) => t.A != a && t.A != b ? t.A : (t.B != a && t.B != b ? t.B : t.C);
        private static double Orient(Delaunay2D.Tri t, IList<double> xs, IList<double> ys)
            => (xs[t.B] - xs[t.A]) * (ys[t.C] - ys[t.A]) - (ys[t.B] - ys[t.A]) * (xs[t.C] - xs[t.A]);
        private static double Side(int p, int q, int r, IList<double> xs, IList<double> ys)
            => (xs[q] - xs[p]) * (ys[r] - ys[p]) - (ys[q] - ys[p]) * (xs[r] - xs[p]);

        /// <summary>Order the triangles around vertex i by shared edges (CCW, since triangles are CCW in uv).</summary>
        private static List<int> WalkFan(int i, List<int> fan, List<Delaunay2D.Tri> tris)
        {
            // For each triangle, find the vertex that follows i in CCW order ("next") and the one before ("prev").
            var byPrev = new Dictionary<int, int>(); // prev-vertex -> triangle
            var nextOf = new Dictionary<int, int>();  // triangle -> next-vertex
            foreach (int t in fan)
            {
                var tr = tris[t];
                int[] v = { tr.A, tr.B, tr.C };
                int k = Array.IndexOf(v, i);
                int next = v[(k + 1) % 3], prev = v[(k + 2) % 3];
                byPrev[prev] = t; nextOf[t] = next;
            }
            var ring = new List<int>();
            int cur = fan[0];
            for (int s = 0; s < fan.Count; s++)
            {
                ring.Add(cur);
                int nx = nextOf[cur];
                if (!byPrev.TryGetValue(nx, out cur)) return null; // broken ring (should not happen for interior)
            }
            return cur == fan[0] ? ring : null;
        }

        private static void AddEdgeTri(Dictionary<long, List<int>> map, int a, int b, int t)
        {
            long k = Delaunay2D.Key(a, b);
            List<int> l; if (!map.TryGetValue(k, out l)) { l = new List<int>(); map[k] = l; }
            l.Add(t);
        }

        /// <summary>Intersection of three planes (point, normal). False if near-parallel.</summary>
        public static bool IntersectPlanes(Vec3 p1, Vec3 n1, Vec3 p2, Vec3 n2, Vec3 p3, Vec3 n3, out Vec3 x)
        {
            double d1 = Vec3.Dot(n1, p1), d2 = Vec3.Dot(n2, p2), d3 = Vec3.Dot(n3, p3);
            var c23 = Vec3.Cross(n2, n3); var c31 = Vec3.Cross(n3, n1); var c12 = Vec3.Cross(n1, n2);
            double det = Vec3.Dot(n1, c23);
            if (Math.Abs(det) < 1e-9) { x = Vec3.Zero; return false; }
            x = (c23 * d1 + c31 * d2 + c12 * d3) * (1.0 / det);
            return true;
        }

        public static Vec3 Circumcentre(Vec3 a, Vec3 b, Vec3 c)
        {
            var ab = b - a; var ac = c - a;
            var abXac = Vec3.Cross(ab, ac);
            double denom = 2 * Vec3.Dot(abXac, abXac);
            if (denom < 1e-18) return (a + b + c) * (1.0 / 3.0);
            var toC = (Vec3.Cross(abXac, ab) * Vec3.Dot(ac, ac) + Vec3.Cross(ac, abXac) * Vec3.Dot(ab, ab)) * (1.0 / denom);
            return a + toC;
        }

        /// <summary>Relative tolerance for the convexity turn test; the absolute threshold is this times spacing squared.</summary>
        public const double ConvexityEps = 1e-12;

        /// <summary>
        /// Convexity of a near-planar polygon with plane normal n (algorithm.md §3.3): all consecutive turns have the
        /// same sign about n <b>and</b> the ring is simple. Once the turns agree in sign, the total turning is exactly
        /// 2*pi*k with k >= 1, and the ring is simple iff k = 1 — so a doubly-folded ring (pentagram, a hexagon walked
        /// twice) is rejected here although no single turn is out of line. Turns below <see cref="ConvexityEps"/>*spacing^2
        /// are read as noise and skipped, except a reversal (the ring doubling back on itself), which is never convex;
        /// a ring whose every turn was skipped is degenerate, not convex. Pass the nominal agent spacing so the
        /// threshold scales with the model's units; spacing 0 means unit scale.
        /// </summary>
        public static bool IsConvexPolygon(List<Vec3> v, Vec3 n, double spacing)
        {
            int m = v.Count; if (m < 3) return false;
            double eps = ConvexityEps * (spacing > 0 ? spacing * spacing : 1.0);
            int sign = 0; double turning = 0;
            for (int i = 0; i < m; i++)
            {
                var a = v[(i + 1) % m] - v[i];
                var b = v[(i + 2) % m] - v[(i + 1) % m];
                double dot = Vec3.Dot(a, b);
                double s = Vec3.Dot(Vec3.Cross(a, b), n);
                if (Math.Abs(s) < eps) { if (dot < 0) return false; continue; }
                int cur = s > 0 ? 1 : -1;
                if (sign == 0) sign = cur; else if (cur != sign) return false;
                turning += Math.Atan2(s, dot);
            }
            if (sign == 0) return false;                       // every turn skipped: collinear, not a plate
            return Math.Abs(turning) < 3 * Math.PI;            // turning is 2*pi*k, k >= 1; this is k == 1
        }
    }
}
