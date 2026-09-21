"""Verdict on whether this pipeline can resolve a position change.

    python tools/delta_report.py results/ <window>

`results/<mesh>-<pos>/coefficient.dat` for pos in (base, tuned) and two mesh levels.

The question is NOT whether the two mesh levels agree on CdA -- they will not, and that is
expected for a bluff body at accessible cell counts. The question is whether they agree on
the DIFFERENCE between two positions. If they do, the delta is mesh-converged even though
the absolutes are not, and the pipeline can rank positions. If they do not, the
discretisation noise is larger than the signal and no amount of post-processing fixes it.
"""
import glob, pathlib, sys

import numpy as np


def series(path, window):
    d = np.loadtxt(path, comments='#', ndmin=2)
    c = d[-window:, 1]                      # column 1 = Cd; Aref = 1 so this is CdA
    return c.mean(), c.std(), int(d[-1, 0])


def main(root, window):
    runs = {}
    for f in sorted(glob.glob(str(pathlib.Path(root) / '*' / '**' / 'coefficient.dat'),
                              recursive=True)):
        # the artifact directory is named "<mesh>-<pos>"
        parts = pathlib.Path(f).parts
        tag = next(p for p in parts if '-' in p and p.rsplit('-', 1)[-1] in ('base', 'tuned'))
        mesh, pos = tag.rsplit('-', 1)
        if 'CdA_total' in f:
            runs[(mesh, pos)] = series(f, window)
    meshes = sorted({m for m, _ in runs})
    if not meshes:
        print('_Inga resultat hittades._')
        return 0

    print(f'### CdA per körning (medel över sista {window} iterationerna)\n')
    print('| nät | position | CdA [m²] | std | spridning | iter |')
    print('|---|---|---|---|---|---|')
    for m in meshes:
        for p in ('base', 'tuned'):
            if (m, p) in runs:
                mu, sd, it = runs[(m, p)]
                print(f'| {m} | {p} | {mu:.4f} | {sd:.4f} | {abs(sd/mu)*100:.2f} % | {it} |')

    deltas = {}
    for m in meshes:
        if (m, 'base') in runs and (m, 'tuned') in runs:
            b, t = runs[(m, 'base')][0], runs[(m, 'tuned')][0]
            deltas[m] = (t - b, (t - b)/b*100)

    print('\n### ΔCdA per nätnivå\n')
    print('| nät | ΔCdA [m²] | Δ % |')
    print('|---|---|---|')
    for m, (d, pc) in deltas.items():
        print(f'| {m} | {d:+.4f} | {pc:+.2f} % |')

    if len(deltas) < 2:
        print('\n**Ofullständigt** – behöver båda nätnivåerna för ett utslag.')
        return 1

    (m1, (d1, _)), (m2, (d2, _)) = list(deltas.items())[:2]
    spread = abs(d1 - d2)
    ref = max(abs(d1), abs(d2))
    rel = spread/ref*100 if ref else float('inf')
    # the solver's own run-to-run wobble, as a floor to compare the spread against
    noise = max(runs[(m, p)][1] for m in deltas for p in ('base', 'tuned'))

    print(f'\n### Utslag\n')
    print(f'- ΔCdA({m1}) = {d1:+.4f} m², ΔCdA({m2}) = {d2:+.4f} m²')
    print(f'- Skillnad mellan nätnivåerna: **{spread:.4f} m² ({rel:.0f} % av deltat)**')
    print(f'- Konvergensbrus (största std): {noise:.4f} m²')
    if d1*d2 <= 0:
        print('\n**NO-GO.** Nätnivåerna är inte ens överens om *tecknet*. '
              'Diskretiseringsbruset dominerar helt – pipelinen kan inte rangordna positioner.')
    elif rel <= 20:
        print('\n**GO.** Deltat är nätkonvergerat inom 20 % trots att absolutvärdena skiljer sig. '
              'Pipelinen kan rangordna positioner av den här storleken.')
    elif rel <= 50:
        print('\n**GRÄNSFALL.** Deltat håller tecken och storleksordning men inte mer. '
              'Användbart för att sålla stora ändringar, inte för att skilja närliggande positioner. '
              'Fler celler, eller en större positionsändring, innan du litar på rangordningen.')
    else:
        print('\n**NO-GO.** Nätnivåerna är inte överens om storleken. '
              'Kör om på fler celler (självhostad runner eller spot-VM) innan du bygger vidare.')
    print(f'\n> Detta säger bara om *nätet* räcker. Posevariation mellan foton '
          f'(±2–3° ryggvinkel ≈ 0.005–0.007 m²) är ett separat och oftast större fel, '
          f'och den enda boten mot den är att inte fotografera om – ändra positionen i modellen.')
    return 0


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'results'
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    sys.exit(main(root, win))
