# Savremeni OGC API standardi

Projekat ispituje tri novija OGC standarda na jednom primeru: vozovi koji se kreću
kroz Austriju i meteorološke stanice duž pruga.

- **OGC SensorThings API** (FROST-Server): meteorološke stanice i merenja, uživo preko MQTT-a
- **OGC API – EDR** (pygeoapi): podaci sa stanica i INCA mreža (padavine, temperatura)
- **OGC API – Moving Features** (FastAPI nad MobilityDB): putanje vozova

Pored toga, upoređuje se čuvanje putanja u **MobilityDB** i u običnom **PostGIS**-u
(tačke i LineStringM) kroz benchmark od sedam upita (Q1–Q7). Rad se nalazi u
`paper/SIR2.odt`, a grafikoni u `paper/figures/sr/`.

## Potrebno

- Docker sa Compose v2
- Python 3.10+ (samo za preuzimanje podataka, bez dodatnih paketa)
- fish shell za skripte u `scripts/` (komande se mogu pokrenuti i ručno, vidi skripte)
- oko 15 GB slobodnog prostora

## 1. Pokretanje servisa

```fish
scripts/stack.fish up       # pravi .env iz .env.example, gradi i pokreće sve servise
scripts/stack.fish status
scripts/stack.fish down     # zaustavlja servise, baze ostaju sačuvane
```

Bez fish-a:

```sh
cp .env.example .env
docker compose up -d --build --wait
```

Sve je dostupno na `http://localhost:8090`:

| Putanja | Servis |
|---|---|
| `/` | web aplikacija (React + Leaflet) |
| `/sta/FROST-Server/v1.1` | SensorThings API |
| `/sta/mqtt` | MQTT preko websocket-a |
| `/ogc/` | OGC API – Features i EDR (pygeoapi) |
| `/mf/` | OGC API – Moving Features |

Baza (MobilityDB/PostGIS) je dostupna i na `localhost:25432` (korisnik `gis`).

## 2. Preuzimanje podataka

Period posmatranja je od 4. do 13. novembra 2026.

```sh
python3 data/fetch_meta.py       # metapodaci GeoSphere Austria
python3 data/fetch_inca.py       # INCA mreža (NetCDF)
python3 data/fetch_stations.py   # 10-minutni podaci za 17 stanica
```

OpenStreetMap izvod za Austriju treba ručno preuzeti sa
[Geofabrik-a](https://download.geofabrik.de/europe/austria.html) i sačuvati u `data/raw/osm/`
(korišćen je `austria-261114.osm.pbf`). Svi podaci idu u `data/raw/`.

## 3. Učitavanje podataka

Servisi moraju biti pokrenuti.

```fish
scripts/data.fish osm        # pruge i stanice iz OSM-a
scripts/data.fish rail       # 4 linije, stajališta i brzine
scripts/data.fish stations   # izbor 17 meteoroloških stanica
scripts/data.fish inca       # priprema INCA mreže za pygeoapi
scripts/data.fish sta        # stanice i merenja u FROST (+ simulirana vlažnost zemljišta)
scripts/data.fish trains1x   # simulacija vozova za 12. novembar (baza trains_1x)
scripts/data.fish trains10x  # simulacija za ceo period (baza trains)
scripts/data.fish obs        # kopija merenja iz FROST-a u obe baze
```

Ili sve odjednom: `scripts/data.fish all`.

Posle ovoga web aplikacija na `http://localhost:8090` prikazuje stanice, pruge, vozove,
INCA mrežu i koridor duž pruge.

### Režim uživo (MQTT)

U aplikaciji uključiti *Uživo* kod meteoroloških stanica, pa pustiti jedan dan merenja u FROST:

```fish
docker compose run --rm -e STEPS=24 sta-loader python replay_observations_live.py
docker compose run --rm sta-loader python delete_replayed_observations.py   # brisanje posle testa
```

Brisanje uraditi pre benchmarka.

## 4. Benchmark (MobilityDB i PostGIS)

Upiti su u `benchmark/sql/<model>/`. Za vreme merenja ništa drugo ne sme da koristi bazu.

```fish
scripts/benchmark.fish complexity    # broj linija i tokena SQL-a po upitu
scripts/benchmark.fish warm1x        # svi indeksi na trains_1x (~20 min)
scripts/benchmark.fish warm10x       # svi indeksi na trains (~60 min)
scripts/data.fish variants           # pet varijanti podataka za analizu osetljivosti
scripts/benchmark.fish sensitivity
python3 benchmark/analyze_sensitivity.py
scripts/benchmark.fish charts        # grafikoni u paper/figures/
```

Rezultati se nalaze u `benchmark/results/<oznaka>/` (`summary.csv`, `runs.csv`, `indexes.csv`,
`environment.json`).

## 5. QGIS

Provera da li QGIS može da čita iste podatke opisana je u [`docs/qgis-guide.md`](docs/qgis-guide.md),
a potrebne ispravke EDR dodatka u [`docs/qgis-edr-plugin-fixes.md`](docs/qgis-edr-plugin-fixes.md).
Gotov QGIS projekat je `testing_standards.qgz`.

## Dokumentacija

- [`docs/demo-guide.md`](docs/demo-guide.md): vodič za demonstraciju u pregledaču
- [`docs/api-examples.md`](docs/api-examples.md): primeri zahteva za sve API-je
- [`docs/versions.md`](docs/versions.md): verzije korišćenih komponenti

## Izvori podataka

- Meteorološki podaci: [GeoSphere Austria Data Hub](https://data.hub.geosphere.at), CC BY 4.0
- Pruge: © OpenStreetMap contributors, ODbL
- Vlažnost zemljišta, vozovi i red vožnje su simulirani
