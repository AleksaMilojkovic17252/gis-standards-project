#!/usr/bin/env fish

set -l usage "usage: scripts/benchmark.fish complexity | warm1x | warm10x | cold10x | sensitivity | charts | all"

if test (count $argv) -ne 1
    echo $usage >&2
    exit 2
end

set -l repo (realpath (dirname (status filename))/..)
cd $repo; or exit 1

set -l host_user (id -u):(id -g)
set -l models postgis_points mdb postgis_lsm
set -l queries q1 q2 q3 q4 q5 q6 q7

function bench --inherit-variable host_user
    docker compose run --rm -T --user $host_user benchmark python run_benchmark.py $argv
end

function wait_for_database
    for attempt in (seq 60)
        if docker compose exec -T mobilitydb pg_isready -q -U gis
            return 0
        end
        sleep 2
    end
    echo "database did not come back" >&2
    return 1
end

function run_cold10x --inherit-variable models --inherit-variable queries
    for model in $models
        bench prepare --database trains --model $model --config best; or return 1
        for query in $queries
            docker compose restart mobilitydb >/dev/null; or return 1
            wait_for_database; or return 1
            bench cold --database trains --label trains_10x --model $model --config best --query $query; or return 1
        end
    end
    docker compose restart mf-api pygeoapi >/dev/null
end

switch $argv[1]
    case complexity
        bench complexity
    case warm1x
        bench warm --database trains_1x --label trains_1x
    case warm10x
        bench warm --database trains --label trains_10x
    case cold10x
        run_cold10x
    case charts
        docker compose run --rm -T --no-deps --user $host_user benchmark python analyze_sensitivity.py >/dev/null
        and docker compose run --rm -T --no-deps --user $host_user benchmark python make_charts.py
    case sensitivity
        for variant in noise0 noise10 sampling5 bunching chained
            bench warm --database trains_1x_$variant --label sensitivity_$variant --config best; or exit 1
        end
    case all
        bench complexity; and bench warm --database trains_1x --label trains_1x
        and bench warm --database trains --label trains_10x
        and run_cold10x
    case '*'
        echo $usage >&2
        exit 2
end
