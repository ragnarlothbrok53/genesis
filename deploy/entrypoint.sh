#!/bin/bash
set -euo pipefail

export POSTGRES_USER="${POSTGRES_USER:-genesis}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-genesis}"
export POSTGRES_DB="${POSTGRES_DB:-genesis}"
export O2_ROOT_EMAIL="${O2_ROOT_EMAIL:-admin@genesis.local}"
export O2_ROOT_PASSWORD="${O2_ROOT_PASSWORD:-genesis-admin}"
export OTEL_EXPORTER_OTLP_TOKEN="${OTEL_EXPORTER_OTLP_TOKEN:-$(printf '%s:%s' "$O2_ROOT_EMAIL" "$O2_ROOT_PASSWORD" | base64 -w0)}"

PGDATA=/data/postgres
PG_BIN="$(ls -d /usr/lib/postgresql/*/bin | head -1)"
PG_USER="$POSTGRES_USER"
PG_PASSWORD="$POSTGRES_PASSWORD"
PG_DB="$POSTGRES_DB"

mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Initializing Postgres cluster..."
  su postgres -c "$PG_BIN/initdb -D $PGDATA --auth-local=trust --auth-host=scram-sha-256 --encoding=UTF8"
  {
    echo "listen_addresses = '127.0.0.1'"
    echo "shared_buffers = 64MB"
    echo "max_connections = 20"
    echo "work_mem = 4MB"
    echo "fsync = on"
  } >> "$PGDATA/postgresql.conf"
  echo "host all all 127.0.0.1/32 scram-sha-256" >> "$PGDATA/pg_hba.conf"

  su postgres -c "$PG_BIN/pg_ctl -D $PGDATA -w start"
  PG_PASSWORD_SQL="${PG_PASSWORD//\'/\'\'}"
  su postgres -c "$PG_BIN/psql -v ON_ERROR_STOP=1 --command \"CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD_SQL';\""
  su postgres -c "$PG_BIN/createdb -O $PG_USER $PG_DB"
  su postgres -c "$PG_BIN/pg_ctl -D $PGDATA -m fast -w stop"
  echo "Postgres initialized."
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
