#!/usr/bin/env python3
"""Rita vaken ur symmetrisnittet: hur luften faktiskt rör sig bakom ryttaren.

Ytfälten säger var trycket sitter. Snittet säger varför: var flödet släpper, hur
långt vaken sträcker sig och var turbulensen produceras.

Riktningen visas med LIC (line integral convolution) i stället för pilar eller
strömlinjer. Pilar kräver att man väljer en täthet, strömlinjer att man väljer
startpunkter, och båda valen döljer det man inte råkade välja. LIC smetar ut ett
brusfält längs flödet i varje pixel och visar därför hela strukturen, inklusive
återcirkulationen, utan att man bestämt var man ska titta.

  python3 tools/plot_wake.py <fallkatalog> <ut.png> [--uinf 12.5]

VIKTIGT: det här är stationär RANS. Bilden visar MEDELFLÖDET. Några
virvelavlösningar syns inte - de är medelvärdesbildade bort. Det man ser är den
stående återcirkulationsbubblan, inte en ögonblicksbild av virvlar.
"""
import sys, os, glob, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_fields import read_vtp, _ramp, _BLUE

_ORANGE = ['#fdf0e7', '#fbd9c2', '#f8bd97', '#f39c६b'.replace('६','6'), '#eb6834',
           '#c84f22', '#a03d19', '#7a2d12']
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def sample(mesh, fields, keys, x0, x1, z0, z1, nx):
    """Triangelvärden -> regelbundet rutnät. NaN där kroppen står."""
    from scipy.interpolate import LinearNDInterpolator
    c = mesh.triangles_center[:, [0, 2]]
    nz = int(nx * (z1 - z0) / (x1 - x0))
    gx = np.linspace(x0, x1, nx); gz = np.linspace(z0, z1, nz)
    X, Z = np.meshgrid(gx, gz)
    cols = np.column_stack([np.asarray(fields[k[0]])[:, k[1]] if isinstance(k, tuple)
                            else np.asarray(fields[k]) for k in keys])
    f = LinearNDInterpolator(c, cols)
    out = f(np.column_stack([X.ravel(), Z.ravel()]))
    return [out[:, i].reshape(nz, nx) for i in range(len(keys))], (nx, nz)


def lic(u, w, steps=26, h=0.9, seed=0):
    """Smeta ut vitt brus längs flödet. Ger riktning i varje pixel."""
    nz, nx = u.shape
    rng = np.random.default_rng(seed)
    noise = rng.random((nz, nx))
    sp = np.hypot(u, w); sp[~np.isfinite(sp)] = 0
    m = np.maximum(sp, 1e-6)
    ux, wz = np.nan_to_num(u) / m, np.nan_to_num(w) / m
    acc = np.zeros((nz, nx)); n = 0
    J, I = np.meshgrid(np.arange(nx), np.arange(nz))
    for sgn in (1, -1):
        x = J.astype(float); z = I.astype(float)
        for _ in range(steps):
            xi = np.clip(x.astype(int), 0, nx - 1); zi = np.clip(z.astype(int), 0, nz - 1)
            acc += noise[zi, xi]; n += 1
            x = x + sgn * h * ux[zi, xi]; z = z - sgn * h * wz[zi, xi]
            x = np.clip(x, 0, nx - 1); z = np.clip(z, 0, nz - 1)
    t = acc / n
    lo, hi = np.percentile(t, 3), np.percentile(t, 97)
    return np.clip((t - lo) / (hi - lo + 1e-9), 0, 1)


