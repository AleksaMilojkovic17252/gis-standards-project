from pathlib import Path

import numpy as np
import xarray as xr
from pyproj import Transformer

input_folder = Path("/data/raw/inca")
output_file = Path("/data/processed/inca_crs84.nc")

grid_step_degrees = 0.01
longitudes = np.round(np.arange(9.46, 17.19 + grid_step_degrees / 2, grid_step_degrees), 4)
latitudes = np.round(np.arange(46.45, 49.09 + grid_step_degrees / 2, grid_step_degrees), 4)

variable_names = {
    "T2M": ("air_temperature", "Air temperature 2 m above ground", "degC"),
    "RH2M": ("relative_humidity", "Relative humidity 2 m above ground", "%"),
    "RR": ("precipitation_amount", "Precipitation sum over the previous hour", "mm"),
}

input_files = sorted(input_folder.glob("inca_*.nc"))
print(f"Reading {len(input_files)} INCA files")
inca = xr.concat([xr.open_dataset(file) for file in input_files], dim="time")[list(variable_names)]
inca = inca.drop_vars([name for name in ("lat", "lon", "lambert_conformal_conic") if name in inca.coords])

to_austria_lambert = Transformer.from_crs("EPSG:4326", "EPSG:31287", always_xy=True)
longitude_grid, latitude_grid = np.meshgrid(longitudes, latitudes)
target_x, target_y = to_austria_lambert.transform(longitude_grid, latitude_grid)

print(f"Regridding to {len(longitudes)} x {len(latitudes)} cells at {grid_step_degrees} degrees")
regridded = inca.interp(
    x=xr.DataArray(target_x, dims=("lat", "lon")),
    y=xr.DataArray(target_y, dims=("lat", "lon")),
    method="linear",
).drop_vars(["x", "y"])
regridded = regridded.assign_coords(lon=("lon", longitudes), lat=("lat", latitudes))

regridded["lon"].attrs = {"standard_name": "longitude", "long_name": "longitude", "units": "degrees_east", "axis": "X"}
regridded["lat"].attrs = {"standard_name": "latitude", "long_name": "latitude", "units": "degrees_north", "axis": "Y"}
regridded["time"].attrs = {"standard_name": "time", "axis": "T"}
for name, (standard_name, long_name, units) in variable_names.items():
    regridded[name] = regridded[name].astype("float32")
    regridded[name].attrs = {"standard_name": standard_name, "long_name": long_name, "units": units}

missing_cells = int(regridded["T2M"].isnull().sum())
if missing_cells:
    raise SystemExit(f"{missing_cells} cells are outside the INCA domain; shrink the target grid")

regridded.attrs = {
    "Conventions": "CF-1.8",
    "title": "INCA analysis (GeoSphere Austria), regridded to a regular lon/lat grid",
    "source": "GeoSphere Austria Data Hub, inca-v1-1h-1km (EPSG:31287, 1 km), bilinear interpolation to WGS84",
    "license": "CC BY 4.0",
    "crs": "EPSG:4326",
}

output_file.parent.mkdir(parents=True, exist_ok=True)
encoding = {name: {"zlib": True, "complevel": 4} for name in variable_names}
temporary_file = output_file.with_name(output_file.stem + ".partial.nc")
regridded.to_netcdf(temporary_file, encoding=encoding)
temporary_file.replace(output_file)
print(f"Saved {output_file} ({output_file.stat().st_size / 1e6:.0f} MB), time {str(regridded.time.values[0])[:16]}"
      f" to {str(regridded.time.values[-1])[:16]}")
