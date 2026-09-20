"""Rider pose: body from anthropometry, contact points from the photo, joints solved.

The point of this layer is Delta-CdA. A position change must be ONE physical input
(`pad_drop_mm=-20`), with every joint following consistently -- editing eight pixel
landmarks by eye puts the error straight into the delta, where it is invisible.

Three layers, deliberately separated:

  1. BODY   - segment lengths. Trunk and arms are measured from the side photo (they are
              directly visible); leg segments come from stature via Winter (2009), because
              the ankle landmark is a guess and the photo-implied femur disagrees with
              anthropometry by ~7%. `segment_report()` prints both so the gap stays visible.
  2. FIT    - where the contact points are: saddle, elbow pads, extension grips, pedals.
              The photo gives the baseline; the FIT deltas move them.
  3. POSE   - solved. Hip rides the saddle, elbows rest on the pads, hands hold the grips,
              feet turn with the cranks. The trunk pitches about the hip until the shoulder
              sits exactly one upper-arm away from the pad -- which is what actually happens
              to your back when you drop the pads.

All offsets are calibrated from the photo at baseline, so FIT = all zeros reproduces the
measured landmarks exactly and every delta away from it is a real geometric change.
Build frame: X forward (rider faces +X), Y left, Z up, mm.
"""
import numpy as np

# Winter (2009), segment length as a fraction of standing height
WINTER = dict(thigh=0.245, shank=0.246, foot=0.152, upper_arm=0.186,
              forearm=0.146, trunk=0.288, head=0.130)


def _ang(v):
    """Angle of an x-z vector above the +x axis [rad]."""
    return np.arctan2(v[2], v[0])


def _circle_circle(c0, r0, c1, r1, prefer):
    """Intersect two circles in the x-z plane; return the root nearest `prefer`."""
    d = np.hypot(*(c1 - c0)[[0, 2]])
    if d > r0 + r1 or d < abs(r0 - r1) or d == 0:
        raise ValueError(f'pose unreachable: centres {d:.0f} mm apart, radii {r0:.0f}/{r1:.0f}. '
                         f'The pads are out of arm\'s reach for this FIT.')
    a = (r0**2 - r1**2 + d**2) / (2*d)
    h = np.sqrt(max(r0**2 - a**2, 0.0))
    u = (c1 - c0)[[0, 2]] / d
    n = np.array([-u[1], u[0]])
    base = c0[[0, 2]] + a*u
    roots = [base + h*n, base - h*n]
    best = min(roots, key=lambda p: np.hypot(*(p - prefer[[0, 2]])))
    return np.array([best[0], 0.0, best[1]])


def rot_about(point, pivot, deg):
    """Rotate an x-z point about a pivot (y untouched)."""
    t = np.radians(deg); c, s = np.cos(t), np.sin(t)
    d = point - pivot
    return pivot + np.array([c*d[0] - s*d[2], d[1], s*d[0] + c*d[2]])


