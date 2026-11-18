-- Q6 trains passing a railway station between t1 and t2, with the time they reach it
SELECT l.trip_id, to_timestamp(ST_InterpolatePoint(l.geom, s.geom)) AS reached
FROM postgis_lsm.trips AS l, rail.stations AS s
WHERE s.osm_id = %(station_osm_id)s
  AND l.period && tstzrange(%(passage_t1)s, %(passage_t2)s, '[]')
  AND ST_DWithin(ST_LocateBetween(l.geom, extract(epoch FROM %(passage_t1)s), extract(epoch FROM %(passage_t2)s)),
                 s.geom, %(passage_m)s);
