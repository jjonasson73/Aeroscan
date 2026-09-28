# 2026-09-28 · quick · yaw [0,10]

`pad_drop_mm=-10 saddle_fore_mm=10 saddle_up_mm=6` vid 12.5 m/s. Commit [`086a519`](https://github.com/jjonasson73/Aeroscan/commit/086a519746ce3420a2ae62fb0fcf5492a5c202f2) · [körningen](https://github.com/jjonasson73/Aeroscan/actions/runs/36427605354)


### CdA mot yaw (medel över sista 400 iterationerna)

| yaw [°] | base CdA ± svängning | tuned CdA ± svängning | ΔCdA [m²] |
|---|---|---|---|
| +0 | 0.1625 ± 0.0002 | 0.1583 ± 0.0004 | -0.0041 ± 0.0004 |
| +10 | 0.1705 ± 0.0006 | 0.1735 ± 0.0002 | +0.0030 ± 0.0006 |

> ⚠ **Kraften lutar fortfarande i fönstret för base vid +0°, base vid +10°.** Körningen var inte konvergerad utan avbruten vid iterationsgränsen. Kör fler iterationer eller medelvärdesbilda över ett längre fönster.

### Vad det betyder vid 40 km/h

CdA_eff är det stillaluft-CdA som hade kostat lika många watt över ett varv, alltså vinden inräknad. Vindriktningen antas likformig över varvet.

| vind [km/h] | typisk yaw [°] | base CdA_eff | tuned CdA_eff | ΔCdA_eff | Δ % |
|---|---|---|---|---|---|
| 0 | 0 | 0.1625 | 0.1583 | -0.0041 | -2.54 % |
| 5 | 7 | 0.1687 | 0.1678 | -0.0009 | -0.54 % |
| 10 | 14 | 0.1789 | 0.1802 | +0.0013 | +0.71 % |
| 15 | 22 | 0.1927 | 0.1947 | +0.0019 | +1.00 % |
| 20 | 30 | 0.2115 | 0.2139 | +0.0024 | +1.12 % |

### Var sitter skillnaden?

ΔCdA per kroppsdel, tuned minus base. Bara ryttaren skiljer sig mellan positionerna – cykel och hjul är identisk geometri, så deras rader ska ligga nära noll och är kontrollen på att körningarna inte drivit isär.

| yaw [°] | rider | bike | wheels |
|---|---|---|---|
| +0 | -0.0037 | -0.0001 | -0.0003 |
| +10 | +0.0034 | +0.0005 | -0.0009 |

<details><summary>Bakgrund: vad yaw gör med varje del i sig (ändring från +0°, negativt = vinst)</summary>

| yaw [°] | del | base | tuned |
|---|---|---|---|
| +10 | rider | -0.0074 | -0.0003 |
| +10 | bike | +0.0053 | +0.0058 |
| +10 | wheels | +0.0101 | +0.0096 |

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
| y0-base | 0.0923 | 0.0480 | 0.0224 | **0.1627** |
| y0-tuned | 0.0881 | 0.0480 | 0.0221 | **0.1582** |
| y10-base | 0.0848 | 0.0535 | 0.0326 | **0.1708** |
| y10-tuned | 0.0881 | 0.0537 | 0.0317 | **0.1736** |

#### y0: ryttarens bidrag per höjdband [m²]

| höjd över mark | base | tuned | Δ |
|---|---|---|---|
| 150–300 | 0.0025 | 0.0024 | -0.0001 |
| 300–450 | 0.0042 | 0.0041 | -0.0002 |
| 450–600 | 0.0097 | 0.0094 | -0.0004 |
| 600–750 | 0.0167 | 0.0171 | +0.0004 |
| 750–900 | 0.0124 | 0.0108 | -0.0016 **&larr;** |
| 900–1050 | 0.0089 | 0.0103 | +0.0014 |
| 1050–1200 | 0.0267 | 0.0230 | -0.0038 **&larr;** |
| 1200–1350 | 0.0118 | 0.0115 | -0.0003 |
| 1350–1500 | -0.0006 | -0.0004 | +0.0002 |
| **summa** | **0.0923** | **0.0881** | **-0.0042** |

#### y10: ryttarens bidrag per höjdband [m²]

| höjd över mark | base | tuned | Δ |
|---|---|---|---|
| 150–300 | 0.0016 | 0.0016 | -0.0000 |
| 300–450 | 0.0041 | 0.0041 | +0.0001 |
| 450–600 | 0.0097 | 0.0108 | +0.0011 |
| 600–750 | 0.0152 | 0.0151 | -0.0000 |
| 750–900 | 0.0090 | 0.0119 | +0.0029 **&larr;** |
| 900–1050 | 0.0100 | 0.0108 | +0.0008 |
| 1050–1200 | 0.0234 | 0.0234 | +0.0000 |
| 1200–1350 | 0.0124 | 0.0108 | -0.0016 **&larr;** |
| 1350–1500 | -0.0005 | -0.0003 | +0.0001 |
| **summa** | **0.0848** | **0.0881** | **+0.0034** |

> Band markerade med &larr; flyttar mer än 0.0015 m². Är deltat en liten rest mellan stora motverkande band är det känsligt för geometri just där.


---

## Bilder

Rå VTK för ParaView ligger i körningens artefakter i 30 dagar. Den fullständiga bilduppsättningen (topvy, skjuvningsmagnitud) finns där; nedan är de tre som faktiskt läses.

### y0-base

**Cp, sidvy**  
Rött är övertryck, blått sug, grått noll.

![Cp, sidvy](y0-base/cp_side.png)

**Väggskjuvning tau_w,x**  
Blått är BACKSTRÖMNING, alltså avlöst flöde. Det gråa bandet är separationslinjen.

![Väggskjuvning tau_w,x](y0-base/tau_x_side.png)

**Vaken i symmetrisnittet**  
Övre panelen är fart, nedre turbulens. Strimmorna följer flödesriktningen.

![Vaken i symmetrisnittet](y0-base/wake.png)

### y0-tuned

**Cp, sidvy**  
Rött är övertryck, blått sug, grått noll.

![Cp, sidvy](y0-tuned/cp_side.png)

**Väggskjuvning tau_w,x**  
Blått är BACKSTRÖMNING, alltså avlöst flöde. Det gråa bandet är separationslinjen.

![Väggskjuvning tau_w,x](y0-tuned/tau_x_side.png)

**Vaken i symmetrisnittet**  
Övre panelen är fart, nedre turbulens. Strimmorna följer flödesriktningen.

![Vaken i symmetrisnittet](y0-tuned/wake.png)

### y10-base

**Cp, sidvy**  
Rött är övertryck, blått sug, grått noll.

![Cp, sidvy](y10-base/cp_side.png)

**Väggskjuvning tau_w,x**  
Blått är BACKSTRÖMNING, alltså avlöst flöde. Det gråa bandet är separationslinjen.

![Väggskjuvning tau_w,x](y10-base/tau_x_side.png)

**Vaken i symmetrisnittet**  
Övre panelen är fart, nedre turbulens. Strimmorna följer flödesriktningen.

![Vaken i symmetrisnittet](y10-base/wake.png)

### y10-tuned

**Cp, sidvy**  
Rött är övertryck, blått sug, grått noll.

![Cp, sidvy](y10-tuned/cp_side.png)

**Väggskjuvning tau_w,x**  
Blått är BACKSTRÖMNING, alltså avlöst flöde. Det gråa bandet är separationslinjen.

![Väggskjuvning tau_w,x](y10-tuned/tau_x_side.png)

**Vaken i symmetrisnittet**  
Övre panelen är fart, nedre turbulens. Strimmorna följer flödesriktningen.

![Vaken i symmetrisnittet](y10-tuned/wake.png)
