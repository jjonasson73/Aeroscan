import numpy as np, trimesh, json
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union
exec(open('build_model.py').read().split('# ---------- primitive helpers')[0])
m = trimesh.load('rider_bike_full.stl')
V = m.vertices*1e3; V = V*np.array([-1, -1, 1]); V[:, 2] += 3.0   # back to build frame
# side: world (X,Z) -> px (inverse of px())
M = np.column_stack([eu, ev])
def to_px(X, Z):
    du = (X - X_REAR)/S; dv = (WHEEL_R - Z)/S
    return REAR_PX[None] + du[:, None]*eu[None] + dv[:, None]*ev[None]
tris = V[m.faces]
sil = unary_union([Polygon(t[:, [0, 2]]) for t in tris if Polygon(t[:, [0, 2]]).area > 1])
im = Image.open('/mnt/user-data/uploads/IMG_0113.PNG').convert('RGBA')
ov = Image.new('RGBA', im.size, (0,0,0,0)); d = ImageDraw.Draw(ov)
geoms = getattr(sil, 'geoms', [sil])
for g in geoms:
    pts = to_px(*np.array(g.exterior.coords).T); d.polygon([tuple(p) for p in pts], fill=(0,200,255,90), outline=(0,120,255,255))
    for h in g.interiors:
        pts = to_px(*np.array(h.coords).T); d.polygon([tuple(p) for p in pts], outline=(255,0,0,255))
Image.alpha_composite(im, ov).crop((0, 1100, 1206, 2200)).convert('RGB').save('overlay_side.png')
# front projection render
fr = unary_union([Polygon(t[:, [1, 2]]) for t in tris if Polygon(t[:, [1, 2]]).area > 1])
W, H = 700, 1000; img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
f = lambda c: [(W/2 - y*0.45, H - 30 - z*0.65) for y, z in c]
for g in getattr(fr, 'geoms', [fr]):
    d.polygon(f(g.exterior.coords), fill=(60,60,70))
    for h in g.interiors: d.polygon(f(h.coords), fill='white')
d.text((10,10), f"Frontal area A = {fr.area/1e6:.3f} m2", fill='black')
img.save('front_projection.png')
