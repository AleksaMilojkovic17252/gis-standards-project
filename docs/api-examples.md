# Primeri API zahteva

Zahtevi spremni za kopiranje, za pokrenute servise (`http://localhost:8090`).
Svi rezultati ispod su provereni nad učitanim podacima (period 2026-11-04 do 2026-11-13 UTC).

URL-ovi su napisani čitljivo. Pregledači sami kodiraju razmake i navodnike.
Za curl koristiti `-G` i `--data-urlencode`, kao u primerima.

```sh
STA=http://localhost:8090/sta/FROST-Server/v1.1
OGC=http://localhost:8090/ogc
```

---

## 1. SensorThings API (FROST-Server)

Model podataka: 17 Thing-ova (stanica), svaki sa 1 Location, 1 FeatureOfInterest i 9 Datastream-ova
(6 merenih, temperatura zemljišta merena na 5 stanica / simulirana na 12, simulirana vlažnost i stanje zemljišta).
2 Sensor-a, 9 ObservedProperty-ja sa definicijama po CF standardnim nazivima, 220.305 Observation-a.

FROST deli rezultate na strane (podrazumevano 100, najviše 10.000). Ostatak se dobija praćenjem `@iot.nextLink`.

### 1.1 Filter po svojstvu: stanice duž Arlbergbahn-a (4)

```
$STA/Things?$filter=properties/line_id eq 'arlbergbahn'&$select=name,properties&$count=true
```
```sh
curl -G "$STA/Things" --data-urlencode "\$filter=properties/line_id eq 'arlbergbahn'" \
     --data-urlencode '$select=name,properties' --data-urlencode '$count=true'
```

### 1.2 Svi simulirani Datastream-ovi (46)

```
$STA/Datastreams?$filter=properties/simulated eq true&$select=name&$count=true
```

### 1.3 Kretanje kroz relacije sa `$expand`: Datastream padavina u Bregenzu

```
$STA/Datastreams?$filter=ObservedProperty/name eq 'Precipitation' and Thing/name eq 'Bregenz'
    &$expand=Thing($select=name),ObservedProperty($select=name,definition)&$select=name,unitOfMeasurement
```
Vraća UCUM jedinicu (`mm`) i CF definiciju `http://vocab.nerc.ac.uk/standard_name/precipitation_amount/`.

### 1.4 Vremenski filter i `$orderby`: najjača 10-minutna kiša u Bregenzu 10. novembra

```
$STA/Observations?$filter=Datastream/Thing/name eq 'Bregenz'
    and Datastream/ObservedProperty/name eq 'Precipitation'
    and phenomenonTime ge 2026-11-10T00:00:00Z and phenomenonTime lt 2026-11-11T00:00:00Z
    and result gt 1
  &$orderby=result desc&$select=phenomenonTime,result&$count=true
```
→ 2 vrednosti: 1,3 mm u 06:50 Z, 1,2 mm u 06:40 Z.

### 1.5 Prostorni filter `geo.intersects`: stanice u pravougaoniku iznad Tirola (5)

```
$STA/Things?$filter=geo.intersects(Locations/location,
    geography'POLYGON((10.0 46.9, 12.9 46.9, 12.9 47.8, 10.0 47.8, 10.0 46.9))')&$select=name&$count=true
```

### 1.6 Filter po rastojanju `geo.distance`: stanice blizu Wien Hauptbahnhof-a (3)

```
$STA/Things?$filter=geo.distance(Locations/location, geography'POINT(16.378 48.185)') lt 0.2&$select=name
```
Napomena: FROST računa rastojanje u jedinicama koordinata (stepeni), ne u metrima.

### 1.7 Poslednja vrednost svakog Datastream-a jedne stanice

```
$STA/Datastreams?$filter=Thing/name eq 'Linz Stadt'&$select=name
    &$expand=Observations($orderby=phenomenonTime desc;$top=1;$select=phenomenonTime,result)
```

