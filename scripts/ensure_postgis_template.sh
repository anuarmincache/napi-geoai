#!/usr/bin/env bash
# Cria template vazio com PostGIS para restores isolados (role napi sem superuser).
# Digite a senha sudo no terminal. Não altera napi_geoai nem outros serviços.
set -euo pipefail

echo "==> Criando template_napi_postgis (se ausente)"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'template_napi_postgis' AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS template_napi_postgis;
CREATE DATABASE template_napi_postgis OWNER napi IS_TEMPLATE true;
SQL

sudo -u postgres psql -d template_napi_postgis -v ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE CONNECT ON DATABASE template_napi_postgis FROM PUBLIC;
GRANT CONNECT ON DATABASE template_napi_postgis TO napi;
SQL

echo "==> OK. Verifique:"
sudo -u postgres psql -d template_napi_postgis -c "SELECT PostGIS_Version();"
echo "Pronto para: py -3 scripts/db_ops.py restore-verify --dump ..."
