-- Q2 trains inside a bounding box during [t1, t2]
SELECT trip_id
FROM postgis_lsm.trips
WHERE period && tstzrange(%(t1)s, %(t2)s, '[]')
  AND geom && ST_MakeEnvelope(%(xmin)s, %(ymin)s, %(xmax)s, %(ymax)s, 3416)
  AND ST_Intersects(ST_LocateBetween(geom, extract(epoch FROM %(t1)s), extract(epoch FROM %(t2)s)),
                    ST_MakeEnvelope(%(xmin)s, %(ymin)s, %(xmax)s, %(ymax)s, 3416));
