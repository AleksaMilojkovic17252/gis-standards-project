import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

import numpy as np

local_utc_offset = timedelta(hours=1)
first_departure_local_hour = 6
last_departure_local_hour = 21

train_max_speed_kmh = 230.0
acceleration_m_s2 = 0.5
braking_m_s2 = 0.7
grid_step_m = 5.0

main_station_dwell_s = 120.0
other_station_dwell_s = 60.0
dwell_variation_s = (-15.0, 45.0)
gap_length_s = (5.0, 30.0)


@dataclass(frozen=True)
class GeneratorSettings:
    gps_noise_horizontal_m: float = 3.0
    sample_interval_s: float = 1.0
    sample_jitter_s: float = 0.3
    gap_share_of_time: float = 0.02
    max_departure_delay_s: float = 180.0
    random_delays: bool = True
    random_dwell: bool = True
    bunching_shift_min: int = 0
    chained_delay_share: float = 0.0


baseline_settings = GeneratorSettings()
exact_settings = GeneratorSettings(gps_noise_horizontal_m=0.0, sample_jitter_s=0.0, gap_share_of_time=0.0,
                                   random_delays=False)
sensitivity_variants = {
    "noise0": replace(baseline_settings, gps_noise_horizontal_m=0.0, sample_jitter_s=0.0, gap_share_of_time=0.0),
    "noise10": replace(baseline_settings, gps_noise_horizontal_m=10.0),
    "sampling5": replace(baseline_settings, sample_interval_s=5.0, sample_jitter_s=1.0),
    "bunching": replace(baseline_settings, bunching_shift_min=50),
    "chained": replace(baseline_settings, max_departure_delay_s=900.0, chained_delay_share=0.5),
}


@dataclass
class Line:
    line_id: str
    coordinates: np.ndarray
    stop_names: list
    stop_distances_m: np.ndarray
    segment_starts_m: np.ndarray
    segment_speeds_kmh: np.ndarray

    @property
    def length_m(self):
        return float(self.stop_distances_m[-1])


@dataclass
class Run:
    line: Line
    direction: str
    coordinates: np.ndarray
    vertex_distances_m: np.ndarray
    legs: list
    stop_names: list


@dataclass
class Trip:
    trip_id: int
    train_id: str
    line_id: str
    direction: str
    scheduled_departure: datetime
    actual_departure: datetime
    arrival: datetime
    times: np.ndarray
    x: np.ndarray
    y: np.ndarray


def reverse_line(line):
    length = line.length_m
    segment_ends = np.append(line.segment_starts_m[1:], length)
    return Line(
        line_id=line.line_id,
        coordinates=line.coordinates[::-1].copy(),
        stop_names=line.stop_names[::-1],
        stop_distances_m=(length - line.stop_distances_m)[::-1].copy(),
        segment_starts_m=(length - segment_ends)[::-1].copy(),
        segment_speeds_kmh=line.segment_speeds_kmh[::-1].copy(),
    )


def speed_limit_m_s(line, distances_m):
    segment_index = np.searchsorted(line.segment_starts_m, distances_m, side="right") - 1
    segment_index = np.clip(segment_index, 0, len(line.segment_speeds_kmh) - 1)
    return np.minimum(line.segment_speeds_kmh[segment_index], train_max_speed_kmh) / 3.6


def drive_leg(line, start_m, end_m):
    number_of_points = max(2, int(math.ceil((end_m - start_m) / grid_step_m)) + 1)
    distances = np.linspace(start_m, end_m, number_of_points)
    step = np.diff(distances)
    speeds = speed_limit_m_s(line, distances)
    speeds[0] = 0.0
    speeds[-1] = 0.0
    for index in range(1, number_of_points):
        speeds[index] = min(speeds[index], math.sqrt(speeds[index - 1] ** 2 + 2 * acceleration_m_s2 * step[index - 1]))
    for index in range(number_of_points - 2, -1, -1):
        speeds[index] = min(speeds[index], math.sqrt(speeds[index + 1] ** 2 + 2 * braking_m_s2 * step[index]))
    mean_speeds = np.maximum((speeds[:-1] + speeds[1:]) / 2, 0.01)
    times = np.concatenate([[0.0], np.cumsum(step / mean_speeds)])
    return distances, times


def prepare_run(line, direction):
    oriented_line = line if direction == "forward" else reverse_line(line)
    vertex_steps = np.hypot(*np.diff(oriented_line.coordinates, axis=0).T)
    vertex_distances = np.concatenate([[0.0], np.cumsum(vertex_steps)])
    legs = [drive_leg(oriented_line, start, end)
            for start, end in zip(oriented_line.stop_distances_m[:-1], oriented_line.stop_distances_m[1:])]
    return Run(oriented_line, direction, oriented_line.coordinates, vertex_distances, legs, oriented_line.stop_names)


