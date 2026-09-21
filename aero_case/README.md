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
Skillnad mellan nätnivåerna: 0.0002 m², alltså 5 % av deltat. **Se körning 2 nedan innan du
drar slutsatser av det talet** — den överensstämmelsen var delvis tur, och den verkliga
körning-till-körning-spridningen visade sig vara 0.0010–0.0014 m².

Korskontroll mot screeningen: `fit_sweep.py` gav −1.79 % frontarea för samma ändring,
CFD:n ger −2.2 %. Skillnaden är att Cd också förbättrades något (0.566 → 0.564), alltså
flatare rygg ger både mindre area och något bättre form. Rätt tecken, rimlig storlek.

**Absolutvärdet är däremot för lågt.** CdA ≈ 0.19 och Cd ≈ 0.57 mot 0.20–0.25 respektive
0.60–0.75 för en verklig TT-ryttare — och fotot visar lös t-shirt, mjukisbyxor, sneakers,
ekerhjul och en rund hjälm, vilket i verkligheten drar uppåt. Modellen är för slät. Använd
Δ, inte absolutvärdet.

### Körning 2: pad_drop_mm=-10 saddle_fore_mm=10 saddle_up_mm=10 — GRÄNSFALL

| nät | position | CdA [m²] | std |
|---|---|---|---|
| coarse | baseline | 0.1974 | 0.0006 |
| coarse | tunad | 0.1886 | 0.0003 |
| medium | baseline | 0.1945 | 0.0012 |
| medium | tunad | 0.1899 | 0.0010 |

ΔCdA(coarse) = −0.0088 m², ΔCdA(medium) = −0.0046 m². Skillnad 0.0042 m², alltså **48 %
av deltat** — långt över 20 %-kriteriet.

### Reproducerbarheten, som föll ut gratis
Baseline-geometrin är **identisk** mellan de två körningarna, så skillnaden i baseline-CdA
mäter hur reproducerbar hela kedjan är:

| nät | körning 1 | körning 2 | skillnad |
|---|---|---|---|
| coarse | 0.1960 | 0.1974 | **+0.0014 m² (0.71 %)** |
| medium | 0.1935 | 0.1945 | **+0.0010 m² (0.52 %)** |

Ett identiskt case reproduceras alltså inte exakt. Parallell dekomposition och
MPI-reduktion är inte bitreproducerbara, och snappyHexMesh kan nätta något olika beroende
på lastbalans.

**Detta reviderar felbudgeten.** Efter körning 1 stod här att nätbruset var 0.0002 m² och
försumbart. Den siffran kom från en enda jämförelse och var för optimistisk:

| felkälla | storlek |
|---|---|
| posevariation mellan foton | 0.005–0.007 m² |
| **körning-till-körning, identiskt case** | **0.0010–0.0014 m²** |
| nätnivå, stor ändring (körning 1) | 0.0002 m² |
| nätnivå, liten ändring (körning 2) | 0.0042 m² |

Två körningar som differentieras ger alltså ett delta med osäkerhet kring **±0.0017 m²**.
Ett delta på 0.0045 är då knappt 3σ — detekterbart, men inte precist. **Upplösningsgränsen
ligger runt 2 % CdA.** Under det är siffran en gissning.

**Bättre försöksupplägg:** kör repliker på *en* nätnivå i stället för två olika nivåer. Samma
kostnad, men ger ett riktigt felstapel i stället för en nätjämförelse som vi nu vet inte är
det som begränsar.

### Körning 3: pad_drop_mm=-10 saddle_fore_mm=10 saddle_up_mm=6 · medium · 3 repliker

| replik | baseline | tunad | ΔCdA |
|---|---|---|---|
| r1 | 0.1930 | 0.1885 | −0.0045 |
| r2 | 0.1930 | 0.1884 | −0.0046 |
| r3 | 0.1953 | 0.1866 | **−0.0087** |

Medel −0.0059 ± 0.0014, **median −0.0046**. r3 ligger 3.0σ från r1/r2, som i sin tur skiljer
sig 0.0001 m² åt. Medelvärdet dras av en punkt; medianen är det tal som stämmer med
körning 1 och 2 och med screeningen.

### Brusmodellen bekräftad
Fem oberoende körningar av **identisk** baseline-geometri på medium:

| | CdA |
|---|---|
| körning 1 | 0.1935 |
| körning 2 | 0.1945 |
| körning 3, r1 | 0.1930 |
| körning 3, r2 | 0.1930 |
| körning 3, r3 | 0.1953 |

Spann 0.0023 m², **std 0.0010 m² (0.52 %)** — precis den 0.0010–0.0014 m² som gissades
efter körning 2. Deltaosäkerheten blir då σ ≈ 0.0014 m².

