-- Q7 air temperature at the nearest weather station for every train at time t
WITH trains AS (
    SELECT trip_id, ST_Force2D(ST_GeometryN(ST_LocateAlong(geom, extract(epoch FROM %(t)s)), 1)) AS position
    FROM postgis_lsm.trips
    WHERE period @> %(t)s
)
SELECT tr.trip_id, nearest.station_id, latest.value AS air_temperature
FROM trains AS tr
CROSS JOIN LATERAL (
    SELECT station_id FROM obs.stations ORDER BY geom <-> tr.position LIMIT 1
) AS nearest
CROSS JOIN LATERAL (
    SELECT value FROM obs.observations
    WHERE station_id = nearest.station_id AND property = 'air_temperature' AND t <= %(t)s
    ORDER BY t DESC LIMIT 1
) AS latest;
