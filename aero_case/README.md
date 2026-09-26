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

| nätnivå | ΔCdA vid 10° | 0°-kontroll, base |
|---|---|---|
| coarse | +0.0058 ± 0.0006 | – (jobbet hängde) |
| medium | +0.0118, +0.0128 | 0.1927, 0.1931 |
| **fine** | **+0.0109 ± 0.0019** | 0.1940 ± 0.0012 |

**Medium och fine är överens; det är coarse som är för grovt.** Skillnaden medium–fine är
7–15 % av deltat, alltså inom go/no-go-kriteriets 20 %. Coarse ligger en faktor två fel och
duger inte vid yaw, trots att den fungerade vid 0 grader.

Slutsatsen är alltså: **ΔCdA vid 10 grader är ungefär +0.011 till +0.013 m² och
nätkonvergerat.** Den tunade positionen är omkring 6 % sämre där. Kör inte yaw på `coarse`.

0-graderskontrollen håller också: base landar på 0.1927, 0.1931 och 0.1940 mot den gamla
baselinen 0.1930 ± 0.0010.

En reservation: fine-körningens `tuned` vid 0 grader fick driftflaggan — kraften lutade
fortfarande i medelvärdesfönstret, så körningen var avbruten vid iterationsgränsen snarare
än konvergerad. Det är den svagaste av de fyra punkterna, och 0-gradersdeltat på fine
(−0.0068 ± 0.0030) ska därför läsas med det i åtanke.

**CdA_eff från fine-svepet går inte att jämföra med medium-svepets.** Fine kördes bara på
två vinklar, så kurvan klampas vid 10 grader — allt över den vinkeln får 10-graderspunktens
värde, där den tunade positionen är som sämst. Medium-svepets fyra vinklar, som fångar att
positionen är bättre igen vid 15 grader, är rätt underlag för CdA_eff. Använd det.

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

### Var sitter skillnaden? (uppdelning per kroppsdel, medium)

Svepet jämför två positioner, och **bara ryttaren skiljer sig mellan dem**. ΔCdA per
kroppsdel, tuned minus base:

| yaw | rider | bike | wheels |
|---|---|---|---|
| +0° | −0.0054 | +0.0006 | −0.0001 |
| +5° | −0.0060 | −0.0002 | −0.0003 |
| +10° | **+0.0072** | +0.0030 | +0.0013 |
| +15° | −0.0046 | −0.0013 | +0.0004 |

**Ryttaren bär alltihop.** Hjulen ligger mellan −0.0001 och +0.0013 i alla fyra vinklar,
alltså noll, vilket de ska göra eftersom det är identisk geometri. Hjulraden är därför inte
ett resultat utan **kontrollen**: samma geometri ska ge samma motstånd vinkel för vinkel, och
gör den inte det har näten eller körningarna drivit isär.

Positionen är −0.005 till −0.006 bättre vid 0 och 5 grader, tappar +0.007 vid 10, och är
tillbaka på −0.005 vid 15. En hack i kurvan vid en vinkel, inte en bred försämring.

Cykeln vid 10 grader (+0.0030) är det enda som sticker ut i kontrollen. Ramen är identisk, så
antingen ändrar ryttarens position flödet ner över den, eller så har näten drivit isär vid
just den vinkeln. Med en replik per punkt går det inte att avgöra vilket, och det är ett skäl
att köra 8–12 grader innan man tror på hacken.

### Vinkelförfining 8–12°: hacken är EN grad bred, alltså inte fysik

| yaw | ΔCdA rider | ΔCdA bike | ΔCdA wheels |
|---|---|---|---|
| +8° | −0.0005 | +0.0028 | −0.0001 |
| +9° | −0.0029 | +0.0022 | +0.0003 |
| +10° | **+0.0096** | +0.0035 | +0.0011 |
| +11° | −0.0044 | +0.0010 | +0.0002 |
| +12° | – | – | – |

Vid 8, 9 och 11 grader är den tunade positionen bättre, i linje med 5° (−0.0060) och 15°
(−0.0046). Bara vid exakt 10 grader vänder tecknet. **En hack som är en grad bred är inte en
aerodynamisk effekt** — verklig yaw-beroende interferens varierar slätt över flera grader.
10-graderscaset är avvikande.

**Varför nätstudien inte fångade det.** Coarse, medium och fine gav alla samma tecken vid 10
grader, och det tolkades som att effekten var verklig. Men alla tre nivåerna byggde på
*samma STL vid 10 grader*. Hela kedjan är deterministisk, så ett fel som uppstår före eller
i samband med geometrin reproducerar sig perfekt på varje nätnivå. Att variera nätet testar
bara det som ligger nedströms geometrin. Samma fälla som med replikerna: två körningar av
identisk geometri testade solvern, inte nätet.

Lärdomen är generell: **när pipelinen är deterministisk bevisar reproducerbarhet ingenting
om felkällor uppströms.** För att testa geometrin måste man variera geometrin — här vinkeln.

**Följd för slutsatsen.** CdA_eff-siffrorna som räknades fram tidigare byggde på en kurva som
innehöll 10-graderspunkten. Tas den bort är ΔCdA negativ i hela det mätta intervallet, och
påståendet att positionsvinsten försvinner i sidvind vilar då på en enda dålig punkt.

Körningen gjordes på geometrin **före** commit 16414b1 (vadstaven och huvudproportionerna).
Talen går inte att jämföra med något som körs efter den.

<details><summary>Bakgrund: vad yaw gör med varje del i sig (ändring från 0°, negativt = vinst)</summary>

| yaw | del | base | tuned |
|---|---|---|---|
| +5° | rider | −0.0067 | −0.0072 |
| +5° | bike | +0.0015 | +0.0008 |
| +5° | wheels | +0.0048 | +0.0045 |
| +10° | rider | −0.0191 | −0.0064 |
| +10° | bike | +0.0006 | +0.0030 |
| +10° | wheels | +0.0080 | +0.0094 |
| +15° | rider | −0.0224 | −0.0216 |
| +15° | bike | +0.0039 | +0.0020 |
| +15° | wheels | +0.0119 | +0.0123 |

Det här är gemensam mod och svarar inte på vad positionen gör, men det förklarar varför
totalen sjunker med yaw: ryttarens motstånd faller −0.022 m² från 0 till 15 grader och äter
upp hjulens förlust.

**Hjulen seglar inte.** De blir monotont sämre med yaw, +0.0048 → +0.0080 → +0.0119. Den
seglingseffekt riktiga djupa fälgar ger finns inte här: hjulen är modellerade som plana
skivor med däck, inte som vingprofiler, så de bidrar bara med växande area och avlösning.
Vill man studera seglingseffekten måste fälgprofilen modelleras.

</details>

**Öppet.** Den nätnivå som hade avgjort storleken, `fine`, saknas ännu. En vinkelförfining
runt 10 grader (8, 9, 10, 11, 12) skulle visa hur smal regimen är. Och bara plussidan av
noll är körd; cyklisten är inte spegelsymmetrisk, så −10 grader kan se annorlunda ut.

### Resultat 2026-09-22 på RÄTTAD geometri (commit 23f3ed4 och framåt)

Rund hjälm 280 mm i stället för 324 mm TT-hjälm med svans, fixad vadstav, rättade
huvudproportioner. **Inga äldre CdA-tal i det här dokumentet är jämförbara med de här.**

| yaw | base CdA ± svängning | tuned CdA ± svängning | ΔCdA |
|---|---|---|---|
| +0° | 0.1956 ± 0.0018 | 0.1936 ± 0.0008 | −0.0019 ± 0.0020 ⚠ |
| +5° | 0.1962 ± 0.0016 | 0.1918 ± 0.0012 | −0.0043 ± 0.0020 |
| +10° | 0.1886 ± 0.0008 | 0.1915 ± 0.0012 | +0.0029 ± 0.0014 |
| +15° | 0.1933 ± 0.0007 | 0.1815 ± 0.0016 | **−0.0118 ± 0.0018** |

ΔCdA per kroppsdel:

