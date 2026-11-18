-- Q4 closest approach of two trains
SELECT nearestApproachDistance(a.trip, b.trip) AS distance_m
FROM mdb.trips AS a, mdb.trips AS b
WHERE a.trip_id = %(trip_a)s AND b.trip_id = %(trip_b)s;
