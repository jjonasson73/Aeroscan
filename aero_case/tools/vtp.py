#!/usr/bin/env python3
"""Läs OpenFOAMs .vtp-ytor. Inget mer.

Ligger för sig eftersom både plot_fields (som ritar) och field_report (som räknar)
behöver den, men bara den förra behöver PIL. Låg läsaren kvar i plot_fields drog
field_report in ett bildbibliotek den aldrig använder, och verdict-jobbet föll på
ModuleNotFoundError: No module named 'PIL'. Beroendekedjan ska följa vad koden
faktiskt gör.
"""
import numpy as np
import trimesh


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
    # OpenFOAMs .vtp-patchar kommer med vindning som ger INÅTPEKANDE normaler.
    # Kontrollerat med divergenssatsen: signerad volym blir negativ som den kommer.
    # Lämnas den så inverteras ljussättningen i varje rendering (ovansidan skuggas,
    # undersidan lyser) och tryckintegralen får fel tecken. Vänds här, en gång, i
    # stället för att kompenseras på varje användningsställe.
    v0, v1, v2 = pts[F[:, 0]], pts[F[:, 1]], pts[F[:, 2]]
    if np.einsum('ij,ij->i', v0, np.cross(v1 - v0, v2 - v0)).sum() < 0:
        F = F[:, [0, 2, 1]]
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