| yaw | rider | bike | wheels |
|---|---|---|---|
| +0° | −0.0026 | +0.0011 | −0.0004 |
| +5° | −0.0062 | +0.0023 | −0.0005 |
| +10° | **+0.0014** | +0.0016 | −0.0002 |
| +15° | −0.0125 | +0.0014 | −0.0007 |

**10-gradersavvikelsen krympte med en faktor fem.** Ryttardeltat gick från +0.0072 på den
gamla geometrin (och +0.0096 i engradersvepet) till +0.0014. Totaldeltat är +0.0029 ± 0.0014,
alltså knappt två gånger sin egen osäkerhet. Geometrifelen — vadstaven som stack ut 101 mm
och TT-hjälmen som inte finns — stod för det mesta av den, men inte allt. Något litet finns
kvar vid just den vinkeln.

Kontrollen är också renare: cykeln ligger på +0.0011 till +0.0023 mot +0.0028 och +0.0035
tidigare, och spikar inte längre vid 10 grader. Den är dock systematiskt positiv vid alla
vinklar, vilket är rimligt — en lägre ryttare ändrar vad som matas ner över ramen — men det
är en offset att hålla ögonen på.

### Bilden har vänt: vinsten VÄXER med vinden

| vind [km/h] | typisk yaw | base CdA_eff | tuned CdA_eff | ΔCdA_eff | Δ % |
|---|---|---|---|---|---|
| 0 | 0° | 0.1956 | 0.1936 | −0.0019 | −0.98 % |
| 5 | 7° | 0.1980 | 0.1952 | −0.0028 | −1.40 % |
| 10 | 14° | 0.2048 | 0.2009 | −0.0038 | −1.88 % |
| 15 | 22° | 0.2203 | 0.2126 | −0.0077 | −3.50 % |
| 20 | 30° | 0.2415 | 0.2319 | −0.0096 | **−3.97 %** |

Det är motsatsen till vad den gamla geometrin gav, där vinsten försvann i sidvind. Nu är den
**marginell i stilla luft och växer med vinden**. Mekanismen syns i uppdelningen: den tunade
ryttaren vinner −0.0255 m² på att vridas till 15 grader mot baselines −0.0156. En lägre,
flatare ryttare tjänar mer på yaw.

### Replik: resultatet håller

Två oberoende körningar av identisk geometri (run 35717653137 och 35739559095). Det ger
spridningen mellan körningar på den rättade geometrin — siffran som tidigare lånats från den
gamla modellen.

| yaw | ΔCdA körning 1 | ΔCdA körning 2 | skillnad |
|---|---|---|---|
| +5° | −0.0043 | −0.0050 | 0.0007 |
| +10° | +0.0029 | +0.0029 | **0.0000** |
| +15° | −0.0118 | −0.0115 | 0.0003 |

**Spridningen mellan körningar är 0.0000–0.0007 m²**, alltså tätare än de 0.0010 vi lånat
från den gamla geometrin. Absoluta CdA reproducerar på 0.0002–0.0009.

Konsekvenser:

- **15-graderspunkten håller.** −0.0118 och −0.0115, skillnad 0.0003 mot en effekt på 0.0115.
  Effekten är trettio gånger spridningen. Vändningen — att positionsvinsten växer med vinden
  — är reell på den här geometrin.
- ~~**10-gradersblippen är också reell**~~ — **den här slutsatsen är motbevisad**, se
  avsnittet med kappmuskeln nedan. +0.0029 båda gångerna, exakt, mätte att samma geometri ger
  samma svar. Med siluetthålet ifyllt är punkten −0.0055. Reproducerbarhet säger ingenting om
  huruvida geometrin var rätt.
- **Kontrollen är utmärkt.** Hjulen ligger på −0.0002 till −0.0011 i båda körningarna, alltså
  noll. Cykeln rör sig mest vid 15 grader (+0.0014 mot −0.0002), vilket är den största
  kontrollavvikelsen och värd att hålla ögonen på.

CdA_eff vid höga vindar reproducerar nästan exakt: −3.50 % mot −3.54 % vid 15 km/h, och
−3.97 % mot −3.98 % vid 20 km/h.

**0-graderspunkten saknas i replikeringen.** `y0-base` föll på aptstallet i den andra
körningen, så låg vind går inte att jämföra mellan körningarna. Det är just den punkt som var
flaggad som under brusgolvet, alltså den vi mest ville se replikerad.

Båda körningarna gjordes på geometrin **före** kappmuskeln (commit 7df9390). Siluetthålet
mellan hjälmens bakkant och axeln var 342 mm i dessa körningar och är nu 86 mm, så nästa
körning ger andra tal.

### Resultat 2026-09-22 MED kappmuskeln (commit 7df9390 och framåt)

Run 35762358159, medium, `[0,5,10,15]`, containerbild. Alla åtta jobb gröna — inklusive
`y0-base`, som föll två gånger på aptstallet och nu för första gången har ett värde.

| yaw | base CdA ± svängning | tuned CdA ± svängning | ΔCdA |
|---|---|---|---|
| +0° | 0.1896 ± 0.0009 | 0.1918 ± 0.0011 | **+0.0022** ± 0.0014 |
| +5° | 0.1959 ± 0.0016 | 0.1895 ± 0.0015 | −0.0064 ± 0.0022 |
| +10° | 0.1931 ± 0.0013 | 0.1876 ± 0.0009 | −0.0055 ± 0.0015 |
| +15° | 0.1939 ± 0.0028 | 0.1801 ± 0.0010 | −0.0138 ± 0.0030 |

#### Kappmuskeln flyttade DELTAT, inte bara absolutvärdet

Det var frågan som körningen fanns till för att svara på. Replikspridningen på den gamla
geometrin var 0.0000–0.0007 m². Allt som rör sig mer än så är geometrifixen.

| yaw | ΔCdA före | ΔCdA efter | flytt | mot spridning |
|---|---|---|---|---|
| +0° | −0.0019 | **+0.0022** | +0.0041 | 5.9× |
| +5° | −0.0046 | −0.0064 | −0.0018 | 2.5× |
| +10° | **+0.0029** | **−0.0055** | −0.0084 | **12×** |
| +15° | −0.0117 | −0.0138 | −0.0021 | 3.1× |

Varenda punkt flyttade sig mer än spridningen, och två av dem bytte tecken. Ett 342 mm hål i
siluetten var alltså inte en kosmetisk defekt utan bar en del av svaret.

#### 10-gradershacket var en artefakt — ÖVERSPELAT, se körningen 2026-09-25

Föregående avsnitt drog slutsatsen att blippen vid 10° var *"inte brus, den är en egenskap hos
geometrin"* — den reproducerade ju till +0.0029 på fjärde decimalen i två oberoende körningar.
Den slutsatsen var fel. Med hålet ifyllt är punkten −0.0055, alltså i linje med grannarna.

Reproducerbarheten var äkta. Den mätte bara att samma geometri ger samma svar, inte att
geometrin var rätt. Det är precis den felkälla som determinism inte kan upptäcka.

Kurvan är nu fysikaliskt läsbar: ingen vinst rakt framifrån, ett steg ner till ungefär −0.006
vid 5–10° (de två punkterna är oskiljbara inom sina felstaplar), och en större vinst vid 15°.

#### Stilla luft har bytt tecken

Absolut `base` CdA vid 0° föll från 0.1956 till 0.1896 — den största absoluta ändringen i hela
tabellen, och den sitter just vid den vinkel där flödet går rakt in i skåran. Vid 10° gick den
i stället **upp** 0.0044. Fixen är alltså inte en konstant förskjutning.

Deltat vid 0° gick från −0.0019 till **+0.0022 ± 0.0014**. I stilla luft är den trimmade
positionen nu marginellt *sämre*, inte bättre. Siffran är 1.6× sin egen svängning och 2.2× den
uppmätta körning-till-körning-spridningen på 0.0010 — den är över brusgolvet, men inte med
någon marginal att tala om. Läs den som "ingen vinst i stilla luft, möjligen en liten förlust".

