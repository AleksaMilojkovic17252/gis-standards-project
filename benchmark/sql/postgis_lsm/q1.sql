-- Q1 position of every train at time t
SELECT trip_id, ST_GeometryN(ST_LocateAlong(geom, extract(epoch FROM %(t)s)), 1) AS position
FROM postgis_lsm.trips
WHERE period @> %(t)s;
