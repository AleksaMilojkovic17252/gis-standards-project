-- Q5 total time trains spend within the radius of each weather station
WITH vertices AS (
    SELECT trip_id, (point).path[1] AS vertex, (point).geom AS geom
    FROM postgis_lsm.trips AS t
    CROSS JOIN LATERAL ST_DumpPoints(t.geom) AS point
    WHERE EXISTS (SELECT 1 FROM obs.stations AS s WHERE ST_DWithin(t.geom, s.geom, %(radius_m)s))
), steps AS (
    SELECT geom, lead(ST_M(geom)) OVER (PARTITION BY trip_id ORDER BY vertex) - ST_M(geom) AS step_s
    FROM vertices
)
SELECT s.station_id, make_interval(secs => sum(p.step_s)) AS time_within
FROM obs.stations AS s
JOIN steps AS p ON ST_DWithin(p.geom, s.geom, %(radius_m)s)
GROUP BY s.station_id;
