"""
Parametric rider + TT-bike model for OpenFOAM, scaled from two photos.
Scale refs: 700c rim (622 mm BSD) + 25 mm tyre -> OD 672 mm; helmet width 190 mm.
Build frame: X forward (rider facing +X), Y left, Z up, mm. Exported rotated 180deg
about Z (rider faces -X, flow +X) and in metres.
"""
import numpy as np, trimesh, manifold3d as m3d, json, pathlib, sys
from trimesh.transformations import rotation_matrix as R
from pose import Pose, solve_hip_drop

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

# ---------- the two things you actually set ----------
# The athlete. Height drives segment lengths, mass calibrates body girths.
RIDER = dict(height_mm=1750.0, mass_kg=69.0)

# The position. All zeros = the position in the photo; every entry is a real millimetre
# change to a contact point, and the pose re-solves around it. This is the knob to turn
# for a Delta-CdA comparison -- never the pixel landmarks in L.
FIT = dict(
    pad_drop_mm=0.0,        # elbow pads down (-) / up (+)
    pad_reach_mm=0.0,       # pads and extensions forward (+) / back (-)
    saddle_fore_mm=0.0,     # saddle forward (+) / back (-)
    saddle_up_mm=0.0,       # saddle up (+) / down (-)
    head_pitch_deg=0.0,     # tuck the head (-) / look up (+)
    crank_angle_deg=None,   # None = the crank position in the photo
)
# Yaw: the geometry is rotated about the vertical axis, NOT the inlet direction. Rotating
# the flow instead would send the wake off at an angle and straight into the side boundary
# (10 m downstream at 15 deg is 2.7 m lateral, wider than the domain half-width). With the
# body rotated the wake stays aligned with the long axis of the domain and the symmetry
# sides remain valid.
YAW_DEG = 0.0
ANKLE_OFFSET = (-70.0, 120.0, 95.0)    # ankle relative to the pedal spindle (x, |y|, z)
KNEE_TARGET_DEG = 145.0                # knee at bottom dead centre; fit window is 140-150
BODY_DENSITY = 1010.0                  # kg/m3

_GLOBALS = {'YAW_DEG'}                 # scalars that live at module level, not in a dict
for _a in sys.argv[1:]:                # e.g. `python build_model.py pad_drop_mm=-20`
    if '=' not in _a:
        sys.exit(f'argumentet {_a!r} saknar =; förväntar nyckel=värde')
    _k, _v = _a.split('=', 1)
    # En okänd nyckel MÅSTE avbryta. Skrevs den bara in i FIT skulle en stavfel-körning
    # tyst bygga baseline-geometrin och rapportera ett delta på noll som om det vore ett
    # resultat - exakt den sortens tyst fel som är omöjlig att upptäcka i efterhand.
    if _k.upper() in _GLOBALS:         # yaw_deg and YAW_DEG both work
        globals()[_k.upper()] = float(_v)
        continue
    _target = RIDER if _k in RIDER else FIT if _k in FIT else None
    if _target is None:
        sys.exit(f'okänd parameter {_k!r}. Giltiga: '
                 + ', '.join(sorted(list(RIDER) + list(FIT) + [g.lower() for g in _GLOBALS])))
    _target[_k] = None if _v == 'None' else float(_v)

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
def open_edges(m):
    """Count edges not shared by exactly two faces.

    This is the networkx-free version of the watertightness check:
    trimesh.repair.broken_faces() needs networkx, which is an optional trimesh
    dependency and not worth making the geometry build depend on.
    """
    paired = trimesh.grouping.group_rows(m.edges_sorted, require_count=2)
    return len(m.edges_sorted) - 2*len(paired)


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
def bike(pose):
    bb = pose.bb; ra = P(X_REAR, WHEEL_R); fa = X3(FRONT_AX)
    ht_top, ht_bot = X3(L['ht_top']), X3(L['ht_bot'])
    seat_top = pose.saddle; tt_rear = X3(L['tt_rear'])
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
    d_pad = np.array([pose.fit['pad_reach_mm'], 0.0, pose.fit['pad_drop_mm']])
    bb_ = X3(L['base_bar']) + d_pad; horn = X3(L['horn_end']) + d_pad
    pad = X3(L['pad_top']) + d_pad
    parts += [aero_tube(ht_top + [0, 0, 15], bb_ + [-40, 0, 15], [35, 22, 22]),   # stem
              aero_tube(bb_ + [0, -185, 0], bb_ + [0, 185, 0], [22, 12, 14])]    # base bar
    for s in (1, -1):
        parts += [limb(bb_ + [0, s*185, 0], horn + [0, s*195, 0], 13, 12),        # bullhorn + shifter
                  limb(horn + [0, s*195, 0], horn + [5, s*195, -60], 12, 10),
                  limb(bb_ + [-30, s*85, 20], pad + [-40, s*85, -30], 16, 16),    # pad risers
                  ellipsoid(pad + [-20, s*85, -12], [85, 48, 12]),                # arm pads
                  limb(pad + [40, s*55, -10], pose.grip + [-10, s*25, -25], 11, 11)]  # extensions
    parts.append(ellipsoid(X3(L['bag']), [55, 30, 45]))                          # bag under pads
    # cranks + pedals (right crank forward like the photo)
    pedR, pedL = pose.pedal_R, pose.pedal_L
    for ped, s in ((pedR, -1), (pedL, 1)):
        parts += [limb(bb + [0, s*80, 0], ped + [0, s*85, 0], 16, 12),
                  ellipsoid(ped + [0, s*112, 0], [45, 45, 10])]
    return union(parts), pedR, pedL

