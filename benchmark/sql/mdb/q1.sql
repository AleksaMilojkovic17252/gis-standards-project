-- Q1 position of every train at time t
SELECT trip_id, valueAtTimestamp(trip, %(t)s) AS position
FROM mdb.trips
WHERE trip && span(%(t)s, %(t)s, true, true);
