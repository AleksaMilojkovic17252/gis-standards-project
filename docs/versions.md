# Verzije komponenti

Provereno 2026-11-15.

## Docker image-i i paketi

| Komponenta | Verzija | Napomena |
|---|---|---|
| FROST-Server | `fraunhoferiosb/frost-server:2.8.2` | Poslednje izdanje (2026-10-25). Izbegavati `latest` (pokazuje na 2.9.0-SNAPSHOT). |
| FROST baza | `postgis/postgis:17-3.5` | |
| MobilityDB | `mobilitydb/mobilitydb:17-3.5-1.3` | U image-u: PostgreSQL 17.5, PostGIS 3.5.2, **MobilityDB 1.3.0**, GEOS 3.9.0, PROJ 7.2.1. |
| pymeos | `pymeos==1.3.0` (+ `pymeos-cffi>=1.3.0,<2`) | Odgovara MobilityDB 1.3. Zahteva Python ≥ 3.10. |
| pygeoapi | `geopython/pygeoapi:0.24.0` | Poslednje izdanje (2026-07-28). |
| nginx | `nginx:1.30.6-alpine` | |
| osm2pgsql | `iboates/osm2pgsql:2.3.1` | Image zajednice (projekat osm2pgsql ga ne objavljuje). Libosmium 2.23.1, PROJ 9.8.1, LuaJIT 2.1. |
| train-simulator | `python:3.12.16-slim` + `shapely==2.2.0`, `networkx==3.7`, `psycopg[binary]==3.3.9`, `pymeos==1.3.0` | |
| mf-api | `python:3.12.16-slim` + `fastapi==0.163.1`, `uvicorn==0.54.0`, `psycopg[binary]==3.3.9` | Sopstveni FastAPI servis. |
| web | `node:22.23.5-alpine`, React 19.3.1, Vite 8.3.8, react-leaflet 5.0.0, Leaflet 1.9.4, TypeScript 5.9.3 | |
| OSM izvod | Geofabrik `austria-261114.osm.pbf` (2026-11-14) | Preuzima se ručno. |

## AIST MF-API (`aistairc/mf-api`)

Referentni server za OGC API – Moving Features nije korišćen:

- poslednji commit **2024-02-28**, jedno izdanje `1.0`;
- fork stare verzije pygeoapi-ja, image `ghcr.io/taehoonk/mf-api-server:1.2` na `mobilitydb/mobilitydb:14-3.2-1` (PG 14, MobilityDB 1.0/1.1);
- SQL je pisan za stariji MobilityDB API, a podatke čuva u sopstvenoj šemi preko svojih POST endpoint-a, ne u `mdb.trips`.

Umesto toga napisan je minimalan FastAPI servis za MF Part 1.

## EDR provajderi u pygeoapi 0.24.0

| Provajder | Podržani tipovi upita | Nisu podržani |
|---|---|---|
| `SensorThingsEDR` | `items`, `locations`, `cube`, `area` | `position`, `radius`, `trajectory`, `corridor` |
| `xarray-edr` | `position`, `cube` (bez z-ose) | `area`, `radius`, `trajectory`, `corridor` |

`area` nad stanicama koristi STA `st_within` nad lokacijom Thing-a kome pripada Datastream.

## GeoSphere podaci

- `klima-v2-10min`: 531 stanica, od 1992-05-20. Ima stvarnu temperaturu zemljišta: `tb10`, `tb20`, `tb50` (-10/-20/-50 cm).
  Korišćeni parametri: `tl` (temperatura vazduha), `rf` (relativna vlažnost), `p` (pritisak), `ff` (vetar), `rr` (padavine), `cglo` (globalno zračenje), `tb10`.
- INCA mreža:
  - `inca-v1-1h-1km`: od 2011-03-15. Parametri `T2M`, `RH2M`, `RR`, `GL`, `P0`, `TD2M`, `UU`, `VV`. CRS **EPSG:31287** (MGI / Austria Lambert).
  - `inca-v2-1h-1km`: tek od **2026-10-01**. Parametri `2t`, `2r`, `tp`, … EPSG:31287.

## QGIS i EDR

- Jezgro QGIS-a i dalje **nema EDR provajder**.
- Postoji **QGIS dodatak „Environmental Data Retrieval”** ([`edr_plugin`](https://plugins.qgis.org/plugins/edr_plugin/latest/)), v1.1.0 (2026-01-06), za QGIS 3.99–4.99 (tj. QGIS 4.x). Podržava CoverageJSON od verzije 0.2.0. Potrebne ispravke: [`qgis-edr-plugin-fixes.md`](qgis-edr-plugin-fixes.md).