### 1.8 Stanje u trenutku *t* (koristi ga web aplikacija)

Poslednja vrednost svakog Datastream-a na svakoj stanici u trenutku *t* ili pre njega, u jednom zahtevu:

```
$STA/Things?$select=name
    &$expand=Locations($select=location),
             Datastreams($select=name,unitOfMeasurement;
                 $expand=Observations($select=phenomenonTime,result;
                     $filter=phenomenonTime le 2026-11-12T12:00:00Z;$orderby=phenomenonTime desc;$top=1))
```
```sh
curl -G "$STA/Things" --data-urlencode '$select=name' \
  --data-urlencode '$expand=Locations($select=location),Datastreams($select=name,unitOfMeasurement;$expand=Observations($select=phenomenonTime,result;$filter=phenomenonTime le 2026-11-12T12:00:00Z;$orderby=phenomenonTime desc;$top=1))'
```

### 1.9 Kategorijska merenja: kada je zemljište postalo zasićeno vodom? (21 merenje, prvo u Bregenzu)

```
$STA/Observations?$filter=result eq 'waterlogged'&$expand=Datastream($select=name)
    &$select=phenomenonTime,result&$orderby=phenomenonTime&$count=true&$top=1
```
→ 2026-11-10T06:50Z, "Soil state at Bregenz" (simulirano).

### 1.10 Dnevni maksimum bez agregacije: najtopliji trenutak u Beču 5. novembra

STA 1.1 nema funkcije agregacije, pa je maksimum sortiranje plus `$top=1`:

```
$STA/Observations?$filter=Datastream/Thing/name eq 'Wien Innere Stadt'
    and Datastream/ObservedProperty/name eq 'Air temperature'
    and phenomenonTime ge 2026-11-05T00:00:00Z and phenomenonTime lt 2026-11-06T00:00:00Z
  &$orderby=result desc&$top=1&$select=phenomenonTime,result
```
→ 9,8 °C u 12:00 Z.

### 1.11 MQTT (websockets)

Endpoint: `ws://localhost:8090/sta/mqtt`. Teme koriste iste putanje kao REST API, na primer:

```
v1.1/Datastreams(1)/Observations       # nova merenja jednog Datastream-a
v1.1/Observations                      # sva nova merenja
```

FROST objavljuje na ove teme svaki Observation kreiran preko REST-a; sadržaj poruke je Observation
kao JSON (`phenomenonTime`, `result`, `parameters`, navigacioni linkovi). Ništa ne treba podešavati po
temi: dovoljno je pretplatiti se.

**Ponavljanje uživo.** Skup podataka je istorijski, pa su podaci „uživo” zapravo ponavljanje:
`sta-loader/replay_observations_live.py` kopira jedan dan u stvarne Datastream-ove stanica, sa vremenom
pomerenim posle perioda (podrazumevano: 12. novembar se ponavlja kao 14. novembar, jedan 10-minutni korak
na svakih 5 s, ~153 merenja po koraku, svako označeno sa `"parameters": {"replay": true, "replayed_from": …}`).

```sh
docker compose run --rm -e STEPS=24 sta-loader python replay_observations_live.py   # 2 h podataka za ~2 min
docker compose run --rm sta-loader python delete_replayed_observations.py           # posle toga
```

Podešavanja (promenljive okruženja): `SOURCE_START`, `TARGET_START`, `SECONDS_PER_STEP` (5), `STEPS` (144 = jedan dan).
Brisanje uklanja svaki Observation posle 13. novembra 23:50 (tamo postoje samo ponovljeni podaci); FROST
zatim sam vraća `phenomenonTime` Datastream-ova na 4–13. novembar.

Spisak ponovljenih merenja dok ponavljanje traje:

```
/sta/FROST-Server/v1.1/Observations
  ?$filter=phenomenonTime gt 2026-11-13T23:50:00Z
  &$select=phenomenonTime,result,parameters&$orderby=phenomenonTime desc&$count=true
```

