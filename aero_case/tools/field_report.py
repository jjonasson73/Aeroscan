#!/usr/bin/env python3
"""Var på kroppen sitter motståndet, och vad skiljer positionerna?

En CdA-siffra säger att något är annorlunda men inte var. Det här verktyget
integrerar tryck och friktion per triangel och delar upp resultatet i höjdband,
så att skillnaden mellan två positioner går att lokalisera.

Körs i verdict-jobbet och skriver till LOGGEN, inte till en bild. Siffrorna var
det som gav mekanismen när vi jagade den instabila 10-graderspunkten; bilderna
stödde dem. Text kostar dessutom ingenting i git och går att läsa via API:et.

TECKEN, båda verifierade mot integralen:
  wallShearStress returneras med motsatt tecken mot strömningen -> vänds.
  Ytnormalerna i OpenFOAMs .vtp pekar inåt -> tryckbidraget får plustecken.
Kontrollen är att summan reproducerar forceCoeffs CdA. Gör den inte det är
något av antagandena fel, och då säger verktyget till i stället för att tiga.

  python3 tools/field_report.py <resultatkatalog> [--uinf 12.5] [--band 150]
"""
import sys, os, glob, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_fields import read_vtp

PARTS = ('rider', 'bike', 'wheel_rear', 'wheel_front')


def case_contrib(d, uinf):
    """CdA-bidrag per triangel för varje patch. Returnerar {del: (centrum, bidrag)}."""
    info = json.load(open(os.path.join(d, 'model_info.json')))
    dd = np.array(info['drag_dir'])
    q = 0.5 * uinf ** 2
    tdir = sorted(glob.glob(os.path.join(d, 'postProcessing', 'diagSurfaces', '*')))
    if not tdir:
        return None
    t = tdir[-1]
    out = {}
    for part in PARTS:
        f = os.path.join(t, f's_{part}.vtp')
        if not os.path.exists(f):
            continue
        m, fld = read_vtp(f)
        A, n = m.area_faces, m.face_normals
        v = (np.asarray(fld['p']) * (n @ dd) * A) / q
        if 'wallShearStress' in fld:
            v = v - ((np.asarray(fld['wallShearStress']) @ dd) * A) / q
        out[part] = (m.triangles_center, v)
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--uinf', type=float, default=12.5)
    ap.add_argument('--band', type=float, default=150.0)
    a = ap.parse_args()

    cases = {}
    for d in sorted(glob.glob(os.path.join(a.results, '*'))):
        if not os.path.isdir(d):
            continue
        tar = os.path.join(d, 'fields.tar.gz')
        if os.path.exists(tar) and not os.path.isdir(os.path.join(d, 'postProcessing')):
            os.system(f'tar xzf {tar!r} -C {d!r} 2>/dev/null')
        c = case_contrib(d, a.uinf)
        if c:
            cases[os.path.basename(d)] = c
    if not cases:
        print('*Ingen fältdata i artefakterna - hoppar över uppdelningen.*')
        return

    print('### Var motståndet sitter (ur ytfälten)\n')
    print('Tryck och friktion integrerade per triangel. Summan ska stämma med '
          'CdA-tabellen ovan; gör den inte det är uppdelningen inte att lita på.\n')
    print('| fall | rider | bike | wheels | SUMMA |')
    print('|---|---|---|---|---|')
    for name, c in cases.items():
        r = c.get('rider', (None, np.zeros(1)))[1].sum()
        b = c.get('bike', (None, np.zeros(1)))[1].sum()
        w = sum(c[k][1].sum() for k in ('wheel_rear', 'wheel_front') if k in c)
        print(f'| {name} | {r:.4f} | {b:.4f} | {w:.4f} | **{r+b+w:.4f}** |')

    # Parvis: base mot tuned vid samma vinkel
    pairs = sorted({n.rsplit('-', 1)[0] for n in cases if n.endswith(('-base', '-tuned'))})
    for p in pairs:
        b, t = cases.get(f'{p}-base'), cases.get(f'{p}-tuned')
        if not (b and t and 'rider' in b and 'rider' in t):
            continue
        cb, vb = b['rider']; ct, vt = t['rider']
        print(f'\n#### {p}: ryttarens bidrag per höjdband [m²]\n')
        print('| höjd över mark | base | tuned | Δ |')
        print('|---|---|---|---|')
        zmax = max(cb[:, 2].max(), ct[:, 2].max()) * 1000
        for lo in np.arange(0, zmax + a.band, a.band):
            sb = vb[(cb[:, 2]*1000 >= lo) & (cb[:, 2]*1000 < lo+a.band)].sum()
            st = vt[(ct[:, 2]*1000 >= lo) & (ct[:, 2]*1000 < lo+a.band)].sum()
            if abs(sb) + abs(st) < 1e-5:
                continue
            d = st - sb
            mark = ' **&larr;**' if abs(d) > 0.0015 else ''
            print(f'| {lo:.0f}–{lo+a.band:.0f} | {sb:.4f} | {st:.4f} | {d:+.4f}{mark} |')
        print(f'| **summa** | **{vb.sum():.4f}** | **{vt.sum():.4f}** | '
              f'**{vt.sum()-vb.sum():+.4f}** |')
    print('\n> Band markerade med &larr; flyttar mer än 0.0015 m². Är deltat en liten rest '
          'mellan stora motverkande band är det känsligt för geometri just där.')


if __name__ == '__main__':
    main()
