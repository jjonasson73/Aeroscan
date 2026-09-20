"""
Parametric rider + TT-bike model for OpenFOAM, scaled from two photos.
Scale refs: 700c rim (622 mm BSD) + 25 mm tyre -> OD 672 mm; helmet width 190 mm.
Build frame: X forward (rider facing +X), Y left, Z up, mm. Exported rotated 180deg
about Z (rider faces -X, flow +X) and in metres.
"""
import numpy as np, trimesh, manifold3d as m3d, json, pathlib
from trimesh.transformations import rotation_matrix as R

HERE = pathlib.Path(__file__).resolve().parent   # outputs go next to the script, not into cwd
GEOM = HERE / 'geometry'

# ---------- photo -> bike coordinate transform (side view IMG_0113, full-res px) ----------
REAR_PX, FRONT_PX = np.array([265., 1860.]), np.array([895., 1895.])
WHEEL_R = 336.0                     # (622 + 2*25)/2
WHEEL_PX = 432.0                    # mean measured wheel OD in px (rear 420 / front 450: perspective)
S = 2*WHEEL_R / WHEEL_PX            # mm/px  (~1.556)
eu = (FRONT_PX-REAR_PX)/np.linalg.norm(FRONT_PX-REAR_PX)   # corrects ~3 deg camera roll
ev = np.array([-eu[1], eu[0]])
X_REAR = -400.0
def px(x, y):
    d = np.array([x, y]) - REAR_PX
    return np.array([X_REAR + S*d.dot(eu), WHEEL_R - S*d.dot(ev)])
WB = S*np.linalg.norm(FRONT_PX-REAR_PX)

# ---------- measured landmarks (px -> mm, X/Z) ----------
L = {k: px(*v) for k, v in {
    'bb': (505, 1930), 'helmet_top': (900, 1230), 'helmet_front': (995, 1320),
    'helmet_tail': (795, 1262), 'nose': (945, 1395), 'chin': (910, 1422),
    'back_low': (450, 1350), 'back_high': (800, 1272), 'butt': (410, 1400),
    'hip': (478, 1425), 'shoulder': (800, 1315), 'elbow': (812, 1488),
    'hands': (1000, 1400), 'chest_low': (720, 1480), 'pad_top': (820, 1495),
    'base_bar': (880, 1612), 'horn_end': (945, 1650), 'ht_top': (785, 1605),
    'ht_bot': (822, 1712), 'tt_rear': (480, 1610), 'seat_top': (430, 1490),
    'pedal_R': (600, 1930), 'knee_R': (645, 1628), 'bag': (715, 1520),
    'bottle': (345, 1425)}.items()}
FRONT_AX = np.array([X_REAR+WB, WHEEL_R])

# ---------- primitive helpers (all watertight) ----------
def P(x, z, y=0.0): return np.array([x, y, z], float)
def X3(p2, y=0.0): return P(p2[0], p2[1], y)
def ellipsoid(c, a, sub=3, rot=None):
    m = trimesh.creation.icosphere(subdivisions=sub); m.apply_scale(a)
    if rot is not None: m.apply_transform(rot)
    m.apply_translation(c); return m
def limb(p1, p2, r1, r2, sub=3):
    return trimesh.convex.convex_hull(np.vstack([ellipsoid(p1, [r1]*3, sub).vertices,
                                                 ellipsoid(p2, [r2]*3, sub).vertices]))
def aero_tube(p1, p2, a1, a2=None, sub=3):  # ellipsoidal ends -> aero-ish cross-section
    return trimesh.convex.convex_hull(np.vstack([ellipsoid(p1, a1, sub).vertices,
                                                 ellipsoid(p2, a1 if a2 is None else a2, sub).vertices]))
def hull(*ms): return trimesh.convex.convex_hull(np.vstack([m.vertices for m in ms]))
def cyl_y(c, r, h, sec=64):
    m = trimesh.creation.cylinder(radius=r, height=h, sections=sec)
    m.apply_transform(R(np.pi/2, [1, 0, 0])); m.apply_translation(c); return m
def revolve_y(profile, center, seg=180):
    cs = m3d.CrossSection([np.asarray(profile, float)])
    mf = m3d.Manifold.revolve(cs, circular_segments=seg)   # axis = z
    msh = mf.to_mesh()
    m = trimesh.Trimesh(msh.vert_properties[:, :3], msh.tri_verts)
    m.apply_transform(R(np.pi/2, [1, 0, 0])); m.apply_translation(center); return m
