import math

step_seconds = 600
root_zone_depth_mm = 300
saturation_percent = 45.0
field_capacity_percent = 35.0
wilting_point_percent = 12.0
initial_moisture_percent = 26.0
drainage_rate_per_step = 0.02
stress_free_fraction = 0.5
latent_heat_mj_per_kg = 2.45

soil_temperature_time_constant_hours = 12.0

soil_state_thresholds = [
    (20.0, "dry"),
    (32.0, "moist"),
    (40.0, "wet"),
    (math.inf, "waterlogged"),
]


def fill_gaps(values, fallback):
    filled = []
    last_value = None
    for value in values:
        if value is not None:
            last_value = value
        filled.append(last_value if last_value is not None else fallback)
    return filled


def makkink_reference_evapotranspiration_mm(air_temperature_c, global_radiation_w_m2, air_pressure_hpa):
    saturation_vapour_pressure_kpa = 0.6108 * math.exp(17.27 * air_temperature_c / (air_temperature_c + 237.3))
    slope_kpa_per_c = 4098 * saturation_vapour_pressure_kpa / (air_temperature_c + 237.3) ** 2
    psychrometric_constant_kpa_per_c = 0.000665 * air_pressure_hpa / 10
    radiation_mj_m2 = max(global_radiation_w_m2, 0.0) * step_seconds / 1e6
    return 0.61 * slope_kpa_per_c / (slope_kpa_per_c + psychrometric_constant_kpa_per_c) * radiation_mj_m2 / latent_heat_mj_per_kg


def water_stress_factor(moisture_percent):
    available_range = field_capacity_percent - wilting_point_percent
    stress_threshold = field_capacity_percent - stress_free_fraction * available_range
    if moisture_percent >= stress_threshold:
        return 1.0
    return max(0.0, (moisture_percent - wilting_point_percent) / (stress_threshold - wilting_point_percent))


def soil_moisture_percent(precipitation_mm, air_temperature_c, global_radiation_w_m2, air_pressure_hpa):
    precipitation_mm = fill_gaps(precipitation_mm, 0.0)
    air_temperature_c = fill_gaps(air_temperature_c, 5.0)
    global_radiation_w_m2 = fill_gaps(global_radiation_w_m2, 0.0)
    air_pressure_hpa = fill_gaps(air_pressure_hpa, 1013.25)

    storage_mm = initial_moisture_percent / 100 * root_zone_depth_mm
    saturation_storage_mm = saturation_percent / 100 * root_zone_depth_mm
    field_capacity_storage_mm = field_capacity_percent / 100 * root_zone_depth_mm

    moisture_series = []
    for rain, temperature, radiation, pressure in zip(precipitation_mm, air_temperature_c,
                                                       global_radiation_w_m2, air_pressure_hpa):
        moisture_percent = 100 * storage_mm / root_zone_depth_mm
        evapotranspiration_mm = (makkink_reference_evapotranspiration_mm(temperature, radiation, pressure)
                                 * water_stress_factor(moisture_percent))
        storage_mm = min(storage_mm + rain, saturation_storage_mm) - evapotranspiration_mm
        if storage_mm > field_capacity_storage_mm:
            storage_mm -= drainage_rate_per_step * (storage_mm - field_capacity_storage_mm)
        storage_mm = max(storage_mm, 0.0)
        moisture_series.append(round(100 * storage_mm / root_zone_depth_mm, 2))
    return moisture_series


def soil_state(moisture_percent):
    for upper_limit, state in soil_state_thresholds:
        if moisture_percent < upper_limit:
            return state
    return soil_state_thresholds[-1][1]


def soil_temperature_c(air_temperature_c):
    air_temperature_c = fill_gaps(air_temperature_c, 5.0)
    first_day_steps = 24 * 3600 // step_seconds
    soil_temperature = sum(air_temperature_c[:first_day_steps]) / len(air_temperature_c[:first_day_steps])
    smoothing = step_seconds / (soil_temperature_time_constant_hours * 3600)
    soil_temperature_series = []
    for air_temperature in air_temperature_c:
        soil_temperature += smoothing * (air_temperature - soil_temperature)
        soil_temperature_series.append(round(soil_temperature, 2))
    return soil_temperature_series
