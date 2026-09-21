"""Guard the couplings the README calls out, before burning an Actions runner on them.

Checks that 0/U's rotatingWallVelocity origins still sit on the axles build_model.py
produced, and that the geometry/ STLs OpenFOAM will read are closed surfaces.
Exits non-zero with a specific message on the first failure.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent.parent
info = json.load(open(HERE / 'model_info.json'))
fail = []

src = (HERE / '0' / 'U').read_text()
for patch, key in (('wheel_rear', 'axle_rear_m'), ('wheel_front', 'axle_front_m')):
    blk = src.split(patch, 1)[1]
    got = [float(v) for v in re.search(r'origin\s+\(([^)]*)\)', blk).group(1).split()]
    want = info[key]
    if max(abs(a - b) for a, b in zip(got, want)) > 1e-3:
        fail.append(f'0/U {patch} origin {got} != model {want}; rebuild from build_model.py')
    else:
        print(f'ok   0/U {patch} origin {got}')

try:
    import trimesh
except ImportError:
    print('skip STL check (trimesh not installed)')
else:
    for name in ('rider', 'bike', 'wheel_rear', 'wheel_front'):
        m = trimesh.load(HERE / 'geometry' / f'{name}.stl')
        broken = len(trimesh.repair.broken_faces(m))
        if not m.is_watertight or broken:
            fail.append(f'geometry/{name}.stl is not closed: {broken} broken faces')
        else:
            print(f'ok   geometry/{name}.stl watertight ({len(m.faces)} faces)')

for f in fail:
    print('FAIL', f, file=sys.stderr)
sys.exit(1 if fail else 0)