def weld(m, rel_tol=1e-5, rounds=6):
    """Collapse the sub-micron slivers the boolean engine leaves behind.

    trimesh's is_watertight only looks at face/vertex *indices*, so a mesh full of
    zero-area triangles still passes it -- while the exported STL (a triangle soup that
    every reader re-welds by position) falls apart into hundreds of open shells.
    The tolerance is relative to the part's own size so this is safe whether the mesh is
    still in mm or already scaled to metres: 1e-5 of the bbox diagonal is ~10 um here,
    400x below the finest snappy cell, and leaves part volumes unchanged to 5 s.f.
    """
    digits = max(0, int(round(-np.log10(m.scale * rel_tol))))
    for _ in range(rounds):
        n0 = len(m.faces)
        m.merge_vertices(digits_vertex=digits)
        m.update_faces(m.nondegenerate_faces())
        m.update_faces(m.unique_faces())
        m.remove_unreferenced_vertices()
        if len(m.faces) == n0:
            break
    m.fix_normals()
    return m

def union(ms):
    return weld(trimesh.boolean.union(ms, engine='manifold'))

# ---------- wheels ----------
def wheel(cx):
    c = P(cx, WHEEL_R)
    th = np.linspace(0, 2*np.pi, 48, endpoint=False)
    tyre = [(311 + 4 + 12.5*np.cos(t)*1.0 + 8.5, 12.5*np.sin(t)) for t in th]      # 25 mm tyre, OD 672
    rim = [(274, -6), (280, -10.5), (300, -11.5), (318, -11), (318, 11), (300, 11.5), (280, 10.5), (274, 6)]  # ~40 mm rim
    parts = [revolve_y(tyre, c), revolve_y(rim, c), cyl_y(c, 28, 100), ]
    return union(parts)

# ---------- bike ----------
def bike():
    bb = X3(L['bb']); ra = P(X_REAR, WHEEL_R); fa = X3(FRONT_AX)
    ht_top, ht_bot = X3(L['ht_top']), X3(L['ht_bot'])
    seat_top = X3(L['seat_top']); tt_rear = X3(L['tt_rear'])
    parts = [
        aero_tube(bb, seat_top, [32, 16, 20]),                          # aero seat tube / mast
        aero_tube(tt_rear + [0, 0, -10], ht_top, [28, 17, 25]),         # top tube
        aero_tube(ht_top + [0, 0, 20], ht_bot + [5, 0, -30], [40, 20, 30]),   # head tube
        aero_tube(ht_bot, bb + [60, 0, 10], [38, 22, 32], [45, 32, 45]),# down tube
        aero_tube(bb + [0, 0, 0], bb + [-40, 0, 0], [45, 35, 45]),      # BB shell
        cyl_y(bb, 105, 5).apply_translation([0, -75, 0]),               # chainring (drive side = -Y)
        cyl_y(ra, 55, 30).apply_translation([0, -35, 0]),               # cassette
    ]
    for s in (1, -1):
        parts += [aero_tube(ht_bot + [0, s*40, 0], fa + [0, s*55, 0], [25, 12, 25], [15, 10, 15]),  # fork
                  limb(bb + [-30, s*42, 10], ra + [0, s*62, 0], 13, 9),                           # chainstay
                  limb(seat_top + [-15, s*25, -230], ra + [0, s*62, 0], 12, 8)]                   # seatstay
    # saddle + seatpost + rear bottle
    sad = seat_top + [-60, 0, 45]
    parts += [limb(seat_top, sad + [0, 0, -20], 14, 14),
              ellipsoid(sad, [125, 65, 20]),
              limb(X3(L['bottle']) + [-80, 0, 0], X3(L['bottle']) + [70, 0, 15], 37, 37),
              limb(sad + [-90, 0, 0], X3(L['bottle']) + [0, 0, -35], 10, 10)]
    # cockpit
    bb_ = X3(L['base_bar']); horn = X3(L['horn_end']); pad = X3(L['pad_top'])
    parts += [aero_tube(ht_top + [0, 0, 15], bb_ + [-40, 0, 15], [35, 22, 22]),   # stem
              aero_tube(bb_ + [0, -185, 0], bb_ + [0, 185, 0], [22, 12, 14])]    # base bar
    for s in (1, -1):
        parts += [limb(bb_ + [0, s*185, 0], horn + [0, s*195, 0], 13, 12),        # bullhorn + shifter
                  limb(horn + [0, s*195, 0], horn + [5, s*195, -60], 12, 10),
                  limb(bb_ + [-30, s*85, 20], pad + [-40, s*85, -30], 16, 16),    # pad risers
                  ellipsoid(pad + [-20, s*85, -12], [85, 48, 12]),                # arm pads
                  limb(pad + [40, s*55, -10], X3(L['hands']) + [-10, s*25, -25], 11, 11)]  # extensions
    parts.append(ellipsoid(X3(L['bag']), [55, 30, 45]))                          # bag under pads
    # cranks + pedals (right crank forward like the photo)
    pR = X3(L['pedal_R']); v = pR - bb; ang = np.arctan2(v[2], v[0])
    CR = 170.0
    pedR = bb + CR*np.array([np.cos(ang), 0, np.sin(ang)]); pedL = bb - (pedR - bb)
    for ped, s in ((pedR, -1), (pedL, 1)):
        parts += [limb(bb + [0, s*80, 0], ped + [0, s*85, 0], 16, 12),
                  ellipsoid(ped + [0, s*112, 0], [45, 45, 10])]
    return union(parts), pedR, pedL