Notera att r1 och r2 reproducerade varandra på fjärde decimalen. Bruset är alltså inte
jämnt fördelat utan kommer i skov: oftast reproducerar pipelinen sig nästan exakt, ibland
hamnar ett jobb i ett annat nättillstånd och skiftar ~0.002 m². Sannolikt
prismalagerpåläggningen, som tar binära beslut mot kvalitetströsklar.

### Alla tre positioner är aerodynamiskt oskiljbara

| position | ΔCdA (median) | höftvinkel | knä BDC |
|---|---|---|---|
| pad −20 | −0.0045 | **54.3°** | 145.1° |
| pad −10, sadel fram 10 upp 10 | −0.0046 | 57.5° | **149.8°** |
| pad −10, sadel fram 10 upp 6 | −0.0046 | 57.6° | 147.8° |

Alla tre ligger inom 0.0001 m² av varandra, alltså **14 gånger under deltaosäkerheten**.
Slutsats: **välj på fit-vinklar, inte på CdA.** Den sista raden är den enda som håller både
höftvinkeln oförändrad och knät mitt i fit-fönstret.

### Δ-CdA: vad som faktiskt går att lita på
28 mm padhöjd ≈ 2° ryggvinkel ≈ **2 % CdA**. Konvergenstoleransen är 0.2 %, alltså tio
gånger under signalen. Det som kan dränka den är **nätbruset**: varje position ger ny STL
och nytt snappy-nät. Innan du litar på ett delta – kör samma två positioner på både
`coarse` och `fine`. Stämmer ΔCdA mellan nivåerna är deltat nätkonvergerat även om
absolutvärdena inte är det. `quick` är för att röktesta pipelinen, inte för att jämföra.

Allt detta är vid 0° yaw. Verklig CdA domineras av 5–15° yaw, och en position som vinner
rakt framifrån vinner inte nödvändigtvis i sidvind – se **Sidvind (yaw)** nedan.

**Fotografera inte om för varje position.** 1° ryggvinkel ≈ 0.0035 m² frontarea ≈ 0.0024 m²
CdA – ungefär vad 10 mm padhöjd är värd. Posevariationen mellan två foton av "samma"
position är 2–3°, alltså större än ändringen du testar, och felet är oberoende mellan foton
så det adderas i stället för att ta ut sig. Ta **ett** baselinefotopar och ändra positionen
via `FIT`. Då är landmärken, kropp och tyg identiska och bara det du ville ändra skiljer.
Fotot på den tunade positionen har en annan roll: kontrollera att du faktiskt intog den pose
modellen förutsade.

## Sidvind (yaw)
Actions → **aero-yaw** → Run workflow. Kör båda positionerna vid varje vinkel och räknar om
svepet till medeleffekt över ett varv.

Ingen åker på en fast yaw-vinkel; vinkeln följer av åkfart och vind. Vid 40 km/h ger 5 km/h
sidvind ca 7°, 10 km/h ca 14° och 15 km/h ca 21°. CdA kan skilja betydligt mer mellan 0 och
15° än mellan två sittpositioner, så svepet svarar på en fråga som `aero-delta` inte kan:
**håller positionsvinsten när det blåser?**

### Yaw görs genom att vrida geometrin, inte inloppet
Det ligger nära till hands att i stället vrida `Uinlet`. Gör inte det. Då far vaken snett ut
ur domänen – 10 m nedströms vid 15° är 2.7 m i sidled, bredare än domänens halva bredd på
2.5 m – och `sides` kan inte längre vara symmetriplan, eftersom flödet ska passera dem.
Vrids kroppen i stället ligger vaken kvar längs domänens långa axel och randvillkoren står
orörda. Vid 20° når maskinen y = ±0.41 m, väl inom `nearBox`.

`build_model.py yaw_deg=<grader>` vrider hela maskinen om lodaxeln. Fyra saker måste följa
med, och **var och en av dem är tyst om den inte gör det**:

| vad | varför |
|---|---|
| `dragDir` | drag rapporteras längs **färdriktningen**, inte längs vinden |
| `pitchAxis` | momentets referensram följer kroppen |
| hjulaxel | hjulen snurrar fortfarande kring sin egen axel |
| axelorigo | axlarna har flyttat sig |

`tools/configure_case.sh` läser alla fyra ur `model_info.json` och sätter dem; vid yaw = 0 är
de exakt de värden caset levereras med, så rakfram-körningarna påverkas inte.
`tools/check_case.py` vaktar kopplingen. **`./Allrun` på egen hand gör inte rotationen** –
den vägen går bara genom `configure_case.sh`.

Att `dragDir` måste vridas är det subtila. Vid yaw skiljer färdriktningen och vindriktningen
sig åt, och bara komponenten längs färdriktningen kostar watt – en ryttare i sidvind bär en
stor sidokraft som inte uträttar något arbete. Ett kvarglömt `(1 0 0)` kraschar ingenting,
det rapporterar bara vindaxelkraften och överdriver vad sidvinden kostar.

