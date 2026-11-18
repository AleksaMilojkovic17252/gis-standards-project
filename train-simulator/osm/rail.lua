local rail_ways = osm2pgsql.define_way_table('osm_rail_ways', {
    { column = 'maxspeed', type = 'text' },
    { column = 'maxspeed_forward', type = 'text' },
    { column = 'maxspeed_backward', type = 'text' },
    { column = 'service', type = 'text' },
    { column = 'usage', type = 'text' },
    { column = 'name', type = 'text' },
    { column = 'node_ids', sql_type = 'int8[]', not_null = true },
    { column = 'geom', type = 'linestring', projection = 4326, not_null = true },
}, { schema = 'rail' })

local stations = osm2pgsql.define_node_table('osm_stations', {
    { column = 'name', type = 'text', not_null = true },
    { column = 'railway', type = 'text', not_null = true },
    { column = 'uic_ref', type = 'text' },
    { column = 'geom', type = 'point', projection = 4326, not_null = true },
}, { schema = 'rail' })

local station_types = { station = true, halt = true }

function osm2pgsql.process_node(object)
    local tags = object.tags
    local is_train_station = station_types[tags.railway] and (tags.station == nil or tags.station == 'train')
    if is_train_station and tags.name then
        stations:insert({
            name = tags.name,
            railway = tags.railway,
            uic_ref = tags.uic_ref,
            geom = object:as_point(),
        })
    end
end

function osm2pgsql.process_way(object)
    local tags = object.tags
    if tags.railway ~= 'rail' then
        return
    end
    rail_ways:insert({
        maxspeed = tags.maxspeed,
        maxspeed_forward = tags['maxspeed:forward'],
        maxspeed_backward = tags['maxspeed:backward'],
        service = tags.service,
        usage = tags.usage,
        name = tags.name,
        node_ids = '{' .. table.concat(object.nodes, ',') .. '}',
        geom = object:as_linestring(),
    })
end