#### Vad det kostar i watt — ÖVERSPELAT, se körningen 2026-09-25

| vind | typisk yaw | ΔCdA_eff | Δ% | watt | över passet |
|---|---|---|---|---|---|
| 0 km/h | 0° | +0.0022 | +1.17 % | **+1.8 W** | +4 Wh |
| 5 km/h | 7° | −0.0043 | −2.17 % | −3.6 W | −8 Wh |
| 10 km/h | 14° | −0.0075 | −3.65 % | −6.3 W | −14 Wh |
| 15 km/h | 22° | −0.0107 | −4.86 % | −9.0 W | −20 Wh |
| 20 km/h | 30° | −0.0127 | −5.25 % | −10.7 W | −23 Wh |

Brytpunkten ligger mellan 0 och 5 km/h vind. I praktiken: positionen betalar sig så fort det
blåser alls, och kostar knappt något när det inte gör det. Vinsten är också större än före
fixen — −5.25 % mot −3.97 % vid 20 km/h.

#### Förbehåll på den här körningen

- **15-graderspunkten bär den största effekten och har den svagaste grunden.** Rapporten
  flaggar att kraften fortfarande lutar i fönstret för `base` vid +15° — körningen avbröts vid
  iterationsgränsen utan att konvergera. Svängningen är också störst där (±0.0028). Vinkeln som
  driver hela slutsatsen om sidvind är alltså den som behöver fler iterationer.
- **Kontrollen håller.** Hjulen ligger på −0.0001 till −0.0012, alltså noll. Cykeln är störst
  vid +5° med +0.0015, vilket är en femtedel av ryttarens −0.0075 vid samma vinkel. Samma
  storleksordning som före fixen.
- **En replik per punkt igen.** Den här körningen har inga repliker på den nya geometrin, så
  spridningen 0.0000–0.0007 m² är lånad från den gamla. Rimligt, men lånad.
- Fortfarande bara plussidan av noll.

### Vad som INTE är avgjort

Uppdaterat efter körningen med kappmuskeln.

- **15-graderspunkten är inte konvergerad.** `base` vid +15° avbröts vid iterationsgränsen med
  kraften fortfarande lutande. Det är den punkt som bär den största effekten i hela svepet.
  Detta är den enskilt viktigaste bristen just nu.
- **Stilla luft är fortfarande inte avgjort**, men av motsatt skäl mot förut. Deltat vid 0° är
  nu +0.0022 ± 0.0014, alltså nätt och jämnt över brusgolvet och med fel tecken mot vad vi
  först trodde. Påståendet är "ingen vinst i stilla luft", inte "en vinst" och inte "en
  säkerställd förlust".
- **Inga repliker på den nya geometrin.** Spridningen 0.0000–0.0007 m² är mätt på geometrin
  före kappmuskeln och lånad hit.
- **Bara plussidan av noll.** Cyklisten är inte spegelsymmetrisk.
- Svängningsamplituderna (±0.0009 till ±0.0030) är större än brusgolvet på 0.0010. Använd ± i
  tabellen, inte 0.0010.

Nästa steg som faktiskt avgör något, i ordning: **fler iterationer vid 15°**, sedan
**repliker på den nya geometrin**. Fler vinklar avgör ingenting.

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

## Foto-genererad 3D-modell (2026-09-25)

En AI-genererad STL från fotot, `3D.from.pic.stl`, 1 760 114 trianglar, 88 MB. Rå fil ligger
som release-asset `scan-v1`, inte i git.

### Skalan går att låsa mot hjulet

Modellen kommer i godtyckliga enheter, normerad till en 100-enheters låda. Skalan hämtas ur
hjulet, som är den mest välbestämda geometrin i hela meshen — 700c + 25 mm däck = 672 mm.

Hough-ackumulering på centrumplanet, med villkoret att båda hjulen står på samma golv
(`cz = zmin + r`). Utan det villkoret låser sökningen på kramkransen, som är en renare cirkel
än hjulet.

**16.6337 mm/enhet.** Fyra oberoende kontroller på den skalan:

| mått | modellen | verkligt |
|---|---|---|
| hjulradie fram vs bak | identiska | – |
| hjulbas | 965 mm | 980–1020 |
| hjulbas / hjuldiameter | 1.436 | 1.46–1.52 |
| totallängd × bredd × höjd | 1663 × 506 × 1375 mm | rimligt |

Cykeln är alltså rätt proportionerad.

### Men kroppen är generisk, inte vår ryttare

| | skanning | parametrisk |
|---|---|---|
| total volym | 0.1232 m³ | 0.0896 m³ |
| frontalarea (samma rastermetod) | 0.4602 m² | 0.3599 m² |

Ryttarens volym blir ~0.108 m³, vilket vid 1016 kg/m³ ger **105–110 kg**. Ryttaren väger 69.

Det går inte att skala bort: för 69 kg måste allt krympa 13 %, och då blir hjulen 587 mm och
hjulbasen 843 mm. Verktyget byggde en generisk kropp i cykelns skala.

Uppblåsningen är **jämnt utspridd**, inte lokaliserad till löst tyg på benen:

| höjd över mark | kvot skanning/parametrisk |
|---|---|
| 200–400 mm (fötter, vev) | 1.28× |
| 400–700 mm (vader, lår) | 1.24× |
| 700–900 mm (lår, höft) | 1.22× |
| **900–1200 mm (bål, armar)** | **1.39×** |
| 1200–1300 mm (rygg, nacke) | 1.19× |

Värsta bandet är bålen och armarna. En rak inbytning av överkroppen skulle alltså importera
den mest uppblåsta regionen.

### Symmetri

Bästa symmetriplanet ligger på **y = +17.5 mm**, inte noll. Efter centrering är
medianavvikelsen mot spegelbilden 5.0 mm, alltså 1 % av bredden.

| höjd över mark | median | p90 |
|---|---|---|
| 200–600 mm | 3–9 mm | 87–109 mm |
| 800–1200 mm | 8 mm | 41–54 mm |
| 1200–1400 mm | 3.2 mm | 8.7 mm |

Det nedre bandet **ska** vara asymmetriskt — ena benet uppe, andra nere, och kedja, kassett
och växel sitter bara på höger sida. Där vore spegling fel. Det misstänkta bandet är
800–1200 mm, höft och bål, som borde vara symmetriskt. Huvudet högst upp är utmärkt.

### Resultat 2026-09-25 med nape + hjälmbredd 205, 2500 iterationer — SLUTSATSERNA HÅLLER INTE

Run 36183594465, commit 70e21da, alla åtta jobb gröna.

| yaw | base CdA ± svängning | tuned CdA ± svängning | ΔCdA |
|---|---|---|---|
| +0° | 0.1923 ± 0.0012 | 0.1897 ± 0.0013 | −0.0026 ± 0.0018 |
| +5° | 0.1983 ± 0.0026 | 0.1889 ± 0.0010 | −0.0095 ± 0.0028 |
| +10° | 0.1899 ± 0.0012 | 0.1928 ± 0.0017 | **+0.0030** ± 0.0021 |
| +15° | 0.1918 ± 0.0017 | 0.1912 ± 0.0008 | **−0.0006** ± 0.0019 ⚠ |

#### Deltat är inte konvergerat med avseende på geometridetalj

Det här är körningens viktigaste besked, och det är negativt.

| yaw | A replik 1 | B replik 2 | C kappmuskel | D nape+hjälm |
|---|---|---|---|---|
| +0° | −0.0019 | – | +0.0022 | −0.0026 |
| +5° | −0.0043 | −0.0050 | −0.0064 | −0.0095 |
| +10° | **+0.0029** | **+0.0029** | **−0.0055** | **+0.0030** |
| +15° | −0.0118 | −0.0115 | −0.0138 | **−0.0006** |

| | hur mycket deltat flyttade sig |
|---|---|
| replik, identisk geometri (B−A) | 0.0000–0.0007, medel 0.0003 |
| kappmuskeln (C−B) | 0.0014–0.0084, medel 0.0040 |
| nape + hjälmbredd (D−C) | 0.0031–0.0132, **medel 0.0074** |

