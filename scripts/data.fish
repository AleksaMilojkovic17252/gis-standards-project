#!/usr/bin/env fish

set -l usage "usage: scripts/data.fish osm | rail | stations | inca | sta | trains1x | trains10x | obs | variants | all"

if test (count $argv) -ne 1
    echo $usage >&2
    exit 2
end

set -l repo (realpath (dirname (status filename))/..)
cd $repo; or exit 1

set -l host_user (id -u):(id -g)

function run_osm
    docker compose run --rm osm2pgsql
end

function run_rail
    docker compose run --rm train-simulator python build_rail_lines.py
end

function run_stations --inherit-variable host_user
    docker compose run --rm --user $host_user train-simulator python select_weather_stations.py
end

function run_inca --inherit-variable host_user
    docker run --rm --user $host_user \
        -v $PWD/data:/data \
        -v $PWD/data/prepare_inca.py:/scripts/prepare_inca.py:ro \
        --entrypoint python3 geopython/pygeoapi:0.24.0 -W ignore /scripts/prepare_inca.py
    and docker compose restart pygeoapi
end

function run_sta
    docker compose run --rm sta-loader
end

function run_trains1x
    docker compose run --rm train-simulator python load_trains.py 1x
end

function run_trains10x
    docker compose run --rm train-simulator python load_trains.py 10x
end

function run_obs
    docker compose run --rm train-simulator python copy_observations.py
end

function run_variants
    for variant in noise0 noise10 sampling5 bunching chained
        docker compose run --rm train-simulator python load_trains.py 1x-$variant; or return 1
    end
    docker compose run --rm train-simulator python copy_observations.py --variants
end

switch $argv[1]
    case osm
        run_osm
    case rail
        run_rail
    case stations
        run_stations
    case inca
        run_inca
    case sta
        run_sta
    case trains1x
        run_trains1x
    case trains10x
        run_trains10x
    case obs
        run_obs
    case variants
        run_variants
    case all
        run_osm; and run_rail; and run_stations; and run_inca; and run_sta
        and run_trains1x; and run_trains10x; and run_obs
    case '*'
        echo $usage >&2
        exit 2
end
