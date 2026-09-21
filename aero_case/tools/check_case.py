"""Guard the couplings the README calls out, before burning an Actions runner on them.

Checks that 0/U's rotatingWallVelocity origins and axes, and controlDict's dragDir, still
agree with the geometry build_model.py produced, and that the geometry/ STLs OpenFOAM will
read are closed surfaces. Exits non-zero with a specific message on the first failure.

Yaw: build_model.py can turn the machine about the vertical axis, and tools/configure_case.sh
then rotates the axle origins, the wheel axes and dragDir to match. This script runs BEFORE
that, so at a non-zero yaw it expects to find the case still in its shipped straight-ahead
state and says so, rather than failing on a mismatch that is about to be fixed. What it will
not accept is a case that matches neither -- that is real drift.
"""
import json, math, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
info = json.load(open(HERE / 'model_info.json'))
yaw = float(info.get('yaw_deg', 0.0))
fail, pending = [], []


def unyaw(v):
    """Turn a vector back to the straight-ahead frame, i.e. what the shipped case holds."""
    c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))
    return [v[0]*c - v[1]*s, v[0]*s + v[1]*c, v[2]]


def close(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) <= 1e-3


def compare(what, got, want):
    if close(got, want):
        print(f'ok   {what} {[round(v, 4) for v in got]}')
    elif yaw and close(got, unyaw(want)):
        pending.append(what)
    else:
        fail.append(f'{what} is {got}, model says {want}; rebuild from build_model.py')


src = (HERE / '0' / 'U').read_text()
for patch, key in (('wheel_rear', 'axle_rear_m'), ('wheel_front', 'axle_front_m')):
    blk = src.split(patch, 1)[1]
    for field, want in (('origin', info[key]), ('axis', info['wheel_axis'])):
        got = [float(v) for v in re.search(rf'{field}\s+\(([^)]*)\)', blk).group(1).split()]
        compare(f'0/U {patch} {field}', got, want)

# dragDir decides which component of the force is reported as drag. At yaw the travel axis
# and the wind axis diverge, and only the travel-axis component costs the rider watts, so a
# stale (1 0 0) here does not crash anything -- it just answers a different question.
cd = (HERE / 'system' / 'controlDict').read_text()
got = [float(v) for v in re.search(r'dragDir\s+\(([^)]*)\)', cd).group(1).split()]
compare('system/controlDict dragDir', got, info['drag_dir'])

if pending:
    print(f'note {len(pending)} poster ligger kvar i rak riktning och roteras till '
          f'yaw {yaw:+.1f} grader av tools/configure_case.sh:')
    for w in pending:
        print(f'       {w}')
    print('     ./Allrun på egen hand gör INTE den rotationen -- kör configure_case.sh först.')

try:
    import trimesh
except ImportError:
    print('skip STL check (trimesh not installed)')
else:
    def open_edges(m):
        paired = trimesh.grouping.group_rows(m.edges_sorted, require_count=2)
        return len(m.edges_sorted) - 2*len(paired)

    for name in ('rider', 'bike', 'wheel_rear', 'wheel_front'):
        m = trimesh.load(HERE / 'geometry' / f'{name}.stl')
        bad = open_edges(m)
        if not m.is_watertight or bad:
            fail.append(f'geometry/{name}.stl is not closed: {bad} open edges')
        else:
            print(f'ok   geometry/{name}.stl watertight ({len(m.faces)} faces)')

for f in fail:
    print('FAIL', f, file=sys.stderr)
sys.exit(1 if fail else 0)