# ---------- rider ----------
def ik_knee(hip, ank, L1=440, L2=440):
    d = ank - hip; Ld = np.linalg.norm(d); dh = d/Ld
    a = (Ld**2 + L1**2 - L2**2)/(2*Ld); h = np.sqrt(max(L1**2 - a**2, 0))
    f = np.array([1, 0, 0]) - dh*dh[0]; f /= np.linalg.norm(f)
    return hip + a*dh + h*f

def rider(pedR, pedL):
    hip, sh, el, hands = X3(L['hip']), X3(L['shoulder']), X3(L['elbow']), X3(L['hands'])
    back_hi = X3(L['back_high']); chest_lo = X3(L['chest_low']); butt = X3(L['butt'])
    # torso = hull of pelvis, abdomen, chest ellipsoids; heights from back line / chest underside
    pelvis_c = hip + [-30, 0, 20]
    chest_c = np.array([sh[0] - 90, 0, 0.5*(back_hi[2] + chest_lo[2])])
    chest_hz = 0.5*(back_hi[2] - chest_lo[2])
    abd_c = 0.5*(pelvis_c + chest_c) + [0, 0, -10]
    torso = hull(ellipsoid(pelvis_c, [pelvis_c[0]-butt[0]+10, 165, 125]),
                 ellipsoid(abd_c, [150, 160, 118]),
                 ellipsoid(chest_c, [165, 172, chest_hz]),
                 ellipsoid(sh + [0, 130, 0], [60, 55, 60]), ellipsoid(sh + [0, -130, 0], [60, 55, 60]))
    # head & helmet (helmet: 190 mm wide, length from photo)
    ht, hf, htail = X3(L['helmet_top']), X3(L['helmet_front']), X3(L['helmet_tail'])
    h_len = hf[0] - htail[0]
    hel_c = np.array([0.5*(hf[0] + htail[0]) + 5, 0, ht[2] - 100])
    helmet = ellipsoid(hel_c, [h_len/2, 95, 100], rot=R(np.radians(-12), [0, 1, 0]))
    chin, nose = X3(L['chin']), X3(L['nose'])
    head_c = np.array([nose[0] - 95, 0, 0.5*(hel_c[2] + chin[2]) - 5])
    head = ellipsoid(head_c, [100, 72, (hel_c[2] + 60 - chin[2])/2])
    neck = limb(sh + [-40, 0, 20], head_c + [-40, 0, -20], 60, 55)
    parts = [torso, helmet, head, neck, ellipsoid(hands + [-15, 0, -5], [65, 55, 55])]
    for s in (1, -1):
        e = el + [0, s*85, 0]
        parts += [limb(sh + [0, s*135, 0], e, 55, 46),                            # upper arm
                  limb(e, hands + [-60, s*32, -10], 44, 33)]                      # forearm
    # legs (2-link IK to the pedals; hip width & stance from front photo)
    for ped, s in ((pedR, -1), (pedL, 1)):
        hj = hip + [0, s*95, 0]
        ank = ped + [-70, s*120, 95]
        kn = ik_knee(hj, ank)
        parts += [limb(hj, kn, 88, 58), limb(kn, ank, 58, 36),
                  limb(kn + [-35, 0, -60], ank + [-20, 0, 120], 48, 34),          # calf
                  ellipsoid(ped + [15, s*120, 38], [140, 52, 48])]               # shoe
        if s == -1: kneeR = kn
    return union(parts), kneeR

