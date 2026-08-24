"""Render the harness JSON to PNGs. Usage: python render.py out.json out.png
Writes <out>.png (plan), <out>-axo.png (axonometric), <out>-plates.png (each K<0 plate seen along its own normal)."""
import json, sys, math, os
from PIL import Image, ImageDraw
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src)); L = d['L']; W = 900
GREEN, RED, GREY = (42, 157, 58), (214, 40, 40), (60, 60, 60)
# A boundary plate is DROPPED before every statistic is taken (algorithm.md 3), so drawing
# it like a survivor is drawing a plate nothing is measured over. It is still worth seeing
# -- what the drop took is exactly what a plan view is for -- so it goes in as a thin grey
# outline and stays out of the catalogues entirely. Hosts that emit no 'boundary' key are
# unaffected: everything reads as interior, which is what it did before.
edge = lambda p: p.get('boundary', False)

def plan(path):
    S = (W - 40) / L
    X = lambda x: (x + L / 2) * S + 20
    Y = lambda y: (L / 2 - y) * S + 20
    im = Image.new('RGB', (W, W), 'white'); dr = ImageDraw.Draw(im, 'RGBA')
    c = L / 80
    for i, j in d['kneg']:
        x = -L / 2 + L * (i + 0.5) / 80; y = -L / 2 + L * (j + 0.5) / 80
        dr.rectangle([X(x - c / 2), Y(y + c / 2), X(x + c / 2), Y(y - c / 2)], fill=(244, 230, 230, 255))
    ag = d['agents']
    for a, b, cc, fb in d.get('tris', []):
        if fb:
            dr.polygon([(X(ag[k][0]), Y(ag[k][1])) for k in (a, b, cc)], fill=(255, 200, 0, 70))
    for p in d['plates']:
        pts = [(X(v[0]), Y(v[1])) for v in p['v']]
        if edge(p):
            dr.line(pts + [pts[0]], fill=GREY + (70,))
            continue
        col = GREEN if p['convex'] else RED
        dr.polygon(pts, fill=col + (60,), outline=col + (255,))
    for a in ag:
        dr.ellipse([X(a[0]) - 2, Y(a[1]) - 2, X(a[0]) + 2, Y(a[1]) + 2], fill=GREY + (255,))
    im.save(path); print('wrote', path)

def axo(path):
    # view direction from (+x,-y,+z) corner; simple orthographic
    az, el = math.radians(-35), math.radians(35)
    cx, cy = math.cos(az), math.sin(az)
    def proj(v):
        x, y, z = v
        # rotate about z by az, then tilt
        xr = x * cx - y * cy; yr = x * cy + y * cx
        return xr, yr * math.sin(el) + z * math.cos(el), -yr * math.cos(el) + z * math.sin(el)
    items = []
    for p in d['plates']:
        if edge(p):
            continue
        pv = [proj(v) for v in p['v']]
        items.append((sum(q[2] for q in pv) / len(pv), pv, GREEN if p['convex'] else RED))
    xs = [q[0] for _, pv, _ in items for q in pv]; ys = [q[1] for _, pv, _ in items for q in pv]
    for a in d['agents']:
        q = proj(a); xs.append(q[0]); ys.append(q[1])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    S = (W - 40) / max(x1 - x0, y1 - y0)
    X = lambda x: (x - x0) * S + 20
    Y = lambda y: (y1 - y) * S + 20
    H = int((y1 - y0) * S + 40)
    im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im, 'RGBA')
    items.sort(key=lambda t: t[0])  # far (more negative depth toward viewer?) -> draw far first
    for _, pv, col in items:
        dr.polygon([(X(q[0]), Y(q[1])) for q in pv], fill=col + (110,), outline=col + (255,))
    for a in d['agents']:
        q = proj(a); dr.ellipse([X(q[0]) - 2, Y(q[1]) - 2, X(q[0]) + 2, Y(q[1]) + 2], fill=GREY + (255,))
    im.save(path); print('wrote', path)

def catalogue(path, which='kneg'):
    """Each plate drawn in its own tangent plane (u,v basis), one cell per plate."""
    plates = [p for p in d['plates'] if not edge(p) and (p['K'] < 0) == (which == 'kneg')]
    if not plates: return
    n = len(plates); cols = 10; rows = (n + cols - 1) // cols; cell = 90
    im = Image.new('RGB', (cols * cell, rows * cell), 'white'); dr = ImageDraw.Draw(im, 'RGBA')
    for idx, p in enumerate(plates):
        vs = p['v']; c = [sum(v[k] for v in vs) / len(vs) for k in range(3)]
        # plane basis from first two edges
        e1 = [vs[0][k] - c[k] for k in range(3)]; e2 = [vs[1][k] - c[k] for k in range(3)]
        nrm = [e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0]]
        ln = math.sqrt(sum(q*q for q in nrm)) or 1; nrm = [q/ln for q in nrm]
        l1 = math.sqrt(sum(q*q for q in e1)) or 1; u = [q/l1 for q in e1]
        v_ = [nrm[1]*u[2]-nrm[2]*u[1], nrm[2]*u[0]-nrm[0]*u[2], nrm[0]*u[1]-nrm[1]*u[0]]
        uv = [(sum((vv[k]-c[k])*u[k] for k in range(3)), sum((vv[k]-c[k])*v_[k] for k in range(3))) for vv in vs]
        r = max(math.hypot(a, b) for a, b in uv) or 1; s = (cell * 0.42) / r
        ox, oy = (idx % cols) * cell + cell / 2, (idx // cols) * cell + cell / 2
        pts = [(ox + a * s, oy - b * s) for a, b in uv]
        col = GREEN if p['convex'] else RED
        dr.polygon(pts, fill=col + (60,), outline=col + (255,))
        dr.text((ox - cell/2 + 3, oy - cell/2 + 2), f"{len(vs)}g K={p['K']:.2f}", fill=(0, 0, 0))
    im.save(path); print('wrote', path)

plan(dst)
base, ext = os.path.splitext(dst)
axo(base + '-axo' + ext)
catalogue(base + '-kneg' + ext, 'kneg')
catalogue(base + '-kpos' + ext, 'kpos')
