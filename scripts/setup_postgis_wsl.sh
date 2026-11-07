#!/usr/bin/env bash
# Instala e configura PostgreSQL 16 + PostGIS no Ubuntu WSL2 (somente local).
# Execute no terminal Ubuntu e digite a senha sudo quando solicitado.
# Não usa Supabase nem serviços pagos.
set -euo pipefail

echo "==> Atualizando índices apt"
sudo apt-get update

echo "==> Instalando postgresql-16 + postgis"
sudo apt-get install -y postgresql-16 postgresql-16-postgis-3 postgresql-contrib

echo "==> Iniciando serviço"
sudo service postgresql start

echo "==> Criando role/database locais (idempotente)"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='napi'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE napi LOGIN PASSWORD 'napi_local_dev_only' CREATEDB;"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='napi_geoai'" | grep -q 1; then
  sudo -u postgres createdb -O napi napi_geoai
fi

echo "==> Habilitando PostGIS no banco napi_geoai"
sudo -u postgres psql -d napi_geoai -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "==> Teste local"
sudo -u postgres psql -d napi_geoai -c "SELECT PostGIS_Version();"
PGPASSWORD=napi_local_dev_only psql -h 127.0.0.1 -U napi -d napi_geoai -c "SELECT 1 AS ok;"

echo
echo "Pronto. No PowerShell (raiz do repo):"
echo '  $env:DATABASE_URL="postgresql://napi:napi_local_dev_only@127.0.0.1:5432/napi_geoai"'
echo "  py -3 scripts/migrate_db.py"
echo "  py -3 scripts/import_parana_boundary_db.py"
echo "  py -3 -m pytest -q"