**Den andra geometriändringen var mycket mindre än den första och flyttade svaret 1.8 gånger
mer.** Kappmuskeln fyllde ett hål på 342 mm. `nape` fyllde en grop på 42 mm och breddade
hjälmen 15 mm. Hade modellen närmat sig ett svar skulle den andra ändringen ha flyttat
mindre, inte mer.

Successiva förfiningar konvergerar alltså inte. Effekten vi mäter (0.002–0.010 m²) är mindre
än modellens känslighet för geometridetaljer vi ännu inte fått rätt.

#### Vad som föll

- **10-gradershacket har bytt tecken tre gånger**: +0.0029, +0.0029, −0.0055, +0.0030. Det är
  inte en egenskap hos geometrin och inte brus i vanlig mening — det följer varje
  geometriändring. Slutsatsen i föregående avsnitt, att kappmuskeln avslöjade hacket som en
  artefakt, var för tidig. Hacket kom tillbaka.
- **15-graderspunkten kollapsade** från −0.0138 till −0.0006 och flaggas nu som mindre än sin
  egen svängning. Rapportens ord: "Där finns ingen mätbar skillnad mellan positionerna."
  Nästan hela rörelsen sitter i `tuned`, som gick 0.1801 → 0.1912. Det gamla värdet 0.1801 var
  det lägsta i hela tabellen, med minsta svängningen, och bar ensamt slutsatsen om att
  positionsvinsten växer med vinden. Det har inte reproducerats.
- **CdA_eff-bilden är omvänd.** Förut +1.17 % i stilla luft och −5.25 % vid 20 km/h vind,
  alltså en vinst som växte med vinden. Nu −1.35 % i stilla luft och −0.83 % vid 20 km/h,
  alltså en vinst som krymper. Båda kan inte stämma.

#### Fler iterationer var fel medicin

1500 → 2500 iterationer gav **ingen** krympning av svängningsamplituderna:

| | svängning, åtta fall |
|---|---|
| 1500 iter | 0.0009 0.0016 0.0013 0.0028 · 0.0011 0.0015 0.0009 0.0010 |
| 2500 iter | 0.0012 0.0026 0.0012 0.0017 · 0.0013 0.0010 0.0017 0.0008 |

Och konvergensflaggan försvann inte — den **flyttade**, från base vid +15° till base vid +5°.
En körning som inte konvergerar vid 2500 iterationer och vars oro byter vinkel mellan
körningar är inte underiterered. Flödet vid yaw är genuint instationärt, och stationär RANS med
medelvärde över ett fast fönster är fel verktyg för det.

Kontrollen försämrades också: `bike` vid +15° ligger på +0.0029 trots identisk geometri, vilket
rapporten själv flaggar.

#### Vad som fortfarande står

Bara en sak har varit stabil genom alla fyra körningarna:

- **+5° har varit negativt varje gång**: −0.0043, −0.0050, −0.0064, −0.0095. Tecknet håller.
  Storleken gör det inte — den har mer än fördubblats.

Allt annat har bytt tecken eller storleksordning minst en gång.

#### Vad som måste göras innan någon siffra används igen

I den här ordningen, och inte fler vinklar:

1. **Nätkonvergens på DELTAT.** Varenda körning hittills är på `medium`. Ändrar sig deltat
   mellan `medium` och `fine` är siffran inte nätupplöst, och då spelar geometridetaljerna
   ingen roll än. Det här steget borde ha kommit före allt annat i det här avsnittet.
2. **Instationär körning eller mycket längre medelvärde vid yaw**, eftersom flödet där inte
   går mot ett stationärt tillstånd.
3. Först därefter geometridetaljer.

Tills dess gäller: **reproducerbarheten är utmärkt (0.0003) och noggrannheten okänd.** Att
samma geometri ger samma svar har vi bevisat fyra gånger. Att svaret är rätt har vi inte
bevisat en enda gång.

### Renderingar

Vyerna som mätningarna nedan bygger på ligger i `docs/scan/`:

| fil | vad den visar |
|---|---|
| `01-helvy.png` | hela modellen från sidan |
| `02-huvudparti-rutnat.png` | huvudpartiet med mm-rutnät i x och z — den mest användbara |
| `03-huvudholje-tre-vyer.png` | det utskurna huvudhöljet, sida/fram/ovan |
| `04-siluettjamforelse.png` | sagittalsiluett mot den parametriska modellen, uppriktade i hjässan |
| `06-hjalm-kapad.png` | den kapade hjälmen i tre vyer, med bakstyckesgallring |

Siluettjämförelsen är svårläst eftersom poserna skiljer sig påtagligt. Läs den med skepsis.

### Huvudpartiet: `geometry/scan_helmet_crop.stl`

Hjälmen och huvudet är ett sammansmält skal **utan söm**, så hjälmen går inte att skära ut för
sig. Två metoder provade, båda misslyckas:

- **Planskärning** tar antingen med axelkrönet eller klipper hjälmens bakkant. Det finns ingen
  plannivå som skiljer dem.
- **Regionväxt längs ytan**, som ska stanna vid en skarp kant, rinner över 85 % av meshen redan
  vid 18° tröskel. Skanningen har ingen skarp kant vid hjälmbrättet — ytan är slät hela vägen.

Det som ligger incheckat är därför en **kapad låda**, x < −348, z > 1250, |y| < 118: vattentät,
30 k trianglar, 241 × 236 × 125 mm. Referensgeometri, inte körbar.

> **De plana ytorna i filen är mina snittplan, inte geometri.** Likaså sitter små utskjutande
> flikar kvar i bakkanten där nacke och axel passerar snittet. Öppnas filen i en visare som
> inte kullar baksidor ser de ut som vingar på hjälmen. Det är de inte.
>
> En tidigare version, `scan_head_shell.stl`, var dessutom **öppen** — snitten kapades inte —
> så visaren ritade skalets insida genom hålen. Den filen är borttagen.

Hjälmens mått, med armarna uteslutna Hjälmens mått, med armarna uteslutna (x ∈ [−600, −360]):

| | längd | bredd | höjd |
|---|---|---|---|
| skanning rå | 275 | 260 | (140, trunkerad av snittet) |
| skanning ÷1.28 | 215 | 203 | – |
| `HELMET` i dag | 280 | 190 | 165 |

Längden stämmer. Bredden är ~7 % större än modellens efter uppblåsningskorrigering.
Höjdsiffran duger inte — mätfönstret skär av hjälmens underkant.

Frontalarean räknad **nedåt från varje modells egen hjässa**, vilket tar bort poseskillnaden
(skanningens ryttare sitter 28 mm lägre):

| mm under hjässan | kvot | mot baslinjen 1.28× |
|---|---|---|
| 0–80 | 1.25–1.47 | normal |
| **80–120** | **1.67–2.01** | **kraftigt över** |
| 120–300 | 1.21–1.48 | normal |

80–120 mm under hjässan är övergången hjälm–axel, alltså samma region som kappmuskeln
fyllde. Skanningen säger att den fortfarande är för smal i den parametriska modellen.
Jämförelsen störs av att poserna skiljer sig, så det är en indikation, inte ett mått.

### Övrigt som skulle bitit senare

- **Euler-tal −602**, alltså 302 genomgående tunnlar i ytan. Osynliga i renderingen, men
  `surfaceFeatureExtract` skulle bli tokig på dem.
- **Ekrarna finns med.** Riktiga ekrar är ~2 mm mot finaste cellen 3.91 mm. Snappy kan inte
  upplösa dem. Den parametriska modellen utelämnar dem medvetet.
- Ett löst skräpfragment på 62 trianglar låg i filen.

### Åtgärd: nacken fyller gropen bakom hjälmen (2026-09-25)

Skanningens tydligaste besked gäller siluetten bakåt från hjässan. Mätt som övre
höljelinjen i en sagittal skiva på ±30 mm, z relativt hjässan:

