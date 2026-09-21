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
- `build_model.py` – geometri; `RIDER` (längd/vikt) och `FIT` (position) står överst
- `pose.py` – antropometri, poselösare och fit-vinklar
- `tools/` – `inlet_conditions.py` (U → omega_hjul, k, omega_inlopp), `check_case.py` (konsistensvakt),
  `cda_summary.py` (CdA-tabell till jobbsammanfattningen), `fit_sweep.py` (positionssweep)

## Installera
    pip install -r requirements.txt     # numpy, scipy, trimesh, manifold3d, shapely, pillow

## Ändra position (det här är poängen)
All positionsändring går genom `FIT` överst i `build_model.py` – **aldrig** genom pixel-
landmärkena i `L`. Nollor = positionen i fotot; varje post är en verklig millimeter, och
posen löses om kring den så att alla leder följer med konsekvent.

    FIT = dict(pad_drop_mm=0, pad_reach_mm=0, saddle_fore_mm=0,
               saddle_up_mm=0, head_pitch_deg=0, crank_angle_deg=None)

    python build_model.py pad_drop_mm=-20        # engångsvärde från kommandoraden
    python tools/fit_sweep.py pad_drop_mm -30 -20 -10 0 10

`fit_sweep.py` ger frontarea, alla fit-vinklar och en screening-ΔCdA utan att näta något –
använd den för att välja vilka positioner som är värda en CFD-körning.

### Tre lager
1. **Kropp** – segmentlängder. Bål och armar mäts ur sidofotot; benen från längden
   (Winter 2009), eftersom ankeln är en gissning. Omkretsar kalibreras så att
   kroppsmassan blir `RIDER['mass_kg']`.
2. **Fit** – kontaktpunkterna: sadel, armbågspads, extensions, pedaler.
3. **Pose** – löses ut. Bålen roterar kring höften tills axeln ligger exakt en överarm
   från padden, vilket är vad som faktiskt händer med ryggen när du sänker padsen.

Höftledcentrum ligger under ytlandmärket `hip`; offseten löses **en gång vid baseline** ur
knävinkeln i botten (fit-fönster 140–150°) och hålls sedan fast. Höjer du sadeln så att
knävinkeln går ur fönstret ska det synas – inte kalibreras bort.

### Fit-vinklar
`model_info.json` → `fit_angles`, och skriptet skriver ut dem:
`back_deg` (ryggvinkeln man läser av ett foto), `torso_deg` (höftled→axelled, brantare),
`hip_closed_deg`, `knee_bottom_deg`, `shoulder_deg`, `elbow_deg`, `forearm_deg`,
plus fit-koordinaterna `saddle_height_mm`, `saddle_setback_mm`, `effective_sta_deg`,
`pad_stack_mm`, `pad_reach_mm`, `saddle_to_pad_drop_mm`, `grip_rise_mm`.

## Bygg om geometrin
    python build_model.py               # skriver ALLTID till geometry/ och model_info.json
    python overlay.py /sokvag/till/sidofoto.png     # → preview/overlay_side.png, preview/front_projection.png
    python tools/check_case.py          # axelpositioner + att STL:erna är slutna
    python tools/render_views.py        # → preview/exposure.png, preview/silhouette_delta.png

`render_views.py` färgar ytorna efter hur rakt de möter flödet och ritar frontarean för
baseline mot en tunad position med skillnaden markerad. Allt kommer ur geometrin — det är
alltså ingen CFD-data, men det är exakt den yta som bygger formmotståndet.

`build_model.py` och `overlay.py` skriver relativt sin egen katalog, så de går att köra
från vilken arbetskatalog som helst.

## Kör (OpenFOAM ESI v2312+)
    ./Allrun          # 8 kärnor, ändra i system/decomposeParDict
Aref = 1 → `Cd` i postProcessing/CdA_*/ är direkt **CdA [m²]**, uppdelat på ryttare/cykel/hjul.
Projicerad frontarea för modellen: 0.346 m² (efter masskalibreringen; var 0.361 med den
okalibrerade kroppen).

### Go/no-go innan du litar på något delta
Actions → **aero-delta** → Run workflow. Kör samma två positioner på två nätnivåer och
skriver ut ett utslag. Absolutvärdena kommer inte att stämma mellan nivåerna – frågan är om
de är överens om *skillnaden*. Är de inom 20 % är deltat nätkonvergerat.

### Go/no-go-resultat 2026-09-21: GO
`pad_drop_mm=-20`, 1500 iterationer med fast iterationsantal, 12.5 m/s, 4 kärnor:

