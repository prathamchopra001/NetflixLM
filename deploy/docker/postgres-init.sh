#!/bin/sh
# First start of an empty data volume only. `nip` is the superuser from POSTGRES_USER.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE mlflow"
