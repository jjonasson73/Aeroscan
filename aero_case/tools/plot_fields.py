#!/usr/bin/env python3
"""Rendera ytfält från en CFD-körning till PNG.

En CdA-siffra säger att något är fel men aldrig var. Det här verktyget målar
fälten på modellen så att separationsbubblor, sugtoppar och skillnaden mellan
två positioner går att se.

Färgval, inte smak:
  Cp och skillnadskartor  -> DIVERGERANDE, blå <-> grå <-> röd, noll i grått.
  |tau_w|                 -> SEKVENTIELL, en hue ljus->mörk.
  tau_x                   -> divergerande, och då är den grå bandet
                             separationslinjen: där vänder väggskjuvningen.
Aldrig regnbåge. En regnbågsskala lägger falska kanter där hue:n hoppar, och i
ett tryckfält blir de kanterna lätt lästa som fysik.

  python3 tools/plot_fields.py <fältkatalog> <utkatalog> [--uinf 12.5] [--tag namn]
"""
import sys, os, glob, argparse
import numpy as np, meshio, trimesh
from PIL import Image, ImageDraw

SURFACE   = (252, 252, 251)
INK       = (11, 11, 11)
INK_SOFT  = (82, 81, 78)
GRID      = (214, 213, 208)

_BLUE = ['#f0efec', '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
_RED  = ['#f0efec', '#fbd8d5', '#f6b0af', '#ef8280', '#e34948', '#c53434', '#a32828', '#8f2120']
_SEQ  = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5',
         '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b']

def _hex(h): return np.array([int(h[i:i+2], 16) for i in (1, 3, 5)], float)

def _ramp(stops, t):
    """t i [0,1] -> RGB, linjär interpolation mellan stoppen."""
    c = np.array([_hex(s) for s in stops])
    x = np.clip(t, 0, 1) * (len(c) - 1)
    i = np.clip(x.astype(int), 0, len(c) - 2); f = (x - i)[:, None]
    return c[i] * (1 - f) + c[i + 1] * f

def diverging(v, lim):
    """Noll blir grått. Samma antal steg per arm, så en symmetrisk avvikelse
    ser symmetrisk ut."""
    t = np.clip(np.abs(v) / lim, 0, 1)
    out = np.where((v >= 0)[:, None], _ramp(_RED, t), _ramp(_BLUE, t))
    return out

def sequential(v, lo, hi):
    return _ramp(_SEQ, (v - lo) / (hi - lo + 1e-30))

_VTP_DT = {'Float32': '<f4', 'Float64': '<f8', 'Int32': '<i4', 'Int64': '<i8',
           'UInt32': '<u4', 'UInt64': '<u8', 'UInt8': 'u1', 'Int8': 'i1'}


def _vtp_array(el, header_dt='<u8'):
    """En DataArray ur en VTK XML-fil: base64(UInt64 antal_bytes + rådata)."""
    import base64
    raw = base64.b64decode(''.join(el.text.split()))
    n = int(np.frombuffer(raw[:8], header_dt, 1)[0])
    a = np.frombuffer(raw[8:8 + n], _VTP_DT[el.attrib['type']])
    nc = int(el.attrib.get('NumberOfComponents', 1))
    return a.reshape(-1, nc) if nc > 1 else a


