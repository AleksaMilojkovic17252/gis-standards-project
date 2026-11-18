from pathlib import Path
from urllib.request import urlopen

api_url = "https://dataset.api.hub.geosphere.at/v1"
dataset_paths = {
    "klima-v2-10min": "station/historical/klima-v2-10min",
    "inca-v1-1h-1km": "grid/historical/inca-v1-1h-1km",
}
output_folder = Path(__file__).parent / "raw" / "geosphere"
output_folder.mkdir(parents=True, exist_ok=True)

for dataset_name, dataset_path in dataset_paths.items():
    metadata_url = f"{api_url}/{dataset_path}/metadata"
    output_file = output_folder / f"{dataset_name}.metadata.json"
    print(f"Downloading {metadata_url}")
    with urlopen(metadata_url, timeout=60) as response:
        output_file.write_bytes(response.read())
    print(f"Saved {output_file}")
