#!/bin/sh
set -eu
export ABGEN_INIT_PASSWORD="$(cat /run/secrets/db_app)"
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password ABGEN_INIT_PASSWORD
CREATE ROLE abgen LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE abgen OWNER abgen;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL
