import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import soil_model

frost_url = os.environ.get("FROST_URL", "http://frost:8080/FROST-Server/v1.1").rstrip("/")
stations_file = Path("/data/processed/selected_weather_stations.json")
observations_folder = Path("/data/raw/geosphere/klima-v2-10min")

cf_vocabulary = "http://vocab.nerc.ac.uk/standard_name/"
ucum = "http://unitsofmeasure.org/ucum.html"
measurement_type = "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement"
category_type = "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_CategoryObservation"

observed_properties = {
    "air_temperature": ("Air temperature", cf_vocabulary + "air_temperature/",
                        "Air temperature 2 m above ground"),
    "relative_humidity": ("Relative humidity", cf_vocabulary + "relative_humidity/",
                          "Relative humidity 2 m above ground"),
    "air_pressure": ("Air pressure", cf_vocabulary + "air_pressure/",
                     "Air pressure at station level"),
    "wind_speed": ("Wind speed", cf_vocabulary + "wind_speed/",
                   "Mean wind speed over 10 minutes"),
    "precipitation_amount": ("Precipitation", cf_vocabulary + "precipitation_amount/",
                             "Precipitation sum over the 10 minutes before the timestamp"),
    "global_radiation": ("Global radiation", cf_vocabulary + "surface_downwelling_shortwave_flux_in_air/",
                         "Mean global (shortwave) radiation over 10 minutes"),
    "soil_temperature": ("Soil temperature at 10 cm", cf_vocabulary + "soil_temperature/",
                         "Soil temperature 10 cm below ground"),
    "soil_moisture": ("Soil moisture", cf_vocabulary + "volume_fraction_of_condensed_water_in_soil/",
                      "Volumetric soil water content of the root zone (0-30 cm)"),
    "soil_state": ("Soil state", "urn:ogc-api-research-sandbox:soil-state",
                   "Soil state class derived from soil moisture: dry < 20 %, moist < 32 %, wet < 40 %, "
                   "waterlogged >= 40 %"),
}

measured_datastreams = [
    ("tl", "air_temperature", ("degree Celsius", "°C", "Cel")),
    ("rf", "relative_humidity", ("percent", "%", "%")),
    ("p", "air_pressure", ("hectopascal", "hPa", "hPa")),
    ("ff", "wind_speed", ("metre per second", "m/s", "m/s")),
    ("rr", "precipitation_amount", ("millimetre", "mm", "mm")),
    ("cglo", "global_radiation", ("watt per square metre", "W/m²", "W/m2")),
]


class FrostError(Exception):
    pass