| mm bakom hjässan | skanning | parametrisk FÖRE | parametrisk EFTER |
|---|---|---|---|
| 40 | −2 | −13 | −10 |
| 60 | −6 | **−134** | −41 |
| 80 | −11 | −118 | −99 |
| 140 | −33 | −97 | −98 |

Den parametriska modellen hade ett **lokalt minimum** — ytan föll till −134 och steg sedan
tillbaka till −97. Alltså en konkav grop, 42 mm djup, samma sorts defekt som hålet på 342 mm
men mindre. Skanningen har ingen: dess linje faller monotont.

Orsaken satt i koordinaterna. Kappmuskelns framkant slutade vid bygg-x 419 medan hjälmens
bakre spets ligger vid x 457 — **38 mm glapp** utan något som bar siluetten.

Åtgärden är en fjärde ellipsoid i kappmuskelns skal, `nape`, som fyller glappet framåt-uppåt.

| | före | efter |
|---|---|---|
| skårdjup | 42.2 mm | **3.5 mm** |
| `girth_scale` | 0.9093 | 0.9066 |
| `rider_implied_mass_kg` | 69.09 | 69.09 |
| `frontal_area_m2` | 0.3509 | 0.3519 |

**Stoppvillkoret är cellstorleken.** Finaste cellen vid ytan är 3.91 mm, så en grop grundare
än så kan nätet inte upplösa. Större `nape` gav 1.8 och 1.4 mm men lade till material för
ingenting — 3.5 mm är under gränsen och där slutar vi.

Massaförankringen sköter sig själv: `calibrate_girth` löser om `g` mot 69 kg, så den tillagda
halsvolymen krympte resten 0.3 %. Modellen kan alltså inte blåsas upp av den här sortens fix.

**Skanningens absoluta profil jagas INTE.** Dess ryttare har plattare rygg, så rygghöjden
relativt hjälmen är en poseskillnad och inte ett fel. Bara den lokala gropen är åtgärdad.

Samtidigt: `HELMET['width_mm']` 190 → 205, ur skanningens 260 mm delat med den generella
uppblåsningen 1.28.

Se `docs/scan/05-nacke-efter.png`.

### Oavsiktlig men avgörande: 10° är stabilt, 0° är inte konvergerat (2026-09-26)

Run 36224931538 kördes för fältbildernas skull, `[0,10]`, 1500 iterationer, commit 2ebb5ae.
`build_model.py` är **oförändrad** sedan 70e21da, så geometrin är identisk med körningen dagen
före. Enda skillnaden är iterationstalet. Det gör paret till ett rent experiment på numeriken.

| | 2500 iter | 1500 iter | skillnad |
|---|---|---|---|
| 0° base | 0.1923 | 0.1952 | **+0.0029** |
| 0° tuned | 0.1897 | 0.1889 | −0.0008 |
| **0° ΔCdA** | **−0.0026** | **−0.0063** | **0.0037** |
| 10° base | 0.1899 | 0.1899 | **0.0000** |
| 10° tuned | 0.1928 | 0.1929 | 0.0001 |
| **10° ΔCdA** | **+0.0030** | **+0.0030** | **0.0000** |

**10-graderspunkten reproducerar på fjärde decimalen** mellan 1500 och 2500 iterationer. Den är
konvergerad, och de extra tusen iterationerna ändrade ingenting.

**0-graderspunkten gör det inte.** Deltat rör sig 0.0037, fem gånger replikspridningen, och
`base` ensam flyttar 0.0029. Vid 1500 iterationer driver 0°-fallet fortfarande.

Det vänder på antagandet som styrde de senaste dagarnas arbete. Jag valde 10° som
diagnosvinkel eftersom dess tecken bytt tre gånger och jag läste det som instabilitet. Tecknet
bytte mellan **geometriversioner**, inte mellan körningar. Punkten är numeriskt stenhård och
extremt geometrikänslig — vilket är två helt olika problem.

Konsekvenser:

- Slutsatsen att deltat inte är konvergerat med avseende på geometridetalj **står kvar**, och
  får nu stöd från andra hållet: samma geometri ger samma svar på fjärde decimalen, så när
  svaret ändå flyttar sig är det geometrin.
- Alla 0°-siffror från körningar med **1500 iterationer är underiterererade** och ska inte
  jämföras med 2500-iterationskörningen. Det gäller replikerna, kappmuskelkörningen och den här.
- CdA_eff-tabellen i den här körningen vilar på ett underiterererat 0° och ska inte läsas som
  ett resultat.

Minsta iterationstal för 0° är alltså **över 1500**. Om det räcker med 2500 är inte visat — det
kräver ett tredje steg, exempelvis 3500, för att se om 0° då står still.

### Fältbilderna svarar: deltat är en korsning, inte ett hopp (2026-09-26)

Run 36224931538 med fältdata. Två valideringar först, eftersom en fältbild är värdelös om
skalningen är fel:

- **Stagnationstrycket ger Cp = +1.014.** Läroboksfacit är exakt 1.0. Trycket och skalningen
  stämmer.
- **Ytintegralen reproducerar rapportens CdA.** Summan av tryck- och friktionsbidrag per
  triangel ger 0.1916 mot rapporterade 0.1899 vid y10-base, alltså 0.9 % fel. Uppdelningen
  nedan går därför att lita på.

#### Ett teckenfel, funnet av integralen

OpenFOAMs `wallShearStress` returnerar spänningen med **motsatt tecken mot
strömningsriktningen**. Med råa värden blev friktions-CdA −0.0111 m², och friktionsmotstånd
måste vara positivt i färdriktningen. Vänt tecken ger +0.0111, vilket är **5.8 % av total CdA** —
rimligt för en trubbig kropp.

Utan den vändningen läste bilden bakvänt: allt attached flöde såg ut som backströmning.
`tools/plot_fields.py` vänder nu tecknet och motiverar det i koden.

#### Det som faktiskt hände

| ryttarens CdA | 0° | 10° | ändring |
|---|---|---|---|
| base | 0.1275 | 0.1144 | **−0.0131** |
| tuned | 0.1179 | **0.1179** | **0.0000** |

**Den trimmade positionen är oförändrad av yaw. Basen tappar kraftigt.** Tecknet på ΔCdA vänder
mellan 0° och 10° därför att **kurvorna korsar varandra**, inte för att någon punkt hoppar.

Det förklarar hela instabiliteten. Deltat är differensen mellan en brant fallande och en platt
kurva. Var de korsas avgör tecknet, och korsningen flyttar sig lätt när geometrin ändras.

#### Och det sitter i ett enda band

CdA-bidrag per höjdband över mark, se `docs/fields/01-hojdband.png`:

| höjd | 0° base | 0° tuned | Δ | 10° base | 10° tuned | Δ |
|---|---|---|---|---|---|---|
| 600–750 | 0.0239 | 0.0212 | −0.0027 | 0.0187 | 0.0185 | −0.0002 |
| 900–1050 | 0.0138 | 0.0167 | +0.0029 | 0.0194 | 0.0193 | −0.0001 |
| **1050–1200** | **0.0318** | **0.0259** | **−0.0059** | **0.0257** | **0.0309** | **+0.0052** |
| 1200–1350 | 0.0176 | 0.0149 | −0.0027 | 0.0157 | 0.0138 | −0.0019 |

**Bandet 1050–1200 mm vänder ensamt.** Det är övre ryggen och axlarna, strax under
axelleden på 1229 mm. Vid 0° är `tuned` klart bättre där, vid 10° klart sämre. Ingen annan del
av kroppen gör något liknande.

Och bandet **1200–1350 mm** är precis där `nape`-ellipsoiden lades till. Att den ändringen
flyttade 10-graderspunkten 0.0085 är alltså inte längre förvånande — den satt mitt i en av de
två stora termer som nästan tar ut varandra.

Slutsatsen att deltat inte är konvergerat med avseende på geometridetalj står alltså kvar, men
nu med en mekanism: **ΔCdA är en liten rest mellan stora motverkande bidrag i övre ryggen.**
Rör man geometrin där rör sig resten oproportionerligt.

