"""Sweep one fit parameter and tabulate what it does to the geometry.

    python tools/fit_sweep.py pad_drop_mm -30 -20 -10 0 10

Prints frontal area, the fit angles, and the estimated Delta-CdA for each value, without
meshing anything. Use it to pick which positions are worth an Actions run: a change that
does not move the frontal area or the back angle is not worth six hours of CFD.

The CdA estimate assumes Cd stays constant (CdA/A ~ 0.69 for a TT rider), so it is a
screening number only -- the whole reason to run the CFD is that Cd does NOT stay constant.
"""
import json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
CD_OVER_A = 0.69


def run(param, value):
    r = subprocess.run([sys.executable, 'build_model.py', f'{param}={value}'],
                       cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        last = [x for x in r.stderr.strip().splitlines() if x.strip()][-1]
        return last.split(':', 1)[-1].strip()      # the pose solver's own message
    return json.load(open(HERE / 'model_info.json'))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    param, values = sys.argv[1], sys.argv[2:]
    rows, base = [], None
    for v in values:
        info = run(param, v)
        if isinstance(info, str):
            rows.append((v, None, info)); continue
        area = info['frontal_area_m2']
        if base is None or float(v) == 0:
            base = area
        rows.append((v, area, info['fit_angles']))

    print(f"\n{param} sweep   (frontarea, vinklar, screening-CdA)\n")
    hdr = f"{param:>14s} {'A [m2]':>8s} {'dA':>8s} {'dA %':>7s} {'~dCdA':>8s} " \
          f"{'rygg':>6s} {'bål':>6s} {'axel':>6s} {'armbåge':>8s} {'höft':>6s} {'knä':>6s}"
    print(hdr); print('-'*len(hdr))
    for v, area, a in rows:
        if area is None:
            print(f"{v:>14s}   -- {a}"); continue
        d = area - base
        print(f"{v:>14s} {area:8.4f} {d:+8.4f} {d/base*100:+6.2f}% {d*CD_OVER_A:+8.4f} "
              f"{a['back_deg']:5.1f}° {a['torso_deg']:5.1f}° {a['shoulder_deg']:5.1f}° "
              f"{a['elbow_deg']:7.1f}° {a['hip_closed_deg']:5.1f}° {a['knee_bottom_deg']:5.1f}°")
    print(f"\nbaseline A = {base:.4f} m2;  ~dCdA antar Cd konstant (CdA/A = {CD_OVER_A})")
    run(param, 0)      # leave geometry/ at the baseline, never at the last swept value
    print("geometry/ återställd till baseline.")