def request(method, path_or_url, body=None):
    url = path_or_url if path_or_url.startswith("http") else f"{frost_url}/{path_or_url}"
    data = json.dumps(body).encode() if body is not None else None
    http_request = urllib.request.Request(url, data=data, method=method,
                                          headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(http_request, timeout=300) as response:
            content = response.read()
            location = response.headers.get("Location")
            return (json.loads(content) if content else None), location
    except urllib.error.HTTPError as error:
        raise FrostError(f"{method} {url} -> HTTP {error.code}: {error.read()[:500].decode(errors='replace')}")


def create(entity_set, entity):
    _, location = request("POST", entity_set, entity)
    return int(re.search(r"\((\d+)\)$", location).group(1))


def delete_all(entity_set):
    deleted = 0
    while True:
        page, _ = request("GET", f"{entity_set}?$select=id&$top=1000")
        if not page["value"]:
            return deleted
        for entity in page["value"]:
            request("DELETE", f"{entity_set}({entity['@iot.id']})")
            deleted += 1


def read_station_series(station_id):
    timestamps = []
    series = {}
    for observation_file in sorted(observations_folder.glob(f"{station_id}_*.geojson")):
        chunk = json.loads(observation_file.read_text())
        parameters = chunk["features"][0]["properties"]["parameters"]
        timestamps += chunk["timestamps"]
        for name, parameter in parameters.items():
            series.setdefault(name, []).extend(parameter["data"])
    if not timestamps:
        raise FileNotFoundError(f"No observation files for station {station_id} in {observations_folder}")
    timestamps = [timestamp.replace("+00:00", "Z") for timestamp in timestamps]
    return timestamps, series


def create_sensors():
    tawes_sensor = create("Sensors", {
        "name": "GeoSphere TAWES station",
        "description": "Automatic weather station (TAWES) of GeoSphere Austria, 10-minute values",
        "encodingType": "text/html",
        "metadata": "https://data.hub.geosphere.at/dataset/klima-v2-10min",
        "properties": {"simulated": False, "operator": "GeoSphere Austria", "licence": "CC BY 4.0"},
    })
    simulated_sensor = create("Sensors", {
        "name": "Simulated soil probe v1",
        "description": "Simulated soil probe: bucket model for soil moisture driven by measured precipitation, "
                       "temperature and radiation (Makkink evapotranspiration), and a damped copy of air "
                       "temperature for soil temperature where no measurement exists",
        "encodingType": "text/plain",
        "metadata": "See sta-loader/soil_model.py in the research sandbox repository",
        "properties": {"simulated": True},
    })
    return tawes_sensor, simulated_sensor


def create_observed_properties():
    return {key: create("ObservedProperties", {"name": name, "definition": definition, "description": description})
            for key, (name, definition, description) in observed_properties.items()}


def create_station(station):
    thing_id = create("Things", {
        "name": station["name"],
        "description": f"GeoSphere Austria weather station {station['name']} near the {station['line_id']} line",
        "properties": {
            "geosphere_station_id": station["id"],
            "altitude_m": station["altitude_m"],
            "line_id": station["line_id"],
            "distance_to_track_m": round(station["distance_to_track_m"], 1),
            "source": "GeoSphere Austria Data Hub, klima-v2-10min",
            "licence": "CC BY 4.0",
        },
        "Locations": [{
            "name": station["name"],
            "description": f"Location of weather station {station['name']}",
            "encodingType": "application/geo+json",
            "location": {"type": "Point", "coordinates": [station["lon"], station["lat"]]},
        }],
    })
    feature_id = create("FeaturesOfInterest", {
        "name": f"Atmosphere and soil at {station['name']}",
        "description": f"Air and soil at weather station {station['name']}",
        "encodingType": "application/geo+json",
        "feature": {"type": "Point", "coordinates": [station["lon"], station["lat"]]},
    })
    return thing_id, feature_id


def create_datastream(thing_id, sensor_id, observed_property_id, name, description, unit, simulated,
                      observation_type=measurement_type):
    unit_name, unit_symbol, ucum_code = unit
    return create("Datastreams", {
        "name": name,
        "description": description,
        "observationType": observation_type,
        "unitOfMeasurement": {"name": unit_name, "symbol": unit_symbol,
                              "definition": f"{ucum}#{ucum_code}" if ucum_code else "urn:ogc-api-research-sandbox:class"},
        "properties": {"simulated": simulated},
        "Thing": {"@iot.id": thing_id},
        "Sensor": {"@iot.id": sensor_id},
        "ObservedProperty": {"@iot.id": observed_property_id},
    })


def upload_observations(datastream_id, feature_id, timestamps, results):
    rows = [[timestamp, timestamp, result, feature_id]
            for timestamp, result in zip(timestamps, results) if result is not None]
    response, _ = request("POST", "CreateObservations", [{
        "Datastream": {"@iot.id": datastream_id},
        "components": ["phenomenonTime", "resultTime", "result", "FeatureOfInterest/id"],
        "dataArray@iot.count": len(rows),
        "dataArray": rows,
    }])
    failures = [entry for entry in response if entry == "error"]
    if failures:
        raise FrostError(f"{len(failures)} observations failed for Datastream {datastream_id}")
    return len(rows)


def load_station(station, sensors, observed_property_ids):
    tawes_sensor, simulated_sensor = sensors
    timestamps, series = read_station_series(station["id"])
    thing_id, feature_id = create_station(station)
    station_name = station["name"]
    uploaded = 0

    for parameter, property_key, unit in measured_datastreams:
        datastream_id = create_datastream(
            thing_id, tawes_sensor, observed_property_ids[property_key],
            f"{observed_properties[property_key][0]} at {station_name}",
            f"{observed_properties[property_key][2]} (GeoSphere parameter '{parameter}')", unit, simulated=False)
        uploaded += upload_observations(datastream_id, feature_id, timestamps, series[parameter])

    measured_soil_temperature = series.get("tb10", [])
    has_measured_soil_temperature = sum(v is not None for v in measured_soil_temperature) >= 0.9 * len(timestamps)
    if has_measured_soil_temperature:
        soil_temperature_sensor, soil_temperatures = tawes_sensor, measured_soil_temperature
        description = "Soil temperature 10 cm below ground (GeoSphere parameter 'tb10')"
    else:
        soil_temperature_sensor, soil_temperatures = simulated_sensor, soil_model.soil_temperature_c(series["tl"])
        description = "SIMULATED soil temperature 10 cm below ground (damped air temperature, no measurement)"
    datastream_id = create_datastream(
        thing_id, soil_temperature_sensor, observed_property_ids["soil_temperature"],
        f"Soil temperature at 10 cm at {station_name}", description, ("degree Celsius", "°C", "Cel"),
        simulated=not has_measured_soil_temperature)
    uploaded += upload_observations(datastream_id, feature_id, timestamps, soil_temperatures)

    moisture = soil_model.soil_moisture_percent(series["rr"], series["tl"], series["cglo"], series["p"])
    datastream_id = create_datastream(
        thing_id, simulated_sensor, observed_property_ids["soil_moisture"],
        f"Soil moisture at {station_name}", "SIMULATED volumetric soil moisture of the root zone (bucket model)",
        ("percent (volume fraction)", "%", "%"), simulated=True)
    uploaded += upload_observations(datastream_id, feature_id, timestamps, moisture)

    datastream_id = create_datastream(
        thing_id, simulated_sensor, observed_property_ids["soil_state"],
        f"Soil state at {station_name}", "SIMULATED soil state class derived from simulated soil moisture",
        ("soil state class", "", None), simulated=True, observation_type=category_type)
    uploaded += upload_observations(datastream_id, feature_id, timestamps,
                                    [soil_model.soil_state(value) for value in moisture])

    soil_temperature_source = "measured" if has_measured_soil_temperature else "simulated"
    print(f"  {station['id']:>6} {station_name:<32} {uploaded:>6} observations, soil temperature "
          f"{soil_temperature_source}, soil moisture {min(moisture):.1f}-{max(moisture):.1f} %")
    return uploaded


def main():
    stations = json.loads(stations_file.read_text())
    print(f"FROST: {frost_url}")
    print("Deleting existing entities")
    for entity_set in ("Things", "Locations", "FeaturesOfInterest", "Sensors", "ObservedProperties"):
        print(f"  {entity_set}: {delete_all(entity_set)} deleted")

    sensors = create_sensors()
    observed_property_ids = create_observed_properties()
    print(f"Loading {len(stations)} stations")
    total = sum(load_station(station, sensors, observed_property_ids) for station in stations)
    print(f"Done: {total} observations")


if __name__ == "__main__":
    try:
        main()
    except FrostError as error:
        sys.exit(str(error))
