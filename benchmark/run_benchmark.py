import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

main_database_url = os.environ["DATABASE_URL"]
benchmark_folder = Path(__file__).resolve().parent
sql_folder = benchmark_folder / "sql"
results_folder = benchmark_folder / "results"

warm_runs = 5
statement_timeout_s = 300
queries = [f"q{number}" for number in range(1, 8)]

models = {
    "postgis_points": {
        "table": "postgis_points.positions",
        "configs": {
            "none": [],
            "gist_geom": ["USING gist (geom)"],
            "brin_t": ["USING brin (t)"],
            "btree_trip_t": ["(trip_id, t)"],
            "all": ["USING gist (geom)", "USING brin (t)", "(trip_id, t)"],
        },
        "best": "all",
    },
    "mdb": {
        "table": "mdb.trips",
        "configs": {
            "none": [],
            "gist_trip": ["USING gist (trip)"],
        },
        "best": "gist_trip",
    },
    "postgis_lsm": {
        "table": "postgis_lsm.trips",
        "configs": {
            "none": [],
            "gist_geom": ["USING gist (geom)"],
            "gist_period": ["USING gist (period)"],
            "all": ["USING gist (geom)", "USING gist (period)"],
        },
        "best": "all",
    },
}

query_time = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
base_parameters = {
    "t": query_time,
    "t1": query_time,
    "t2": query_time + timedelta(hours=1),
    "passage_t1": query_time - timedelta(hours=2),
    "passage_t2": query_time + timedelta(hours=2),
    "radius_m": 10_000,
    "passage_m": 200,
}
q2_box_half_size_m = 5_000
q2_station_name = "Linz Hauptbahnhof"
q4_trains = ("westbahn-f-1000", "westbahn-b-1000")
q6_station_name = "Linz Hauptbahnhof"
service_day = "2026-11-12"


def database_url_for(database_name):
    return make_conninfo(main_database_url, dbname=database_name)


def resolve_parameters(connection):
    parameters = dict(base_parameters)
    station_x, station_y = connection.execute(
        "SELECT ST_X(geom), ST_Y(geom) FROM rail.stations WHERE name = %s ORDER BY osm_id LIMIT 1",
        (q2_station_name,)).fetchone()
    parameters.update(xmin=station_x - q2_box_half_size_m, ymin=station_y - q2_box_half_size_m,
                      xmax=station_x + q2_box_half_size_m, ymax=station_y + q2_box_half_size_m)
    for key, train_id in zip(("trip_a", "trip_b"), q4_trains):
        parameters[key] = connection.execute(
            "SELECT trip_id FROM sim.trip_info WHERE train_id = %s AND scheduled_departure::date = %s",
            (train_id, service_day)).fetchone()[0]
    parameters["station_osm_id"] = connection.execute(
        "SELECT osm_id FROM rail.line_stops WHERE name = %s LIMIT 1", (q6_station_name,)).fetchone()[0]
    return parameters


def fingerprint(query, rows):
    def number(value):
        if value is None:
            return None
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    if query == "q3":
        lengths = [number(row[1]) for row in rows if row[1] is not None]
        return round(statistics.mean(lengths), 1) if lengths else None
    if query == "q4":
        return round(number(rows[0][0]), 2) if rows and rows[0][0] is not None else None
    if query == "q5":
        return round(sum(number(row[1]) or 0 for row in rows), 1)
    if query == "q7":
        temperatures = [number(row[2]) for row in rows if row[2] is not None]
        return round(statistics.mean(temperatures), 3) if temperatures else None
    return len(rows)


def set_index_config(connection, model_name, config_name):
    model = models[model_name]
    table = model["table"]
    existing = connection.execute("""
        SELECT format('%%I.%%I', schemaname, indexname) FROM pg_indexes
        WHERE format('%%I.%%I', schemaname, tablename) = %s AND indexname LIKE 'bench\\_%%'
    """, (table,)).fetchall()
    for (index_name,) in existing:
        connection.execute(f"DROP INDEX {index_name}")
    started = time.perf_counter()
    for position, definition in enumerate(model["configs"][config_name]):
        index_name = f"bench_{model_name}_{config_name}_{position}"
        connection.execute(f"CREATE INDEX {index_name} ON {table} {definition}")
    build_s = time.perf_counter() - started
    connection.execute(f"ANALYZE {table}")
    table_bytes, index_bytes = connection.execute(
        "SELECT pg_table_size(%s), pg_indexes_size(%s)", (table, table)).fetchone()
    return build_s, table_bytes, index_bytes


def run_query(connection, sql_text, parameters):
    started = time.perf_counter()
    try:
        rows = connection.execute(sql_text, parameters).fetchall()
    except psycopg.errors.QueryCanceled:
        connection.rollback()
        return None, None
    elapsed_ms = (time.perf_counter() - started) * 1000
    connection.rollback()
    return elapsed_ms, rows


def sql_for(model_name, query):
    return (sql_folder / model_name / f"{query}.sql").read_text()


def append_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="") as file:
        writer = csv.writer(file)
        if is_new:
            writer.writerow(header)
        writer.writerows(rows)


def write_sql_complexity():
    rows = []
    for model_name in models:
        for query in queries:
            text = sql_for(model_name, query)
            code_lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("--")]
            rows.append((model_name, query, len(code_lines), len(" ".join(code_lines).split())))
    path = results_folder / "sql_complexity.csv"
    path.unlink(missing_ok=True)
    append_csv(path, ["model", "query", "lines", "tokens"], rows)