# ---------- build ----------
b, pedR, pedL = bike()
r, kneeR = rider(pedR, pedL)
wR, wF = wheel(X_REAR), wheel(X_REAR + WB)
SINK = 3.0   # tyre contact: sink 3 mm below z=0 so snappy gets a clean contact patch
parts = {'rider': r, 'bike': b, 'wheel_rear': wR, 'wheel_front': wF}
T = R(np.pi, [0, 0, 1])          # rider faces -X, flow along +X
GEOM.mkdir(exist_ok=True)
for k, m in parts.items():
    m.apply_translation([0, 0, -SINK]); m.apply_transform(T); m.apply_scale(1e-3)
    m.export(GEOM / f'{k}.stl')
full = union(list(parts.values())); full.export(GEOM / 'rider_bike_full.stl')

# Validate what snappyHexMesh will actually read, not the in-memory topology: STL is a
# triangle soup, so a part is only closed if it survives an export/reload round trip.
for k in parts:
    chk = trimesh.load(GEOM / f'{k}.stl')
    broken = len(trimesh.repair.broken_faces(chk))
    assert chk.is_watertight and not broken, \
        f'{k}.stl not watertight after export: {broken} broken faces, ' \
        f'{len(chk.split(only_watertight=False))} shells'

# frontal area (projection on Y-Z, clipped to the part above ground)
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
tris = full.vertices[full.faces][:, :, 1:]
polys = [Polygon(t) for t in tris if Polygon(t).area > 1e-10]
proj = unary_union(polys).intersection(box(-10, 0, 10, 10))

# Sanity levers for the two assumptions the photos cannot check by themselves:
#  - rider volume vs. the athlete's real mass (body density ~1010 kg/m3)
#  - the IK knee vs. the measured knee_R landmark (see README "Known state")
rider_vol = parts['rider'].volume                 # already scaled to m^3 above
knee_resid = float(np.hypot(*(kneeR[[0, 2]] - L['knee_R'])))
# Everything the OpenFOAM case has to stay in sync with, emitted so the workflow can
# read it instead of duplicating the numbers (see "Nyckelkonventioner" in the README).
axle_rear = [round(-X_REAR*1e-3, 6), 0.0, round((WHEEL_R - SINK)*1e-3, 6)]
axle_front = [round(-(X_REAR + WB)*1e-3, 6), 0.0, round((WHEEL_R - SINK)*1e-3, 6)]
info = dict(scale_mm_per_px=S, wheelbase_mm=WB, bb_height_mm=L['bb'][1],
            wheel_radius_m=WHEEL_R*1e-3, axle_rear_m=axle_rear, axle_front_m=axle_front,
            helmet_top_mm=L['helmet_top'][1], helmet_length_mm=L['helmet_front'][0]-L['helmet_tail'][0],
            frontal_area_m2=proj.area, bbox_m=full.bounds.tolist(),
            rider_volume_m3=rider_vol, rider_implied_mass_kg=rider_vol*1010,
            knee_ik_mm=kneeR.round(1).tolist(), knee_residual_mm=round(knee_resid, 1),
            n_faces={k: len(m.faces) for k, m in parts.items()},
            landmarks_mm={k: v.round(0).tolist() for k, v in L.items()})
json.dump(info, open(HERE / 'model_info.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in info.items() if k != 'landmarks_mm'}, indent=1))
if knee_resid > 25:
    print(f'\nWARNING: IK knee sits {knee_resid:.0f} mm from the measured knee_R landmark.\n'
          f'  L1/L2 in ik_knee() are {440}/{440} mm but the photo implies a shorter femur/tibia,\n'
          f'  and the ankle offset in rider() is a guess. The knee is the most exposed part of\n'
          f'  the leg, so this feeds straight into frontal area and the CdA split.')
