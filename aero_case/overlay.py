"""Validation: project the built model back onto the source photos.

    python overlay.py [side_photo.png]

The side photo is not in the repo (it is a personal photo), so pass it as an argument
or set AEROSCAN_SIDE_PHOTO. Without it only the front projection is rendered.
Outputs land in preview/ next to this script, regardless of the working directory.
"""
import sys, os, pathlib
import numpy as np, trimesh
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE = pathlib.Path(__file__).resolve().parent
PREVIEW = HERE / 'preview'; PREVIEW.mkdir(exist_ok=True)
FULL = HERE / 'geometry' / 'rider_bike_full.stl'

# reuse the photo->bike transform (everything above the primitive helpers)
exec(open(HERE / 'build_model.py').read().split('# ---------- primitive helpers')[0])

if not FULL.exists():
    sys.exit(f'{FULL} missing - run `python build_model.py` first.')
m = trimesh.load(FULL)
V = m.vertices*1e3; V = V*np.array([-1, -1, 1]); V[:, 2] += 3.0   # back to build frame
tris = V[m.faces]

# ---------- side view: overlay the silhouette on the photo ----------
photo = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('AEROSCAN_SIDE_PHOTO')
if photo and pathlib.Path(photo).exists():
    def to_px(X, Z):   # inverse of px() in build_model.py
        du = (X - X_REAR)/S; dv = (WHEEL_R - Z)/S
        return REAR_PX[None] + du[:, None]*eu[None] + dv[:, None]*ev[None]
    sil = unary_union([Polygon(t[:, [0, 2]]) for t in tris if Polygon(t[:, [0, 2]]).area > 1])
    im = Image.open(photo).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for g in getattr(sil, 'geoms', [sil]):
        pts = to_px(*np.array(g.exterior.coords).T)
        d.polygon([tuple(p) for p in pts], fill=(0, 200, 255, 90), outline=(0, 120, 255, 255))
        for h in g.interiors:
            pts = to_px(*np.array(h.coords).T)
            d.polygon([tuple(p) for p in pts], outline=(255, 0, 0, 255))
    box = (0, 1100, min(1206, im.width), min(2200, im.height))   # crop to the rider
    Image.alpha_composite(im, ov).crop(box).convert('RGB').save(PREVIEW / 'overlay_side.png')
    print('wrote', PREVIEW / 'overlay_side.png')
else:
    print('no side photo given (argv[1] or $AEROSCAN_SIDE_PHOTO) - skipping overlay_side.png')

# ---------- front view: render the projected silhouette + its area ----------
fr = unary_union([Polygon(t[:, [1, 2]]) for t in tris if Polygon(t[:, [1, 2]]).area > 1])
W, H = 700, 1000; img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
f = lambda c: [(W/2 - y*0.45, H - 30 - z*0.65) for y, z in c]
for g in getattr(fr, 'geoms', [fr]):
    d.polygon(f(g.exterior.coords), fill=(60, 60, 70))
    for h in g.interiors:
        d.polygon(f(h.coords), fill='white')
d.text((10, 10), f"Frontal area A = {fr.area/1e6:.3f} m2", fill='black')
img.save(PREVIEW / 'front_projection.png')
print('wrote', PREVIEW / 'front_projection.png')