def read_vtp(path):
    """VTK XML PolyData. meshio läser inte .vtp, och OpenFOAMs `surfaces` skriver
    just .vtp med surfaceFormat vtk. Formatet är okomprimerad base64 med en
    UInt64-längd först, alltså inget som motiverar ett hundramegabytes paket."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    if root.attrib.get('compressor'):
        raise SystemExit(f'{path}: komprimerad VTP stöds inte')
    hdr = _VTP_DT[root.attrib.get('header_type', 'UInt64')]
    piece = root.find('.//Piece')
    pts = _vtp_array(piece.find('Points/DataArray'), hdr).astype(np.float64)
    polys = piece.find('Polys')
    conn = _vtp_array([d for d in polys if d.attrib['Name'] == 'connectivity'][0], hdr)
    offs = _vtp_array([d for d in polys if d.attrib['Name'] == 'offsets'][0], hdr)
    starts = np.concatenate(([0], offs[:-1]))
    tris, src = [], []
    for i, (a, b) in enumerate(zip(starts, offs)):
        poly = conn[a:b]
        for j in range(1, len(poly) - 1):          # triangelfläkt
            tris.append((poly[0], poly[j], poly[j + 1])); src.append(i)
    F = np.asarray(tris, np.int64); S = np.asarray(src, np.int64)
    fields = {}
    cd = piece.find('CellData')
    if cd is not None:
        for d in cd:
            fields[d.attrib['Name']] = _vtp_array(d, hdr)[S]
    pd = piece.find('PointData')
    if pd is not None:
        for d in pd:
            fields[d.attrib['Name']] = _vtp_array(d, hdr)[F].mean(axis=1)
    return trimesh.Trimesh(vertices=pts, faces=F, process=False), fields


def read_surface(path):
    """VTK -> (trimesh, {fältnamn: värde per triangel})."""
    if path.endswith('.vtp'):
        return read_vtp(path)
    m = meshio.read(path)
    pts = m.points.astype(np.float64)
    tris, src = [], []          # src: index i den ursprungliga cellistan
    n = 0
    for blk in m.cells:
        d = blk.data
        if blk.type == 'triangle':
            tris.append(d); src.append(np.arange(n, n + len(d)))
        elif blk.type == 'quad':
            tris.append(d[:, [0, 1, 2]]); tris.append(d[:, [0, 2, 3]])
            src.append(np.arange(n, n + len(d))); src.append(np.arange(n, n + len(d)))
        elif blk.type == 'polygon':                      # triangelfläkt
            for k, poly in enumerate(d):
                for j in range(1, len(poly) - 1):
                    tris.append(np.array([[poly[0], poly[j], poly[j + 1]]]))
                    src.append(np.array([n + k]))
        n += len(d)
    F = np.vstack(tris); S = np.concatenate(src)
    mesh = trimesh.Trimesh(vertices=pts, faces=F, process=False)
    fields = {}
    for k, v in (m.cell_data or {}).items():
        a = np.concatenate([np.asarray(x) for x in v])
        fields[k] = a[S] if len(a) >= S.max() + 1 else None
    for k, v in (m.point_data or {}).items():           # punktdata -> medel per triangel
        a = np.asarray(v)
        fields[k] = a[F].mean(axis=1)
    return mesh, {k: v for k, v in fields.items() if v is not None}

def render(mesh, val, colour_fn, title, unit, fn, view='side', n=5_000_000,
           W=1000, note=None, ticks=None):
    ax = {'side': (0, 2, 1), 'top': (0, 1, 2), 'front': (1, 2, 0)}[view]
    pts, fid = trimesh.sample.sample_surface(mesh, n)
    # Bakstyckesgallring. Utan den vinner den bortre ytan djuptestet och bilden visar
    # insidan av skalet genom varje öppen kant -- vilket ser ut som utskjutande flikar
    # på modellen. Kameran står vid +d, så bara ytor vars normal pekar mot den ritas.
    keep = mesh.face_normals[fid][:, ax[2]] > 0
    pts, fid = pts[keep], fid[keep]
    v = np.asarray(val)[fid]
    h, vv, d = pts[:, ax[0]], pts[:, ax[1]], pts[:, ax[2]]
    sh, sv = np.ptp(h), np.ptp(vv)
    PAD, BAR = 16, 74
    H = int(W * sv / sh)
    gx = ((h - h.min()) / sh * (W - 1)).astype(np.int32)
    gy = ((vv.max() - vv) / sv * (H - 1)).astype(np.int32)
    rgb = colour_fn(v)
    # svag ljussättning så formen syns genom färgen, men aldrig så mycket att
    # den flyttar en färg till en annan nivå i skalan
    L = np.array([-.4, .5, .78]); L /= np.linalg.norm(L)
    sh_ = (np.clip(mesh.face_normals[fid] @ L, 0, 1) * 0.28 + 0.80)[:, None]
    rgb = np.clip(rgb * sh_, 0, 255)
    buf = np.full((H * W, 3), np.nan); o = np.argsort(d)
    buf[(gy.astype(np.int64) * W + gx)[o]] = rgb[o]
    img = buf.reshape(H, W, 3)
    # Punktsamplingen lämnar enstaka tomma pixlar mitt i ytan. De läses som hål i
    # modellen, alltså som geometri, vilket är precis fel intryck i en fältbild.
    # Fyll bara pixlar som har grannar - konturen lämnas orörd.
    import scipy.ndimage as ndi
    for _ in range(3):
        hole = np.isnan(img[:, :, 0])
        if not hole.any():
            break
        filled = (~hole).astype(float)
        cnt = ndi.uniform_filter(filled, 3) * 9
        inner = hole & (cnt >= 3)
        if not inner.any():
            break
        for c in range(3):
            ch = np.where(hole, 0.0, img[:, :, c])
            sm = ndi.uniform_filter(ch, 3) * 9
            img[:, :, c] = np.where(inner, sm / np.maximum(cnt, 1), img[:, :, c])
    img = np.where(np.isnan(img), 255.0, img).astype(np.uint8)
    canvas = Image.new('RGB', (W + 2*PAD, H + 2*PAD + BAR), SURFACE)
    canvas.paste(Image.fromarray(img), (PAD, PAD + 34))
    dr = ImageDraw.Draw(canvas)
    dr.text((PAD, 8), title, fill=INK)
    if note: dr.text((PAD, 21), note, fill=INK_SOFT)
    # färgskala med siffror - utan den är bilden dekoration, inte data
    bx, by, bw, bh = PAD, H + PAD + 46, W - 2*PAD, 14
    t = np.linspace(0, 1, bw)
    bar = colour_fn(ticks['map'](t)).reshape(1, bw, 3).astype(np.uint8).repeat(bh, 0)
    canvas.paste(Image.fromarray(bar), (bx, by))
    dr.rectangle([bx, by, bx + bw - 1, by + bh - 1], outline=GRID)
    for frac, lab in ticks['marks']:
        x = int(bx + frac * (bw - 1))
        dr.line([(x, by + bh), (x, by + bh + 4)], fill=GRID)
        dr.text((max(bx, x - 12), by + bh + 6), lab, fill=INK_SOFT)
    dr.text((bx + bw - 44, by - 12), unit, fill=INK_SOFT)
    canvas.save(fn)
    return fn


def load_case(d):
    """Plocka ihop ytpatcharna i en körning till en mesh med fält."""
    tdirs = sorted(glob.glob(os.path.join(d, 'postProcessing', 'diagSurfaces', '*')))
    if not tdirs:
        tdirs = sorted(glob.glob(os.path.join(d, 'diagSurfaces', '*'))) or [d]
    t = tdirs[-1]
    parts = {}
    for f in sorted(sorted(glob.glob(os.path.join(t, '*.vtp')) + glob.glob(os.path.join(t, '*.vtk')))):
        name = os.path.basename(f).rsplit('.', 1)[0].removeprefix('s_')
        try:
            parts[name] = read_surface(f)
        except Exception as e:
            print(f"  hoppar över {name}: {type(e).__name__}: {e}")
    if not parts:
        raise SystemExit(f"hittade ingen .vtk under {t}")
    return parts, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case'); ap.add_argument('out')
    ap.add_argument('--uinf', type=float, default=12.5)
    ap.add_argument('--tag', default='')
    ap.add_argument('--only', default='', help='bara den här patchen, t.ex. rider')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    parts, t = load_case(a.case)
    print(f"tid {os.path.basename(t)}, patchar: {', '.join(parts)}")
    q = 0.5 * a.uinf**2                       # p är kinematiskt (m^2/s^2)
    keep = [a.only] if a.only else list(parts)
    meshes = [parts[k][0] for k in keep]
    tri = trimesh.util.concatenate(meshes)
    def cat(key):
        return np.concatenate([parts[k][1][key] for k in keep])
    cp = cat('p') / q
    lim = float(np.percentile(np.abs(cp), 99))
    tick = lambda lo, hi: {'map': lambda t: lo + t*(hi-lo),
                           'marks': [(0, f'{lo:+.2f}'), (0.5, '0'), (1, f'{hi:+.2f}')]}
    tg = a.tag or os.path.basename(os.path.abspath(a.case))
    outs = []
    for view in ('side', 'top'):
        outs.append(render(tri, cp, lambda v: diverging(v, lim),
                           f'Cp  ·  {tg}  ·  {view}', 'Cp [-]',
                           os.path.join(a.out, f'cp_{view}.png'), view=view,
                           note='rott = overtryck (stagnation), blatt = undertryck (sug), gratt = noll',
                           ticks={'map': lambda t: (t*2-1)*lim,
                                  'marks': [(0, f'{-lim:+.2f}'), (0.5, '0'), (1, f'{lim:+.2f}')]}))
    if 'wallShearStress' in parts[keep[0]][1]:
        w = np.vstack([parts[k][1]['wallShearStress'] for k in keep])
        mag = np.linalg.norm(w, axis=1); hi = float(np.percentile(mag, 99))
        outs.append(render(tri, mag, lambda v: sequential(v, 0, hi),
                           f'|tau_w|  ·  {tg}', 'm2/s2',
                           os.path.join(a.out, 'tau_mag_side.png'),
                           note='ljust = lag skjuvning, alltso avlost eller stillastaende flode',
                           ticks=tick(0, hi)))
        # TECKENKONVENTION. OpenFOAMs wallShearStress returnerar spänningen med
        # MOTSATT tecken mot strömningsriktningen. Kontrollerat mot integralen:
        # summan av tau_x*dA över alla patchar blir -0.0111 m^2 i råa värden, och
        # friktionsmotstånd måste vara positivt i färdriktningen. Vänt tecken ger
        # +0.0111, alltså 5.8 % av total CdA, vilket är rimligt för en trubbig kropp.
        # Utan den här vändningen läses bilden bakvänt: allt attached flöde såg ut
        # som backströmning.
        tx = -w[:, 0]; tl = float(np.percentile(np.abs(tx), 99))
        outs.append(render(tri, tx, lambda v: diverging(v, tl),
                           f'tau_w,x  ·  {tg}  ·  det gra bandet ar separationslinjen', 'm2/s2',
                           os.path.join(a.out, 'tau_x_side.png'),
                           note='rott = medstroms (attached), BLATT = backstromning alltsa AVLOST',
                           ticks={'map': lambda t: (t*2-1)*tl,
                                  'marks': [(0, f'{-tl:+.3f}'), (0.5, '0'), (1, f'{tl:+.3f}')]}))
    for o in outs: print(f"  {o}")


if __name__ == '__main__':
    main()
