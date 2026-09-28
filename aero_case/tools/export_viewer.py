#!/usr/bin/env python3
"""Packa en körnings fält till det format 3D-visaren läser.

Visaren hade fälten inbakade som datafiler och kunde därför bara visa den körning
den publicerades med. Den här exportören gör samma paket per körning, så att
visaren kan hämta vilken körning som helst från results-grenen i stället.

Formatet är inte nytt - det är exakt det visaren redan avkodar:

  <fall>.txt        base64 av: uint32 nv, uint32 nt, uint16[nv*3] positioner,
                    uint16[nt*3] index, uint8[nv] cp, uint8[nv] tau_x
  <fall>-bike.txt   samma utan skalärer (cykel och hjul, grå)
  <fall>-slice.txt  som ryttaren men med uint32-index när nv >= 65536,
                    och skalärerna är fart och turbulens

Positioner kvantiseras till uint16 över meshens egen låda, skalärer till uint8.
256 nivåer räcker när färgskalan har åtta stopp, och hela lasten stannar under
fyra megabyte per körning.

manifest.json bär lo/sc per mesh och de gemensamma färggränserna. Det är den
biten som tidigare låg hårdkodad i HTML:en och som gjorde visaren låst till en
enda körning.
"""
import argparse, base64, glob, json, os, struct, sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vtp import read_vtp

RIDER_FACES = 28000        # uint16-index kräver < 65536 hörn; 28k trianglar ger ~14k
BIKE_FACES = 16000         # gra utan skalarer, sa den behover inte ryttarens upplosning
SLICE_MAX_EDGE = 0.09      # m

# Snittet beskärs relativt ryttarens centrum, inte i världskoordinater, så att
# beskärningen följer kroppen när geometrin vrids vid yaw.
SLICE_X = (-1.30, 2.90)
SLICE_Z = (0.00, 1.90)


def face_to_vertex(mesh, vals):
    """Medelvarde av de trianglar som ror hornet.

    OpenFOAMs surfaces-objekt skriver fälten PER TRIANGEL - p, wallShearStress, U
    och k har alla lika manga varden som meshen har trianglar, inte horn. Visaren
    fargar per horn. Utan den har omraekningen indexeras triangelvarden med
    hornindex, vilket ger ett slumpmonster som ser ut som brus pa kroppen.
    """
    f = np.asarray(mesh.faces).ravel()
    nv = len(mesh.vertices)
    vals = np.asarray(vals, float)
    cnt = np.bincount(f, minlength=nv)
    s = np.bincount(f, weights=np.repeat(vals, 3), minlength=nv)
    return s / np.maximum(cnt, 1)


def quant_pos(v):
    """uint16 över meshens egen låda. Returnerar (packat, lo, sc)."""
    lo = v.min(0)
    sc = v.max(0) - lo
    sc[sc <= 0] = 1e-9          # platt axel (snittplanet i y) ger division med noll
    q = np.rint((v - lo) / sc * 65535).clip(0, 65535).astype('<u2')
    return q, lo, sc


def pack(v, f, scalars=()):
    """Visarens binärlayout. Index blir uint32 först när hörnen inte ryms i uint16."""
    q, lo, sc = quant_pos(v)
    big = len(v) >= 65536
    idx = f.astype('<u4' if big else '<u2')
    buf = struct.pack('<II', len(v), len(f)) + q.tobytes() + idx.tobytes()
    for s in scalars:
        buf += s.tobytes()
    return base64.b64encode(buf).decode('ascii'), lo, sc


def to_u8_sym(v, lim):
    """Symmetrisk skalär kring noll. Visaren avkodar (q/255-0.5)*2*lim."""
    return np.rint((v / lim / 2 + 0.5) * 255).clip(0, 255).astype(np.uint8)


def to_u8_seq(v, lim):
    """Sekventiell skalär från noll. Visaren avkodar q/255*lim."""
    return np.rint(v / lim * 255).clip(0, 255).astype(np.uint8)


def decimate(mesh, target, values):
    """Decimera och flytta med skalärerna via närmaste ursprungliga hörn.

    Decimeringen skapar nya hörn, så skalärerna kan inte följa med av sig själva.
    Närmaste granne räcker: de nya hörnen ligger på den gamla ytan, och fälten är
    släta på den skala decimeringen arbetar.
    """
    if len(mesh.faces) <= target:
        return mesh, values
    d = mesh.simplify_quadric_decimation(face_count=target)
    if not values:
        return d, values
    from scipy.spatial import cKDTree
    _, j = cKDTree(np.asarray(mesh.vertices)).query(np.asarray(d.vertices))
    return d, [v[j] for v in values]


def load_surface(case, names):
    """Läs och slå ihop patchar. Returnerar (mesh, fält) eller (None, None)."""
    meshes, fields = [], []
    for n in names:
        g = glob.glob(os.path.join(case, 'postProcessing', 'diagSurfaces', '*', f'{n}.vtp'))
        if not g:
            continue
        m, f = read_vtp(sorted(g)[-1])
        meshes.append(m)
        fields.append(f)
    if not meshes:
        return None, None
    if len(meshes) == 1:
        return meshes[0], fields[0]
    merged = trimesh.util.concatenate(meshes)
    keys = set(fields[0])
    for f in fields[1:]:
        keys &= set(f)
    return merged, {k: np.concatenate([np.asarray(f[k]) for f in fields]) for k in keys}


