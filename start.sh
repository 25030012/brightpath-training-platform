#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

if command -v initdb >/dev/null 2>&1 && command -v pg_ctl >/dev/null 2>&1; then
    if [ ! -d ".pgdata" ]; then
        initdb -D .pgdata -U postgres --auth=trust --no-locale --encoding=UTF8 >/dev/null
        cat >> .pgdata/postgresql.conf <<EOF
shared_memory_type = mmap
dynamic_shared_memory_type = mmap
listen_addresses = ''
unix_socket_directories = '/tmp'
port = 5433
EOF
    fi
    if ! pg_isready -h /tmp -p 5433 >/dev/null 2>&1; then
        pg_ctl -D .pgdata -l .pgdata/postgres.log start >/dev/null || true
    fi
    createdb -h /tmp -p 5433 -U postgres brightpath 2>/dev/null || true
fi

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py import_seed --data-dir data

PORT="${PORT:-8000}"
echo "Starting BrightPath Training Platform on http://127.0.0.1:${PORT}"
exec .venv/bin/python manage.py runserver "127.0.0.1:${PORT}" --noreload