class Pose:
    """Solved joint positions plus the offsets used to get there."""

    def __init__(self, L, X3, height_mm, fit, hip_drop_mm=0.0):
        self.height = height_mm
        self.hip_drop = hip_drop_mm
        self.fit = fit
        self.L = L
        # --- baseline (photo) geometry -------------------------------------------------
        m = {k: X3(L[k]) for k in
             ('bb', 'hip', 'shoulder', 'elbow', 'hands', 'seat_top', 'pad_top', 'pedal_R',
              'knee_R', 'butt', 'back_high', 'back_low', 'chest_low',
              'helmet_top', 'helmet_front', 'helmet_tail', 'nose', 'chin')}
        # `hip` in the photo is a SURFACE point; the femoral head sits below it. The offset
        # is the one anatomical unknown the photo cannot give, so it is solved from the
        # knee angle at bottom dead centre -- the most established number in bike fitting.
        m['hip'] = m['hip'] - np.array([0.0, 0.0, hip_drop_mm])
        self.measured = m

        # Segment lengths the photo can see directly.
        self.trunk_len = np.linalg.norm((m['shoulder'] - m['hip'])[[0, 2]])
        self.upper_arm = np.linalg.norm((m['elbow'] - m['shoulder'])[[0, 2]])
        self.forearm = np.linalg.norm((m['hands'] - m['elbow'])[[0, 2]])
        # Leg segments from stature: the ankle is a guess, so the photo cannot fix these.
        self.thigh = WINTER['thigh'] * height_mm
        self.shank = WINTER['shank'] * height_mm

        # --- contact points, moved by the fit deltas -----------------------------------
        d_saddle = np.array([fit['saddle_fore_mm'], 0.0, fit['saddle_up_mm']])
        d_pad = np.array([fit['pad_reach_mm'], 0.0, fit['pad_drop_mm']])
        self.bb = m['bb']
        self.saddle = m['seat_top'] + d_saddle
        self.hip = m['hip'] + d_saddle          # the hip joint rides the saddle
        self.pad = m['elbow'] + d_pad           # elbow rests on the pad
        self.grip = m['hands'] + d_pad          # extensions move with the pads
        self.crank_deg = fit['crank_angle_deg']

        # --- solve the trunk --------------------------------------------------------
        self.elbow = self.pad
        self.shoulder = _circle_circle(self.hip, self.trunk_len,
                                       self.elbow, self.upper_arm, prefer=m['shoulder'])
        self.trunk_pitch = np.degrees(_ang(self.shoulder - self.hip)
                                      - _ang(m['shoulder'] - m['hip']))
        # Everything rigidly attached to the trunk follows that rotation.
        for k in ('butt', 'back_high', 'back_low', 'chest_low'):
            setattr(self, k, rot_about(m[k], self.hip, self.trunk_pitch))
        # Head and helmet ride the shoulder, plus an independent head pitch.
        dsh = self.shoulder - m['shoulder']
        for k in ('helmet_top', 'helmet_front', 'helmet_tail', 'nose', 'chin'):
            p = rot_about(m[k], m['shoulder'], self.trunk_pitch) + dsh
            setattr(self, k, rot_about(p, self.shoulder, fit['head_pitch_deg']))

        # Hands sit on the grips; the forearm length is a consequence, so check it.
        self.hands = self.grip
        self.forearm_resid = np.linalg.norm((self.hands - self.elbow)[[0, 2]]) - self.forearm

        # --- legs -------------------------------------------------------------------
        v = m['pedal_R'] - self.bb
        self.crank_len = 170.0
        base_crank = np.degrees(_ang(v))
        ang = base_crank if self.crank_deg is None else self.crank_deg
        self.crank_deg_used = ang
        t = np.radians(ang)
        self.pedal_R = self.bb + self.crank_len*np.array([np.cos(t), 0, np.sin(t)])
        self.pedal_L = self.bb - (self.pedal_R - self.bb)

    def leg(self, pedal, side, ankle_offset):
        """Hip joint, knee and ankle for one leg. side = -1 right, +1 left."""
        hj = self.hip + [0, side*95, 0]
        ank = pedal + [ankle_offset[0], side*ankle_offset[1], ankle_offset[2]]
        d = ank - hj; Ld = np.linalg.norm(d)
        reach = self.thigh + self.shank
        if Ld > reach:
            raise ValueError(f'leg cannot reach the pedal: {Ld:.0f} mm needed, {reach:.0f} available. '
                             f'saddle_up_mm is too large for a {self.height/10:.0f} cm rider.')
        dh = d/Ld
        a = (Ld**2 + self.thigh**2 - self.shank**2)/(2*Ld)
        h = np.sqrt(max(self.thigh**2 - a**2, 0))
        f = np.array([1., 0, 0]) - dh*dh[0]; f /= np.linalg.norm(f)
        return hj, hj + a*dh + h*f, ank

    # ------------------------------------------------------------------ fit angles ----
    def angles(self, ankle_offset):
        """The angles and coordinates a bike fitter actually reads."""
        def between(a, b, c):    # interior angle at b, in the x-z plane
            u, v = (a - b)[[0, 2]], (c - b)[[0, 2]]
            cs = u.dot(v)/(np.linalg.norm(u)*np.linalg.norm(v))
            return np.degrees(np.arccos(np.clip(cs, -1, 1)))

        hj, knee, ank = self.leg(self.pedal_R, -1, ankle_offset)
        # knee angle at the bottom of the stroke: the classic 140-150 deg fit window
        t = np.radians(-90.0)
        ped_bot = self.bb + self.crank_len*np.array([np.cos(t), 0, np.sin(t)])
        _, knee_b, ank_b = self.leg(ped_bot, -1, ankle_offset)
        t = np.radians(90.0)
        ped_top = self.bb + self.crank_len*np.array([np.cos(t), 0, np.sin(t)])
        hj_t, knee_t, ank_t = self.leg(ped_top, -1, ankle_offset)

        horiz = self.hip + [100, 0, 0]
        setback = self.bb[0] - self.saddle[0]
        sh_vec = self.saddle - self.bb
        return {
            # aero-relevant
            # back_deg is the number read off a photo (the visible back line); torso_deg
            # is hip joint to shoulder joint, which sits steeper because the femoral head
            # is below the skin. Both are reported so neither gets confused for the other.
            'back_deg': round(float(np.degrees(_ang(self.back_high - self.back_low))), 1),
            'torso_deg': round(float(np.degrees(_ang(self.shoulder - self.hip))), 1),
            'forearm_deg': round(float(np.degrees(_ang(self.hands - self.elbow))), 1),
            'trunk_pitch_vs_photo_deg': round(float(self.trunk_pitch), 2),
            # joint angles
            'hip_closed_deg': round(float(between(self.shoulder, hj_t, knee_t)), 1),
            'knee_bottom_deg': round(float(between(hj, knee_b, ank_b)), 1),
            'shoulder_deg': round(float(between(self.hip, self.shoulder, self.elbow)), 1),
            'elbow_deg': round(float(between(self.shoulder, self.elbow, self.hands)), 1),
            # fit coordinates, all relative to the bottom bracket
            'saddle_height_mm': round(float(np.linalg.norm(sh_vec)), 1),
            'saddle_setback_mm': round(float(setback), 1),
            'effective_sta_deg': round(float(np.degrees(np.arctan2(sh_vec[2], -sh_vec[0]))), 1),
            'pad_stack_mm': round(float(self.pad[2] - self.bb[2]), 1),
            'pad_reach_mm': round(float(self.pad[0] - self.bb[0]), 1),
            'saddle_to_pad_drop_mm': round(float(self.saddle[2] - self.pad[2]), 1),
            'grip_rise_mm': round(float(self.hands[2] - self.pad[2]), 1),
        }

    def segment_report(self):
        h = self.height
        return {
            'trunk_photo_mm': round(float(self.trunk_len), 1),
            'trunk_winter_mm': round(WINTER['trunk']*h, 1),
            'upper_arm_photo_mm': round(float(self.upper_arm), 1),
            'upper_arm_winter_mm': round(WINTER['upper_arm']*h, 1),
            'forearm_photo_mm': round(float(self.forearm), 1),
            'forearm_winter_mm': round(WINTER['forearm']*h, 1),
            'thigh_winter_mm': round(self.thigh, 1),
            'shank_winter_mm': round(self.shank, 1),
            'forearm_residual_mm': round(float(self.forearm_resid), 1),
        }


def solve_hip_drop(L, X3, height_mm, fit, ankle_offset, target_deg=145.0,
                   lo=0.0, hi=120.0, tol=0.15):
    """Find how far below the surface hip landmark the femoral head sits.

    Solved from the knee angle at bottom dead centre rather than guessed, because that
    angle is the best-established number in fitting (140-150 deg) while the offset is
    invisible in a photo. Returns (hip_drop_mm, achieved_knee_angle_deg).

    Call this ONCE, at the baseline fit. The offset is anatomy, so it must stay fixed as
    the fit changes -- re-solving it per position would quietly hide the thing you want to
    see, namely that a saddle change has pushed the knee angle out of the fit window.
    """
    def knee_at(d):
        try:
            return Pose(L, X3, height_mm, fit, d).angles(ankle_offset)['knee_bottom_deg']
        except ValueError:
            return 180.0        # leg cannot reach: the joint centre must sit lower still

    if knee_at(lo) < target_deg:        # already flexed enough without any offset
        return lo, knee_at(lo)
    for _ in range(40):
        mid = 0.5*(lo + hi)
        if knee_at(mid) > target_deg:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    d = 0.5*(lo + hi)
    return round(d, 1), knee_at(d)