def crop_slice(mesh, centre):
    """Beskär snittet och släng trianglar som spänner över kroppens hål.

    Utan kantfiltret ritas kroppen som ett mörkt streck: cuttingPlane lämnar ett
    hål där kroppen är, och trianguleringen broar över det med några få mycket
    långa trianglar.
    """
    v = np.asarray(mesh.vertices)
    f = np.asarray(mesh.faces)
    x, z = v[:, 0] - centre[0], v[:, 2]
    inside = ((x >= SLICE_X[0]) & (x <= SLICE_X[1]) &
              (z >= SLICE_Z[0]) & (z <= SLICE_Z[1]))
    f = f[inside[f].all(axis=1)]
    e = np.stack([np.linalg.norm(v[f[:, a]] - v[f[:, b]], axis=1)
                  for a, b in ((0, 1), (1, 2), (2, 0))], axis=1)
    f = f[e.max(axis=1) <= SLICE_MAX_EDGE]
    keep = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[keep] = np.arange(len(keep))
    return keep, remap[f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results'); ap.add_argument('out')
    ap.add_argument('--uinf', type=float, default=12.5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    q = 0.5 * a.uinf ** 2

    raw, order = {}, []
    for d in sorted(glob.glob(os.path.join(a.results, '*'))):
        if not os.path.isdir(os.path.join(d, 'postProcessing')):
            continue
        case = os.path.basename(d)
        rm, rf = load_surface(d, ['s_rider'])
        if rm is None:
            print(f'{case}: ingen ryttaryta, hoppas över', file=sys.stderr)
            continue
        centre = (np.asarray(rm.vertices).min(0) + np.asarray(rm.vertices).max(0)) / 2
        # Skalarerna raknas per triangel och laggs sedan om till horn.
        cp = face_to_vertex(rm, np.asarray(rf['p']) / q)
        tx = face_to_vertex(rm, -np.asarray(rf['wallShearStress'])[:, 0]) \
            if 'wallShearStress' in rf else np.zeros(len(rm.vertices))
        bm, _ = load_surface(d, ['s_bike', 's_wheel_front', 's_wheel_rear'])

        sm = su = sk = None
        g = glob.glob(os.path.join(d, 'postProcessing', 'diagSlice', '*', '*.vtp'))
        if g:
            sm, sf = read_vtp(sorted(g)[-1])
            su = face_to_vertex(sm, np.linalg.norm(np.asarray(sf['U']), axis=1) / a.uinf)
            sk = face_to_vertex(sm, np.asarray(sf['k']))

        raw[case] = dict(rm=rm, cp=cp, tx=tx, bm=bm, sm=sm, su=su, sk=sk, centre=centre)
        order.append(case)
        print(f'{case}: ryttare {len(rm.faces):,} tri'
              + (f', cykel {len(bm.faces):,} tri' if bm is not None else ', ingen cykel')
              + (f', snitt {len(sm.faces):,} tri' if sm is not None else ', inget snitt'))

    if not order:
        print('inga fall med fältdata', file=sys.stderr)
        return 1

    # Färggränserna måste vara GEMENSAMMA för alla fall, annars betyder samma färg
    # olika saker när man växlar mellan dem och jämförelsen blir meningslös.
    lim = dict(
        cp=float(np.percentile(np.abs(np.concatenate([r['cp'] for r in raw.values()])), 99)),
        tx=float(np.percentile(np.abs(np.concatenate([r['tx'] for r in raw.values()])), 99)),
        u=float(np.percentile(np.concatenate(
            [r['su'] for r in raw.values() if r['su'] is not None]), 99.5))
        if any(r['su'] is not None for r in raw.values()) else 1.35,
        k=float(np.percentile(np.concatenate(
            [r['sk'] for r in raw.values() if r['sk'] is not None]), 99))
        if any(r['sk'] is not None for r in raw.values()) else 1.0,
    )

    man = dict(cases=order, lim={k: round(v, 4) for k, v in lim.items()},
               uinf=a.uinf, rider={}, bike={}, slice={})
    total = 0
    for case in order:
        r = raw[case]
        c = r['centre']

        rm, (cp, tx) = decimate(r['rm'], RIDER_FACES, [r['cp'], r['tx']])
        v = np.asarray(rm.vertices) - c
        s, lo, sc = pack(v, np.asarray(rm.faces),
                         [to_u8_sym(cp, lim['cp']), to_u8_sym(tx, lim['tx'])])
        total += _write(a.out, f'{case}.txt', s)
        man['rider'][case] = _meta(lo, sc)

        if r['bm'] is not None:
            bm, _ = decimate(r['bm'], BIKE_FACES, [])
            v = np.asarray(bm.vertices) - c
            s, lo, sc = pack(v, np.asarray(bm.faces))
            total += _write(a.out, f'{case}-bike.txt', s)
            man['bike'][case] = _meta(lo, sc)

        if r['sm'] is not None:
            keep, f = crop_slice(r['sm'], c)
            v = np.asarray(r['sm'].vertices)[keep] - c
            s, lo, sc = pack(v, f, [to_u8_seq(r['su'][keep], lim['u']),
                                    to_u8_seq(r['sk'][keep], lim['k'])])
            total += _write(a.out, f'{case}-slice.txt', s)
            man['slice'][case] = _meta(lo, sc)

    json.dump(man, open(os.path.join(a.out, 'manifest.json'), 'w'), indent=1)
    print(f'visardata klar, {total/1e6:.1f} MB över {len(order)} fall')
    return 0


def _write(out, name, s):
    p = os.path.join(out, name)
    open(p, 'w').write(s)
    return os.path.getsize(p)


def _meta(lo, sc):
    return dict(lo=[round(float(x), 5) for x in lo], sc=[round(float(x), 5) for x in sc])


if __name__ == '__main__':
    sys.exit(main())
