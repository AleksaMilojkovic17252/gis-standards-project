-- Q7 air temperature at the nearest weather station for every train at time t
WITH before AS (
    SELECT DISTINCT ON (trip_id) trip_id, t, geom
    FROM postgis_points.positions
    WHERE t <= %(t)s AND t > %(t)s - interval '1 minute'
    ORDER BY trip_id, t DESC
), after AS (
    SELECT DISTINCT ON (trip_id) trip_id, t, geom
    FROM postgis_points.positions
    WHERE t >= %(t)s AND t < %(t)s + interval '1 minute'
    ORDER BY trip_id, t
), trains AS (
    SELECT b.trip_id,
           CASE WHEN a.t = b.t THEN b.geom
                ELSE ST_LineInterpolatePoint(ST_MakeLine(b.geom, a.geom),
                     extract(epoch FROM %(t)s - b.t) / extract(epoch FROM a.t - b.t)) END AS position
    FROM before AS b JOIN after AS a USING (trip_id)
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