def panel(vals, stops, lo, hi, tex, body, gamma=0.55):
    t = np.clip((vals - lo) / (hi - lo + 1e-12), 0, 1)
    rgb = _ramp(stops, t.ravel()).reshape(vals.shape + (3,))
    shade = 0.72 + 0.56 * (tex ** gamma)          # LIC som ljushetstextur
    rgb = np.clip(rgb * shade[..., None], 0, 255)
    rgb[body] = (128, 133, 138)                   # kroppen: massiv, ingen data
    return rgb.astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case'); ap.add_argument('out')
    ap.add_argument('--uinf', type=float, default=12.5)
    ap.add_argument('--x0', type=float, default=-2.4); ap.add_argument('--x1', type=float, default=5.2)
    ap.add_argument('--z0', type=float, default=0.0); ap.add_argument('--z1', type=float, default=2.3)
    ap.add_argument('--nx', type=int, default=1180)
    a = ap.parse_args()

    f = glob.glob(os.path.join(a.case, 'postProcessing', 'diagSlice', '*', '*.vtp'))
    if not f:
        raise SystemExit(f'ingen diagSlice under {a.case}')
    mesh, fld = read_vtp(sorted(f)[-1])
    (ux, uz, umag, k), (nx, nz) = sample(
        mesh, fld, [('U', 0), ('U', 2), 'k', 'k'], a.x0, a.x1, a.z0, a.z1, a.nx)
    umag = np.hypot(np.nan_to_num(ux), np.nan_to_num(uz))
    Uall = np.asarray(fld['U'])
    body = ~np.isfinite(ux)
    tex = lic(ux, uz)

    pa = panel(umag / a.uinf, _BLUE[1:], 0, 1.35, tex, body)
    pb = panel(np.nan_to_num(k), _ORANGE, 0, float(np.nanpercentile(k, 99)), tex, body)

    PAD, TOP, MID, BOT = 18, 106, 62, 96
    BAR = 12
    W = PAD * 2 + nx; H = TOP + nz + MID + nz + BOT
    im = Image.new('RGB', (W, H), (252, 252, 251)); dr = ImageDraw.Draw(im)
    f11 = ImageFont.truetype(FONT, 11); f12 = ImageFont.truetype(FONT, 12)
    f13 = ImageFont.truetype(FONTB, 13)
    im.paste(Image.fromarray(pa), (PAD, TOP))
    im.paste(Image.fromarray(pb), (PAD, TOP + nz + MID))

    def bar(y, stops, lo, hi, unit, fmt='{:.2f}'):
        t = np.linspace(0, 1, nx)
        strip = _ramp(stops, t).reshape(1, nx, 3).astype(np.uint8).repeat(BAR, 0)
        im.paste(Image.fromarray(strip), (PAD, y))
        dr.rectangle([PAD, y, PAD + nx - 1, y + BAR - 1], outline=(214, 213, 208))
        for fr in (0, .25, .5, .75, 1):
            x = int(PAD + fr * (nx - 1))
            dr.text((min(x, PAD + nx - 34) if fr == 1 else max(PAD, x - 12), y + BAR + 4),
                    fmt.format(lo + fr * (hi - lo)), font=f11, fill=(82, 81, 78))
        dr.text((PAD + nx - 62, y - 14), unit, font=f11, fill=(82, 81, 78))

    tag = os.path.basename(os.path.abspath(a.case))
    dr.text((PAD, 16), f'Vaken i symmetrisnittet · {tag}', font=f13, fill=(11, 11, 11))
    dr.text((PAD, 37), 'Strukturen i ytan är LIC: brus utsmetat längs flödet, så riktningen '
                       'syns i varje pixel utan valda startpunkter.', font=f11, fill=(82, 81, 78))
    dr.text((PAD, 53), 'Stationär RANS — detta är MEDELFLÖDET. Virvelavlösningar är '
                       'medelvärdesbildade bort; bubblan bakom kroppen står still.',
            font=f11, fill=(82, 81, 78))
    dr.text((PAD, 69), 'Grått = kroppen, där det inte finns någon luft att lösa för.',
            font=f11, fill=(82, 81, 78))
    dr.text((PAD, TOP - 16), 'hastighet   ljust = stillastående luft, alltså vaken   ·   '
                             'mörkt = full fart', font=f12, fill=(11, 11, 11))
    kmax = float(np.nanpercentile(k, 99))
    bar(TOP + nz + 14, _BLUE[1:], 0, 1.35, '|U| / U∞')
    dr.text((PAD, TOP + nz + MID - 16), 'turbulent energi   mörkt = där turbulensen '
                                        'produceras, alltså skjuvskikten', font=f12, fill=(11, 11, 11))
    bar(TOP + 2 * nz + MID + 14, _ORANGE, 0, kmax, 'k  [m²/s²]', '{:.1f}')
    back = float((Uall[:, 0] < 0).mean() * 100)
    dr.text((PAD, H - 34), f'snitt y = 0 · x från {a.x0:+.1f} till {a.x1:+.1f} m · '
                           f'ryttaren blickar mot −x · U∞ = {a.uinf} m/s', font=f11, fill=(82, 81, 78))
    dr.text((PAD, H - 19), f'{back:.1f} % av snittets celler har negativ x-hastighet, alltså '
                           f'backströmning. Lägsta {Uall[:,0].min():.1f} m/s.',
            font=f11, fill=(82, 81, 78))
    im.save(a.out)
    print(f'{a.out}  {W}x{H}   backströmning i {back:.1f} % av snittet')


if __name__ == '__main__':
    main()
