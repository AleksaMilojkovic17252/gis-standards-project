import io
import os
import sys
import time

import numpy as np
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from shapely import from_wkb

import simulate_trains as simulator

main_database_url = os.environ["DATABASE_URL"]
random_seed = 20261112
simplify_tolerance_m = 10.0

scales = {
    "1x": {"database": "trains_1x", "days": [simulator.one_x_day], "with_exact_variant": True},
    "10x": {"database": None, "days": simulator.service_days_from(simulator.period_first_day, 10),
            "with_exact_variant": False},
}
for variant_name in simulator.sensitivity_variants:
    scales[f"1x-{variant_name}"] = {"database": f"trains_1x_{variant_name}", "days": [simulator.one_x_day],
                                    "with_exact_variant": False, "settings": simulator.sensitivity_variants[variant_name]}

copied_rail_tables = ["rail.lines", "rail.line_stops", "rail.stations"]

qgis_views_sql = """
    CREATE OR REPLACE VIEW mdb.trips_paths AS
        SELECT trip_id, train_id, line_id, startTimestamp(trip) AS departure, endTimestamp(trip) AS arrival,
               trajectory(trip)::geometry(LineString, 3416) AS geom
        FROM mdb.trips_simplified;
    CREATE OR REPLACE VIEW postgis_points.positions_one_hour AS
        SELECT row_number() OVER (ORDER BY t, trip_id) AS id, trip_id, train_id, t, geom
        FROM postgis_points.positions
        WHERE t >= '2026-11-12 10:00:00+00' AND t < '2026-11-12 11:00:00+00';
"""


def database_url_for(database_name):
    return main_database_url if database_name is None else make_conninfo(main_database_url, dbname=database_name)


def ensure_database(database_name):
    if database_name is None:
        with psycopg.connect(main_database_url) as connection:
            connection.execute("CREATE SCHEMA IF NOT EXISTS sim")
        return
    with psycopg.connect(main_database_url, autocommit=True) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template_mobilitydb").format(
                sql.Identifier(database_name)))
            print(f"Created database {database_name}")
    with psycopg.connect(database_url_for(database_name)) as connection:
        connection.execute("""
            CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
            CREATE SCHEMA IF NOT EXISTS rail;
            CREATE SCHEMA IF NOT EXISTS mdb;
            CREATE SCHEMA IF NOT EXISTS postgis_points;
            CREATE SCHEMA IF NOT EXISTS postgis_lsm;
            CREATE SCHEMA IF NOT EXISTS obs;
            CREATE SCHEMA IF NOT EXISTS sim;
        """)


def copy_rail_tables(database_name):
    if database_name is None:
        return
    with psycopg.connect(main_database_url) as source, psycopg.connect(database_url_for(database_name)) as target:
        for table in copied_rail_tables:
            schema_name, table_name = table.split(".")
            columns = source.execute("""
                SELECT string_agg(format('%%I %%s', a.attname, format_type(a.atttypid, a.atttypmod)), ', '
                                  ORDER BY a.attnum)
                FROM pg_attribute a
                WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
            """, (table,)).fetchone()[0]
            target.execute(f"DROP TABLE IF EXISTS {table} CASCADE; CREATE TABLE {table} ({columns})")
            buffer = io.BytesIO()
            with source.cursor().copy(f"COPY {table} TO STDOUT (FORMAT binary)") as copy_out:
                for chunk in copy_out:
                    buffer.write(chunk)
            with target.cursor().copy(f"COPY {table} FROM STDIN (FORMAT binary)") as copy_in:
                copy_in.write(buffer.getvalue())
            print(f"Copied {table} to {database_name}")
        target.execute("""
            ALTER TABLE rail.lines ADD PRIMARY KEY (line_id);
            ALTER TABLE rail.stations ADD PRIMARY KEY (osm_id);
            ALTER TABLE rail.line_stops ADD PRIMARY KEY (line_id, stop_sequence);
            CREATE INDEX ON rail.lines USING gist (geom);
            CREATE INDEX ON rail.stations USING gist (geom);
        """)


