import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

stations_url = "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min"
station_ids = {
    39: "Innsbruck Universität",
    50: "Landeck",
    14311: "Langen am Arlberg",
    15: "Bregenz",
    145: "Salzburg Freisaal",
    14: "Bischofshofen",
    118: "Kitzbühel",
    42: "Jenbach",
    32: "Gumpoldskirchen",
    88: "Semmering",
    217: "Kapfenberg Flugfeld",
    16413: "Graz Straßgang",
    5925: "Wien Innere Stadt",
    106: "Wien Mariabrunn",
    4: "Amstetten",
    56: "Linz Stadt",
    4821: "Vöcklabruck",
}
parameter_names = ["tl", "rf", "p", "ff", "rr", "cglo", "tb10"]
period_start = datetime(2026, 11, 4, 0, 0)
period_end = datetime(2026, 11, 14, 0, 0)
days_per_file = 5

output_folder = Path(__file__).parent / "raw" / "geosphere" / "klima-v2-10min"
output_folder.mkdir(parents=True, exist_ok=True)

for station_id, station_name in station_ids.items():
    chunk_start = period_start
    while chunk_start < period_end:
        chunk_end = chunk_start + timedelta(days=days_per_file) - timedelta(minutes=10)
        output_file = output_folder / f"{station_id}_{chunk_start:%Y%m%d}.geojson"

        if output_file.exists():
            print(f"Already downloaded {output_file.name}")
        else:
            query = {
                "parameters": ",".join(parameter_names),
                "station_ids": station_id,
                "start": chunk_start.strftime("%Y-%m-%dT%H:%M"),
                "end": chunk_end.strftime("%Y-%m-%dT%H:%M"),
                "output_format": "geojson",
            }
            print(f"Downloading {station_name} ({station_id}) from {chunk_start} to {chunk_end}")
            with urlopen(f"{stations_url}?{urlencode(query)}", timeout=120) as response:
                output_file.write_bytes(response.read())
            time.sleep(1)

        chunk_start += timedelta(days=days_per_file)
