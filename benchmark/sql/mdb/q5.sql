-- Q5 total time trains spend within the radius of each weather station
SELECT s.station_id, sum(duration(atGeometry(m.trip, ST_Buffer(s.geom, %(radius_m)s)))) AS time_within
FROM obs.stations AS s
JOIN mdb.trips AS m ON eDwithin(m.trip, s.geom, %(radius_m)s)
GROUP BY s.station_id;
