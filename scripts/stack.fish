#!/usr/bin/env fish

set -l usage "usage: scripts/stack.fish up | down | status"

if test (count $argv) -ne 1
    echo $usage >&2
    exit 2
end

set -l repo (realpath (dirname (status filename))/..)
cd $repo; or exit 1

function _public_port
    set -l port (string replace -r '^PUBLIC_PORT=' '' (grep -E '^PUBLIC_PORT=' .env 2>/dev/null))
    test -n "$port"; and echo $port; or echo 8090
end

switch $argv[1]
    case up
        if not test -f .env
            cp .env.example .env
            echo "Created .env from .env.example (change the passwords if you like)."
        end

        docker compose up -d --build --wait --wait-timeout 300
        set -l rc $status
        echo
        docker compose ps
        if test $rc -ne 0
            echo
            echo "Some services are not healthy. Check logs with: docker compose logs <service>" >&2
            exit $rc
        end

        set -l port (_public_port)
        echo
        echo "Stack is up:"
        echo "  Viewer           http://localhost:$port/"
        echo "  SensorThings     http://localhost:$port/sta/FROST-Server/v1.1"
        echo "  pygeoapi         http://localhost:$port/ogc/"
        echo "  Moving Features  http://localhost:$port/mf/"

    case down
        docker compose down

    case status
        docker compose ps -a

    case '*'
        echo $usage >&2
        exit 2
end
