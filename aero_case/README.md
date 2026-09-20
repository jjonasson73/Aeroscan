# AeroScan – ryttare + TT-cykel för OpenFOAM

**Skala:** hjul 700c + 25 mm däck → Ø672 mm (sidovy, 1.556 mm/px, ~3° kamerarotation korrigerad via axellinjen). Hjälmbredd 190 mm → breddskala i frontvyn (perspektivkorrigerad för axlar/knän).
**Kontroll:** hjälmlängd från sidovyn blev 316 mm (rimligt för kort aerohjälm), hjulbas 982 mm, vevlagerhöjd 248 mm.

## Innehåll
- `geometry/` – rider.stl, bike.stl, wheel_rear.stl, wheel_front.stl (vattentäta, meter).
  `rider_bike_full.stl` (boolesk union) genereras också men är gitignorerad – den används bara
  av `overlay.py` och frontarea-beräkningen.
- Koordinater: ryttaren tittar mot −x, flöde +x, z upp, mark z = 0 (däcken sänkta 3 mm för ren kontaktyta)
- `0/ constant/ system/` – simpleFoam, kOmegaSST, 12.5 m/s (45 km/h), rullande mark, roterande hjul
- `0/include/initialConditions` – **enda stället** där hastigheten står. U, k och omega härleds därifrån.
- `build_model.py` – parametrisk modell; alla landmärken (px) står överst, justera och kör om
- `tools/` – `inlet_conditions.py` (U → omega_hjul, k, omega_inlopp), `check_case.py` (konsistensvakt),
  `cda_summary.py` (CdA-tabell till jobbsammanfattningen)

## Installera
    pip install -r requirements.txt     # numpy, scipy, trimesh, manifold3d, shapely, pillow

## Bygg om geometrin
    python build_model.py               # skriver ALLTID till geometry/ och model_info.json
    python overlay.py /sokvag/till/sidofoto.png     # → preview/overlay_side.png, preview/front_projection.png
    python tools/check_case.py          # axelpositioner + att STL:erna är slutna

`build_model.py` och `overlay.py` skriver relativt sin egen katalog, så de går att köra
från vilken arbetskatalog som helst.

## Kör (OpenFOAM ESI v2312+)
    ./Allrun          # 8 kärnor, ändra i system/decomposeParDict
Aref = 1 → `Cd` i postProcessing/CdA_*/ är direkt **CdA [m²]**, uppdelat på ryttare/cykel/hjul.
Projicerad frontarea för modellen: 0.361 m².

## Begränsningar
- Kroppen är byggd av ellipsoider/konvexa skal – ger rätt volym/siluett, inte veck i löst tyg
- Ekrar är utelämnade (hjulen = fälg + däck + nav). Navet hänger fritt inuti fälgen.
- Från sidobilden syns bara en ryttarsida; symmetri antagen
- Perspektiv: bakhjulet ser ~7 % mindre ut än framhjulet i bilden → ±3–4 % osäkerhet i längdmått
- **Benens IK är inte kalibrerad mot fotot.** `ik_knee()` använder L1 = L2 = 440 mm, vilket
  placerar knät 78 mm från det uppmätta landmärket `knee_R`. 440 mm stämmer dock mot Winter
  för 175 cm (lår 429, underben 431), så felet ligger troligen i landmärkena (`hip` och
  `knee_R` är ytpunkter, inte ledcentra) och i den gissade ankelpositionen
  `ped + [-70, s*120, 95]`. Avvikelsen är nästan helt i x, så frontarean ändras bara ~0.3 %
  (0.3614 → 0.3625 m²) – men vaken bakom benet påverkas mer än så.
- **Bålen är ~50 % för voluminös.** Modellerad kroppsvolym (utan hjälm och skor) är 79.3 L
  → 80 kg, mot åkarens 69 kg. Uppdelat: bål 51.5 L mot ~34 L antropometriskt, ben 25.6 mot
  20.0, armar 7.7 mot 6.0. Två orsaker:
  1. `torso = hull(...)` är ett **konvext** skal och kan därför inte ha någon midja.
  2. `chest_low` (z = 965 mm) ligger i princip i samma höjd som `elbow` (961 mm) och strax
     över `bag` (903 mm) – landmärket följer sannolikt arm-/väskelinjen, inte bröstbenet.
     Att höja det 100 mm tar bort 7.4 kg **utan att ändra frontarean alls** (0.3614 m²),
     eftersom den volymen ligger skuggad bakom låren i y-z-projektionen.

  Hjälmbredden 190 mm är inte förklaringen: för att nå 69 kg enbart via breddskalan skulle
  hjälmen behöva vara ~152–164 mm, vilket ingen vuxen aerohjälm är. En rimlig kombination är
  `chest_low` +100 mm och bredd ×0.95 (hjälm 180 mm) → 70.4 kg och A = 0.3546 m² (−1.9 %).
- **Frontvyns skalning finns inte i koden.** Kroppsbredderna (95 mm halv hjälmbredd, 165/172 mm
  bål osv.) är hårdkodade konstanter utan spårbarhet till frontfotot, och `overlay.py` validerar
  bara sidovyn. Byter man frontfoto uppdateras ingenting automatiskt.
