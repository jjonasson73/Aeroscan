"""Rendera modellen till preview/. Ingen CFD-data inblandad - allt kommer ur geometrin.

    python tools/render_views.py

Två bilder:
  preview/exposure.png         3/4-vy färgad efter hur rakt varje yta möter flödet
  preview/silhouette_delta.png frontarean baseline vs tunad position, med skillnaden

Exponeringsfärgen är cos(vinkeln mellan ytnormalen och flödet), alltså ren geometri.
Det är INTE ett CFD-tryckfält - men det är exakt den yta som bygger formmotståndet, så
den visar var motståndet uppstår och varför en flatare rygg hjälper.
"""
import pathlib
import subprocess
import sys

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

HERE = pathlib.Path(__file__).resolve().parent.parent
PREVIEW = HERE / 'preview'
FONTDIR = pathlib.Path('/usr/share/fonts/truetype/dejavu')
BG = (13, 16, 22)
INK, DIM = (230, 236, 243), (136, 148, 168)
HOT, COOL, ADD = (233, 84, 52), (94, 178, 206), (108, 214, 150)
STOPS = [(0.00, (26, 38, 66)), (0.35, (34, 120, 148)), (0.60, (86, 176, 128)),
         (0.80, (233, 186, 74)), (1.00, (233, 84, 52))]


def font(size, bold=False, mono=False):
    name = 'DejaVuSansMono.ttf' if mono else ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    p = FONTDIR / name
    return ImageFont.truetype(str(p), size) if p.exists() else ImageFont.load_default(size)


def ramp(t, stops=STOPS):
    t = np.clip(np.asarray(t, float), 0, 1)
    xs = np.array([s[0] for s in stops])
    cs = np.array([s[1] for s in stops], float)
    return np.stack([np.interp(t, xs, cs[:, k]) for k in range(3)], axis=-1)


def render(mesh, az, el, W, H, margin=0.08, light=(-0.4, -0.7, 0.6)):
    """Painter's algorithm: kulla baksidor, sortera på djup, rita bakifrån."""
    a, e = np.radians(az), np.radians(el)
    d = np.array([np.cos(a)*np.cos(e), np.sin(a)*np.cos(e), -np.sin(e)])
    r = np.cross(d, [0, 0, 1.0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)

    tri, n = mesh.vertices[mesh.faces], mesh.face_normals
    keep = (n @ d) < 0
    tri, n = tri[keep], n[keep]
    depth = tri.mean(axis=1) @ d

    P = np.stack([tri @ r, tri @ u], axis=-1)
    lo, hi = P.reshape(-1, 2).min(0), P.reshape(-1, 2).max(0)
    s = (1 - 2*margin) * min(W, H) / (hi - lo).max()
    P = P * s + (np.array([W, H])/2 - (lo + hi)/2 * s)
    P[:, :, 1] = H - P[:, :, 1]

    L = np.array(light, float); L /= np.linalg.norm(L)
    # flödet går +x, så ytor vars normal pekar mot -x möter vinden
    rgb = ramp(np.clip(-n[:, 0], 0, 1)) * (0.34 + 0.66*np.clip(n @ L, 0, 1))[:, None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    img = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(img)
    for i in np.argsort(depth)[::-1]:
        p = P[i]
        if (p.max(0) - p.min(0)).max() < 0.7:
            continue
        c = tuple(int(v) for v in rgb[i])
        dr.polygon([tuple(q) for q in p], fill=c, outline=c)
    return img


def silhouette(path):
    m = trimesh.load(path)
    t = m.vertices[m.faces][:, :, 1:]
    p = unary_union([Polygon(x) for x in t if Polygon(x).area > 1e-10])
    return p.intersection(box(-10, 0, 10, 10))


def exposure_view(full_stl, out):
    W, H = 1500, 1020
    img = render(trimesh.load(full_stl), az=28, el=16, W=W, H=H)
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((56, 44), "Var vinden träffar", font=font(38, bold=True), fill=INK)
    d.text((56, 94), "ytans vinkel mot flödet · geometri, inte CFD-tryck",
           font=font(21), fill=DIM)
    # färgskala
    x0, y1, bw, bh = 56, H - 74, 320, 18
    for i in range(bw):
        c = tuple(int(v) for v in ramp(i/(bw-1))[0]) if ramp(i/(bw-1)).ndim > 1 \
            else tuple(int(v) for v in ramp(i/(bw-1)))
        d.line([(x0+i, y1), (x0+i, y1+bh)], fill=c)
    d.text((x0, y1 - 30), "i lä", font=font(19), fill=DIM)
    d.text((x0 + bw - 96, y1 - 30), "rakt mot vinden", font=font(19), fill=DIM)
    img.save(out)
    return out


def silhouette_view(base_stl, tuned_stl, label, out):
    base, tuned = silhouette(base_stl), silhouette(tuned_stl)
    gone, added = base.difference(tuned), tuned.difference(base)
    W, H = 1180, 1420
    S, cx, y0 = 690, W/2, H - 300
    xy = lambda c: [(cx - y*S, y0 - z*S) for y, z in c]
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img, 'RGBA')

    def fill(g, col):
        for p in getattr(g, 'geoms', [g]):
            if p.is_empty:
                continue
            d.polygon(xy(p.exterior.coords), fill=col + (255,))
            for h in p.interiors:
                d.polygon(xy(h.coords), fill=BG + (255,))

    d.line([(70, y0), (W-70, y0)], fill=(48, 58, 76), width=2)
    fill(base, (48, 66, 96)); fill(tuned, COOL); fill(added, ADD); fill(gone, HOT)
    d.text((70, 54), "Frontarea sett uppströms", font=font(38, bold=True), fill=INK)
    d.text((70, 104), label, font=font(21), fill=DIM)

    rows = [(COOL, "tunad position", tuned.area), ((48, 66, 96), "baseline", base.area),
            (HOT, "försvinner", gone.area), (ADD, "tillkommer", added.area)]
    for i, (c, lab, v) in enumerate(rows):
        y = H - 238 + i*40
        d.rectangle([70, y, 100, y+26], fill=c + (255,))
        d.text((116, y+2), lab, font=font(21), fill=(206, 214, 226))
        d.text((300, y+2), f"{v:.4f} m²", font=font(21, mono=True), fill=INK)
    x = W - 430
    d.text((x, H-252), f"−{100*(base.area-tuned.area)/base.area:.2f} %",
           font=font(66, bold=True), fill=HOT)
    d.text((x+4, H-172), "frontarea", font=font(21), fill=DIM)
    img.save(out)
    return out


if __name__ == '__main__':
    PREVIEW.mkdir(exist_ok=True)
    geom = HERE / 'geometry' / 'rider_bike_full.stl'
    if not geom.exists():
        sys.exit(f'{geom} saknas - kör `python build_model.py` först.')
    print('skrev', exposure_view(geom, PREVIEW / 'exposure.png'))

    param, delta = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('pad_drop_mm', '-20')
    tmp = PREVIEW / '_tuned.stl'
    base = PREVIEW / '_base.stl'
    base.write_bytes(geom.read_bytes())
    subprocess.run([sys.executable, 'build_model.py', f'{param}={delta}'],
                   cwd=HERE, check=True, capture_output=True)
    tmp.write_bytes(geom.read_bytes())
    subprocess.run([sys.executable, 'build_model.py'], cwd=HERE, check=True, capture_output=True)
    print('skrev', silhouette_view(base, tmp,
                                   f"{param} = {delta} mm  ·  samma kropp, bara kontaktpunkten flyttad",
                                   PREVIEW / 'silhouette_delta.png'))
    base.unlink(); tmp.unlink()