def read_lines():
    with psycopg.connect(main_database_url) as connection:
        lines = []
        rows = connection.execute("SELECT line_id, ST_AsBinary(geom) FROM rail.lines ORDER BY line_id").fetchall()
        for line_id, geometry_wkb in rows:
            stops = connection.execute(
                "SELECT name, distance_along_m FROM rail.line_stops WHERE line_id = %s ORDER BY stop_sequence",
                (line_id,)).fetchall()
            segments = connection.execute(
                "SELECT from_m, maxspeed_kmh FROM rail.line_segments WHERE line_id = %s ORDER BY segment_sequence",
                (line_id,)).fetchall()
            lines.append(simulator.Line(
                line_id=line_id,
                coordinates=np.array(from_wkb(geometry_wkb).coords),
                stop_names=[name for name, _ in stops],
                stop_distances_m=np.array([distance for _, distance in stops]),
                segment_starts_m=np.array([start for start, _ in segments]),
                segment_speeds_kmh=np.array([speed for _, speed in segments]),
            ))
    return lines


def table_names(suffix):
    return {
        "trips": f"sim.trip_info{suffix}",
        "staging": f"sim.staging{suffix}",
        "positions": f"postgis_points.positions{suffix}",
        "mdb": f"mdb.trips{suffix}",
        "mdb_simplified": f"mdb.trips{suffix}_simplified",
        "lsm": f"postgis_lsm.trips{suffix}",
        "lsm_simplified": f"postgis_lsm.trips{suffix}_simplified",
    }


def load_variant(connection, lines, days, exact, settings):
    suffix = "_exact" if exact else ""
    tables = table_names(suffix)
    started = time.time()

    trips = list(simulator.simulate_days(lines, days, seed=random_seed,
                                         settings=simulator.exact_settings if exact else settings))
    trip_ids = np.concatenate([np.full(trip.times.size, trip.trip_id, dtype=np.int32) for trip in trips])
    times = np.concatenate([trip.times for trip in trips])
    xs = np.concatenate([trip.x for trip in trips])
    ys = np.concatenate([trip.y for trip in trips])
    order = np.argsort(times, kind="stable")
    print(f"  simulated {len(trips)} trips, {times.size:,} points in {time.time() - started:.0f} s")

    connection.execute(f"""
        DROP TABLE IF EXISTS {tables['trips']}, {tables['staging']}, {tables['positions']},
                             {tables['mdb']}, {tables['mdb_simplified']},
                             {tables['lsm']}, {tables['lsm_simplified']} CASCADE;
        CREATE TABLE {tables['trips']} (
            trip_id integer PRIMARY KEY,
            train_id text NOT NULL,
            line_id text NOT NULL,
            direction text NOT NULL,
            scheduled_departure timestamptz NOT NULL,
            actual_departure timestamptz NOT NULL,
            arrival timestamptz NOT NULL,
            simulated boolean NOT NULL DEFAULT true
        );
        CREATE UNLOGGED TABLE {tables['staging']} (trip_id integer, t double precision, x double precision,
                                                   y double precision);
    """)
    with connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO {tables['trips']} VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(trip.trip_id, trip.train_id, trip.line_id, trip.direction, trip.scheduled_departure,
              trip.actual_departure, trip.arrival) for trip in trips])
        with cursor.copy(f"COPY {tables['staging']} FROM STDIN") as copy:
            chunk_size = 500_000
            for chunk_start in range(0, order.size, chunk_size):
                chunk = order[chunk_start:chunk_start + chunk_size]
                lines_of_text = "".join(
                    f"{trip_id}\t{t:.3f}\t{x:.2f}\t{y:.2f}\n"
                    for trip_id, t, x, y in zip(trip_ids[chunk], times[chunk], xs[chunk], ys[chunk]))
                copy.write(lines_of_text)
    print(f"  staged in {time.time() - started:.0f} s")

    connection.execute(f"""
        CREATE TABLE {tables['positions']} (
            trip_id integer NOT NULL,
            train_id text NOT NULL,
            t timestamptz NOT NULL,
            geom geometry(Point, 3416) NOT NULL
        );
        INSERT INTO {tables['positions']}
            SELECT s.trip_id, i.train_id, to_timestamp(s.t), ST_SetSRID(ST_MakePoint(s.x, s.y), 3416)
            FROM {tables['staging']} AS s JOIN {tables['trips']} AS i USING (trip_id)
            ORDER BY s.t;
        DROP TABLE {tables['staging']};
    """)
    print(f"  {tables['positions']} loaded in time order in {time.time() - started:.0f} s")

    connection.execute(f"""
        CREATE TABLE {tables['mdb']} (
            trip_id integer PRIMARY KEY,
            train_id text NOT NULL,
            line_id text NOT NULL,
            trip tgeompoint NOT NULL
        );
        INSERT INTO {tables['mdb']}
            SELECT p.trip_id, i.train_id, i.line_id,
                   tgeompointSeq(array_agg(tgeompoint(p.geom, p.t) ORDER BY p.t), 'linear', true, true)
            FROM {tables['positions']} AS p JOIN {tables['trips']} AS i USING (trip_id)
            GROUP BY p.trip_id, i.train_id, i.line_id, i.actual_departure
            ORDER BY i.actual_departure, p.trip_id;
        CREATE TABLE {tables['mdb_simplified']} AS
            SELECT trip_id, train_id, line_id, douglasPeuckerSimplify(trip, {simplify_tolerance_m}) AS trip
            FROM {tables['mdb']} ORDER BY trip_id;
        ALTER TABLE {tables['mdb_simplified']} ADD PRIMARY KEY (trip_id);
    """)
    print(f"  {tables['mdb']} built in {time.time() - started:.0f} s")

    connection.execute(f"""
        CREATE TABLE {tables['lsm']} (
            trip_id integer PRIMARY KEY,
            train_id text NOT NULL,
            geom geometry(LineStringM, 3416) NOT NULL,
            period tstzrange NOT NULL
        );
        INSERT INTO {tables['lsm']}
            SELECT p.trip_id, i.train_id,
                   ST_SetSRID(ST_MakeLine(ST_MakePointM(ST_X(p.geom), ST_Y(p.geom), extract(epoch FROM p.t))
                                          ORDER BY p.t), 3416),
                   tstzrange(min(p.t), max(p.t), '[]')
            FROM {tables['positions']} AS p JOIN {tables['trips']} AS i USING (trip_id)
            GROUP BY p.trip_id, i.train_id, i.actual_departure
            ORDER BY i.actual_departure, p.trip_id;
        CREATE TABLE {tables['lsm_simplified']} AS
            SELECT trip_id, train_id, ST_Simplify(geom, {simplify_tolerance_m})::geometry(LineStringM, 3416) AS geom,
                   period
            FROM {tables['lsm']} ORDER BY trip_id;
        ALTER TABLE {tables['lsm_simplified']} ADD PRIMARY KEY (trip_id);
    """)
    print(f"  {tables['lsm']} built in {time.time() - started:.0f} s")
    return tables


