#!/bin/sh
set -eu
export LESEFLUX_INIT_PASSWORD="$(cat /run/secrets/db-app)"
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password LESEFLUX_INIT_PASSWORD
CREATE ROLE leseflux LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE leseflux OWNER leseflux;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL
