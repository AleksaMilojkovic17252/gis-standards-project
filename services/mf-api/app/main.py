import json
import os
from datetime import datetime, timezone
from functools import lru_cache

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8090/mf").rstrip("/")
DATABASE_URL = os.environ["DATABASE_URL"]

COLLECTIONS = {
    "trains": {
        "table": "mdb.trips",
        "title": "Trains (full trajectories)",
        "description": "Simulated train trips on four Austrian rail lines, 4-13 Nov 2026. "
                       "Sampled at about 1 s with jitter, dropouts and ~3 m GPS noise. SIMULATED data.",
    },
    "trains-simplified": {
        "table": "mdb.trips_simplified",
        "title": "Trains (simplified trajectories)",
        "description": "The same trips simplified with Douglas-Peucker (10 m). Smaller responses, "
                       "intended for map display. SIMULATED data.",
    },
}

CRS84 = {"type": "Name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
TRS = {"type": "Link", "properties": {"type": "OGCDEF", "href": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"}}
CONFORMANCE = [
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections",
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/common",
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/mf-collection",
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/movingfeatures",
]
MAX_LIMIT = 1000

app = FastAPI(
    title="OGC API - Moving Features (trains in Austria)",
    version="0.2.0",
    description="Partial implementation of OGC API - Moving Features Part 1 (read-only) on MobilityDB. "
                "Train data is simulated.",
)


def link(href, rel, type_="application/json", title=None):
    out = {"href": f"{BASE_URL}{href}", "rel": rel, "type": type_}
    if title:
        out["title"] = title
    return out


def query(sql, params=()):
    with psycopg.connect(DATABASE_URL) as connection:
        return connection.execute(sql, params).fetchall()


def collection_or_404(collection_id):
    if collection_id not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
    return COLLECTIONS[collection_id]


def parse_instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_datetime(datetime_):
    if not datetime_:
        return None
    try:
        if "/" in datetime_:
            start, end = datetime_.split("/", 1)
            return (None if start in ("", "..") else parse_instant(start),
                    None if end in ("", "..") else parse_instant(end))
        instant = parse_instant(datetime_)
        return instant, instant
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Invalid datetime '{datetime_}': {error}") from error


def time_span_sql(span):
    start, end = span
    lower = start.isoformat() if start else "-infinity"
    upper = end.isoformat() if end else "infinity"
    return f"[{lower}, {upper}]"


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=None)
def collection_extent(table):
    (box, start, end), = query(f"""
        SELECT ST_AsGeoJSON(ST_Transform(extent(trip)::geometry, 4326)), Tmin(extent(trip)), Tmax(extent(trip))
        FROM {table}
    """)
    coordinates = json.loads(box)["coordinates"][0]
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return [min(xs), min(ys), max(xs), max(ys)], [iso(start), iso(end)]


def collection_document(collection_id):
    collection = COLLECTIONS[collection_id]
    bbox, interval = collection_extent(collection["table"])
    return {
        "id": collection_id,
        "title": collection["title"],
        "description": collection["description"],
        "itemType": "movingfeature",
        "updateFrequency": 0,
        "extent": {
            "spatial": {"bbox": [bbox], "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            "temporal": {"interval": [interval], "trs": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"},
        },
        "links": [
            link(f"/collections/{collection_id}", "self"),
            link(f"/collections/{collection_id}/items", "items", "application/geo+json"),
        ],
    }


def moving_feature(collection_id, row):
    trip_id, train_id, line_id, start, end, box = row
    coordinates = json.loads(box)["coordinates"][0]
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    base = f"/collections/{collection_id}/items/{trip_id}"
    return {
        "type": "Feature",
        "id": str(trip_id),
        "properties": {"train_id": train_id, "line_id": line_id, "simulated": True},
        "crs": CRS84,
        "trs": TRS,
        "time": [iso(start), iso(end)],
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "links": [
            link(base, "self", "application/geo+json"),
            link(f"{base}/tgsequence", "related", title="Temporal geometry sequence"),
        ],
    }


FEATURE_COLUMNS = """
    trip_id, train_id, line_id, startTimestamp(trip), endTimestamp(trip),
    ST_AsGeoJSON(ST_Transform(stbox(trip)::geometry, 4326))
"""


@app.get("/")
def landing_page():
    return {
        "title": app.title,
        "description": app.description,
        "links": [
            link("/", "self", title="This document"),
            link("/openapi.json", "service-desc", "application/vnd.oai.openapi+json;version=3.0"),
            link("/docs", "service-doc", "text/html"),
            link("/conformance", "conformance"),
            link("/collections", "data"),
        ],
    }


@app.get("/conformance")
def conformance():
    return {"conformsTo": CONFORMANCE}


@app.get("/collections")
def collections():
    return {
        "collections": [collection_document(collection_id) for collection_id in COLLECTIONS],
        "links": [link("/collections", "self")],
    }


@app.get("/collections/{collection_id}")
def collection(collection_id: str):
    collection_or_404(collection_id)
    return collection_document(collection_id)


@app.get("/collections/{collection_id}/items")
def items(
    collection_id: str,
    limit: int = Query(10, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat (CRS84)"),
    datetime_: str | None = Query(None, alias="datetime"),
):
    table = collection_or_404(collection_id)["table"]
    conditions = []
    params = []
    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = [float(value) for value in bbox.split(",")]
        except ValueError as error:
            raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat") from error
        conditions.append("eIntersects(trip, ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 3416))")
        params += [min_lon, min_lat, max_lon, max_lat]
    span = parse_datetime(datetime_)
    if span:
        conditions.append("trip && %s::tstzspan")
        params.append(time_span_sql(span))
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    (number_matched,), = query(f"SELECT count(*) FROM {table} {where}", params)
    rows = query(f"SELECT {FEATURE_COLUMNS} FROM {table} {where} ORDER BY trip_id LIMIT %s OFFSET %s",
                 params + [limit, offset])
    features = [moving_feature(collection_id, row) for row in rows]
    links = [link(f"/collections/{collection_id}/items?limit={limit}&offset={offset}", "self",
                  "application/geo+json")]
    if offset + limit < number_matched:
        links.append(link(f"/collections/{collection_id}/items?limit={limit}&offset={offset + limit}", "next",
                          "application/geo+json"))
    return JSONResponse({
        "type": "FeatureCollection",
        "features": features,
        "crs": CRS84,
        "trs": TRS,
        "links": links,
        "timeStamp": iso(datetime.now(timezone.utc)),
        "numberMatched": number_matched,
        "numberReturned": len(features),
    }, media_type="application/geo+json")


@app.get("/collections/{collection_id}/items/{feature_id}")
def item(collection_id: str, feature_id: int):
    table = collection_or_404(collection_id)["table"]
    rows = query(f"SELECT {FEATURE_COLUMNS} FROM {table} WHERE trip_id = %s", (feature_id,))
    if not rows:
        raise HTTPException(status_code=404, detail=f"Moving feature {feature_id} not found")
    return JSONResponse(moving_feature(collection_id, rows[0]), media_type="application/geo+json")


def temporal_trip_sql(datetime_, leaf):
    expression = "transform(trip, 4326)"
    params = []
    if leaf:
        try:
            instants = [parse_instant(value) for value in leaf.split(",")]
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Invalid leaf: {error}") from error
        expression = f"atTime({expression}, %s::tstzset)"
        params.append("{" + ", ".join(instant.isoformat() for instant in instants) + "}")
    else:
        span = parse_datetime(datetime_)
        if span:
            expression = f"atTime({expression}, %s::tstzspan)"
            params.append(time_span_sql(span))
    return expression, params


def to_moving_point(mfjson_text, interpolation_override=None):
    mfjson = json.loads(mfjson_text)
    sequences = mfjson.get("sequences") or [mfjson]
    coordinates = []
    datetimes = []
    for sequence in sequences:
        coordinates += [[round(x, 6), round(y, 6)] for x, y, *_ in sequence["coordinates"]]
        datetimes += [value.replace("+00", "Z") if value.endswith("+00") else value for value in sequence["datetimes"]]
    return {
        "id": "1",
        "type": "MovingPoint",
        "datetimes": datetimes,
        "coordinates": coordinates,
        "interpolation": interpolation_override or mfjson.get("interpolation", "Linear"),
        "crs": CRS84,
        "trs": TRS,
    }


@app.get("/collections/{collection_id}/items/{feature_id}/tgsequence")
def tgsequence(
    collection_id: str,
    feature_id: int,
    datetime_: str | None = Query(None, alias="datetime"),
    leaf: str | None = Query(None, description="Comma-separated instants; returns the positions at these times"),
):
    table = collection_or_404(collection_id)["table"]
    expression, params = temporal_trip_sql(datetime_, leaf)
    rows = query(f"SELECT asMFJSON({expression}, 0, 0, 6) FROM {table} WHERE trip_id = %s", params + [feature_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Moving feature {feature_id} not found")
    mfjson_text = rows[0][0]
    geometry_sequence = [] if mfjson_text is None else [
        to_moving_point(mfjson_text, "Discrete" if leaf else None)]
    base = f"/collections/{collection_id}/items/{feature_id}/tgsequence"
    return {
        "type": "TemporalGeometrySequence",
        "geometrySequence": geometry_sequence,
        "links": [link(base, "self"), link(f"{base}/1/velocity", "related", title="Velocity of tGeometry 1")],
        "timeStamp": iso(datetime.now(timezone.utc)),
        "numberMatched": len(geometry_sequence),
        "numberReturned": len(geometry_sequence),
    }


@app.get("/collections/{collection_id}/items/{feature_id}/tgsequence/{tgeometry_id}/velocity")
def velocity(
    collection_id: str,
    feature_id: int,
    tgeometry_id: str,
    datetime_: str | None = Query(None, alias="datetime"),
    leaf: str | None = Query(None),
):
    table = collection_or_404(collection_id)["table"]
    if tgeometry_id != "1":
        raise HTTPException(status_code=404, detail=f"Temporal geometry {tgeometry_id} not found")
    speed_expression = "speed(trip)"
    params = []
    if leaf:
        instants = [parse_instant(value) for value in leaf.split(",")]
        speed_expression = f"atTime({speed_expression}, %s::tstzset)"
        params.append("{" + ", ".join(instant.isoformat() for instant in instants) + "}")
    else:
        span = parse_datetime(datetime_)
        if span:
            speed_expression = f"atTime({speed_expression}, %s::tstzspan)"
            params.append(time_span_sql(span))
    rows = query(f"SELECT asMFJSON({speed_expression}, 0, 0, 3) FROM {table} WHERE trip_id = %s",
                 params + [feature_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Moving feature {feature_id} not found")
    value_sequence = []
    if rows[0][0] is not None:
        mfjson = json.loads(rows[0][0])
        for sequence in mfjson.get("sequences") or [mfjson]:
            value_sequence.append({
                "datetimes": [value.replace("+00", "Z") if value.endswith("+00") else value
                              for value in sequence["datetimes"]],
                "values": sequence["values"],
                "interpolation": "Discrete" if leaf else mfjson.get("interpolation", "Step"),
            })
    return {
        "name": "velocity",
        "type": "TReal",
        "form": "m/s",
        "valueSequence": value_sequence,
        "links": [link(f"/collections/{collection_id}/items/{feature_id}/tgsequence/{tgeometry_id}/velocity", "self")],
    }


@app.get("/health")
def health():
    try:
        (version,), = query("SELECT mobilitydb_version()")
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    return {"status": "ok", "mobilitydb": version}
