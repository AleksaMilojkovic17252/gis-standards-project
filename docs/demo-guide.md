# Vodič za demonstraciju

Redosled za prikazivanje projekta u pregledaču. Svi linkovi rade kada su servisi pokrenuti
(`scripts/stack.fish up`) i podaci učitani (`scripts/data.fish all`).

**Priča:** vozovi prelaze Austriju po stvarnim prugama, a meteorološke stanice duž pruga mere
vreme. Isti podaci se objavljuju kroz tri OGC standarda, i svaki standard odgovara na drugu vrstu
pitanja.

**Period:** 4–13. novembar 2026 (UTC). Suvo do 8. novembra, kiša na zapadu 9–10. novembra (Bregenz 29 i
32 mm/dan), kiša u celoj zemlji 12–13. novembra.

> **ID-jevi stanica** u delovima 1 i 3 su FROST ID-jevi i menjaju se kada se ponovo pokrene `scripts/data.fish sta`.
> Trenutni ID-jevi: 18 Innsbruck Universität, 21 Bregenz, 30 Wien Innere Stadt, 33 Linz Stadt.
> Provera: http://localhost:8090/sta/FROST-Server/v1.1/Things?$select=id,name

Savet: Firefox prikazuje JSON pregledno. U drugim pregledačima koristiti neki JSON viewer dodatak.

---

## 1. SensorThings API: „šta svaki senzor meri i šta je izmerio?”

**Poenta:** STA je *model podataka* za senzore (Thing → Datastream → Observation), nad kojim se šalju
upiti sa URL opcijama sličnim OData-i (`$filter`, `$expand`, `$orderby`).

1. **Ulazna tačka**: spisak tipova entiteta.
   http://localhost:8090/sta/FROST-Server/v1.1

2. **Jedna stanica sa svim povezanim podacima**: lokacija, 9 Datastream-ova i za svaki senzor i
   merena veličina.
   http://localhost:8090/sta/FROST-Server/v1.1/Things(21)?$expand=Locations,Datastreams($select=name,unitOfMeasurement,properties;$expand=Sensor($select=name),ObservedProperty($select=name,definition))

   Pokazati: `properties.simulated` (stvarno ili simulirano), UCUM jedinice i definicije po CF
   standardnim nazivima.

3. **Stvarno i simulirano jedno pored drugog**: svi simulirani Datastream-ovi (46).
   http://localhost:8090/sta/FROST-Server/v1.1/Datastreams?$filter=properties/simulated%20eq%20true&$select=name&$count=true

4. **Kišni događaj**: najjače 10-minutne padavine u Bregenzu 10. novembra.
   http://localhost:8090/sta/FROST-Server/v1.1/Observations?$filter=Datastream/Thing/name%20eq%20%27Bregenz%27%20and%20Datastream/ObservedProperty/name%20eq%20%27Precipitation%27%20and%20phenomenonTime%20ge%202026-11-10T00:00:00Z%20and%20phenomenonTime%20lt%202026-11-11T00:00:00Z&$orderby=result%20desc&$top=5&$select=phenomenonTime,result

5. **Reakcija zemljišta** (simulirano): kada je zemljište u Bregenzu postalo zasićeno vodom.
   http://localhost:8090/sta/FROST-Server/v1.1/Observations?$filter=result%20eq%20%27waterlogged%27&$expand=Datastream($select=name)&$select=phenomenonTime,result&$orderby=phenomenonTime&$count=true

6. **Prostorni filter**: stanice unutar pravougaonika iznad Tirola.
   http://localhost:8090/sta/FROST-Server/v1.1/Things?$filter=geo.intersects(Locations/location,geography%27POLYGON((10.0%2046.9,12.9%2046.9,12.9%2047.8,10.0%2047.8,10.0%2046.9))%27)&$select=name

7. **Stanje u jednom trenutku** (koristi ga web aplikacija): poslednja vrednost svakog Datastream-a na
   svakoj stanici u podne 12. novembra, u **jednom** zahtevu.
   http://localhost:8090/sta/FROST-Server/v1.1/Things?$select=name&$expand=Datastreams($select=name;$expand=Observations($select=phenomenonTime,result;$filter=phenomenonTime%20le%202026-11-12T12:00:00Z;$orderby=phenomenonTime%20desc;$top=1))

