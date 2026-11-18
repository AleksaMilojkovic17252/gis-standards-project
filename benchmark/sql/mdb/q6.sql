-- Q6 trains passing a railway station between t1 and t2, with the time they reach it
SELECT m.trip_id,
       startTimestamp(atGeometry(atTime(m.trip, span(%(passage_t1)s, %(passage_t2)s, true, true)),
                                 ST_Buffer(s.geom, %(passage_m)s))) AS reached
FROM mdb.trips AS m, rail.stations AS s
WHERE s.osm_id = %(station_osm_id)s
  AND m.trip && span(%(passage_t1)s, %(passage_t2)s, true, true)
  AND eDwithin(atTime(m.trip, span(%(passage_t1)s, %(passage_t2)s, true, true)), s.geom, %(passage_m)s);
