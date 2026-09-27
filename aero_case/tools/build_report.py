#!/usr/bin/env python3
"""Bygg en läsbar rapport ur en färdig körning, och ett index över alla körningar.

Varför: siffrorna har hittills bara funnits i jobbloggen och bilderna har jag
genererat och commitat för hand när jag skrivit upp ett resultat. Det gör att
en körning man inte skrev upp är i praktiken borta - artefakterna med rå VTK
försvinner efter 30 dagar. Rapporten läggs därför på en egen gren där den
renderas direkt i GitHubs webbgränssnitt, och historiken blir grenens git-log.

Två lägen:

  build_report.py <results> <ut> --body <fil> ...   bygg en körnings mapp
  build_report.py --index <runs-katalog>            skriv om index.md

Indexet byggs ur varje körnings meta.json, inte ur markdownen. Att läsa tillbaka
sin egen formatering är en felkälla som växer med tiden; en liten datafil vid
sidan av är billigare att hålla korrekt.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Bilder per fall. Fullständiga uppsättningen (cp_top, tau_mag_side) ligger i
# körningens artefakt i 30 dagar; här tas de tre som faktiskt läses. tau_x före
# tau_mag eftersom tecknet visar separationslinjen, vilket magnituden inte gör.
KEEP = [('cp_side.png', 'Cp, sidvy', 'Rött är övertryck, blått sug, grått noll.'),
        ('tau_x_side.png', 'Väggskjuvning tau_w,x',
         'Blått är BACKSTRÖMNING, alltså avlöst flöde. Det gråa bandet är separationslinjen.'),
        ('wake.png', 'Vaken i symmetrisnittet',
         'Övre panelen är fart, nedre turbulens. Strimmorna följer flödesriktningen.')]

MAXW = 1100          # bredare än så tillför inget läsbart
COLORS = 256         # paletten tar ytrenderingarna från ~350 till ~125 kB


def shrink(path):
    """Krymp och kvantisera på plats. En körning ska kosta megabyte, inte tiotal."""
    from PIL import Image
    im = Image.open(path)
    if im.width > MAXW:
        im = im.resize((MAXW, round(im.height * MAXW / im.width)), Image.LANCZOS)
    im.convert('P', palette=Image.ADAPTIVE, colors=COLORS).save(path, optimize=True)
    return os.path.getsize(path)


def parse_cda(body):
    """Plocka ut deltat ur rapporten för meta.json.

    Klarar båda rapportformaten: yaw_report ger en rad per vinkel med base, tuned
    och delta, delta_report ger en rad per jämförelse med bara delta och procent.

    Toleransen är med flit: ändras ett format ska indexet tappa detaljer, inte
    falla. Därför returneras det som gick att läsa, utan undantag.
    """
    rows, mode = [], None
    for ln in body.splitlines():
        if ln.startswith('| yaw') and 'base CdA' in ln:
            mode = 'yaw'; continue
        if 'ΔCdA [m²]' in ln and 'Δ %' in ln:
            mode = 'delta'; continue
        if ln.startswith('|---') or not mode:
            continue
        if mode == 'yaw':
            m = re.match(r'\|\s*([+-]?\d+)\s*\|\s*([\d.]+)[^|]*\|\s*([\d.]+)[^|]*\|'
                         r'\s*([+-][\d.]+)', ln)
            if m:
                rows.append(dict(yaw=int(m.group(1)), base=float(m.group(2)),
                                 tuned=float(m.group(3)), delta=float(m.group(4))))
                continue
        else:
            m = re.match(r'\|\s*([^|]+?)\s*\|\s*([+-]?[\d.]+)\s*\|', ln)
            if m and re.search(r'\d', m.group(2)):
                rows.append(dict(label=m.group(1).strip('* '), delta=float(m.group(2))))
                continue
        if rows:
            break
    return rows


def fmt_cda(cda):
    """En rads sammanfattning av deltat till indexet, oavsett format."""
    out = []
    for c in cda:
        if 'yaw' in c:
            out.append(f"{c['yaw']:+d}°: {c['delta']:+.4f}")
        else:
            out.append(f"{c['label']}: {c['delta']:+.4f}")
    return ' · '.join(out) or '–'


def build(a):
    os.makedirs(a.out, exist_ok=True)
    body = open(a.body, encoding='utf-8').read() if a.body else ''
    cases = sorted(d for d in glob.glob(os.path.join(a.results, '*')) if os.path.isdir(d))
    made, total = {}, 0
    for d in cases:
        case = os.path.basename(d)
        # field_report har redan packat upp fields.tar.gz i fallets katalog. Finns
        # ingen postProcessing har fältdatan inte skrivits och fallet hoppas över
        # hellre än att fälla hela rapporten.
        if not os.path.isdir(os.path.join(d, 'postProcessing')):
            print(f'{case}: ingen fältdata, hoppas över', file=sys.stderr); continue
        cd = os.path.join(a.out, case); os.makedirs(cd, exist_ok=True)
        run = lambda *c: subprocess.run(c, cwd=HERE + '/..', check=False,
                                        capture_output=True, text=True)
        r1 = run(sys.executable, 'tools/plot_fields.py', d, cd, '--uinf', str(a.uinf),
                 '--tag', case)
        r2 = run(sys.executable, 'tools/plot_wake.py', d, os.path.join(cd, 'wake.png'),
                 '--uinf', str(a.uinf))
        for r, who in ((r1, 'plot_fields'), (r2, 'plot_wake')):
            if r.returncode:
                print(f'{case}: {who} föll:\n{r.stderr[-800:]}', file=sys.stderr)
        got = []
        for fn, title, note in KEEP:
            p = os.path.join(cd, fn)
            if os.path.exists(p):
                total += shrink(p); got.append((fn, title, note))
        for junk in glob.glob(os.path.join(cd, '*.png')):
            if os.path.basename(junk) not in {k[0] for k in got}:
                os.remove(junk)
        made[case] = got
        print(f'{case}: {len(got)} bilder')

    meta = dict(run_id=a.run_id, mesh=a.mesh, fit=a.fit, angles=a.angles,
                speed=a.uinf, commit=a.commit, date=a.date, slug=a.slug,
                cda=parse_cda(body), cases=sorted(made))
    json.dump(meta, open(os.path.join(a.out, 'meta.json'), 'w'), indent=1)

    with open(os.path.join(a.out, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(f'# {a.date} · {a.mesh} · yaw {a.angles}\n\n')
        f.write(f'`{a.fit}` vid {a.uinf} m/s. Commit [`{a.commit[:7]}`]'
                f'(https://github.com/{a.repo}/commit/{a.commit}) · '
                f'[körningen](https://github.com/{a.repo}/actions/runs/{a.run_id})\n\n')
        f.write(body.split('\n', 1)[1] if body.startswith('## ') else body)
        f.write('\n\n---\n\n## Bilder\n\n')
        f.write('Rå VTK för ParaView ligger i körningens artefakter i 30 dagar. '
                'Den fullständiga bilduppsättningen (topvy, skjuvningsmagnitud) '
                'finns där; nedan är de tre som faktiskt läses.\n')
        for case in sorted(made):
            f.write(f'\n### {case}\n')
            for fn, title, note in made[case]:
                f.write(f'\n**{title}**  \n{note}\n\n![{title}]({case}/{fn})\n')
    print(f'rapport klar, bilder {total/1e6:.1f} MB')


def index(runs):
    metas = []
    for m in glob.glob(os.path.join(runs, '*', 'meta.json')):
        try:
            metas.append(json.load(open(m)))
        except Exception as e:
            print(f'hoppar över {m}: {e}', file=sys.stderr)
    metas.sort(key=lambda m: m.get('date', ''), reverse=True)
    with open(os.path.join(runs, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('# Körningar\n\nNyast först. Varje rad länkar till körningens '
                'rapport med tabeller och bilder.\n\n')
        f.write('| datum | nät | vinklar | ΔCdA | rapport |\n|---|---|---|---|---|\n')
        for m in metas:
            f.write(f"| {m.get('date','?')} | `{m.get('mesh','?')}` | "
                    f"{m.get('angles','?')} | {fmt_cda(m.get('cda', []))} | "
                    f"[öppna]({m.get('slug','.')}/) |\n")
        f.write(f'\n{len(metas)} körningar.\n')
    print(f'index: {len(metas)} körningar')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--index'); ap.add_argument('--body')
    ap.add_argument('--uinf', type=float, default=12.5)
    for k in ('run-id', 'mesh', 'fit', 'angles', 'commit', 'date', 'slug', 'repo'):
        ap.add_argument(f'--{k}', default='')
    a = ap.parse_args()
    if a.index:
        index(a.index)
    else:
        if not (a.results and a.out):
            ap.error('ange <results> <ut>, eller --index')
        build(a)
