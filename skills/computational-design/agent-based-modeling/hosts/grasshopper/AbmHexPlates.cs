// #! csharp
// Agent-based hexagonal plate tessellation of a doubly-curved surface.
// Grasshopper 8 C# Script component (full-file form, driven via Cordyceps gh_script set).
//
// This file is the Grasshopper ADAPTER only (RhinoCommon in/out). build-canvas.ps1 appends
// ../../core/AbmCore.cs (the portable core: Vec3, ISurfaceHost, Solver, Delaunay2D, TangentPlanePlates)
// before sending the combined source to the script component.
//
// References (see ../../references/sources.md): Groenewolt et al. 2018 (ABxM framework),
// Schwinn/Krieg/Menges 2014 (Landesgartenschau plate agents), Li/Liu/Wang 2015 (P-Hex / TPI, principal alignment),
// Wang/Liu/Pottmann 2008 (Dupin indicatrix, validity), Troche 2008 (tangent-plane intersection), Reynolds 1987 (boids).

#region Usings
using System;
using System.Linq;
using System.Collections;
using System.Collections.Generic;

using Rhino;
using Rhino.Geometry;

using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
#endregion

public class Script_Instance : GH_ScriptInstance
{
    private void RunScript(
        Surface srf,
        int count,
        int iterations,
        double spacing,
        double wSeparation,
        double wCohesion,
        double wCentroid,
        double wAlignment,
        double speed,
        bool hexLayout,
        double hexAngle,
        bool keepBoundary,
        int seed,
        ref object plates,
        ref object meshes,
        ref object agents,
        ref object normals,
        ref object e1,
        ref object gauss,
        ref object isConvex,
        ref object kClass,
        ref object report)
    {
        if (srf == null) { report = "no surface"; return; }
        if (count < 4) count = 4;
        if (iterations < 0) iterations = 0;

        var host = new RhinoSurfaceHost(srf);
        var p = new Abm.Parameters
        {
            Count = count,
            Iterations = iterations,
            Spacing = spacing,                 // <= 0: automatic from surface area and count
            SeparationWeight = wSeparation,
            CohesionWeight = wCohesion,
            CentroidWeight = wCentroid,
            AlignmentWeight = wAlignment,      // 12-fold alignment with the principal curvature directions (0 = off)
            Speed = speed > 0 ? speed : 0.2,
            InitialLayout = hexLayout ? Abm.Layout.Hexagonal : Abm.Layout.Random,
            HexAngle = hexAngle < 0 ? double.NaN : hexAngle,   // < 0: automatic (dominant principal direction)
            Seed = seed,
        };

        var solver = new Abm.Solver(host, p);
        solver.Run();
        var plateSet = Abm.TangentPlanePlates.Build(solver.Agents, host, p.Spacing);

        var platesOut = new List<Polyline>();
        var meshesOut = new List<Mesh>();
        var convexOut = new List<bool>();
        var classOut = new List<int>();
        var gaussOut = new List<double>();
        var agentsOut = new List<Point3d>();
        var normalsOut = new List<Vector3d>();
        var e1Out = new List<Vector3d>();
        foreach (var a in solver.Agents)
        {
            agentsOut.Add(ToRh(a.P));
            normalsOut.Add(new Vector3d(a.N.X, a.N.Y, a.N.Z));
            e1Out.Add(new Vector3d(a.E1.X, a.E1.Y, a.E1.Z) * a.Anisotropy);   // principal direction scaled by how well-defined it is
        }
        int boundaryPlates = plateSet.Plates.Count(x => x.TouchesBoundary);
        // Normative order (algorithm.md 3): build -> drop boundary plates -> classify. Classify takes max|K| over
        // whatever is still in the set, so the drop must happen before the first Classify call, not inside the loop.
        if (!keepBoundary) plateSet.Plates.RemoveAll(x => x.TouchesBoundary);   // dual to hull triangles: unbounded/arbitrary
        foreach (var plate in plateSet.Plates)
        {
            var pl = new Polyline(plate.Vertices.Select(ToRh));
            pl.Add(pl[0]); // close
            platesOut.Add(pl);
            var m = Mesh.CreateFromClosedPolyline(pl);   // planar by construction; handles non-convex (bow-tie) outlines
            meshesOut.Add(m ?? new Mesh());
            convexOut.Add(plate.IsConvex);
            var cls = plateSet.Classify(plate);
            classOut.Add((int)cls);   // 0 elliptic, 1 parabolic band, 2 hyperbolic
            gaussOut.Add(plate.GaussianCurvature);
        }
        var t = plateSet.Tally();
        int alignPairs; double alignMean = Abm.Metrics.AlignmentMean(solver.Agents, out alignPairs);

        plates = platesOut;
        meshes = meshesOut;
        agents = agentsOut;
        normals = normalsOut;
        e1 = e1Out;
        gauss = gaussOut;
        isConvex = convexOut;
        kClass = classOut;
        var sides = plateSet.Plates.GroupBy(x => x.Vertices.Count).OrderBy(g => g.Key).Select(g => g.Key + ":" + g.Count());
        var topo = host.Topology;
        string topoLine = topo.IsClosedSurface
            ? string.Format("closed surface: plates={0} of {1} agents, Euler V-E+F={2} (2 for a sphere), pentagons-heptagons={3} (12 for a sphere)", plateSet.Plates.Count, solver.Agents.Count, plateSet.Triangles.Count - plateSet.Triangles.Count * 3 / 2 + plateSet.Plates.Count,
                plateSet.Plates.Count(x => x.Vertices.Count == 5) - plateSet.Plates.Count(x => x.Vertices.Count == 7))
            : (topo.IsNonTrivial ? "surface with seam/pole (uv-free triangulation)" : "open patch");
        report = string.Format(
            "agents={0} spacing={1:0.###} seedAngle={17:0.#} iterations={2} converged={3} maxDisp={4:0.####}\n" +
            "plates={5} (+{6} boundary plates, {7}) tpiFallbacks={8} edgeFlips={9} sides=[{10}]\n" +
            "elliptic K>0: convex={11} concave={12}\nhyperbolic K<0: convex={13} concave={14}\nparabolic band: convex={15} concave={16}\n" +
            "side ratio (min/max, median / p10): elliptic {18} hyperbolic {19}\nalignment mean cos(12phi)={21:0.00} over {22} pairs\n{20}",
            solver.Agents.Count, p.Spacing, solver.IterationsRun, solver.Converged, solver.LastMaxDisplacement,
            platesOut.Count, boundaryPlates, keepBoundary ? "kept" : "dropped", plateSet.FallbackCount, plateSet.EdgeFlips, string.Join(" ", sides),
            t[0, 1], t[0, 0], t[2, 1], t[2, 0], t[1, 1], t[1, 0],
            solver.SeedAngle, Ratios(plateSet, Abm.CurvatureClass.Elliptic), Ratios(plateSet, Abm.CurvatureClass.Hyperbolic), topoLine,
            alignMean, alignPairs);
    }

