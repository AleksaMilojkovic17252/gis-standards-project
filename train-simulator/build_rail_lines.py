import difflib
import math
import os
import re
import sys

import networkx as nx
import psycopg
from shapely import LineString, Point, STRtree, from_wkb, to_wkb

database_url = os.environ["DATABASE_URL"]

default_maxspeed_kmh = 160
service_track_penalty = 10
max_snap_distance_m = 500

lines = {
    "westbahn": (
        "Westbahn: Wien - Salzburg",
        ["Wien Hauptbahnhof", "Wien Meidling", "Tullnerfeld", "St. Pölten Hauptbahnhof", "Amstetten",
         "Linz Hauptbahnhof", "Wels Hauptbahnhof", "Attnang-Puchheim", "Vöcklabruck", "Salzburg Hauptbahnhof"],
    ),
    "suedbahn": (
        "Südbahn: Wien - Graz",
        ["Wien Hauptbahnhof", "Wien Meidling", "Baden", "Wiener Neustadt Hauptbahnhof", "Gloggnitz",
         "Semmering", "Mürzzuschlag", "Kapfenberg", "Bruck an der Mur", "Graz Hauptbahnhof"],
    ),
    "salzburg-innsbruck": (
        "Salzburg - Innsbruck (via Zell am See)",
        ["Salzburg Hauptbahnhof", "Hallein", "Bischofshofen", "St. Johann im Pongau", "Schwarzach-St. Veit",
         "Zell am See", "Saalfelden", "St. Johann in Tirol", "Kitzbühel", "Wörgl Hauptbahnhof", "Jenbach",
         "Innsbruck Hauptbahnhof"],
    ),
    "arlbergbahn": (
        "Arlbergbahn: Innsbruck - Bregenz",
        ["Innsbruck Hauptbahnhof", "Ötztal", "Imst-Pitztal", "Landeck-Zams", "St. Anton am Arlberg",
         "Langen am Arlberg", "Bludenz", "Feldkirch", "Dornbirn", "Bregenz"],
    ),
}


def parse_speed_kmh(value):
    if not value:
        return None
    match = re.match(r"\s*(\d+(?:\.\d+)?)\s*(mph)?", value)
    if not match:
        return None
    speed = float(match.group(1))
    return speed * 1.609344 if match.group(2) else speed


def way_maxspeed_kmh(maxspeed, maxspeed_forward, maxspeed_backward):
    speed = parse_speed_kmh(maxspeed)
    if speed is not None:
        return speed
    directional_speeds = [parse_speed_kmh(value) for value in (maxspeed_forward, maxspeed_backward)]
    directional_speeds = [speed for speed in directional_speeds if speed]
    return min(directional_speeds) if directional_speeds else None


def normalize_name(name):
    return re.sub(r"\s+", " ", name.replace("–", "-")).strip().lower()


def read_rail_ways(connection):
    rows = connection.execute("""
        SELECT way_id, node_ids, maxspeed, maxspeed_forward, maxspeed_backward, service IS NOT NULL,
               ST_AsBinary(ST_Transform(geom, 3416))
        FROM rail.osm_rail_ways
    """).fetchall()
    rail_ways = []
    for way_id, node_ids, maxspeed, maxspeed_forward, maxspeed_backward, is_service_track, geometry_wkb in rows:
        coordinates = list(from_wkb(geometry_wkb).coords)
        if len(coordinates) != len(node_ids):
            continue
        rail_ways.append({
            "way_id": way_id,
            "node_ids": node_ids,
            "coordinates": coordinates,
            "maxspeed_kmh": way_maxspeed_kmh(maxspeed, maxspeed_forward, maxspeed_backward),
            "is_service_track": is_service_track,
        })
    return rail_ways


def read_stations(connection):
    rows = connection.execute("""
        SELECT node_id, name, railway, ST_X(geom_3416), ST_Y(geom_3416)
        FROM (SELECT node_id, name, railway, ST_Transform(geom, 3416) AS geom_3416 FROM rail.osm_stations) AS s
    """).fetchall()
    return [{"osm_id": osm_id, "name": name, "railway": railway, "x": x, "y": y}
            for osm_id, name, railway, x, y in rows]


