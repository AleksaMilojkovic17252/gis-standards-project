-- Q6 trains passing a railway station between t1 and t2, with the time they reach it
SELECT p.trip_id, min(p.t) AS reached
FROM postgis_points.positions AS p, rail.stations AS s
WHERE s.osm_id = %(station_osm_id)s
  AND p.t BETWEEN %(passage_t1)s AND %(passage_t2)s
  AND ST_DWithin(p.geom, s.geom, %(passage_m)s)
GROUP BY p.trip_id;
