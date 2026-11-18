-- Q2 trains inside a bounding box during [t1, t2]
SELECT trip_id
FROM mdb.trips
WHERE trip && stbox(ST_MakeEnvelope(%(xmin)s, %(ymin)s, %(xmax)s, %(ymax)s, 3416), span(%(t1)s, %(t2)s, true, true))
  AND eIntersects(atTime(trip, span(%(t1)s, %(t2)s, true, true)),
                  ST_MakeEnvelope(%(xmin)s, %(ymin)s, %(xmax)s, %(ymax)s, 3416));
