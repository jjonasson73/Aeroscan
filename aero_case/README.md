# AeroScan – ryttare + TT-cykel för OpenFOAM

**Skala:** hjul 700c + 25 mm däck → Ø672 mm (sidovy, 1.556 mm/px, ~3° kamerarotation korrigerad via axellinjen). Hjälmbredd 190 mm → breddskala i frontvyn (perspektivkorrigerad för axlar/knän).
**Kontroll:** hjälmlängd från sidovyn blev 316 mm (rimligt för kort aerohjälm), hjulbas 982 mm, vevlagerhöjd 248 mm.

## Innehåll
- `geometry/` – rider.stl, bike.stl, wheel_rear.stl, wheel_front.stl (vattentäta, meter), rider_bike_full.stl (boolesk union)
- Koordinater: ryttaren tittar mot −x, flöde +x, z upp, mark z = 0 (däcken sänkta 3 mm för ren kontaktyta)
- `0/ constant/ system/` – simpleFoam, kOmegaSST, 12.5 m/s (45 km/h), rullande mark, roterande hjul
- `build_model.py` – parametrisk modell; alla landmärken (px) står överst, justera och kör om

## Kör (OpenFOAM ESI v2312+)
    ./Allrun          # 8 kärnor, ändra i system/decomposeParDict
Aref = 1 → `Cd` i postProcessing/CdA_*/ är direkt **CdA [m²]**, uppdelat på ryttare/cykel/hjul.
Projicerad frontarea för modellen: 0.361 m².

## Begränsningar
- Kroppen är byggd av ellipsoider/konvexa skal – ger rätt volym/siluett, inte veck i löst tyg
- Ekrar är utelämnade (hjulen = fälg + däck + nav)
- Från sidobilden syns bara en ryttarsida; symmetri antagen
- Perspektiv: bakhjulet ser ~7 % mindre ut än framhjulet i bilden → ±3–4 % osäkerhet i längdmått