Web aplikacija se pretplaćuje preko `mqtt.js` (jedna tema po Datastream-u, ukupno 153) kada je uključeno
*Uživo*; vidi `web/src/state/live.ts`.

---

## 2. OGC API – Features (pygeoapi)

| Kolekcija | Izvor | Objekata |
|---|---|---|
| `stations` | SensorThings API (FROST), entitet `Things` | 17 |
| `rail-lines` | MobilityDB, pogled `rail.lines_crs84` | 4 |
| `rail-stations` | MobilityDB, pogled `rail.stations_crs84` | 1.521 |

```
$OGC/collections
$OGC/collections/rail-lines/items?f=json
$OGC/collections/rail-lines/items/westbahn?f=json
$OGC/collections/rail-stations/items?name=Wien Hauptbahnhof&f=json
$OGC/collections/rail-stations/items?bbox=16.3,48.15,16.45,48.25&f=json      # 33 stanice u Beču
$OGC/collections/stations/items?f=json
```
Bez `f=json` dobijaju se HTML strane sa mapom.

**Problem sa redosledom osa:** pruge su sačuvane u EPSG:3416, čiji je zvanični redosled osa
northing, easting. Kada je ovaj sistem naveden kao `storage_crs`, pygeoapi je zamenio ose i postavio
Wien Hauptbahnhof oko 150 km dalje, u Češku. Zato kolekcije čitaju iz pogleda koji podatke već
transformišu u CRS84 (`ST_Transform(geom, 4326)`).

---

## 3. OGC API – EDR (pygeoapi)

| Kolekcija | Provajder | Podaci | Tipovi upita (provereni) |
|---|---|---|---|
| `stations-edr` | SensorThingsEDR (+ SensorThings za `items`) | FROST merenja, 10 min | `items`, `locations`, `cube`, `area` |
| `inca-grid` | xarray-edr | INCA, po satu, mreža 0,01° (`data/processed/inca_crs84.nc`) | `position`, `cube` |

Nisu podržani (HTTP 400 "Unsupported query type"): `position` i `radius` za `stations-edr`;
`area`, `radius`, `trajectory` i `corridor` za `inca-grid`.

Odgovori su CoverageJSON (`f=json`). Metapodaci kolekcije sadrže spisak parametara:
```
$OGC/collections/stations-edr?f=json      # parameter_names
$OGC/collections/inca-grid?f=json
```

### 3.1 Nazivi parametara

- `inca-grid`: `T2M` (°C), `RH2M` (%), `RR` (mm po satu).
- `stations-edr`: **ID-jevi STA ObservedProperty-ja**, ne nazivi. Menjaju se kada se `sta-loader` ponovo
  pokrene. Prvo ih proveriti:
  ```
  $STA/ObservedProperties?$select=id,name
  ```
  Trenutni ID-jevi: 10 temperatura vazduha, 11 relativna vlažnost, 12 vazdušni pritisak, 13 brzina vetra,
  14 padavine, 15 globalno zračenje, 16 temperatura zemljišta na 10 cm, 17 vlažnost zemljišta, 18 stanje zemljišta.

### 3.2 Vremenska serija iz mreže u tački (`position`)

```
$OGC/collections/inca-grid/position?coords=POINT(16.37 48.21)
    &datetime=2026-11-12T00:00:00Z/2026-11-12T23:00:00Z&parameter-name=T2M,RR&f=json
```
→ `PointSeries` sa 24 satne vrednosti T2M (4,3–7,4 °C) i RR, iz najbliže ćelije mreže.

**Jedan vremenski korak:** napisati ga kao interval `t/t`. Jedan trenutak vraća 204 (greška provajdera, vidi 3.7):
```
$OGC/collections/inca-grid/position?coords=POINT(16.3745 48.2083)
    &datetime=2026-11-12T12:00:00Z/2026-11-12T12:00:00Z&parameter-name=T2M&f=json
```
→ najbliža ćelija (16.37, 48.21), 6,94 °C.

