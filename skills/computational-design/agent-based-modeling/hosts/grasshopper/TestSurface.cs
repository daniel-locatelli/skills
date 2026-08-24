// #! csharp
// Test surface with both synclastic (K>0) and anticlastic (K<0) regions:
//   z = h * cos(w x) * cos(w y),  w = periods * pi / L,  on [-L/2, L/2]^2
// periods=1: dome in the centre, saddles toward the (steep) corners.
// periods=2: egg-crate: dome in the centre, valleys at the mid-edges, flat strongly anticlastic saddles at (+-L/4, +-L/4).
using System;
using System.Collections.Generic;
using Rhino.Geometry;
using Grasshopper.Kernel;

public class Script_Instance : GH_ScriptInstance
{
    private void RunScript(double L, double h, int n, int periods, ref object surface)
    {
        if (L <= 0) L = 20; if (h == 0) h = 5; if (n < 4) n = 12; if (periods < 1) periods = 1;
        double w = periods * Math.PI / L;
        var pts = new List<Point3d>();
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
            {
                double x = -L / 2 + L * i / (n - 1);
                double y = -L / 2 + L * j / (n - 1);
                double z = h * Math.Cos(w * x) * Math.Cos(w * y);
                pts.Add(new Point3d(x, y, z));
            }
        surface = NurbsSurface.CreateThroughPoints(pts, n, n, 3, 3, false, false);
    }
}
