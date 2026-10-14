#!/bin/bash
# Runs once, when the PostgreSQL data volume is first initialised.
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    -v airflow_user="$AIRFLOW_DB_USER" \
    -v airflow_password="$AIRFLOW_DB_PASSWORD" \
    -v airflow_db="$AIRFLOW_DB_NAME" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'airflow_user', :'airflow_password')
\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'airflow_db', :'airflow_user')
\gexec
SQL