8. **Straničenje**: na kraju bilo kog dužeg odgovora pokazati `@iot.nextLink`, koji pokazuje na javni
   URL (`localhost:8090`).
   http://localhost:8090/sta/FROST-Server/v1.1/Observations?$top=3

**Ograničenje:** STA 1.1 nema agregaciju (nema sume, proseka ni maksimuma). Dnevni maksimum je
`$orderby=result desc&$top=1`; dnevnu sumu padavina mora da izračuna klijent.

---

## 2. OGC API – Features: „gde se šta nalazi?”

**Poenta:** standardni način objavljivanja vektorskih podataka na webu. Svaka kolekcija radi na isti
način, bez obzira odakle dolaze podaci (ovde: FROST za stanice, PostGIS za pruge).

1. **Početna strana**: http://localhost:8090/ogc/
2. **Kolekcije**: http://localhost:8090/ogc/collections
3. **4 pruge na mapi**: http://localhost:8090/ogc/collections/rail-lines/items
4. **Jedna pruga**: http://localhost:8090/ogc/collections/rail-lines/items/arlbergbahn
5. **Železničke stanice u Beču** (bbox filter): http://localhost:8090/ogc/collections/rail-stations/items?bbox=16.3,48.15,16.45,48.25
6. **Filter po atributu**: http://localhost:8090/ogc/collections/rail-stations/items?name=Innsbruck%20Hauptbahnhof
7. **Meteorološke stanice**, čitane uživo iz FROST-a i prikazane kao objekti: http://localhost:8090/ogc/collections/stations/items
8. **Swagger UI za probanje zahteva**: http://localhost:8090/ogc/openapi

**Zanimljivost:** pruge su sačuvane u EPSG:3416 (Austria Lambert). Kada je ovaj sistem direktno podešen,
pygeoapi je zamenio ose (EPSG:3416 zvanično navodi prvo northing) i postavio Wien Hauptbahnhof
oko 150 km dalje, u Češku. Sada se podaci objavljuju preko pogleda koji ih pretvaraju u geografsku dužinu/širinu.

---

## 3. OGC API – EDR: „kakvo je bilo vreme ovde, u ovo vreme?”

**Poenta:** klijent opisuje samo *mesto i vreme*; server vraća odgovarajuće vrednosti kao
CoverageJSON. Podaci sa stanica i podaci iz mreže se traže **na isti način**, bez poznavanja
STA modela entiteta. pygeoapi iscrtava rezultate na mapi.

1. **Dve EDR kolekcije** (metapodaci, parametri, podržani tipovi upita):
   - http://localhost:8090/ogc/collections/inca-grid
   - http://localhost:8090/ogc/collections/stations-edr

2. **`cube`: INCA mreža temperature oko Beča, podne 12. novembra** (obojeni raster):
   http://localhost:8090/ogc/collections/inca-grid/cube?bbox=16.2,48.1,16.5,48.3&datetime=2026-11-12T12:00:00Z&parameter-name=T2M&f=html

3. **`cube` nad većom oblašću: padavine između Salcburga i Linca za vreme kiše**:
   http://localhost:8090/ogc/collections/inca-grid/cube?bbox=13.0,47.6,14.5,48.4&datetime=2026-11-12T12:00:00Z&parameter-name=RR&f=html

4. **`position`: temperatura u jednoj tački u Beču tokom jednog dana** (vremenska serija):
   http://localhost:8090/ogc/collections/inca-grid/position?coords=POINT(16.37%2048.21)&datetime=2026-11-12T00:00:00Z/2026-11-12T23:00:00Z&parameter-name=T2M&f=html

5. **`locations`: sve meteorološke stanice**:
   http://localhost:8090/ogc/collections/stations-edr/locations

6. **Serija jedne stanice: kiša u Bregenzu za vreme kiše na zapadu, 9–10. novembar**
   (parametar 14 = padavine, 10 = temperatura vazduha):
   http://localhost:8090/ogc/collections/stations-edr/locations/21?datetime=2026-11-09T00:00:00Z/2026-11-10T23:59:59Z&parameter-name=14&f=html

