-- Q3 length, maximum speed and mean speed of every trip
WITH steps AS (
    SELECT trip_id, t,
           ST_Distance(geom, lag(geom) OVER w) AS step_m,
           extract(epoch FROM t - lag(t) OVER w) AS step_s
    FROM postgis_points.positions
    WINDOW w AS (PARTITION BY trip_id ORDER BY t)
)
SELECT trip_id, sum(step_m) AS length_m, max(step_m / step_s) AS max_speed_m_s,
       sum(step_m) / extract(epoch FROM max(t) - min(t)) AS mean_speed_m_s
FROM steps
GROUP BY trip_id;