def record_environment(connection, label):
    settings = dict(connection.execute("""
        SELECT name, setting || coalesce(unit, '') FROM pg_settings
        WHERE name IN ('shared_buffers', 'effective_cache_size', 'work_mem', 'maintenance_work_mem',
                       'max_parallel_workers_per_gather', 'jit', 'random_page_cost')
    """).fetchall())
    environment = {
        "label": label,
        "recorded": datetime.now(timezone.utc).isoformat(),
        "postgres": connection.execute("SHOW server_version").fetchone()[0],
        "mobilitydb": connection.execute("SELECT mobilitydb_full_version()").fetchone()[0],
        "settings": settings,
        "warm_runs": warm_runs,
        "statement_timeout_s": statement_timeout_s,
    }
    path = results_folder / label / "environment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(environment, indent=2, default=str))


def prepare_database(connection):
    connection.execute("CREATE INDEX IF NOT EXISTS observations_lookup ON obs.observations (station_id, property, t)")
    connection.execute("ANALYZE obs.observations")
    connection.commit()


def run_warm(database_name, label, selected_models, selected_queries, selected_configs):
    output = results_folder / label
    with psycopg.connect(database_url_for(database_name)) as connection:
        prepare_database(connection)
        record_environment(connection, label)
        parameters = resolve_parameters(connection)
        connection.execute(f"SET statement_timeout = '{statement_timeout_s}s'")
        connection.commit()
        for model_name in selected_models:
            configs = selected_configs or list(models[model_name]["configs"])
            for config_name in configs:
                if config_name == "best":
                    config_name = models[model_name]["best"]
                build_s, table_bytes, index_bytes = set_index_config(connection, model_name, config_name)
                connection.commit()
                append_csv(output / "indexes.csv",
                           ["model", "config", "build_s", "table_bytes", "index_bytes"],
                           [(model_name, config_name, round(build_s, 3), table_bytes, index_bytes)])
                print(f"{label} {model_name} [{config_name}] index build {build_s:.1f} s, "
                      f"table {table_bytes / 1e6:.1f} MB, indexes {index_bytes / 1e6:.1f} MB", flush=True)
                for query in selected_queries:
                    sql_text = sql_for(model_name, query)
                    warmup_ms, rows = run_query(connection, sql_text, parameters)
                    timings = []
                    if warmup_ms is not None:
                        for _ in range(warm_runs):
                            elapsed_ms, rows = run_query(connection, sql_text, parameters)
                            if elapsed_ms is None:
                                break
                            timings.append(elapsed_ms)
                    timed_out = warmup_ms is None or len(timings) < warm_runs
                    median_ms = statistics.median(timings) if timings and not timed_out else None
                    answer = fingerprint(query, rows) if rows is not None else None
                    append_csv(output / "runs.csv", ["model", "config", "query", "kind", "run", "ms"],
                               [(model_name, config_name, query, "warm", run, round(ms, 3))
                                for run, ms in enumerate(timings, start=1)])
                    append_csv(output / "summary.csv",
                               ["model", "config", "query", "median_ms", "min_ms", "max_ms", "rows", "answer",
                                "timed_out"],
                               [(model_name, config_name, query,
                                 round(median_ms, 3) if median_ms is not None else "",
                                 round(min(timings), 3) if timings else "",
                                 round(max(timings), 3) if timings else "",
                                 len(rows) if rows is not None else "", answer, timed_out)])
                    shown = f"{median_ms:9.1f} ms" if median_ms is not None else "  TIMEOUT  "
                    print(f"    {query} {shown}  rows={len(rows) if rows is not None else '-'}  answer={answer}",
                          flush=True)


def run_prepare(database_name, model_name, config_name):
    with psycopg.connect(database_url_for(database_name)) as connection:
        prepare_database(connection)
        config_name = models[model_name]["best"] if config_name == "best" else config_name
        build_s, _, _ = set_index_config(connection, model_name, config_name)
        connection.commit()
        print(f"{database_name} {model_name} [{config_name}] ready ({build_s:.1f} s)")


def run_cold(database_name, label, model_name, config_name, query):
    output = results_folder / label
    config_name = models[model_name]["best"] if config_name == "best" else config_name
    with psycopg.connect(database_url_for(database_name)) as connection:
        parameters = resolve_parameters(connection)
        connection.rollback()
        connection.execute(f"SET statement_timeout = '{statement_timeout_s}s'")
        elapsed_ms, rows = run_query(connection, sql_for(model_name, query), parameters)
    append_csv(output / "cold.csv", ["model", "config", "query", "ms", "rows", "timed_out"],
               [(model_name, config_name, query, round(elapsed_ms, 3) if elapsed_ms is not None else "",
                 len(rows) if rows is not None else "", elapsed_ms is None)])
    shown = f"{elapsed_ms:9.1f} ms" if elapsed_ms is not None else "  TIMEOUT  "
    print(f"{label} cold {model_name} [{config_name}] {query} {shown}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["warm", "prepare", "cold", "complexity"])
    parser.add_argument("--database", default="trains_1x")
    parser.add_argument("--label", help="results subfolder (default: database name)")
    parser.add_argument("--model", action="append", choices=list(models))
    parser.add_argument("--query", action="append", choices=queries)
    parser.add_argument("--config", action="append", help="index config name, or 'best'")
    args = parser.parse_args()
    label = args.label or args.database

    if args.mode == "complexity":
        write_sql_complexity()
    elif args.mode == "warm":
        run_warm(args.database, label, args.model or list(models), args.query or queries, args.config)
    elif args.mode == "prepare":
        run_prepare(args.database, args.model[0], (args.config or ["best"])[0])
    elif args.mode == "cold":
        run_cold(args.database, label, args.model[0], (args.config or ["best"])[0], args.query[0])


if __name__ == "__main__":
    main()
