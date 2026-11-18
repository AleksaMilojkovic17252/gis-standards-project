-- Q5 total time trains spend within the radius of each weather station
WITH steps AS (
    SELECT geom, lead(t) OVER (PARTITION BY trip_id ORDER BY t) - t AS step
    FROM postgis_points.positions
)
SELECT s.station_id, sum(p.step) AS time_within
FROM obs.stations AS s
JOIN steps AS p ON ST_DWithin(p.geom, s.geom, %(radius_m)s)
GROUP BY s.station_id;