Väggskjuvningen i det bandet, base mot tuned, finns i `docs/fields/02-bal-10grader.png`. Den
visar skillnaden men inte dramatiskt — siffrorna är det starkare beviset, bilden stödjer dem.

**Förbehåll:** fälten är skrivna vid sista iterationen, alltså ett ögonblick. Och 0°-fallen är
underiterererade vid 1500 iterationer, vilket gör 0°-kolumnerna ovan mindre säkra än
10°-kolumnerna.

### Vaken: `tools/plot_wake.py`

`diagSlice` sparar symmetrisnittet med `U`, `p`, `k` och `nut`. Verktyget ritar det.

Riktningen visas med **LIC** — brus utsmetat längs flödet — i stället för pilar eller
strömlinjer. Pilar kräver att man väljer en täthet, strömlinjer att man väljer startpunkter,
och båda valen döljer det man inte råkade välja. LIC visar hela strukturen, inklusive
återcirkulationen, utan att man bestämt var man ska titta.

```
python3 tools/plot_wake.py <fallkatalog> <ut.png> --uinf 12.5
```

**Det här är stationär RANS, alltså MEDELFLÖDET.** Virvelavlösningar syns inte — de är
medelvärdesbildade bort. Det man ser är den stående återcirkulationsbubblan, inte en
ögonblicksbild av virvlar. Vill man se avlösning i tiden krävs URANS eller LES.

#### Andelen backströmning förutsäger INTE motståndet

| fall | backströmning i snittet | lägsta Ux | ryttarens CdA |
|---|---|---|---|
| y0-base | 10.4 % | −9.9 m/s | 0.1275 |
| y0-tuned | **12.3 %** | −10.1 m/s | **0.1179** |
| y10-base | 5.7 % | −6.6 m/s | 0.1144 |
| y10-tuned | **4.1 %** | −6.7 m/s | **0.1179** |

Båda paren går åt fel håll. Vid 0° har `tuned` **mer** backströmning och **mindre** motstånd;
vid 10° har den **mindre** backströmning och **mer** motstånd. Den enkla läsningen "större
bubbla = mer motstånd" håller alltså inte.

Skälet är att snittet är **en tvådimensionell skiva genom ett tredimensionellt flöde**. Vid
yaw ligger avlösningen inte i sagittalplanet, och motståndet beror på var undertrycket verkar
mot bakåtvänd area — inte på hur mycket vänt flöde som råkar finnas i ett plan.

Bilderna visar alltså strukturen. **Siffrorna kommer från ytintegralerna**, inte härifrån. Det
är värt att ha sagt, eftersom en vakbild är övertygande på ett sätt som lätt får en att sluta
räkna.

Ett mönster håller dock i båda positionerna: yaw **halverar** backströmningen i
symmetriplanet, 10.4 → 5.7 och 12.3 → 4.1. Vid vinkel möter flödet kroppen snett och
sagittalplanet är inte längre det plan där den släpper.

Bilderna: `docs/fields/05-vaken-*.png`.

### Uppdelningen räknas nu i körningen: `tools/field_report.py`

Fältbilderna kräver att artefakten laddas ner, och den vägen är blockerad härifrån. Men
**siffrorna var det som gav mekanismen** — bilderna stödde dem. Därför räknas uppdelningen nu
i `verdict`-jobbet och skrivs till **loggen**, som går att läsa via API:et.

Varje körning ger alltså automatiskt:

- CdA-bidrag per del, integrerat ur ytfälten, med summan som kontroll mot forceCoeffs
- ryttarens bidrag per höjdband, base mot tuned, med Δ per band
- en markering på band som flyttar mer än 0.0015 m²

Text kostar ingenting i git, till skillnad från PNG:er som inte deltakomprimeras. Bilderna görs
på begäran med `plot_fields.py` när någon skickar över artefakten.

**Två teckenkonventioner, båda verifierade mot integralen och inte mot magkänslan:**

| | |
|---|---|
| `wallShearStress` | returneras med motsatt tecken mot strömningen → vänds i `plot_fields` |
| vindningen i `.vtp` | ger inåtpekande normaler → **vänds i `read_vtp`**, en gång |

Vindningen hanterades först genom att kompensera tecknet där den användes. Det höll bara tills
samma mesh renderades: med inåtpekande normaler inverteras ljussättningen, så ovansidan
skuggas och undersidan lyser — en cyklist belyst underifrån ser upp och ner ut. Användaren såg
det i 3D-vyn.

Nu vänds vindningen i `read_vtp`, verifierat med divergenssatsen (signerad volym ska vara
positiv: −0.0716 → +0.0710 m³). CdA-summorna är oförändrade; fixen rör orienteringen, inte
fysiken.

Kontrollen är att summan reproducerar `forceCoeffs`. På run 36224931538 stämmer den till
0.5–1 % i alla fyra fallen. Gör den inte det är något antagande fel, och verktyget ska då säga
till i stället för att tiga.

`verdict` installerar bara `numpy` och `trimesh`; `meshio` importeras lat och behövs bara för
`.vtk`, medan OpenFOAM skriver `.vtp`.

### Fältbilder: `tools/plot_fields.py`

En CdA-siffra säger att något är fel men aldrig var. När deltat inte är stabilt är ytfälten
enda sättet att se varför, så körningarna sparar dem nu.

`system/controlDict` har två nya function objects som skriver **en gång, vid sista
iterationen** — inte per iteration:

| | vad |
|---|---|
| `diagSurfaces` | `p` och `wallShearStress` på rider, bike och båda hjulen |
| `diagSlice` | `p`, `U`, `k`, `nut` i symmetrisnittet y = 0 |

`Collect` packar dem som `fields.tar.gz` i artefakten. Utan det steget slängs fälten när
runnern rivs, vilket är vad som hänt i alla körningar hittills.

Rendera lokalt:

```
python3 tools/plot_fields.py <utpackad artefakt> <utkatalog> --uinf 12.5 --tag y10-base
```

Ger `cp_side`, `cp_top`, `tau_mag_side` och `tau_x_side`.

**Färgvalen är inte smak.** Cp och skillnadskartor är divergerande, blå ↔ grå ↔ röd med noll i
grått. `|tau_w|` är sekventiell, en hue ljus→mörk. `tau_x` är divergerande, och då är det grå
bandet **separationslinjen** — där väggskjuvningen byter tecken och flödet vänder.

Aldrig regnbåge. En regnbågsskala lägger falska kanter där hue:n hoppar, och i ett tryckfält
läses de kanterna lätt som fysik. Det är den vanligaste lögnen i CFD-bilder.

**Bakstyckesgallring.** `render()` kullar ytor vars normal pekar bort från kameran. Utan det
vinner den bortre ytan djuptestet och bilden visar skalets insida genom varje öppen kant, vilket
ser ut som utskjutande flikar på modellen. Buggen fanns i den första versionen och hittades av
att en visare ritade `scan_head_shell.stl` på just det sättet.

**Ett förbehåll:** fälten skrivs vid sista iterationen. Är flödet instationärt — vilket det ser
ut att vara vid yaw — är bilden ett ögonblick ur svängningen, inte ett medelvärde. Två
körningar av samma fall kan då visa olika bilder, och det är i sig ett besked.

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

### Nätstudien på den nya geometrin: marginalen är borta, men inte av det skäl jag trodde (2026-09-26)

Run 36250629494, `coarse`, `[0,10]`, 1500 iterationer, commit 85805db. Alla fyra jobb gröna,
ingen driftflagga. `build_model.py`, `pose.py` och `configure_case.sh` är **bitidentiska** med
2ebb5ae, som kördes på `medium` med samma iterationstal — bara efterbehandlingsverktyg skiljer
commiterna. Nätnivån är alltså den enda variabeln.

