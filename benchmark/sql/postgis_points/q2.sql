-- Q2 trains inside a bounding box during [t1, t2]
SELECT DISTINCT trip_id
FROM postgis_points.positions
WHERE t BETWEEN %(t1)s AND %(t2)s
  AND ST_Intersects(geom, ST_MakeEnvelope(%(xmin)s, %(ymin)s, %(xmax)s, %(ymax)s, 3416));