### 3.3 Isečak mreže (`cube`): INCA raster za web aplikaciju

```
$OGC/collections/inca-grid/cube?bbox=16.2,48.1,16.5,48.3&datetime=2026-11-12T12:00:00Z&parameter-name=T2M&f=json
```
→ `Grid` 31 × 21 ćelija. Cela Austrija za jedan sat (`bbox=9.46,46.45,17.19,49.09`): 774 × 265 ćelija,
5,3 MB, 0,6 s.

### 3.4 Serije sa stanica (`locations`)

```
$OGC/collections/stations-edr/locations?f=json
$OGC/collections/stations-edr/locations/18?datetime=2026-11-12T00:00:00Z/2026-11-12T06:00:00Z&parameter-name=10,14&f=json
```
ID-jevi lokacija su STA Thing ID-jevi (18 = Innsbruck Universität posle trenutnog učitavanja). Spisak
sadrži svaku stanicu 9 puta (jednom po Datastream-u) i bez naziva.

### 3.5 Vreme oko pruge (`area`), glavni primer

Web aplikacija pravi bafer od 10 km oko pruge i pojednostavljuje ga pre slanja. Isti poligon u SQL-u:
```sql
SELECT ST_AsText(ST_Transform(ST_Simplify(ST_Buffer(geom, 10000, 'quad_segs=4'), 1000), 4326), 4)
FROM rail.lines WHERE line_id = 'westbahn';      -- 63 temena, 998 karaktera
```
```sh
curl -G "$OGC/collections/stations-edr/area" --data-urlencode "coords=$WKT" \
     --data-urlencode "datetime=2026-11-12T00:00:00Z/2026-11-12T23:59:59Z" \
     --data-urlencode "parameter-name=10,14" --data-urlencode "f=json"
```
→ `CoverageCollection` sa 12 coverage-a: 6 stanica unutar Westbahn koridora (Wien Innere Stadt,
Wien Mariabrunn, Amstetten, Linz Stadt, Vöcklabruck, Salzburg Freisaal) × 2 parametra, po 144 vrednosti.
Padavine 12. novembra: 3,0–11,8 mm. Svih 9 parametara za svih 10 dana: 6,5 MB za 0,85 s.

Nepojednostavljeni bafer (5.448 temena, 86k karaktera) vraća **HTTP 414 URI Too Long**.

### 3.6 Stanice u pravougaoniku (`cube`)

```
$OGC/collections/stations-edr/cube?bbox=16.0,48.0,16.6,48.4&datetime=2026-11-12T00:00:00Z/2026-11-12T06:00:00Z&parameter-name=10&f=json
```

### 3.7 Otkrivena ograničenja provajdera (pygeoapi 0.24.0)

| Problem | Posledica | Rešenje |
|---|---|---|
| SensorThingsEDR ne prati `@iot.nextLink` u proširenim Observations (TODO u kodu) | Svaka serija se tiho skraćuje na FROST `defaultTop` (100) | FROST `defaultTop=2000` (jedna strana prima 10 dana) |
| SensorThingsEDR filtrira vreme po `resultTime` | Nema rezultata ako je `resultTime` null (dozvoljeno u STA) | `sta-loader` postavlja `resultTime = phenomenonTime` |
| SensorThingsEDR `items` zahteva feature provajder | "Invalid provider type" | Drugi provajder (SensorThings, `Things`) u istoj kolekciji |
| xarray-edr ne transformiše koordinate | CRS84 upit nad projektovanom mrežom pogađa pogrešne ćelije | INCA prebačena iz EPSG:31287 u lon/lat |
| xarray-edr pada na NaN ćelijama (`np.isnan` nad mešovitim tipovima) | HTTP 500 za svaki zahtev koji dotakne ćeliju van INCA domena | Mreža isečena na oblast bez NaN vrednosti 9,46–17,19 °E, 46,45–49,09 °N |
| xarray-edr `position` sa jednim trenutkom poredi date sa datetime | HTTP 204, nema podataka | Koristiti `datetime=t/t` |
| xarray-edr `position` sa LINESTRING | HTTP 204 | Nema (trajektorije nisu podržane) |
| Vremena u CoverageJSON-u | `2026-11-12T12:00:00.000000000` (nanosekunde, bez `Z`) | Klijent ih parsira tolerantno |

