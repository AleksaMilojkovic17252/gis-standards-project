-- Q3 length, maximum speed and mean speed of every trip
WITH vertices AS (
    SELECT trip_id, (point).path[1] AS vertex, (point).geom AS geom
    FROM (SELECT trip_id, ST_DumpPoints(geom) AS point FROM postgis_lsm.trips) AS dumped
), steps AS (
    SELECT trip_id,
           ST_Distance(geom, lag(geom) OVER w) AS step_m,
           ST_M(geom) - ST_M(lag(geom) OVER w) AS step_s
    FROM vertices
    WINDOW w AS (PARTITION BY trip_id ORDER BY vertex)
)
SELECT t.trip_id, ST_Length(t.geom) AS length_m, s.max_speed_m_s,
       ST_Length(t.geom) / (ST_M(ST_EndPoint(t.geom)) - ST_M(ST_StartPoint(t.geom))) AS mean_speed_m_s
FROM postgis_lsm.trips AS t
JOIN (SELECT trip_id, max(step_m / step_s) AS max_speed_m_s FROM steps GROUP BY trip_id) AS s USING (trip_id);
