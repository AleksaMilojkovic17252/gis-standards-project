-- Q3 length, maximum speed and mean speed of every trip
SELECT trip_id, length(trip) AS length_m, maxValue(speed(trip)) AS max_speed_m_s,
       length(trip) / extract(epoch FROM duration(trip)) AS mean_speed_m_s
FROM mdb.trips;