# ---------- rider ----------
def rider(pose, g=1.0):
    """Build the rider from a solved Pose. `g` scales every body girth (not length):
    union volume goes roughly as g^2, which is what the mass calibration solves on.

    Returns (full rider incl. helmet and shoes, right knee, body only).
    """
    hip, sh, el, hands = pose.hip, pose.shoulder, pose.elbow, pose.hands
    back_hi, chest_lo, butt = pose.back_high, pose.chest_low, pose.butt
    # torso = hull of pelvis, abdomen, chest ellipsoids; heights from back line / chest underside
    pelvis_c = hip + [-30, 0, 20]
    chest_c = np.array([sh[0] - 90, 0, 0.5*(back_hi[2] + chest_lo[2])])
    chest_hz = 0.5*np.linalg.norm((back_hi - chest_lo)[[0, 2]])
    abd_c = 0.5*(pelvis_c + chest_c) + [0, 0, -10]
    torso = hull(ellipsoid(pelvis_c, [pelvis_c[0]-butt[0]+10, 165*g, 125*g]),
                 ellipsoid(abd_c, [150, 160*g, 118*g]),
                 ellipsoid(chest_c, [165, 172*g, chest_hz*g]),
                 ellipsoid(sh + [0, 130*g, 0], [60, 55*g, 60*g]),
                 ellipsoid(sh + [0, -130*g, 0], [60, 55*g, 60*g]))
    # head & helmet (helmet: 190 mm wide, length from photo; helmet is kit, not body mass)
    ht, hf, htail = pose.helmet_top, pose.helmet_front, pose.helmet_tail
    h_len = np.linalg.norm((hf - htail)[[0, 2]])
    hel_c = np.array([0.5*(hf[0] + htail[0]) + 5, 0, ht[2] - 100])
    hel_tilt = np.degrees(np.arctan2(*(hf - htail)[[2, 0]]))
    helmet = ellipsoid(hel_c, [h_len/2, 95, 100], rot=R(np.radians(-12 + hel_tilt), [0, 1, 0]))
    chin, nose = pose.chin, pose.nose
    # Huvudet slutar vid hakan. Tidigare sattes höjden till (hel_c+60-chin)/2 kring en
    # mittpunkt som lade underkanten 34 mm NEDANFÖR haklandmärket -- en blaffa under
    # hjälmen som inte finns på någon människa.
    # Bredden skalas inte längre med kroppsomfånget: ett huvud växer inte med midjemåttet,
    # och 72*g gav 131 mm huvudbredd mot ca 150 mm för en vuxen. Det gjorde steget ner mot
    # hjälmens 190 mm onödigt stort.
    head_top = hel_c[2] + 60
    head_c = np.array([nose[0] - 95, 0, 0.5*(head_top + chin[2])])
    head = ellipsoid(head_c, [100, 75, 0.5*(head_top - chin[2])])
    neck = limb(sh + [-40, 0, 20], head_c + [-40, 0, -20], 60*g, 55*g)
    body = [torso, head, neck, ellipsoid(hands + [-15, 0, -5], [65, 55*g, 55*g])]
    kit = [helmet]
    for s_ in (1, -1):
        e = el + [0, s_*85, 0]
        body += [limb(sh + [0, s_*135, 0], e, 55*g, 46*g),                     # upper arm
                 limb(e, hands + [-60, s_*32, -10], 44*g, 33*g)]               # forearm
    # legs: feet on the pedals, knee from 2-link IK on the stature-derived segments
    for ped, s_ in ((pose.pedal_R, -1), (pose.pedal_L, 1)):
        hj, kn, ank = pose.leg(ped, s_, ANKLE_OFFSET)
        # Vadmuskeln läggs BAKOM underbenet, uttryckt i benets egen riktning. Tidigare
        # användes fasta offset i världskoordinater (kn+[-35,0,-60] -> ank+[-20,0,120]),
        # vilket bara hade fungerat om underbenet stod lodrätt. Det gör det inte, och på
        # vänsterbenet -- där veven står uppe och underbenet lutar kraftigt -- hamnade
        # nedre änden 106 mm vid sidan av benets axel. Resultatet var en stav som stack ut
        # 101 mm bakom vaden i stället för en muskelbuk.
        u = (ank - kn) / np.linalg.norm(ank - kn)
        back = np.array([-u[2], 0.0, u[0]])              # vinkelrätt mot benet i sagittalplanet
        if back[0] > 0:
            back = -back                                 # ryttaren tittar mot +x, vaden sitter bakåt
        shank = np.linalg.norm(ank - kn)
        body += [limb(hj, kn, 88*g, 58*g), limb(kn, ank, 58*g, 36*g),
                 limb(kn + u*0.15*shank + back*26, kn + u*0.60*shank + back*16,
                      46*g, 34*g)]                                             # calf
        kit.append(ellipsoid(ped + [15, s_*120, 38], [140, 52, 48]))           # shoe
        if s_ == -1:
            kneeR = kn
    return union(body + kit), kneeR, union(body)