7. **`area`: vreme oko pruge**, glavni primer. Padavine 12. novembra na svim stanicama unutar
   koridora od 10 km oko Westbahn-a (Beč – Salcburg). Poligon u URL-u je bafer oko pruge,
   pojednostavljen na 63 temena. Rezultat: 6 stanica.
   [Otvori upit za koridor](http://localhost:8090/ogc/collections/stations-edr/area?coords=POLYGON%28%2812.922%2047.844%2C12.945%2047.899%2C13.11%2048.023%2C13.215%2048.061%2C13.33%2048.082%2C13.394%2048.078%2C13.477%2048.114%2C13.65%2048.102%2C13.744%2048.166%2C13.835%2048.186%2C14.161%2048.346%2C14.281%2048.386%2C14.364%2048.377%2C14.438%2048.324%2C14.581%2048.287%2C14.706%2048.161%2C14.813%2048.204%2C15.012%2048.229%2C15.074%2048.272%2C15.14%2048.293%2C15.305%2048.311%2C15.457%2048.282%2C15.731%2048.329%2C15.896%2048.383%2C16.041%2048.389%2C16.151%2048.362%2C16.33%2048.27%2C16.394%2048.274%2C16.455%2048.259%2C16.51%2048.201%2C16.488%2048.134%2C16.451%2048.109%2C16.34%2048.08%2C16.222%2048.094%2C16.015%2048.205%2C15.978%2048.206%2C15.67%2048.119%2C15.584%2048.121%2C15.455%2048.098%2C15.371%2048.103%2C15.306%2048.127%2C15.225%2048.118%2C15.161%2048.077%2C15.061%2048.047%2C14.906%2048.033%2C14.794%2047.979%2C14.675%2047.962%2C14.547%2047.991%2C14.429%2048.089%2C14.401%2048.137%2C14.27%2048.175%2C13.969%2048.024%2C13.885%2048.005%2C13.769%2047.925%2C13.56%2047.921%2C13.455%2047.893%2C13.271%2047.868%2C13.136%2047.747%2C13.092%2047.729%2C12.99%2047.731%2C12.948%2047.752%2C12.921%2047.782%2C12.922%2047.844%29%29&datetime=2026-11-12T00:00:00Z/2026-11-12T23:59:59Z&parameter-name=14&f=html)
   (isti link sa `f=json` na kraju prikazuje sirovi CoverageJSON)

8. **Isti podaci, dva API-ja**: uporediti kišu u Bregenzu u EDR-u (stavka 6) sa STA upitom iz
   dela 1, stavka 4. Iste vrednosti, drugačiji način postavljanja pitanja.

**Ograničenja** (sva su otkrivena tokom izrade; detalji u [`api-examples.md`](api-examples.md) §3.7):
- **Tiho skraćivanje:** pygeoapi SensorThingsEDR provajder ne prati FROST linkove za straničenje,
  pa je svaka serija bila skraćena na 100 vrednosti bez greške. Rešeno povećanjem veličine strane u FROST-u.
- **Nedostajući tipovi upita:** nema `trajectory`, `corridor` ni `radius`. „Vreme duž putanje voza
  kroz vreme” bi bio trajectory upit, pa web aplikacija mora da kombinuje `area` i `position`.
- **Dužina URL-a:** nepojednostavljeni koridor (5.448 temena) vraća HTTP 414.
- **Nepodržani tipovi upita vraćaju jasnu grešku**, npr.
  http://localhost:8090/ogc/collections/inca-grid/trajectory?coords=LINESTRING(16.37%2048.18,15.62%2048.21)
  → HTTP 400 "Unsupported query type".

---

## 4. OGC API – Moving Features: „gde je bio ovaj voz, kada i kojom brzinom?”

**Poenta:** voz nije tačka sa vremenom u svakom redu; to je **jedan objekat čija se geometrija menja
kroz vreme**. MobilityDB čuva svaku vožnju kao jedan `tgeompoint`, a MF API ga objavljuje kao MF-JSON.
Svi podaci o vozovima su **simulirani** (fiksni seed, pa ID-jevi vožnji ostaju isti).

Primer vožnje **1026**: Arlbergbahn, Innsbruck → Bregenz, 12. novembar, 06:00–08:09 UTC.

1. **Swagger UI**: http://localhost:8090/mf/docs
2. **Dve kolekcije** (pune i pojednostavljene trajektorije, sa obuhvatom): http://localhost:8090/mf/collections
3. **Vozovi u saobraćaju između 08:00 i 08:30 12. novembra** (25):
   http://localhost:8090/mf/collections/trains/items?datetime=2026-11-12T08:00:00Z/2026-11-12T08:30:00Z&limit=50
4. **Vozovi kod Inzbruka u tih pola sata** (bbox + vreme, 13):
   http://localhost:8090/mf/collections/trains/items?bbox=11.3,47.2,11.5,47.3&datetime=2026-11-12T08:00:00Z/2026-11-12T08:30:00Z&limit=50
5. **Jedan pokretni objekat** (metapodaci, vremenski raspon, bbox): http://localhost:8090/mf/collections/trains/items/1026
6. **Njegova trajektorija za 10 sekundi** (MF-JSON `MovingPoint`, oko jedne tačke u sekundi):
   http://localhost:8090/mf/collections/trains/items/1026/tgsequence?datetime=2026-11-12T08:00:00Z/2026-11-12T08:00:10Z
7. **Gde je bio u 08:00 i 08:05?** (`leaf`):
   http://localhost:8090/mf/collections/trains/items/1026/tgsequence?leaf=2026-11-12T08:00:00Z,2026-11-12T08:05:00Z
8. **Brzina pri kočenju pred Bregenzom** (m/s; 92 → 0 km/h):
   http://localhost:8090/mf/collections/trains-simplified/items/1026/tgsequence/1/velocity?datetime=2026-11-12T08:00:00Z/2026-11-12T08:02:00Z
9. **Puna i pojednostavljena veličina**: otvoriti oba i uporediti (oko 364 KB i 36 KB):
   - http://localhost:8090/mf/collections/trains/items/1026/tgsequence
   - http://localhost:8090/mf/collections/trains-simplified/items/1026/tgsequence

**Zanimljivosti:**
- Istih 1,1 milion GPS tačaka dnevno čuva se na tri načina: jedan red po tački (107 MB), jedan
  MobilityDB `tgeompoint` po vožnji (22 MB) i jedan PostGIS `LineStringM` po vožnji (17 MB).
- Normalizacija u MobilityDB-u nije uklonila **ništa** iz podataka sa šumom, a iz podataka bez šuma
  samo 13 %: prave pruge su skoro svuda zakrivljene.
- GPS šum povećava brzinu i dužinu (najveća brzina > 280 km/h na pruzi od 230 km/h), zato web
  aplikacija i primer sa brzinom koriste pojednostavljene trajektorije.
- OGC referentni server (AIST) je iz 2024. i namenjen je starom MobilityDB-u, pa je ovaj API napisan
  od nule u oko 350 linija; implementira samo deo standarda za čitanje.

---

## 5. React web aplikacija: svi standardi u jednom klijentu

Otvoriti http://localhost:8090/ (podrazumevano vreme: 12. novembar, 10:00 UTC, za vreme kiše u celoj zemlji).

1. **Pregled mape:** sive pruge (Features), plavi vozovi (Moving Features), obojene meteorološke
   stanice (SensorThings stanje). Nema sopstveni backend: svaki sloj je standardni OGC API zahtev.
2. **Play** (5 min/s): vozovi se kreću po prugama i staju na stanicama; boje stanica se menjaju
   na svakih 10 simuliranih minuta.
3. **Klik na stanicu:** svih 9 vrednosti u trenutnom vremenu sa grafikonima za 24 h; simulirane vrednosti su označene.
4. **Klik na voz:** brzina, sledeća stanica, vrednosti sa najbliže meteorološke stanice; link otvara
   MF-JSON vožnje.
5. **Vreme oko pruge:** izabrati *Westbahn*, kliknuti dugme: pojavljuje se isprekidani koridor od 10 km,
   a EDR `area` upit vraća stanice unutar njega sa dnevnim padavinama i temperaturom.
6. **INCA mreža:** uključiti *INCA mreža*, izabrati temperaturu ili padavine: EDR `cube` se iscrtava ispod
   mape (prvo pauzirati; ~7 MB po satu podataka).
7. **Bojenje stanica po vlažnosti zemljišta** i skok na 10. novembar 07:00 UTC: Bregenz postaje taman
   (vlažno / zasićeno posle kiše na zapadu).
8. **Režim uživo (MQTT):** uključiti *Uživo* kod stanica (status: *povezano*), pa pokrenuti
   `docker compose run --rm -e STEPS=24 sta-loader python replay_observations_live.py`. Na svakih 5 s preko
   MQTT-a stiže novi 10-minutni korak: broj poruka raste za ~150, boje stanica i opisi se menjaju bez
   ijednog REST zahteva. F12 → Network → WS → `mqtt` → Messages prikazuje poruke. Posle toga očistiti
   podatke sa `delete_replayed_observations.py`.
