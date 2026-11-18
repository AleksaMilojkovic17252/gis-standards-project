-- Q4 closest approach of two trains
SELECT min(ST_Distance(a.geom,
           CASE WHEN after_b.t = before_b.t THEN before_b.geom
                ELSE ST_LineInterpolatePoint(ST_MakeLine(before_b.geom, after_b.geom),
                     extract(epoch FROM a.t - before_b.t) / extract(epoch FROM after_b.t - before_b.t)) END)) AS distance_m
FROM postgis_points.positions AS a
CROSS JOIN LATERAL (
    SELECT t, geom FROM postgis_points.positions
    WHERE trip_id = %(trip_b)s AND t <= a.t ORDER BY t DESC LIMIT 1
) AS before_b
CROSS JOIN LATERAL (
    SELECT t, geom FROM postgis_points.positions
    WHERE trip_id = %(trip_b)s AND t >= a.t ORDER BY t LIMIT 1
) AS after_b
WHERE a.trip_id = %(trip_a)s;
