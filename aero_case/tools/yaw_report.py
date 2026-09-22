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
    """Medelvärde, svängningsamplitud och drift över medelvärdesfönstret.

    std är inte ett mätfel utan hur mycket kraften rör sig INOM fönstret. Vid yaw är
    avlösningen kraftigt asymmetrisk och simpleFoam landar inte alltid på ett stationärt
    tillstånd - kraften fortsätter svänga. Medelvärdet över 150 iterationer blir då ett
    stickprov ur svängningen, inte ett konvergerat värde, och två körningar av samma case
    kan hamna långt ifrån varandra utan att något är fel på någondera.

    drift jämför fönstrets första och andra halva. Är den stor i förhållande till std lutar
    signalen fortfarande - körningen var inte klar, den var avbruten.
    """
    d = np.loadtxt(path, comments='#', ndmin=2)
    c = d[-window:, 1]          # kolumn 1 = Cd; Aref = 1, alltså CdA i m²
    h = len(c)//2
    return c.mean(), c.std(), float(c[h:].mean() - c[:h].mean()), int(d[-1, 0])


PARTS = ('rider', 'bike', 'wheels')


def collect(root, window):
    """Totalen per (vinkel, position), och samma sak uppdelat per kroppsdel.

    Caset räknar ut CdA separat för ryttare, cykel och hjul (fyra forceCoeffs i
    controlDict). Utan uppdelningen säger rapporten att en position är sämre vid yaw men
    inte VAD som är sämre, och det är skillnaden mellan en siffra och något att göra med.
    """
    runs, parts = {}, {}
    for f in sorted(glob.glob(str(pathlib.Path(root) / '*' / '**' / 'coefficient.dat'),
                              recursive=True)):
        tag = next((p for p in pathlib.Path(f).parts
                    if p.startswith('y') and p.rsplit('-', 1)[-1] in ('base', 'tuned')), None)
        if tag is None:
            continue
        grp, pos = tag.rsplit('-', 1)
        yaw = float(grp[1:])
        if 'CdA_total' in f:
            runs[(yaw, pos)] = series(f, window)
        else:
            for part in PARTS:
                if f'CdA_{part}' in f:
                    parts[(yaw, pos, part)] = series(f, window)[0]
    return runs, parts


