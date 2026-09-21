"""Sammanställ ΔCdA över flera körningsgrupper.

    python tools/delta_report.py <katalog> [fönster] [gruppetikett]

Katalogen innehåller artefakter namngivna <grupp>-<position>, där position är base eller
tuned. Grupperna är antingen nätnivåer (coarse, medium) eller repliker (r1, r2).

Två olika frågor beroende på vad grupperna är:

  nätnivåer  - är deltat nätkonvergerat? Absolutvärdena får skilja sig; det är SKILLNADEN
               mellan positionerna som ska hålla.
  repliker   - hur stor är den slumpmässiga spridningen? Identiska case reproduceras inte
               exakt, eftersom parallell dekomposition och MPI-reduktion inte är
               bitreproducerbara. Med repliker blir deltat ett medelvärde med felstapel
               i stället för en enda siffra utan osäkerhet.
"""
import glob
import pathlib
import sys

import numpy as np


def series(path, window):
    d = np.loadtxt(path, comments='#', ndmin=2)
    c = d[-window:, 1]          # kolumn 1 = Cd; Aref = 1, alltså CdA i m²
    return c.mean(), c.std(), int(d[-1, 0])


def main(root, window, label):
    runs = {}
    for f in sorted(glob.glob(str(pathlib.Path(root) / '*' / '**' / 'coefficient.dat'),
                              recursive=True)):
        if 'CdA_total' not in f:
            continue
        tag = next(p for p in pathlib.Path(f).parts
                   if '-' in p and p.rsplit('-', 1)[-1] in ('base', 'tuned'))
        grp, pos = tag.rsplit('-', 1)
        runs[(grp, pos)] = series(f, window)

    groups = sorted({g for g, _ in runs})
    if not groups:
        print('_Inga resultat hittades._')
        return 0

    print(f'### CdA per körning (medel över sista {window} iterationerna)\n')
    print(f'| {label} | position | CdA [m²] | std | spridning | iter |')
    print('|---|---|---|---|---|---|')
    for g in groups:
        for p in ('base', 'tuned'):
            if (g, p) in runs:
                mu, sd, it = runs[(g, p)]
                print(f'| {g} | {p} | {mu:.4f} | {sd:.4f} | {abs(sd/mu)*100:.2f} % | {it} |')

    deltas = {g: runs[(g, 'tuned')][0] - runs[(g, 'base')][0]
              for g in groups if (g, 'base') in runs and (g, 'tuned') in runs}
    if not deltas:
        print('\n**Ofullständigt** – varje grupp behöver både base och tuned.')
        return 1

    print(f'\n### ΔCdA per {label}\n')
    print(f'| {label} | ΔCdA [m²] | Δ % |')
    print('|---|---|---|')
    for g, d in deltas.items():
        print(f'| {g} | {d:+.4f} | {d/runs[(g, "base")][0]*100:+.2f} % |')

    if len(deltas) < 2:
        print(f'\n**Bara en {label}** – inget att jämföra mot. Kör minst två för ett utslag.')
        return 1

    vals = np.array(list(deltas.values()))
    spread = vals.max() - vals.min()
    ref = np.abs(vals).max()
    rel = spread/ref*100 if ref else float('inf')
    noise = max(runs[(g, p)][1] for g in deltas for p in ('base', 'tuned'))

    print('\n### Utslag\n')
    print(f'- ΔCdA per {label}: ' + ', '.join(f'{g} {d:+.4f}' for g, d in deltas.items()))
    if label == 'replik':
        # Med repliker är medelvärdet svaret och spridningen felstapeln.
        se = vals.std(ddof=1)/np.sqrt(len(vals))
        print(f'- **Medelvärde ΔCdA = {vals.mean():+.4f} ± {se:.4f} m²** '
              f'(standardfel över {len(vals)} repliker)')
        print(f'- Spridning mellan repliker: {spread:.4f} m²')
        print(f'- Konvergensbrus inom en körning (största std): {noise:.4f} m²')
        if len(vals) == 2:
            print('- ⚠ Standardfelet är räknat ur **två** punkter och är därför självt mycket '
                  'osäkert. Råkar de två replikerna hamna nära varandra ser deltat mer '
                  'signifikant ut än det är. Tre repliker ger ett rimligt felstapel; två ger '
                  'framför allt en sanity-check på att spridningen är i förväntad storlek '
                  '(vi har mätt upp 0.0010–0.0014 m² mellan separata körningar).')
        if abs(vals.mean()) > 3*se and se > 0:
            print(f'\n**SIGNIFIKANT.** Deltat är {abs(vals.mean())/se:.1f} gånger sitt '
                  f'standardfel. Ändringen går att mäta med det här upplägget.')
        elif abs(vals.mean()) > 2*se and se > 0:
            print(f'\n**SVAG SIGNAL.** Deltat är bara {abs(vals.mean())/se:.1f} gånger sitt '
                  f'standardfel. Tecknet är troligen rätt, storleken osäker. Fler repliker '
                  f'eller en större ändring innan du litar på talet.')
        else:
            print('\n**UNDER BRUSGOLVET.** Deltat går inte att skilja från noll med det här '
                  'antalet repliker. Ändringen är för liten för pipelinen som den står.')
    else:
        print(f'- Skillnad mellan {label}erna: **{spread:.4f} m² ({rel:.0f} % av deltat)**')
        print(f'- Konvergensbrus (största std): {noise:.4f} m²')
        if vals.min()*vals.max() <= 0:
            print('\n**NO-GO.** Grupperna är inte ens överens om *tecknet*.')
        elif rel <= 20:
            print('\n**GO.** Deltat är konvergerat inom 20 % trots att absolutvärdena skiljer sig.')
        elif rel <= 50:
            print('\n**GRÄNSFALL.** Deltat håller tecken och storleksordning men inte mer. '
                  'Användbart för att sålla stora ändringar, inte för att skilja närliggande '
                  'positioner.')
        else:
            print('\n**NO-GO.** Grupperna är inte överens om storleken.')

    print('\n> Posevariation mellan foton (±2–3° ryggvinkel ≈ 0.005–0.007 m²) är ett separat '
          'och oftast större fel, och den enda boten mot den är att inte fotografera om – '
          'ändra positionen i modellen.')
    return 0


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'results'
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    lab = sys.argv[3] if len(sys.argv) > 3 else 'nät'
    sys.exit(main(root, win, lab))