### CdA_eff: svepet omräknat till watt
`tools/yaw_report.py` väger ihop två effekter som drar åt motsatt håll – CdA växer med yaw,
men skenbara vinden är svag i medvind och stark i motvind – till det stillaluft-CdA som hade
kostat lika mycket över ett varv:

    CdA_eff = medel_φ[ CdA(β) · v_air² ] / V²

med vindriktningen φ likformig över varvet. Det är CdA_eff, inte CdA vid en enskild vinkel,
som avgör om en position är bättre på en blåsig dag.

### Resultat 2026-09-21: tecknet håller, storleken gör det inte

**Kortversionen: din tunade position är BÄTTRE rakt fram men SÄMRE runt 10 graders yaw,
och vinsten är borta i sidvind. Hur mycket sämre vet vi inte.**

Position: `pad_drop_mm=-10 saddle_fore_mm=10 saddle_up_mm=6` mot baseline, 12.5 m/s.

Fyra vinklar på medium, två oberoende körningar:

| yaw | ΔCdA körning 1 | ΔCdA körning 2 |
|---|---|---|
| +0° | −0.0052 | −0.0059 |
| +5° | −0.0062 | −0.0081 |
| +10° | **+0.0128** | **+0.0118** |
| +15° | −0.0046 | −0.0072 |

Vid 10 grader byter deltat tecken: den tunade positionen blir 6–7 % *sämre*. De två
körningarna är överens om det på 0.0010 m², alltså inom brusgolvet. Det är inte en
slumpmässig utreagare.

**Vad repliken inte bevisade.** `build_model.py` är deterministisk, så båda körningarna
byggde identiska STL:er och snappyHexMesh gjorde i praktiken samma nät. Repliken testade
alltså solvern och MPI-reduktionen, inte nätet — ett deterministiskt nätfel reproducerar sig
perfekt. Därför kördes samma punkt om på en annan nätnivå.

| nätnivå | ΔCdA vid 10° |
|---|---|
| coarse | +0.0058 ± 0.0006 |
| medium | +0.0118, +0.0128 |

Tecknet håller, storleken gör det inte — en faktor två mellan nivåerna. **Det underkänns av
projektets eget go/no-go-kriterium:** absolutvärdena får skilja sig, men deltat ska hålla
inom 20 % mellan nätnivåer. Vid 0 grader klarade deltat det testet (se go/no-go ovan). Vid
10 grader gör det inte det.

Slutsatsen är alltså: **effekten är verklig, siffran är det inte.** Positionen är sämre
runt 10 grader, men hur mycket är inte upplöst av de här näten.

Vad det betyder praktiskt, från båda medium-körningarna:

| | ΔCdA_eff vid 10 km/h vind (≈14° typisk yaw) |
|---|---|
| körning 1 | +0.45 % |
| körning 2 | −0.42 % |

Alltså **noll**. De −2.4 % som mättes i stilla luft överlever inte vinden. Det svaret är
robust även om 10-graderspunktens storlek skulle visa sig vara ett nätartefakt, för då är
hela kurvan osäker åt andra hållet.

**Det är inte konvergensbrus.** Coarse-körningen ger ± 0.0002 och ± 0.0005 inom
medelvärdesfönstret, utan drift- eller oupplöst-flaggor. Kraften står stilla; lösningarna är
stationära. En tidig hypotes om att simpleFoam svänger vid yaw är därmed avfärdad — men den
gav `yaw_report.py` sin svängnings- och driftdiagnostik, som numera visar det direkt.

**Öppet.** Den nätnivå som hade avgjort storleken, `fine`, saknas ännu. En vinkelförfining
runt 10 grader (8, 9, 10, 11, 12) skulle visa hur smal regimen är. Och bara plussidan av
noll är körd; cyklisten är inte spegelsymmetrisk, så −10 grader kan se annorlunda ut.

### Kostnader att känna till
- **Nätet är detsamma vid alla vinklar.** Svepet kör `configure_case.sh ... wide`, som
  breddar förfiningsboxarna (nearBox y ±0.7 m, wakeBox y ±1.1 m) vid *varje* vinkel, noll
  inräknad. Ett nät som ändrar sig med vinkeln lägger nätbrus rakt in i trenden. Följden är
  att 0°-punkten i svepet inte är bitidentisk med `aero-delta`s baseline – svepet är
  internt konsistent, vilket är det som behövs.
- **Marken rör sig med luften, inte med cykeln.** En rullande väg kan inte vridas. Vid yaw
  är det inte riktigt rätt, men alternativet – stillastående mark – ger ett falskt
  gränsskikt över hela golvet och är sämre.
- **Cyklisten är inte spegelsymmetrisk.** Ett ben är fram, kedjan sitter på höger sida. Äkta
  +β och −β skiljer sig därför. Körs bara ena sidan speglar rapporten kurvan och säger till
  om det.
- En replik per punkt. Spridningen mellan körningar är 0.0010 m², så skillnader under
  ca 0.0014 m² går inte att skilja från brus.

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
