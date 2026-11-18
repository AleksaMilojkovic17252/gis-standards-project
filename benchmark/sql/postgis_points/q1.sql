-- Q1 position of every train at time t
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
)
SELECT b.trip_id,
       CASE WHEN a.t = b.t THEN b.geom
            ELSE ST_LineInterpolatePoint(ST_MakeLine(b.geom, a.geom),
                 extract(epoch FROM %(t)s - b.t) / extract(epoch FROM a.t - b.t)) END AS position
FROM before AS b
JOIN after AS a USING (trip_id);