def dwell_time_s(stop_name, random, settings):
    nominal = main_station_dwell_s if "Hauptbahnhof" in stop_name else other_station_dwell_s
    return nominal + (random.uniform(*dwell_variation_s) if settings.random_dwell else 0.0)


def assemble_motion(run, random, settings):
    all_times = []
    all_distances = []
    clock = 0.0
    for leg_index, (distances, times) in enumerate(run.legs):
        leg_times = times + clock
        if leg_index > 0:
            distances, leg_times = distances[1:], leg_times[1:]
        all_distances.append(distances)
        all_times.append(leg_times)
        clock = leg_times[-1]
        is_last_leg = leg_index == len(run.legs) - 1
        if not is_last_leg:
            clock += dwell_time_s(run.stop_names[leg_index + 1], random, settings)
            all_distances.append(np.array([distances[-1]]))
            all_times.append(np.array([clock]))
    return np.concatenate(all_times), np.concatenate(all_distances)


def sample_times(duration_s, random, settings):
    sample_count = int(duration_s // settings.sample_interval_s) + 1
    times = np.arange(sample_count) * settings.sample_interval_s
    if settings.sample_jitter_s > 0:
        times = times + random.uniform(-settings.sample_jitter_s, settings.sample_jitter_s, size=sample_count)
        times[0] = 0.0
        times[-1] = min(times[-1], duration_s)
    if settings.gap_share_of_time <= 0:
        return times
    keep = np.ones(sample_count, dtype=bool)
    mean_gap_s = sum(gap_length_s) / 2
    gap_start_probability = settings.gap_share_of_time * settings.sample_interval_s / mean_gap_s
    for index in np.flatnonzero(random.random(sample_count) < gap_start_probability):
        gap_end = times[index] + random.uniform(*gap_length_s)
        keep[(times >= times[index]) & (times < gap_end)] = False
    keep[0] = keep[-1] = True
    return times[keep]


def departure_delay_s(random, settings, previous_delay_s):
    if not settings.random_delays:
        return 0.0
    own_delay = min(float(random.exponential(settings.max_departure_delay_s / 3)), settings.max_departure_delay_s)
    return own_delay + settings.chained_delay_share * previous_delay_s


def simulate_trip(run, trip_id, train_id, scheduled_departure, random, settings, delay_s):
    motion_times, motion_distances = assemble_motion(run, random, settings)
    relative_times = sample_times(motion_times[-1], random, settings)
    distances = np.interp(relative_times, motion_times, motion_distances)
    x = np.interp(distances, run.vertex_distances_m, run.coordinates[:, 0])
    y = np.interp(distances, run.vertex_distances_m, run.coordinates[:, 1])
    if settings.gps_noise_horizontal_m > 0:
        noise_per_axis_m = settings.gps_noise_horizontal_m / math.sqrt(2)
        x = x + random.normal(0.0, noise_per_axis_m, size=x.size)
        y = y + random.normal(0.0, noise_per_axis_m, size=y.size)
    actual_departure = scheduled_departure + timedelta(seconds=delay_s)
    return Trip(
        trip_id=trip_id,
        train_id=train_id,
        line_id=run.line.line_id,
        direction=run.direction,
        scheduled_departure=scheduled_departure,
        actual_departure=actual_departure,
        arrival=actual_departure + timedelta(seconds=float(motion_times[-1])),
        times=actual_departure.timestamp() + relative_times,
        x=x,
        y=y,
    )


def departures_utc(service_day, settings):
    for position, local_hour in enumerate(range(first_departure_local_hour, last_departure_local_hour + 1)):
        local_time = datetime(service_day.year, service_day.month, service_day.day, local_hour)
        if settings.bunching_shift_min and position % 2 == 1:
            local_time -= timedelta(minutes=settings.bunching_shift_min)
        yield (local_time - local_utc_offset).replace(tzinfo=timezone.utc), local_time


def simulate_days(lines, service_days, seed, settings=baseline_settings, first_trip_id=1):
    random = np.random.default_rng(seed)
    runs = [prepare_run(line, direction) for line in lines for direction in ("forward", "backward")]
    trip_id = first_trip_id
    for service_day in service_days:
        for run in runs:
            previous_delay_s = 0.0
            for departure, local_time in departures_utc(service_day, settings):
                train_id = f"{run.line.line_id}-{run.direction[0]}-{local_time:%H%M}"
                delay_s = departure_delay_s(random, settings, previous_delay_s)
                yield simulate_trip(run, trip_id, train_id, departure, random, settings, delay_s)
                previous_delay_s = delay_s
                trip_id += 1


def service_days_from(first_day, number_of_days):
    return [first_day + timedelta(days=offset) for offset in range(number_of_days)]


period_first_day = date(2026, 11, 4)
one_x_day = date(2026, 11, 12)
