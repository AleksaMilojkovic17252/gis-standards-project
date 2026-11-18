-- Q4 closest approach of two trains
SELECT ST_DistanceCPA(a.geom, b.geom) AS distance_m
FROM postgis_lsm.trips AS a, postgis_lsm.trips AS b
WHERE a.trip_id = %(trip_a)s AND b.trip_id = %(trip_b)s;