| | coarse | medium | skift |
|---|---|---|---|
| 0° base | 0.2079 ± 0.0005 | 0.1952 | −0.0127 |
| 0° tuned | 0.2079 ± 0.0009 | 0.1889 | −0.0190 |
| **0° ΔCdA** | **+0.0001** ⚠ | **−0.0063** | **0.0063** |
| 10° base | 0.2125 ± 0.0004 | 0.1899 | −0.0226 |
| 10° tuned | 0.2039 ± 0.0008 | 0.1929 | −0.0110 |
| **10° ΔCdA** | **−0.0085** | **+0.0030** | **0.0116** |

Coarse ligger 0.011–0.023 högre i absolut CdA. Det är väntat och ointressant — grova nät
överskattar drag. Det som betyder något är att **felet inte är lika stort för base och tuned**:
vid 10° flyttar base 0.0226 och tuned 0.0110 när nätet förfinas. Det är differensen, 0.0116,
som slår rakt in i deltat och vänder dess tecken.

#### Min tröskel var satt på fel par

Jag skrev före körningen att om ΔCdA rör sig mer än ~0.0010 mellan coarse och medium är deltat
inte nätupplöst. **Den tröskeln var felaktigt formulerad, och att tillämpa den rakt av hade gett
en dramatisk slutsats som data inte bär.** README:s egen nätstudie längre upp visar nämligen att
coarse *redan* var underkänd vid yaw: på den gamla geometrin gav coarse +0.0058 mot medium
+0.0123, en faktor två fel. Att coarse avviker från medium är alltså inte nytt — det var känt,
och det var därför `medium` valdes.

Det den här körningen faktiskt visar är något smalare:

- **Coarse är fortfarande oanvändbar vid yaw.** Bekräftar det kända.
- **Avvikelsen har vuxit från en faktor två till ett teckenbyte** — inte för att nätkänsligheten
  ökat, utan för att *signalen krympt*. Coarse→medium rörde deltat 0.0065 på den gamla
  geometrin och 0.0116 nu, samma storleksordning. Men deltat självt gick från +0.0123 till
  +0.0030.

#### Vad som därmed INTE är visat

Frågan som avgör om siffran duger är **medium mot fine**, inte coarse mot medium. Den
jämförelsen finns bara på den gamla geometrin, där skillnaden var 0.0014 — 11 % av deltat, väl
inom go/no-go-kriteriets 20 %. Ett fel av samma absoluta storlek mot dagens signal på 0.0030
skulle vara **47 %**.

Så marginalen har kollapsat från 11 % till uppskattningsvis ~47 %, men det är en extrapolering
från gammal geometri, inte en mätning. **Om medium är nätkonvergerat för den nya geometrin är
inte visat.** Det kräver medium↔fine på nuvarande geometri, vilket inte är kört.

#### Rangordningen av felkällor, som är det som styr nästa steg

Allt vid 10°, som är den enda vinkeln som är iterationskonvergerad:

| källa | flyttar ΔCdA | mätt på |
|---|---|---|
| repliker, identisk geometri | 0.0003 | medium |
| 1500 → 2500 iterationer | 0.0000 | medium |
| nät, medium → fine | ~0.0014 | gammal geometri |
| kappmuskeln, 342 mm hål | 0.0040 | medium |
| **nape, 42 mm skreva** | **0.0074** | medium |
| *(nät, coarse → medium)* | *0.0116* | *underkänd nivå* |

**Geometridetalj är fortfarande den största posten**, en faktor 3–5 över nätet vid medium. Den
slutsatsen från kappmuskel- och nape-körningarna står kvar, och den här körningen rör den inte.

Men notera vad tabellen säger om signalen: ΔCdA vid 10° är 0.0030, alltså **mindre än
geometrikänsligheten på 0.0040–0.0074**. Positionsdeltat vid 10 grader går i dagsläget inte att
upplösa alls — det som ska mätas är mindre än osäkerheten i det som matar mätningen.

Det är ett argument *för* bättre geometri, inte emot. Men det betyder också att ingen
nätförfining räddar siffran så länge geometrin är en parametrisk approximation, och att en
skanner inte heller ger ett svar förrän medium↔fine är körd på den nya geometrin så att man vet
vilken av de två posterna som faktiskt binder.

#### Rättelse samma dag: medium↔fine testar inte det jag skrev att det testar

Raden ovan löd först att nästa experiment är medium↔fine. Det är fel, och felet kommer av att
jag inte läst nivådefinitionerna ordentligt. Från `tools/configure_case.sh` och
`system/snappyHexMeshDict`:

| nivå | yta | kanter | nearBox | wakeBox |
|---|---|---|---|---|
| coarse | (4 5) | 5 | 3 | 2 |
| medium | (5 6) | 6 | 3 | 2 |
| fine | (5 6) | 6 | 4 | 3 |

**Coarse→medium ändrar bara ytupplösningen. Medium→fine ändrar bara vakboxarna.** Skriptets
egen kommentar på rad 106 säger det: medium är "fine's surface resolution with coarse's
refinement boxes", just för att coarse↔medium ska isolera kroppsupplösningen.

Det betyder att den gamla nätstudiens två jämförelser mätte olika saker:

- **medium↔fine = 0.0014** → *volym- och vakupplösningen* är konvergerad.
- **coarse↔medium = 0.0065** → *ytupplösningen* är inte konvergerad, och medium är den finaste
  ytnivån som finns.

Slutsatsen "medium och fine är överens, alltså duger medium" är därför starkare formulerad än
data bär. Att två nivåer med *identisk yta* ger samma svar visar att boxarna räcker, inte att
ytan gör det. **Ytkonvergens är aldrig visad** — bara att medium är bättre än coarse, vilket är
en jämförelse underifrån.

Så den här körningen och den jag först föreslog svarar båda på fel fråga:

| experiment | testar | status |
|---|---|---|
| coarse↔medium | ytan, underifrån | kört, teckenbyte |
| medium↔fine | boxarna | mätt 0.0014 på gammal geometri |
| **medium↔(6 7)** | **ytan, ovanifrån** | **aldrig kört, finns inte i skriptet** |

Två experiment står alltså kvar, och de är inte utbytbara:

1. **fine vid 10° på nuvarande geometri**, 2 jobb. Boxtermen är känd till 0.0014 från gammal
   geometri, men mot dagens signal på 0.0030 är det 47 %. Den behöver mätas om på den nya
   geometrin, där vaken ändrats av nape och hjälmen. Nivån är bevisat körbar.
2. **En ny ytnivå (6 7) med mediums boxar**, 2 jobb. Den enda som kan visa ytkonvergens. Finns
   inte i `configure_case.sh` och måste läggas till.

Kostnad, mätt på de två körningarna: coarse 35–39 min, medium 84–95 min mesh+solve, alltså
faktor 2.4 per ytnivå. En nivå till landar grovt på 3.5–5 h, inom 6-timmarsgränsen men med
marginal som inte är stor.

Innan punkt 2 är körd är både "nätet räcker" och "nätet räcker inte" obelagda påståenden.

### Ytnivån över medium: `surf`, och varför den blev ett halvsteg (2026-09-26)

Tillagd som nätnivå `surf` i `tools/configure_case.sh`: **mediums boxar, ryttarens yta en nivå
finare.** Enda variabeln mot medium är ryttarens ytupplösning, vilket är villkoret för att
siffran ska gå att tolka.

Bara ryttaren, eftersom den är den enda delen som skiljer base från tuned — det är dess
upplösning som kan flytta deltat. Cykel och hjul är identisk geometri och deras rader i
uppdelningen fungerar som kontroll.

**Ett fullt steg till (6 7) ryms inte.** Räknat på `log.snappyHexMesh` från medium: ytbandet i
castellated-nätet är 168 647 celler på nivå 5 och 227 400 på nivå 6, och ryttaren är 51 % av
ytarean (1.714 m² av 3.374 m²). En nivå upp åttafaldigar de berörda cellerna:

| variant | castellated | slutnät | grov solvtid | mot taket 355 min |
|---|---|---|---|---|
| medium, som referens | 461 k | 1.40 M | 84–95 min (mätt) | — |
| rider (6 6) | 1.06 M | ~3.2 M | ~220 min | ryms |
| rider (6 7) | 1.87 M | ~5.7 M | ~380 min | **spränger** |
| alla fyra (6 7) | 3.23 M | ~9.8 M | — | spränger grovt |