## 4. OGC API – Moving Features (FastAPI nad MobilityDB)

```sh
MF=http://localhost:8090/mf
```

Delimična implementacija Part 1 (samo čitanje), baza `trains` (10×, 1.280 simuliranih vožnji, 4–13. novembar).
Interaktivna dokumentacija (Swagger UI): `$MF/docs`.

| Kolekcija | Tabela | Cela vožnja kao MF-JSON |
|---|---|---|
| `trains` | `mdb.trips` | ~364 KB |
| `trains-simplified` | `mdb.trips_simplified` (Douglas–Peucker 10 m) | ~36 KB |

ID-jevi vožnji: `trip_id` iz `sim.trip_info`. Primer korišćen ispod: **1026** = `arlbergbahn-f-0700`
(Innsbruck → Bregenz, 12. novembar, 06:00–08:09 UTC).

### 4.1 Kolekcije i conformance

```
$MF/conformance
$MF/collections
$MF/collections/trains
```

### 4.2 Pokretni objekti (vožnje)

```
$MF/collections/trains/items?limit=10
$MF/collections/trains/items?datetime=2026-11-12T08:00:00Z/2026-11-12T08:30:00Z&limit=50     # 25 vožnji u tom periodu
$MF/collections/trains/items?bbox=11.3,47.2,11.5,47.3&datetime=2026-11-12T08:00:00Z/2026-11-12T08:30:00Z   # kod Inzbruka: 13
$MF/collections/trains/items/1026
```
Svaki objekat ima `time` (prvi i poslednji trenutak), `bbox` (CRS84) i svojstva `train_id`,
`line_id`, `simulated`. `bbox` vraća vožnje čija putanja bilo kada dotakne pravougaonik (`eIntersects`);
`datetime` vraća vožnje čije se trajanje preklapa sa intervalom.

### 4.3 Vremenska geometrija (`tgsequence`)

```
$MF/collections/trains/items/1026/tgsequence?datetime=2026-11-12T08:00:00Z/2026-11-12T08:00:10Z   # prozor od 10 s
$MF/collections/trains-simplified/items/1026/tgsequence                                          # cela vožnja, mala
$MF/collections/trains/items/1026/tgsequence?leaf=2026-11-12T08:00:00Z,2026-11-12T08:05:00Z      # položaj u 2 trenutka
```
Odgovor: `TemporalGeometrySequence` sa jednim `MovingPoint` (`datetimes`, `coordinates` u CRS84,
`interpolation` `Linear`, ili `Discrete` za `leaf`). Pravi se pomoću MobilityDB
`asMFJSON(transform(atTime(trip, …), 4326), 0, 0, 6)`.

### 4.4 Brzina

```
$MF/collections/trains-simplified/items/1026/tgsequence/1/velocity?datetime=2026-11-12T08:00:00Z/2026-11-12T08:02:00Z
```
→ `TReal` u m/s, stepenasta interpolacija, iz MobilityDB `speed(trip)`. U ovom prozoru voz koči pred
Bregenzom: 92 → 68 → 50 → 36 → 20 → 0 km/h. Za brzinu koristiti pojednostavljenu kolekciju: na punoj
trajektoriji GPS šum od ±3 m na intervalima od 0,4–1,3 s daje skokove brzine iznad 280 km/h.

### 4.5 Šta nije implementirano

Operacije upisa (POST/DELETE), `tproperties` osim brzine, `distance`, `acceleration`,
parametar `subTrajectory` i Part 2 (MF-JSON Trajectory). Strana conformance navodi klase kojima se
teži; implementacija je delimična.