def calibrate_girth(pose, target_kg, tol=0.004, max_iter=6):
    """Solve the girth scale g so the modelled body mass matches the athlete's.

    Without this the trunk hull (convex, so it cannot have a waist) runs ~16% heavy.
    Volume ~ g^2, so the secant iteration below converges in two or three steps.
    """
    target_v = target_kg/BODY_DENSITY*1e9          # mm^3
    g, hist = 1.0, []
    for _ in range(max_iter):
        v = rider(pose, g)[2].volume
        hist.append((g, v/1e6, v/1e9*BODY_DENSITY))
        if abs(v/target_v - 1) < tol:
            break
        g *= (target_v/v)**0.5                     # exact for a pure cross-section scale
    return g, hist


# ---------- build ----------
# Anatomy, so solved at the BASELINE fit and then held fixed: if a saddle change takes the
# knee angle out of the fit window, that is a result, not something to calibrate away.
BASELINE_FIT = {k: (None if k == 'crank_angle_deg' else 0.0) for k in FIT}
HIP_DROP, KNEE_BDC = solve_hip_drop(L, X3, RIDER['height_mm'], BASELINE_FIT,
                                    ANKLE_OFFSET, KNEE_TARGET_DEG)
pose = Pose(L, X3, RIDER['height_mm'], FIT, HIP_DROP)
b, pedR, pedL = bike(pose)
GIRTH, girth_hist = calibrate_girth(pose, RIDER['mass_kg'])
r, kneeR, body = rider(pose, GIRTH)
wR, wF = wheel(X_REAR), wheel(X_REAR + WB)
SINK = 3.0   # tyre contact: sink 3 mm below z=0 so snappy gets a clean contact patch
parts = {'rider': r, 'bike': b, 'wheel_rear': wR, 'wheel_front': wF}
# 180 deg puts the rider facing -X with the flow along +X; YAW_DEG then turns the whole
# machine about the vertical axis so the relative wind meets it at an angle.
T = R(np.pi + np.radians(YAW_DEG), [0, 0, 1])
GEOM.mkdir(exist_ok=True)
for k, m in parts.items():
    m.apply_translation([0, 0, -SINK]); m.apply_transform(T); m.apply_scale(1e-3)
    m.export(GEOM / f'{k}.stl')
full = union(list(parts.values())); full.export(GEOM / 'rider_bike_full.stl')

# Validate what snappyHexMesh will actually read, not the in-memory topology: STL is a
# triangle soup, so a part is only closed if it survives an export/reload round trip.
for k in parts:
    chk = trimesh.load(GEOM / f'{k}.stl')
    bad = open_edges(chk)
    assert chk.is_watertight and not bad, \
        f'{k}.stl not watertight after export: {bad} open edges, ' \
        f'{len(chk.split(only_watertight=False))} shells'

# frontal area (projection on Y-Z, clipped to the part above ground)
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
tris = full.vertices[full.faces][:, :, 1:]
polys = [Polygon(t) for t in tris if Polygon(t).area > 1e-10]
proj = unary_union(polys).intersection(box(-10, 0, 10, 10))

body.apply_translation([0, 0, -SINK]); body.apply_transform(T); body.apply_scale(1e-3)
rider_vol = body.volume                           # body only: no helmet, no shoes
knee_resid = float(np.hypot(*(kneeR[[0, 2]] - L['knee_R'])))

# Everything the OpenFOAM case has to stay in sync with, emitted so the workflow can
# read it instead of duplicating the numbers (see "Nyckelkonventioner" in the README).
_c, _s = np.cos(np.radians(YAW_DEG)), np.sin(np.radians(YAW_DEG))
def _yaw(v):
    """Turn an export-frame vector about the vertical axis by YAW_DEG."""
    return [round(v[0]*_c - v[1]*_s, 6), round(v[0]*_s + v[1]*_c, 6), round(v[2], 6)]

