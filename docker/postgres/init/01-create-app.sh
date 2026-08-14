#!/bin/sh
set -eu

psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set app_user="$POS_DB_USER" \
  --set app_password="$POS_DB_PASSWORD" \
  --set app_db="$POS_DB_NAME" <<'EOSQL'
SELECT format(
    'CREATE ROLE %I WITH LOGIN PASSWORD %L CREATEDB',
    :'app_user',
    :'app_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'app_user'
) \gexec

SELECT format(
    'CREATE DATABASE %I OWNER %I',
    :'app_db',
    :'app_user'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'app_db'
) \gexec
EOSQL