def build_graph(rail_ways):
    graph = nx.Graph()
    node_xy = {}
    mainline_node_ids = set()
    for way in rail_ways:
        for node_id, xy in zip(way["node_ids"], way["coordinates"]):
            node_xy[node_id] = xy
            if not way["is_service_track"]:
                mainline_node_ids.add(node_id)
        for index in range(len(way["node_ids"]) - 1):
            start_node, end_node = way["node_ids"][index], way["node_ids"][index + 1]
            (start_x, start_y), (end_x, end_y) = way["coordinates"][index], way["coordinates"][index + 1]
            length_m = math.hypot(end_x - start_x, end_y - start_y)
            weight = length_m * (service_track_penalty if way["is_service_track"] else 1)
            if graph.has_edge(start_node, end_node) and graph[start_node][end_node]["weight"] <= weight:
                continue
            graph.add_edge(start_node, end_node, length_m=length_m, weight=weight,
                           maxspeed_kmh=way["maxspeed_kmh"], way_id=way["way_id"])
    return graph, node_xy, mainline_node_ids


def find_station(stop_name, stations_by_name, all_station_names, previous_station):
    candidates = stations_by_name.get(normalize_name(stop_name), [])
    if not candidates:
        suggestions = difflib.get_close_matches(stop_name, all_station_names, n=5, cutoff=0.6)
        sys.exit(f"Station '{stop_name}' not found in OSM. Close matches: {suggestions}")
    if previous_station is None:
        return sorted(candidates, key=lambda station: station["railway"] != "station")[0]
    return min(candidates, key=lambda station: math.hypot(station["x"] - previous_station["x"],
                                                           station["y"] - previous_station["y"]))


def snap_to_track(station, mainline_tree, mainline_node_list):
    indices, distances = mainline_tree.query_nearest(Point(station["x"], station["y"]),
                                                     max_distance=max_snap_distance_m, return_distance=True)
    if len(indices) == 0:
        sys.exit(f"Station '{station['name']}' is more than {max_snap_distance_m} m from any main track")
    return mainline_node_list[indices[0]], float(distances[0])


def build_line(stop_names, stations_by_name, all_station_names, graph, node_xy, mainline_tree, mainline_node_list):
    stops = []
    previous_station = None
    for stop_name in stop_names:
        station = find_station(stop_name, stations_by_name, all_station_names, previous_station)
        track_node, snap_distance_m = snap_to_track(station, mainline_tree, mainline_node_list)
        stops.append({"station": station, "track_node": track_node, "snap_distance_m": snap_distance_m})
        previous_station = station

    path_nodes = [stops[0]["track_node"]]
    stops[0]["path_index"] = 0
    for previous_stop, next_stop in zip(stops, stops[1:]):
        try:
            leg = nx.shortest_path(graph, previous_stop["track_node"], next_stop["track_node"], weight="weight")
        except nx.NetworkXNoPath:
            sys.exit(f"No rail path between {previous_stop['station']['name']} and {next_stop['station']['name']}")
        path_nodes.extend(leg[1:])
        next_stop["path_index"] = len(path_nodes) - 1

    distance_along_m = [0.0]
    for start_node, end_node in zip(path_nodes, path_nodes[1:]):
        distance_along_m.append(distance_along_m[-1] + graph[start_node][end_node]["length_m"])
    for stop in stops:
        stop["distance_along_m"] = distance_along_m[stop["path_index"]]

    segments = []
    for index, (start_node, end_node) in enumerate(zip(path_nodes, path_nodes[1:])):
        osm_speed = graph[start_node][end_node]["maxspeed_kmh"]
        speed = osm_speed if osm_speed else default_maxspeed_kmh
        source = "osm" if osm_speed else "default"
        if segments and segments[-1]["maxspeed_kmh"] == speed and segments[-1]["source"] == source:
            segments[-1]["end_index"] = index + 1
        else:
            segments.append({"start_index": index, "end_index": index + 1, "maxspeed_kmh": speed, "source": source})
    for segment in segments:
        segment["from_m"] = distance_along_m[segment["start_index"]]
        segment["to_m"] = distance_along_m[segment["end_index"]]
        segment_nodes = path_nodes[segment["start_index"]:segment["end_index"] + 1]
        segment["geometry"] = LineString([node_xy[node] for node in segment_nodes])

    line_geometry = LineString([node_xy[node] for node in path_nodes])
    return line_geometry, stops, segments