axle_rear = _yaw([-X_REAR*1e-3, 0.0, (WHEEL_R - SINK)*1e-3])
axle_front = _yaw([-(X_REAR + WB)*1e-3, 0.0, (WHEEL_R - SINK)*1e-3])
# The wheels still spin about their own axle, which the yaw rotation carried along with the
# rest of the bike -- the machine turns, the flow does not.
wheel_axis = _yaw([0.0, -1.0, 0.0])
# Drag is reported along the DIRECTION OF TRAVEL, not along the wind. At yaw those differ,
# and it is the travel-axis component that costs watts: a sailing rider feels a big side
# force that does no work. Leaving dragDir at (1 0 0) would report the wind-axis force and
# quietly overstate the cost of yaw.
drag_dir = _yaw([1.0, 0.0, 0.0])
pitch_axis = _yaw([0.0, 1.0, 0.0])
info = dict(scale_mm_per_px=S, wheelbase_mm=WB, bb_height_mm=L['bb'][1],
            yaw_deg=YAW_DEG, wheel_axis=wheel_axis,
            drag_dir=drag_dir, lift_dir=[0.0, 0.0, 1.0], pitch_axis=pitch_axis,
            wheel_radius_m=WHEEL_R*1e-3, axle_rear_m=axle_rear, axle_front_m=axle_front,
            helmet_top_mm=L['helmet_top'][1], helmet_length_mm=L['helmet_front'][0]-L['helmet_tail'][0],
            frontal_area_m2=proj.area, bbox_m=full.bounds.tolist(),
            rider=dict(RIDER), fit=dict(FIT), girth_scale=round(GIRTH, 4),
            hip_drop_mm=HIP_DROP,
            rider_volume_m3=rider_vol, rider_implied_mass_kg=rider_vol*BODY_DENSITY,
            fit_angles=pose.angles(ANKLE_OFFSET), segments=pose.segment_report(),
            knee_ik_mm=kneeR.round(1).tolist(), knee_residual_mm=round(knee_resid, 1),
            n_faces={k: len(m.faces) for k, m in parts.items()},
            landmarks_mm={k: v.round(0).tolist() for k, v in L.items()})
json.dump(info, open(HERE / 'model_info.json', 'w'), indent=1)

fa = info['fit_angles']
print(f"RIDER  {RIDER['height_mm']/10:.0f} cm, {RIDER['mass_kg']:.0f} kg   "
      f"girth scale {GIRTH:.3f} -> {rider_vol*BODY_DENSITY:.1f} kg modellerad kropp")
print(f"       höftledcentrum {HIP_DROP:.0f} mm under ytlandmärket (löst ur knävinkeln)")
print(f"FIT    " + ', '.join(f'{k}={v}' for k, v in FIT.items() if v))
if YAW_DEG:
    print(f"YAW    {YAW_DEG:+.1f} deg: geometrin vriden, flödet kvar längs +x. "
          f"dragDir {drag_dir} (färdriktningen, inte vindriktningen)")
print(f"AREA   frontarea {proj.area:.4f} m2")
print('\nFIT-VINKLAR')
for k, v in fa.items():
    print(f"  {k:26s} {v:8.1f}")
print(f"\n  ryggvinkel {fa['back_deg']:.1f} grader mot horisontalplanet "
      f"(pitch mot fotot {fa['trunk_pitch_vs_photo_deg']:+.2f})")
if not 140 <= fa['knee_bottom_deg'] <= 150:
    print(f"  WARNING: knävinkel i botten {fa['knee_bottom_deg']:.0f} grader ligger utanför "
          f"fit-fönstret 140-150 trots lösningen - kolla ANKLE_OFFSET och saddle_up_mm.")
mass_err = rider_vol*BODY_DENSITY/RIDER['mass_kg'] - 1
if abs(mass_err) > 0.05:
    print(f"  WARNING: kroppsmassa {mass_err*100:+.0f}% fel trots kalibrering")
if abs(pose.forearm_resid) > 15:
    print(f"  NOTE: underarmen sträcks {pose.forearm_resid:+.0f} mm av detta FIT - "
          f"padsen och greppen flyttades olika mycket.")
if knee_resid > 25:
    print(f"  NOTE: IK-knät ligger {knee_resid:.0f} mm fran landmärket knee_R. "
          f"Lar/underben ar {pose.thigh:.0f}/{pose.shank:.0f} mm (Winter, "
          f"{RIDER['height_mm']/10:.0f} cm); avvikelsen sitter nastan helt i x, sa "
          f"frontarean paverkas ~0.3%.")
