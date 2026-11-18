-- Q7 air temperature at the nearest weather station for every train at time t
SELECT m.trip_id, nearest.station_id, valueAtTimestamp(o.values_float, %(t)s) AS air_temperature
FROM mdb.trips AS m
CROSS JOIN LATERAL (
    SELECT station_id FROM obs.stations
    ORDER BY geom <-> valueAtTimestamp(m.trip, %(t)s) LIMIT 1
) AS nearest
JOIN obs.series AS o ON o.station_id = nearest.station_id AND o.property = 'air_temperature'
WHERE m.trip && span(%(t)s, %(t)s, true, true);