def write_lines(connection, built_lines):
    connection.execute("""
        DROP TABLE IF EXISTS rail.line_segments, rail.line_stops, rail.lines, rail.stations CASCADE;
        CREATE TABLE rail.stations AS
            SELECT node_id AS osm_id, name, railway, uic_ref, ST_Transform(geom, 3416)::geometry(Point, 3416) AS geom
            FROM rail.osm_stations;
        ALTER TABLE rail.stations ADD PRIMARY KEY (osm_id);
        CREATE TABLE rail.lines (
            line_id text PRIMARY KEY,
            name text NOT NULL,
            from_station text NOT NULL,
            to_station text NOT NULL,
            length_m double precision NOT NULL,
            geom geometry(LineString, 3416) NOT NULL
        );
        CREATE TABLE rail.line_stops (
            line_id text REFERENCES rail.lines,
            stop_sequence integer,
            osm_id bigint REFERENCES rail.stations,
            name text NOT NULL,
            distance_along_m double precision NOT NULL,
            PRIMARY KEY (line_id, stop_sequence)
        );
        CREATE TABLE rail.line_segments (
            line_id text REFERENCES rail.lines,
            segment_sequence integer,
            from_m double precision NOT NULL,
            to_m double precision NOT NULL,
            maxspeed_kmh double precision NOT NULL,
            maxspeed_source text NOT NULL,
            geom geometry(LineString, 3416) NOT NULL,
            PRIMARY KEY (line_id, segment_sequence)
        );
    """)
    with connection.cursor() as cursor:
        for line_id, (line_name, line_geometry, stops, segments) in built_lines.items():
            cursor.execute(
                "INSERT INTO rail.lines VALUES (%s, %s, %s, %s, %s, ST_GeomFromWKB(%s, 3416))",
                (line_id, line_name, stops[0]["station"]["name"], stops[-1]["station"]["name"],
                 line_geometry.length, to_wkb(line_geometry)),
            )
            cursor.executemany(
                "INSERT INTO rail.line_stops VALUES (%s, %s, %s, %s, %s)",
                [(line_id, sequence, stop["station"]["osm_id"], stop["station"]["name"], stop["distance_along_m"])
                 for sequence, stop in enumerate(stops, start=1)],
            )
            cursor.executemany(
                "INSERT INTO rail.line_segments VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromWKB(%s, 3416))",
                [(line_id, sequence, segment["from_m"], segment["to_m"], segment["maxspeed_kmh"],
                  segment["source"], to_wkb(segment["geometry"]))
                 for sequence, segment in enumerate(segments, start=1)],
            )
    connection.execute("""
        CREATE INDEX ON rail.stations USING gist (geom);
        CREATE INDEX ON rail.lines USING gist (geom);
        CREATE INDEX ON rail.line_segments USING gist (geom);
        ANALYZE rail.stations, rail.lines, rail.line_stops, rail.line_segments;
        CREATE VIEW rail.lines_crs84 AS
            SELECT line_id, name, from_station, to_station, length_m,
                   ST_Transform(geom, 4326)::geometry(LineString, 4326) AS geom
            FROM rail.lines;
        CREATE VIEW rail.stations_crs84 AS
            SELECT osm_id, name, railway, uic_ref, ST_Transform(geom, 4326)::geometry(Point, 4326) AS geom
            FROM rail.stations;
    """)


def main():
    with psycopg.connect(database_url) as connection:
        rail_ways = read_rail_ways(connection)
        stations = read_stations(connection)
        print(f"{len(rail_ways)} rail ways, {len(stations)} named stations/halts")

        graph, node_xy, mainline_node_ids = build_graph(rail_ways)
        print(f"graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

        mainline_node_list = list(mainline_node_ids)
        mainline_tree = STRtree([Point(node_xy[node]) for node in mainline_node_list])

        stations_by_name = {}
        for station in stations:
            stations_by_name.setdefault(normalize_name(station["name"]), []).append(station)
        all_station_names = sorted({station["name"] for station in stations})

        built_lines = {}
        for line_id, (line_name, stop_names) in lines.items():
            line_geometry, stops, segments = build_line(stop_names, stations_by_name, all_station_names, graph,
                                                        node_xy, mainline_tree, mainline_node_list)
            built_lines[line_id] = (line_name, line_geometry, stops, segments)
            default_speed_km = sum(s["to_m"] - s["from_m"] for s in segments if s["source"] == "default") / 1000
            print(f"\n{line_name}: {line_geometry.length / 1000:.1f} km, {len(segments)} speed segments, "
                  f"{default_speed_km:.1f} km without maxspeed")
            for stop in stops:
                print(f"  {stop['distance_along_m'] / 1000:7.1f} km  {stop['station']['name']:<32}"
                      f" (osm {stop['station']['osm_id']}, snapped {stop['snap_distance_m']:.0f} m)")

        write_lines(connection, built_lines)
    print("\nWrote rail.stations, rail.lines, rail.line_stops, rail.line_segments")


if __name__ == "__main__":
    main()