    private static Point3d ToRh(Abm.Vec3 v) => new Point3d(v.X, v.Y, v.Z);

    /// <summary>Side-ratio order statistics, taken from the core so that this host and the .NET harness report the
    /// same population and the same nearest-rank convention (algorithm.md 4). Boundary plates are already out of the
    /// set by the time this runs, so the class threshold matches too.</summary>
    private static string Ratios(Abm.PlateSet set, Abm.CurvatureClass c)
    {
        var st = Abm.Metrics.SideRatios(set, c, 0.1, true);
        if (st.Count == 0) return "-";
        return st.Median.ToString("0.00") + " / " + st.P10.ToString("0.00") + " (n=" + st.Count + ")";
    }
}

/// <summary>RhinoCommon implementation of the host-agnostic surface interface (+ exact principal curvatures).</summary>
public class RhinoSurfaceHost : Abm.ISurfaceHost, Abm.IPrincipalCurvatureHost
{
    private readonly Surface _s;
    public RhinoSurfaceHost(Surface s) { _s = s; }

    public void Domain(out double u0, out double u1, out double v0, out double v1)
    {
        var du = _s.Domain(0); var dv = _s.Domain(1);
        u0 = du.T0; u1 = du.T1; v0 = dv.T0; v1 = dv.T1;
    }

    /// <summary>Seams (IsClosed) and poles (IsSingular: 0 = south v0, 1 = east u1, 2 = north v1, 3 = west u0).</summary>
    public Abm.SurfaceTopology Topology => new Abm.SurfaceTopology
    {
        ClosedU = _s.IsClosed(0), ClosedV = _s.IsClosed(1),
        SingularV0 = _s.IsSingular(0), SingularU1 = _s.IsSingular(1), SingularV1 = _s.IsSingular(2), SingularU0 = _s.IsSingular(3),
    };

    public Abm.Vec3 PointAt(double u, double v)
    {
        var p = _s.PointAt(u, v);
        return new Abm.Vec3(p.X, p.Y, p.Z);
    }

    public Abm.Vec3 NormalAt(double u, double v)
    {
        var n = _s.NormalAt(u, v); n.Unitize();
        return new Abm.Vec3(n.X, n.Y, n.Z);
    }

    public double GaussianAt(double u, double v)
    {
        var c = _s.CurvatureAt(u, v);
        return c == null ? 0.0 : c.Gaussian;
    }

    public bool PrincipalAt(double u, double v, out double k1, out double k2, out Abm.Vec3 e1)
    {
        var c = _s.CurvatureAt(u, v);
        k1 = k2 = 0; e1 = new Abm.Vec3(0, 0, 0);
        if (c == null) return false;
        int i = Math.Abs(c.Kappa(0)) >= Math.Abs(c.Kappa(1)) ? 0 : 1;
        k1 = c.Kappa(i); k2 = c.Kappa(1 - i);
        var d = c.Direction(i); d.Unitize();
        e1 = new Abm.Vec3(d.X, d.Y, d.Z);
        return true;
    }

    public bool ClosestUV(Abm.Vec3 p, out double u, out double v)
    {
        return _s.ClosestPoint(new Point3d(p.X, p.Y, p.Z), out u, out v);
    }
}