En timeout förlorar hela jobbet, så (6 6) är valt: det lyfter *minnivån* från 5 till 6 så att
ytan blir jämnt upplöst i stället för krökningsstyrd. Kantförfiningen låg redan på 6 och är
oförändrad.

**Det träffar dessutom rätt ställe.** Fältuppdelningen lokaliserade teckenvändningen till bandet
1050–1200 mm, alltså övre ryggen och skuldrorna — en bred, flack yta, som är precis den sorts
region medium lägger på nivå 5 och som (6 6) lyfter. De krökta partierna låg redan på 6.

**Asymmetrin i vad utfallet bevisar, satt före körningen:**

- **Flyttar ΔCdA sig** → ytupplösningen binder. Fullgott resultat, och då är nätet flaskhalsen
  före geometrin.
- **Står ΔCdA still** → svagare bevis än det ser ut. De krökta partierna låg på nivå 6 i båda
  fallen, så ett nivå-7-test återstår och kräver en större maskin än GitHubs löpare. Det får
  läsas som "ingen indikation på ytberoende", inte som "ytan är konvergerad".

Tröskeln är densamma som förut, och den gäller nu rätt par: **rör sig ΔCdA vid 10° mer än
~0.0010 är ytan inte upplöst.**

#### Sidofynd: `$NP` är odefinierad i aero-yaw.yml

`configure_case.sh` anropas med `"$NP"` men variabeln sätts aldrig i det workflowet, så
`foamDictionary -entry numberOfSubdomains -set ""` blir en no-op. Alla körningar har därmed
använt 4 processorer (`nProcs : 4` i varje logg), konsekvent i både coarse- och
medium-körningen, så ingen jämförelse är korrupt.

**Lämnas orörd med flit.** Att sätta processantalet ändrar MPI-reduktionsordningen och därmed
sista decimalerna, vilket skulle bryta jämförbarheten mot medium-körningen som hela
nätstudien vilar på. Fixas när ingen aktiv jämförelse hänger på den.

### Utfallet: 0° är nätkonvergerat, 10° är det inte — och medium är avvikaren (2026-09-26)

Run 36255126139, `surf`, `[0,10]`, 1500 iterationer, commit 6d4a3b3. Alla fem jobb gröna, ingen
driftflagga. Fältuppdelningen kom med den här gången, så PIL-fixen håller.

| yaw | base CdA ± svängning | tuned CdA ± svängning | ΔCdA |
|---|---|---|---|
| +0 | 0.1965 ± 0.0025 | 0.1902 ± 0.0021 | **−0.0063** ± 0.0032 |
| +10 | 0.1974 ± 0.0014 | 0.1889 ± 0.0018 | **−0.0084** ± 0.0023 |

Kontrollraderna är bra: vid 0° ligger bike på +0.0007 och wheels på −0.0003, vid 10° −0.0012 och
−0.0009. Jämfört med coarse-körningens −0.0041 på bike har näten inte drivit isär.

#### Tre nivåer, två helt olika svar

| yaw | coarse (4 5) | medium (5 6) | surf (6 6) | spann |
|---|---|---|---|---|
| **0°** | +0.0001 ⚠ | **−0.0063** | **−0.0063** | 0.0063 |
| **10°** | **−0.0085** | **+0.0030** | **−0.0084** | 0.0116 |

**Vid 0° är deltat nätkonvergerat.** Medium och surf ger −0.0063 båda, identiskt på fjärde
decimalen. Ytförfiningen flyttade det **0.0000**. Coarse ligger utanför, men dess 0°-delta var
flaggat som mindre än svängningen och var aldrig ett resultat. Det här är första gången i
projektet ett delta står still mot en nätändring.

**Vid 10° är det inte konvergerat, och värre: det är icke-monotont.** −0.0085 → +0.0030 →
−0.0084 när nätet förfinas i tre steg. En konvergerande följd går monotont mot ett värde; den här
går ner, upp, ner. Då går det inte ens att extrapolera fram ett svar.

Tröskeln satt före körningen var att en rörelse över 0.0010 vid 10° betyder att ytupplösningen
binder. Rörelsen är **0.0115**. Tröskeln är uppfylld med stor marginal.

Men fyndet är rikare än tröskeln förutsåg: **coarse och surf är överens om −0.0085, och medium
står ensam på +0.0030.** Två av tre nivåer säger att den tunade positionen *vinner* vid 10
grader. Det är medium som säger att den förlorar — och medium är den körning hela slutsatsen
"positionen förlorar i sidvind" vilade på.

#### Mekanismen pekar mot att medium är felet, inte att allt är brus

Bandet 1050–1200 mm, övre ryggen, vid 10 grader:

| nivå | base | tuned | Δ |
|---|---|---|---|
| medium | 0.0257 | 0.0309 | **+0.0052** |
| surf | 0.0258 | 0.0267 | **+0.0009** |

**`base` rörde sig +0.0001. `tuned` rörde sig −0.0042.** Ytförfiningen lämnade baseline i stort
sett oberörd och tog bort fyra femtedelar av det positiva bidraget i den tunade positionen. Det
var precis det bidraget som vände tecknet på medium.

Det är fysikaliskt rimligt: den tunade positionen är lägre och flackare, så dess övre rygg möter
flödet mer strykande. En flack yta i strykande flöde är den sortens region medium lägger på nivå
5 och där upplösningen betyder mest. Hypotesen är därför att **medium underupplöste den tunade
positionens övre rygg vid yaw och producerade ett falskt positivt bidrag där.**

Det är en hypotes med stöd, inte ett fastställt faktum. Tre punkter kan inte skilja "medium är
avvikande" från "alla tre är brus". Det som skulle avgöra det är en replik av medium vid 10° med
störd nätning — reproducerar inte +0.0030 var medium anomal.

#### Var projektet står: ingen vinkel har båda egenskaperna

| vinkel | iterationskonvergerad | nätkonvergerad (yta) |
|---|---|---|
| **0°** | **NEJ** — rör sig 0.0037 mellan 1500 och 2500 | **JA** — 0.0000 medium→surf |
| **10°** | **JA** — 0.0000 mellan 1500 och 2500 | **NEJ** — 0.0115, icke-monotont |

Det är en obekväm symmetri. Varje vinkel har den egenskap den andra saknar, och inget tal i
projektet har ännu båda.

**Billigaste vägen till ett fullt kvalificerat tal: `surf` vid 0° med 2500 iterationer, två
jobb.** 0° är redan nätkonvergerat, så det som fattas är iterationerna. Körtiden nedan säger att
det ryms.

#### Min tidsuppskattning var för pessimistisk

| | mesh+solve | mot förutsagt |
|---|---|---|
| medium | 84–95 min, snitt 90 | — |
| surf | 102–138 min, snitt 121 | **1.35×**, jag förutsåg 2.3× |

Cellantalet går inte att verifiera — artefakten ligger på Azure blob-lagring som proxyn
policyblockerar, och loggar serveras inte för pågående jobb (404), så förvarningen jag planerade
mitt i körningen var aldrig möjlig. Men faktorn 1.35 mot förutsagda 2.3 betyder att nätet växte
klart mindre än de ~3.2 M celler jag räknade fram.

**Konsekvensen är att (6 7) sannolikt hade rymts.** Min uppskattning på ~380 min byggde på samma
överskattning. Ett riktigt nivå-7-test på ytan är alltså inte utom räckhåll för GitHubs löpare,
tvärtemot vad jag skrev innan körningen. Det är den jämförelse som skulle stänga 10-gradersfrågan.

#### Vad som inte ska läsas ur den här körningen

CdA_eff-tabellen säger nu att den tunade positionen vinner vid varje vindstyrka, −3.2 % till
−4.1 %. **Läs den inte som ett resultat.** Den vilar på 10-graderspunkten, som är den punkt som
just visats vara icke-konvergerad, och på ett 0° som är underiterererat. Att den ser trevlig ut
är inget argument för den.