| nät | position | CdA [m²] | std | spridning |
|---|---|---|---|---|
| coarse | baseline | 0.1960 | 0.0012 | 0.59 % |
| coarse | tunad | 0.1917 | 0.0005 | 0.28 % |
| medium | baseline | 0.1935 | 0.0007 | 0.35 % |
| medium | tunad | 0.1890 | 0.0011 | 0.60 % |

**ΔCdA(coarse) = −0.0043 m² (−2.20 %), ΔCdA(medium) = −0.0045 m² (−2.34 %).**
Skillnad mellan nätnivåerna: 0.0002 m², alltså 5 % av deltat. Deltat är nätkonvergerat
trots att absolutvärdena skiljer sig — pipelinen kan rangordna positioner av den här
storleken.

Korskontroll mot screeningen: `fit_sweep.py` gav −1.79 % frontarea för samma ändring,
CFD:n ger −2.2 %. Skillnaden är att Cd också förbättrades något (0.566 → 0.564), alltså
flatare rygg ger både mindre area och något bättre form. Rätt tecken, rimlig storlek.

**Absolutvärdet är däremot för lågt.** CdA ≈ 0.19 och Cd ≈ 0.57 mot 0.20–0.25 respektive
0.60–0.75 för en verklig TT-ryttare — och fotot visar lös t-shirt, mjukisbyxor, sneakers,
ekerhjul och en rund hjälm, vilket i verkligheten drar uppåt. Modellen är för slät. Använd
Δ, inte absolutvärdet.

### Δ-CdA: vad som faktiskt går att lita på
28 mm padhöjd ≈ 2° ryggvinkel ≈ **2 % CdA**. Konvergenstoleransen är 0.2 %, alltså tio
gånger under signalen. Det som kan dränka den är **nätbruset**: varje position ger ny STL
och nytt snappy-nät. Innan du litar på ett delta – kör samma två positioner på både
`coarse` och `fine`. Stämmer ΔCdA mellan nivåerna är deltat nätkonvergerat även om
absolutvärdena inte är det. `quick` är för att röktesta pipelinen, inte för att jämföra.

Allt detta är vid 0° yaw. Verklig CdA domineras av 5–15° yaw, och en position som vinner
rakt framifrån vinner inte nödvändigtvis i sidvind.

**Fotografera inte om för varje position.** 1° ryggvinkel ≈ 0.0035 m² frontarea ≈ 0.0024 m²
CdA – ungefär vad 10 mm padhöjd är värd. Posevariationen mellan två foton av "samma"
position är 2–3°, alltså större än ändringen du testar, och felet är oberoende mellan foton
så det adderas i stället för att ta ut sig. Ta **ett** baselinefotopar och ändra positionen
via `FIT`. Då är landmärken, kropp och tyg identiska och bara det du ville ändra skiljer.
Fotot på den tunade positionen har en annan roll: kontrollera att du faktiskt intog den pose
modellen förutsade.

## Begränsningar
- Kroppen är byggd av ellipsoider/konvexa skal – ger rätt volym/siluett, inte veck i löst tyg
- Ekrar är utelämnade (hjulen = fälg + däck + nav). Navet hänger fritt inuti fälgen.
- Från sidobilden syns bara en ryttarsida; symmetri antagen
- Perspektiv: bakhjulet ser ~7 % mindre ut än framhjulet i bilden → ±3–4 % osäkerhet i längdmått
- **Knät hamnar 78 mm från landmärket `knee_R`,** nästan helt i x. Lår/underben är 429/430 mm
  (Winter, 175 cm) och knävinkeln i botten ligger i fit-fönstret, så segmenten stämmer –
  avvikelsen kommer från att `hip`/`knee_R` är ytpunkter och från den ogissade
  `ANKLE_OFFSET`. Frontarean påverkas ~0.3 %, och felet är **gemensamt läge** mellan två
  positioner, så det tar i praktiken ut sig i ett Δ-CdA.
- **`ANKLE_OFFSET` är inte uppmätt.** Den sätter knävinkeln tillsammans med sadelhöjden.
  Mät den från fotot om du vill att `knee_bottom_deg` ska vara ett absolut tal och inte
  bara jämförbart mellan positioner.
- **Frontvyns skalning finns inte i koden.** Kroppsbredderna (95 mm halv hjälmbredd, 165/172 mm
  bål osv.) är hårdkodade konstanter utan spårbarhet till frontfotot, och `overlay.py` validerar
  bara sidovyn. Byter man frontfoto uppdateras ingenting automatiskt.
