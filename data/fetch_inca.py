import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

inca_url = "https://dataset.api.hub.geosphere.at/v1/grid/historical/inca-v1-1h-1km"
parameter_names = ["T2M", "RH2M", "RR"]
austria_bbox = "46.3,9.4,49.1,17.2"
period_start = datetime(2026, 11, 4, 0, 0)
period_end = datetime(2026, 11, 14, 0, 0)
hours_per_file = 12

output_folder = Path(__file__).parent / "raw" / "inca"
output_folder.mkdir(parents=True, exist_ok=True)

chunk_start = period_start
while chunk_start < period_end:
    chunk_end = chunk_start + timedelta(hours=hours_per_file - 1)
    output_file = output_folder / f"inca_{chunk_start:%Y%m%dT%H}.nc"

    if output_file.exists():
        print(f"Already downloaded {output_file.name}")
    else:
        query = [("parameters", name) for name in parameter_names]
        query += [
            ("start", chunk_start.strftime("%Y-%m-%dT%H:%M")),
            ("end", chunk_end.strftime("%Y-%m-%dT%H:%M")),
            ("bbox", austria_bbox),
            ("output_format", "netcdf"),
        ]
        print(f"Downloading {chunk_start} to {chunk_end}")
        with urlopen(f"{inca_url}?{urlencode(query)}", timeout=300) as response:
            output_file.write_bytes(response.read())
        time.sleep(1)

    chunk_start += timedelta(hours=hours_per_file)
