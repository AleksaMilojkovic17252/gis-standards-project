import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import psycopg

database_url = os.environ["DATABASE_URL"]
metadata_file = Path("/data/raw/geosphere/klima-v2-10min.metadata.json")
output_file = Path("/data/processed/selected_weather_stations.json")
stations_url = "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min"
required_parameters = ["tl", "rf", "p", "ff", "rr", "cglo"]
min_share_of_values = 0.9

period_start = "2026-11-04"
period_end = "2026-11-14"
max_distance_to_track_m = 10_000
max_station_altitude_m = 1_400
number_of_section_stations = 12


def load_candidate_stations():
    metadata = json.loads(metadata_file.read_text())
    stations_by_location = {}
    for station in metadata["stations"]:
        valid_for_period = station["valid_from"][:10] <= period_start and station["valid_to"][:10] >= period_end
        low_enough = station["altitude"] <= max_station_altitude_m
        if not (station["is_active"] and valid_for_period and station["has_global_radiation"] and low_enough):
            continue
        location_key = (round(station["lat"], 3), round(station["lon"], 3))
        known_station = stations_by_location.get(location_key)
        if known_station is None or int(station["id"]) < int(known_station["id"]):
            stations_by_location[location_key] = station
    return list(stations_by_location.values())


def measure_distance_to_lines(connection, stations):
    connection.execute("CREATE TEMP TABLE candidate (id int, name text, altitude double precision, geom geometry(Point, 3416))")
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO candidate VALUES (%s, %s, %s, ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 3416))",
            [(int(s["id"]), s["name"], s["altitude"], s["lon"], s["lat"]) for s in stations],
        )
    rows = connection.execute("""
        SELECT c.id, c.name, c.altitude, ST_X(c.geom), ST_Y(c.geom), ST_Y(ST_Transform(c.geom, 4326)),
               ST_X(ST_Transform(c.geom, 4326)), nearest.line_id, nearest.distance_m, nearest.along_m
        FROM candidate AS c
        CROSS JOIN LATERAL (
            SELECT l.line_id, ST_Distance(l.geom, c.geom) AS distance_m,
                   ST_LineLocatePoint(l.geom, c.geom) * l.length_m AS along_m
            FROM rail.lines AS l
            ORDER BY l.geom <-> c.geom
            LIMIT 1
        ) AS nearest
        WHERE nearest.distance_m <= %s
        ORDER BY nearest.distance_m
    """, (max_distance_to_track_m,)).fetchall()
    keys = ["id", "name", "altitude_m", "x", "y", "lat", "lon", "line_id", "distance_to_track_m", "distance_along_line_m"]
    return [dict(zip(keys, row)) for row in rows]


def keep_stations_with_required_parameters(stations):
    query = {
        "parameters": ",".join(required_parameters),
        "station_ids": ",".join(str(station["id"]) for station in stations),
        "start": f"{period_start}T00:00",
        "end": f"{period_start}T23:50",
        "output_format": "geojson",
    }
    with urlopen(f"{stations_url}?{urlencode(query)}", timeout=120) as response:
        sample = json.load(response)
    complete_station_ids = set()
    for feature in sample["features"]:
        parameters = feature["properties"]["parameters"]
        has_all = all(
            sum(value is not None for value in parameters[name]["data"]) >= min_share_of_values * len(parameters[name]["data"])
            for name in required_parameters
        )
        if has_all:
            complete_station_ids.add(int(feature["properties"]["station"]))
    return [station for station in stations if station["id"] in complete_station_ids]


def pick_terminal_stations(connection, stations_near_track):
    terminal_points = connection.execute("""
        SELECT DISTINCT ST_X(point), ST_Y(point)
        FROM rail.lines, LATERAL (VALUES (ST_StartPoint(geom)), (ST_EndPoint(geom))) AS ends(point)
    """).fetchall()
    return [min(stations_near_track, key=lambda s: math.hypot(s["x"] - x, s["y"] - y)) for x, y in terminal_points]


def pick_one_station_per_section(connection, stations_near_track):
    line_lengths_m = dict(connection.execute("SELECT line_id, length_m FROM rail.lines").fetchall())
    total_length_m = sum(line_lengths_m.values())
    selected = []
    for line_id, line_length_m in line_lengths_m.items():
        number_of_sections = max(1, round(number_of_section_stations * line_length_m / total_length_m))
        section_length_m = line_length_m / number_of_sections
        for section_index in range(number_of_sections):
            section_start_m = section_index * section_length_m
            section_end_m = section_start_m + section_length_m
            stations_in_section = [s for s in stations_near_track if s["line_id"] == line_id
                                   and section_start_m <= s["distance_along_line_m"] <= section_end_m]
            if stations_in_section:
                selected.append(min(stations_in_section, key=lambda s: s["distance_to_track_m"]))
    return selected


def pick_stations(connection, stations_near_track):
    selected_by_id = {}
    for station in pick_terminal_stations(connection, stations_near_track) + \
            pick_one_station_per_section(connection, stations_near_track):
        selected_by_id[station["id"]] = station
    return sorted(selected_by_id.values(), key=lambda s: (s["line_id"], s["distance_along_line_m"]))


def main():
    candidates = load_candidate_stations()
    with psycopg.connect(database_url) as connection:
        stations_near_track = measure_distance_to_lines(connection, candidates)
        stations_near_track = keep_stations_with_required_parameters(stations_near_track)
        selected = pick_stations(connection, stations_near_track)

    print(f"{len(candidates)} active stations with radiation below {max_station_altitude_m} m, {len(stations_near_track)} within "
          f"{max_distance_to_track_m / 1000:.0f} km of a line with all of {required_parameters}, {len(selected)} selected:\n")
    for station in selected:
        print(f"  {station['id']:>6}  {station['name']:<36} {station['line_id']:<20}"
              f" {station['distance_along_line_m'] / 1000:6.1f} km along, {station['distance_to_track_m'] / 1000:4.1f} km off track,"
              f" {station['altitude_m']:6.0f} m")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(
        [{key: station[key] for key in ("id", "name", "lat", "lon", "altitude_m", "line_id",
                                         "distance_to_track_m", "distance_along_line_m")} for station in selected],
        indent=2, ensure_ascii=False))
    print(f"\nSaved {output_file}")


if __name__ == "__main__":
    main()