def report(connection, tables):
    rows = connection.execute(f"""
        SELECT 'positions' AS model, count(*)::bigint, pg_total_relation_size('{tables['positions']}')
        FROM {tables['positions']}
        UNION ALL SELECT 'mdb', sum(numInstants(trip))::bigint, pg_total_relation_size('{tables['mdb']}')
        FROM {tables['mdb']}
        UNION ALL SELECT 'mdb_simplified', sum(numInstants(trip))::bigint,
                         pg_total_relation_size('{tables['mdb_simplified']}') FROM {tables['mdb_simplified']}
        UNION ALL SELECT 'lsm', sum(ST_NPoints(geom))::bigint, pg_total_relation_size('{tables['lsm']}')
        FROM {tables['lsm']}
        UNION ALL SELECT 'lsm_simplified', sum(ST_NPoints(geom))::bigint,
                         pg_total_relation_size('{tables['lsm_simplified']}') FROM {tables['lsm_simplified']}
    """).fetchall()
    for model, points, size_bytes in rows:
        print(f"    {model:<16} {points:>12,} points  {size_bytes / 1e6:9.1f} MB")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in scales:
        sys.exit(f"usage: python load_trains.py {' | '.join(scales)}")
    scale = scales[sys.argv[1]]
    database_name = scale["database"]
    ensure_database(database_name)
    copy_rail_tables(database_name)
    lines = read_lines()

    variants = [False, True] if scale["with_exact_variant"] else [False]
    with psycopg.connect(database_url_for(database_name)) as connection:
        loaded = []
        for exact in variants:
            print(f"Loading {sys.argv[1]} ({len(scale['days'])} days){' noise-free variant' if exact else ''}")
            loaded.append(load_variant(connection, lines, scale["days"], exact,
                                       scale.get("settings", simulator.baseline_settings)))
            connection.commit()
    with psycopg.connect(database_url_for(database_name)) as connection:
        connection.execute(qgis_views_sql)
    with psycopg.connect(database_url_for(database_name), autocommit=True) as connection:
        connection.execute("VACUUM ANALYZE")
        for tables in loaded:
            print(f"  sizes for {tables['positions']}:")
            report(connection, tables)


if __name__ == "__main__":
    main()
