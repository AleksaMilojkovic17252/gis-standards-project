import json
import os
import re
import sys
import urllib.request

import psycopg
from psycopg.conninfo import make_conninfo

main_database_url = os.environ["DATABASE_URL"]
frost_url = os.environ.get("FROST_URL", "http://frost:8080/FROST-Server/v1.1").rstrip("/")
target_databases = [None, "trains_1x"]
variant_databases = [f"trains_1x_{name}" for name in ("noise0", "noise10", "sampling5", "bunching", "chained")]


def get_json(path):
    with urllib.request.urlopen(f"{frost_url}/{path}", timeout=120) as response:
        return json.load(response)


def property_key(observed_property_name):
    return re.sub(r"[^a-z0-9]+", "_", observed_property_name.lower()).strip("_")


def read_from_frost():
    things = get_json(
        "Things?$select=id,name,properties&$top=1000"
        "&$expand=Locations($select=location),"
        "Datastreams($select=id,properties;$expand=ObservedProperty($select=name))"
    )["value"]
    stations = []
    observations = []
    for thing in things:
        station_id = thing["properties"]["geosphere_station_id"]
        longitude, latitude = thing["Locations"][0]["location"]["coordinates"]
        stations.append((station_id, thing["@iot.id"], thing["name"], longitude, latitude))
        for datastream in thing["Datastreams"]:
            key = property_key(datastream["ObservedProperty"]["name"])
            simulated = datastream["properties"]["simulated"]
            page = get_json(f"Datastreams({datastream['@iot.id']})/Observations"
                            "?$select=phenomenonTime,result&$orderby=phenomenonTime&$top=10000")
            for observation in page["value"]:
                result = observation["result"]
                numeric = result if isinstance(result, (int, float)) else None
                text = result if isinstance(result, str) else None
                observations.append((station_id, key, observation["phenomenonTime"], numeric, text, simulated))
    observations.sort(key=lambda row: row[2])
    return stations, observations


def write_to_database(database_url, stations, observations):
    with psycopg.connect(database_url) as connection:
        connection.execute("""
            CREATE SCHEMA IF NOT EXISTS obs;
            DROP TABLE IF EXISTS obs.series, obs.observations, obs.stations CASCADE;
            CREATE TABLE obs.stations (
                station_id integer PRIMARY KEY,
                frost_thing_id integer NOT NULL,
                name text NOT NULL,
                geom geometry(Point, 3416) NOT NULL
            );
            CREATE TABLE obs.observations (
                station_id integer NOT NULL REFERENCES obs.stations,
                property text NOT NULL,
                t timestamptz NOT NULL,
                value double precision,
                value_text text,
                simulated boolean NOT NULL
            );
        """)
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO obs.stations VALUES (%s, %s, %s, ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 3416))",
                stations)
            with cursor.copy("COPY obs.observations FROM STDIN") as copy:
                for row in observations:
                    copy.write_row(row)
        connection.execute("""
            CREATE TABLE obs.series AS
                SELECT station_id, property, bool_or(simulated) AS simulated,
                       CASE WHEN bool_and(value IS NOT NULL)
                            THEN tfloatSeq(array_agg(tfloat(value, t) ORDER BY t), 'step') END AS values_float,
                       CASE WHEN bool_and(value_text IS NOT NULL)
                            THEN ttextSeq(array_agg(ttext(value_text, t) ORDER BY t), 'step') END AS values_text
                FROM obs.observations
                GROUP BY station_id, property
                ORDER BY station_id, property;
            ALTER TABLE obs.series ADD PRIMARY KEY (station_id, property);
            CREATE INDEX ON obs.stations USING gist (geom);
            ANALYZE obs.stations, obs.observations, obs.series;
        """)


def main():
    stations, observations = read_from_frost()
    print(f"Read {len(stations)} stations and {len(observations):,} observations from FROST")
    databases = variant_databases if "--variants" in sys.argv else target_databases
    for database_name in databases:
        database_url = main_database_url if database_name is None else make_conninfo(main_database_url,
                                                                                     dbname=database_name)
        write_to_database(database_url, stations, observations)
        print(f"Wrote obs.stations, obs.observations, obs.series to {database_name or 'trains'}")


if __name__ == "__main__":
    main()
