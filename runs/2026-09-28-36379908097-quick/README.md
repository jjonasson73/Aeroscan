# 2026-09-28 · quick · yaw [0,10]

`pad_drop_mm=-10 saddle_fore_mm=10 saddle_up_mm=6` vid 12.5 m/s. Commit [`84142a0`](https://github.com/jjonasson73/Aeroscan/commit/84142a0e375b6238bfa8c3132ca905d26c94f8e0) · [körningen](https://github.com/jjonasson73/Aeroscan/actions/runs/36379908097)


### CdA mot yaw (medel över sista 400 iterationerna)

| yaw [°] | base CdA ± svängning | tuned CdA ± svängning | ΔCdA [m²] |
|---|---|---|---|
| +0 | 0.1632 ± 0.0002 | 0.1582 ± 0.0004 | -0.0050 ± 0.0005 |
| +10 | 0.1695 ± 0.0005 | 0.1745 ± 0.0003 | +0.0050 ± 0.0006 |

> ⚠ **Kraften lutar fortfarande i fönstret för base vid +10°.** Körningen var inte konvergerad utan avbruten vid iterationsgränsen. Kör fler iterationer eller medelvärdesbilda över ett längre fönster.

### Vad det betyder vid 40 km/h

CdA_eff är det stillaluft-CdA som hade kostat lika många watt över ett varv, alltså vinden inräknad. Vindriktningen antas likformig över varvet.

| vind [km/h] | typisk yaw [°] | base CdA_eff | tuned CdA_eff | ΔCdA_eff | Δ % |
|---|---|---|---|---|---|
| 0 | 0 | 0.1632 | 0.1582 | -0.0050 | -3.08 % |
| 5 | 7 | 0.1686 | 0.1681 | -0.0005 | -0.29 % |
| 10 | 14 | 0.1784 | 0.1810 | +0.0026 | +1.47 % |
| 15 | 22 | 0.1920 | 0.1956 | +0.0036 | +1.88 % |
| 20 | 30 | 0.2106 | 0.2150 | +0.0043 | +2.06 % |

### Var sitter skillnaden?

ΔCdA per kroppsdel, tuned minus base. Bara ryttaren skiljer sig mellan positionerna – cykel och hjul är identisk geometri, så deras rader ska ligga nära noll och är kontrollen på att körningarna inte drivit isär.

| yaw [°] | rider | bike | wheels |
|---|---|---|---|
| +0 | -0.0044 | -0.0003 | -0.0003 |
| +10 | +0.0045 | +0.0011 | -0.0006 |

<details><summary>Bakgrund: vad yaw gör med varje del i sig (ändring från +0°, negativt = vinst)</summary>

| yaw [°] | del | base | tuned |
|---|---|---|---|
| +10 | rider | -0.0087 | +0.0002 |
| +10 | bike | +0.0048 | +0.0063 |
| +10 | wheels | +0.0101 | +0.0098 |

Summan av delarna är inte exakt totalen – delarna påverkar varandras flöde.

</details>

### Läsanvisning

- "typisk yaw" är 95:e percentilen av |yaw| över varvet, inte medelvärdet – medelvärdet är nära noll av symmetriskäl och säger ingenting.
- ⚠ Bara **en sida** av noll är körd, så kurvan speglas. Cyklisten är inte spegelsymmetrisk – ett ben är fram, kedjan sitter på höger sida – så äkta +beta och −beta skiljer sig. Kör båda tecknen innan du litar på siffran.
- ⚠ Vinden driver ut yaw förbi svepets yttersta punkt (+10°). Där klampas CdA till ändvärdet i stället för att extrapoleras, vilket **underskattar** kostnaden av de starkaste vindarna.
- Spridningen mellan separata körningar av identisk geometri mättes vid 0° till 0.0010 m² (0.5 %). Den gäller ett fall som konvergerar. Svänger kraften vid yaw är spridningen mellan körningar större än så, och ± i tabellen ovan är då den siffra att gå på – inte 0.0010.
- Marken rör sig med luften, inte med cykeln. Vid yaw är det inte riktigt rätt – en rullande väg kan inte vridas – men alternativet, stillastående mark, ger ett falskt gränsskikt över hela golvet och är sämre.

### Var motståndet sitter (ur ytfälten)

Tryck och friktion integrerade per triangel. Summan ska stämma med CdA-tabellen ovan; gör den inte det är uppdelningen inte att lita på.

| fall | rider | bike | wheels | SUMMA |
|---|---|---|---|---|
| y0-base | 0.0929 | 0.0483 | 0.0224 | **0.1636** |
| y0-tuned | 0.0882 | 0.0480 | 0.0221 | **0.1584** |
| y10-base | 0.0842 | 0.0535 | 0.0325 | **0.1702** |
| y10-tuned | 0.0887 | 0.0543 | 0.0318 | **0.1747** |

#### y0: ryttarens bidrag per höjdband [m²]

| höjd över mark | base | tuned | Δ |
|---|---|---|---|
| 150–300 | 0.0024 | 0.0024 | -0.0000 |
| 300–450 | 0.0042 | 0.0041 | -0.0001 |
| 450–600 | 0.0097 | 0.0093 | -0.0004 |
| 600–750 | 0.0166 | 0.0175 | +0.0009 |
| 750–900 | 0.0120 | 0.0110 | -0.0010 |
| 900–1050 | 0.0086 | 0.0096 | +0.0009 |
| 1050–1200 | 0.0269 | 0.0235 | -0.0034 **&larr;** |
| 1200–1350 | 0.0130 | 0.0113 | -0.0018 **&larr;** |
| 1350–1500 | -0.0007 | -0.0005 | +0.0002 |
| **summa** | **0.0929** | **0.0882** | **-0.0047** |

#### y10: ryttarens bidrag per höjdband [m²]

| höjd över mark | base | tuned | Δ |
|---|---|---|---|
| 150–300 | 0.0016 | 0.0016 | +0.0000 |
| 300–450 | 0.0040 | 0.0041 | +0.0001 |
| 450–600 | 0.0098 | 0.0107 | +0.0009 |
| 600–750 | 0.0154 | 0.0144 | -0.0009 |
| 750–900 | 0.0091 | 0.0116 | +0.0025 **&larr;** |
| 900–1050 | 0.0099 | 0.0112 | +0.0013 |
| 1050–1200 | 0.0227 | 0.0246 | +0.0018 **&larr;** |
| 1200–1350 | 0.0122 | 0.0107 | -0.0015 **&larr;** |
| 1350–1500 | -0.0005 | -0.0004 | +0.0001 |
| **summa** | **0.0842** | **0.0887** | **+0.0044** |

> Band markerade med &larr; flyttar mer än 0.0015 m². Är deltat en liten rest mellan stora motverkande band är det känsligt för geometri just där.


---

## Bilder

Rå VTK för ParaView ligger i körningens artefakter i 30 dagar. Den fullständiga bilduppsättningen (topvy, skjuvningsmagnitud) finns där; nedan är de tre som faktiskt läses.

### y0-base

### y0-tuned

### y10-base

### y10-tuned