def breakdown(angles, parts, positions):
    """Var sitter skillnaden mellan positionerna?

    Leder med DELTAT per kroppsdel, inte med nivåerna. Svepet jämför två positioner, och
    bara ryttaren skiljer sig mellan dem - cykel och hjul är identisk geometri. Deras
    yaw-beteende är gemensam mod och hör inte hemma i svaret på vad positionen gör; att
    leda med det gör en enkel jämförelse förvirrande.

    Hjulraden har ändå ett jobb: den är kontrollen. Samma geometri ska ge samma motstånd
    vinkel för vinkel. Skiljer den sig har näten eller körningarna drivit isär.
    """
    if not parts or len(positions) != 2:
        return
    print('\n### Var sitter skillnaden?\n')
    print('ΔCdA per kroppsdel, tuned minus base. Bara ryttaren skiljer sig mellan '
          'positionerna – cykel och hjul är identisk geometri, så deras rader ska ligga '
          'nära noll och är kontrollen på att körningarna inte drivit isär.\n')
    print('| yaw [°] | ' + ' | '.join(PARTS) + ' |')
    print('|---' * (1 + len(PARTS)) + '|')
    drift = []
    for y in angles:
        cells = []
        for part in PARTS:
            a, b = (y, 'base', part), (y, 'tuned', part)
            if a in parts and b in parts:
                d = parts[b] - parts[a]
                cells.append(f'{d:+.4f}')
                if part != 'rider' and abs(d) > 0.0025:
                    drift.append(f'{part} vid {y:+.0f}° ({d:+.4f})')
            else:
                cells.append('–')
        print(f'| {y:+.0f} | ' + ' | '.join(cells) + ' |')
    if drift:
        print(f'\n> ⚠ **{", ".join(drift)}** skiljer sig trots identisk geometri. Antingen '
              'ändrar ryttarens position flödet ner över cykeln, eller så har näten drivit '
              'isär. Med en replik per punkt går det inte att avgöra vilket.')

    # Nivåerna och yaw-beteendet per del: bakgrund, inte svaret på positionsfrågan.
    base_ang = min(angles, key=abs)
    others = [y for y in angles if y != base_ang]
    if not others:
        return
    print(f'\n<details><summary>Bakgrund: vad yaw gör med varje del i sig '
          f'(ändring från {base_ang:+.0f}°, negativt = vinst)</summary>\n')
    print('| yaw [°] | del | ' + ' | '.join(positions) + ' |')
    print('|---' * (2 + len(positions)) + '|')
    for y in others:
        for part in PARTS:
            cells = []
            for p in positions:
                a, b = (base_ang, p, part), (y, p, part)
                cells.append(f'{parts[b] - parts[a]:+.4f}'
                             if a in parts and b in parts else '–')
            print(f'| {y:+.0f} | {part} | ' + ' | '.join(cells) + ' |')
    print('\nSumman av delarna är inte exakt totalen – delarna påverkar varandras flöde.')
    print('\n</details>')


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
    runs, parts = collect(root, window)
    if not runs:
        print('_Inga resultat hittades._')
        return 0

    angles = sorted({y for y, _ in runs})
    positions = [p for p in ('base', 'tuned') if any(q == p for _, q in runs)]

    print(f'### CdA mot yaw (medel över sista {window} iterationerna)\n')
    print('| yaw [°] | ' + ' | '.join(f'{p} CdA ± svängning' for p in positions)
          + (' | ΔCdA [m²] |' if len(positions) == 2 else ' |'))
    print('|---' * (1 + len(positions) + (len(positions) == 2)) + '|')
    unresolved, drifting = [], []
    for y in angles:
        cells = []
        for p in positions:
            if (y, p) in runs:
                mu, sd, dr, _ = runs[(y, p)]
                cells.append(f'{mu:.4f} ± {sd:.4f}')
                if abs(dr) > sd:
                    drifting.append(f'{p} vid {y:+.0f}°')
            else:
                cells.append('–')
        row = f'| {y:+.0f} | ' + ' | '.join(cells)
        if len(positions) == 2 and (y, 'base') in runs and (y, 'tuned') in runs:
            b, sb = runs[(y, 'base')][0], runs[(y, 'base')][1]
            t, st = runs[(y, 'tuned')][0], runs[(y, 'tuned')][1]
            # Svängningen i de två körningarna adderas i kvadratur. Det är en grov gräns:
            # punkterna i fönstret är starkt autokorrelerade, så detta är snarare
            # svängningens bredd än ett standardfel. Men är deltat mindre än så finns det
            # ingenting att rapportera.
            u = float(np.hypot(sb, st))
            flag = ' ⚠' if abs(t - b) < u else ''
            row += f' | {t-b:+.4f} ± {u:.4f}{flag} |'
            if abs(t - b) < u:
                unresolved.append(f'{y:+.0f}°')
        elif len(positions) == 2:
            row += ' | – |'
        else:
            row += ' |'
        print(row)

    if unresolved or drifting:
        print()
        if unresolved:
            print(f'> ⚠ **Deltat är mindre än svängningen vid {", ".join(unresolved)}.** '
                  'Där finns ingen mätbar skillnad mellan positionerna – siffran i tabellen '
                  'är ett stickprov ur svängningen, inte ett resultat.')
        if drifting:
            print(f'> ⚠ **Kraften lutar fortfarande i fönstret för {", ".join(drifting)}.** '
                  'Körningen var inte konvergerad utan avbruten vid iterationsgränsen. '
                  'Kör fler iterationer eller medelvärdesbilda över ett längre fönster.')

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
            vals[p], _both, typ = effective(ang, cda, V_kmh, W)
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

    breakdown(angles, parts, positions)

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
    print('- Spridningen mellan separata körningar av identisk geometri mättes vid 0° till '
          '0.0010 m² (0.5 %). Den gäller ett fall som konvergerar. Svänger kraften vid yaw '
          'är spridningen mellan körningar större än så, och ± i tabellen ovan är då den '
          'siffra att gå på – inte 0.0010.')
    print('- Marken rör sig med luften, inte med cykeln. Vid yaw är det inte riktigt rätt – '
          'en rullande väg kan inte vridas – men alternativet, stillastående mark, ger ett '
          'falskt gränsskikt över hela golvet och är sämre.')
    return 0


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'results'
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    spd = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    sys.exit(main(root, win, spd))
