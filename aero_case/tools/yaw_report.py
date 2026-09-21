"""Sammanställ ett yaw-svep och räkna om det till något man kan känna på pedalerna.

    python tools/yaw_report.py <katalog> [fönster] [åkfart km/h]

Katalogen innehåller artefakter namngivna y<vinkel>-<position>, t.ex. y0-base, y-10-tuned.

Varför inte bara en CdA-per-vinkel-tabell: ingen åker på en fast yaw-vinkel. Vinkeln följer
av åkfarten och vinden, och på ett varv möter man alla vindriktningar. Det som avgör hur
mycket vinden kostar är medeleffekten över varvet, och den väger ihop två saker som drar åt
motsatt håll -- CdA växer med yaw, men skenbara vinden är svag i medvind och stark i motvind.
Därför räknas svepet om till ett CdA_eff, det CdA som i stilla luft hade kostat lika mycket.

    P_luft = 0.5 * rho * CdA(beta) * v_air^2 * V        (kraften verkar längs färdriktningen)
    CdA_eff = medel_phi[ CdA(beta) * v_air^2 ] / V^2

där phi är vindriktningen i förhållande till färdriktningen, likformigt fördelad över varvet.
"""
import glob
import pathlib
import sys

import numpy as np


def series(path, window):
    d = np.loadtxt(path, comments='#', ndmin=2)
    c = d[-window:, 1]          # kolumn 1 = Cd; Aref = 1, alltså CdA i m²
    return c.mean(), c.std(), int(d[-1, 0])


def collect(root, window):
    runs = {}
    for f in sorted(glob.glob(str(pathlib.Path(root) / '*' / '**' / 'coefficient.dat'),
                              recursive=True)):
        if 'CdA_total' not in f:
            continue
        tag = next((p for p in pathlib.Path(f).parts
                    if p.startswith('y') and p.rsplit('-', 1)[-1] in ('base', 'tuned')), None)
        if tag is None:
            continue
        grp, pos = tag.rsplit('-', 1)
        runs[(float(grp[1:]), pos)] = series(f, window)
    return runs


def curve(runs, pos):
    """CdA(yaw) för en position, som sorterade vinklar och värden."""
    pts = sorted((y, v[0]) for (y, p), v in runs.items() if p == pos)
    return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])


def effective(ang, cda, V_kmh, W_kmh, n=2000):
    """CdA_eff över ett varv i vind W, dvs det stillaluft-CdA som kostar lika mycket."""
    V, W = V_kmh/3.6, W_kmh/3.6
    phi = np.linspace(0, 2*np.pi, n, endpoint=False)
    # Skenbar vind i cyklistens system: åkfarten rakt fram plus vinden.
    vx, vy = V + W*np.cos(phi), W*np.sin(phi)
    v_air = np.hypot(vx, vy)
    beta = np.degrees(np.arctan2(vy, vx))
    # Utanför svepet extrapoleras inte -- np.interp klampar till ändpunkterna. Det
    # underskattar hellre än hittar på en trend som inte är mätt.
    both = ang.min() < 0 < ang.max()
    c = np.interp(beta if both else np.abs(beta), ang, cda)
    return float(np.mean(c * v_air**2) / V**2), both, float(np.percentile(np.abs(beta), 95))


def main(root, window, V_kmh):
    runs = collect(root, window)
    if not runs:
        print('_Inga resultat hittades._')
        return 0

    angles = sorted({y for y, _ in runs})
    positions = [p for p in ('base', 'tuned') if any(q == p for _, q in runs)]

    print(f'### CdA mot yaw (medel över sista {window} iterationerna)\n')
    print('| yaw [°] | ' + ' | '.join(f'{p} CdA [m²]' for p in positions)
          + (' | ΔCdA [m²] | Δ % |' if len(positions) == 2 else ' |'))
    print('|---' * (1 + len(positions) + 2*(len(positions) == 2)) + '|')
    for y in angles:
        cells = []
        for p in positions:
            cells.append(f'{runs[(y, p)][0]:.4f}' if (y, p) in runs else '–')
        row = f'| {y:+.0f} | ' + ' | '.join(cells)
        if len(positions) == 2 and (y, 'base') in runs and (y, 'tuned') in runs:
            b, t = runs[(y, 'base')][0], runs[(y, 'tuned')][0]
            row += f' | {t-b:+.4f} | {(t-b)/b*100:+.2f} % |'
        elif len(positions) == 2:
            row += ' | – | – |'
        else:
            row += ' |'
        print(row)

    print(f'\n### Vad det betyder vid {V_kmh:.0f} km/h\n')
    print('CdA_eff är det stillaluft-CdA som hade kostat lika många watt över ett varv, '
          'alltså vinden inräknad. Vindriktningen antas likformig över varvet.\n')
    head = '| vind [km/h] | typisk yaw [°] | ' + ' | '.join(f'{p} CdA_eff' for p in positions)
    head += ' | ΔCdA_eff | Δ % |' if len(positions) == 2 else ' |'
    print(head)
    print('|---' * (2 + len(positions) + 2*(len(positions) == 2)) + '|')

    warn_clamped = False
    for W in (0, 5, 10, 15, 20):
        vals, typ = {}, None
        for p in positions:
            ang, cda = curve(runs, p)
            if len(ang) < 2:
                continue
            vals[p], both, typ = effective(ang, cda, V_kmh, W)
            if typ > ang.max() + 0.5:
                warn_clamped = True
        if not vals:
            continue
        row = f'| {W} | {typ:.0f} | ' + ' | '.join(f'{vals[p]:.4f}' if p in vals else '–'
                                                   for p in positions)
        if len(positions) == 2 and len(vals) == 2:
            d = vals['tuned'] - vals['base']
            row += f' | {d:+.4f} | {d/vals["base"]*100:+.2f} % |'
        elif len(positions) == 2:
            row += ' | – | – |'
        else:
            row += ' |'
        print(row)

    print('\n### Läsanvisning\n')
    print('- "typisk yaw" är 95:e percentilen av |yaw| över varvet, inte medelvärdet – '
          'medelvärdet är nära noll av symmetriskäl och säger ingenting.')
    ang_b, _ = curve(runs, positions[0])
    if not (ang_b.min() < 0 < ang_b.max()):
        print('- ⚠ Bara **en sida** av noll är körd, så kurvan speglas. Cyklisten är inte '
              'spegelsymmetrisk – ett ben är fram, kedjan sitter på höger sida – så äkta '
              '+beta och −beta skiljer sig. Kör båda tecknen innan du litar på siffran.')
    if warn_clamped:
        print(f'- ⚠ Vinden driver ut yaw förbi svepets yttersta punkt ({ang_b.max():+.0f}°). '
              'Där klampas CdA till ändvärdet i stället för att extrapoleras, vilket '
              '**underskattar** kostnaden av de starkaste vindarna.')
    print('- Enskilda körningar bär samma slumpmässiga spridning som tidigare mätts till '
          '0.0010 m² (0.5 %). En skillnad mellan två positioner som är mindre än ungefär '
          '0.0014 m² går inte att skilja från brus på en enda replik per punkt.')
    print('- Marken rör sig med luften, inte med cykeln. Vid yaw är det inte riktigt rätt – '
          'en rullande väg kan inte vridas – men alternativet, stillastående mark, ger ett '
          'falskt gränsskikt över hela golvet och är sämre.')
    return 0


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'results'
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    spd = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    sys.exit(main(root, win, spd))
