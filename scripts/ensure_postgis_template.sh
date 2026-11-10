#!/usr/bin/env bash
# Garante template_napi_postgis de forma IDEMPOTENTE e NÃO DESTRUTIVA.
# - Se ausente: cria vazio + PostGIS (exige sudo).
# - Se presente e adequado: sai sem alterações.
# - Se presente mas incorreto: FALHA com diagnóstico (NÃO faz DROP/terminate).
# Não toca em napi_geoai. Cluster alvo padrão: porta 5433 (WSL deste host).
set -euo pipefail

TEMPLATE="${TEMPLATE_NAPI_POSTGIS:-template_napi_postgis}"
OWNER="${TEMPLATE_OWNER:-napi}"
# Neste computador o cluster nativo escuta em 5433 — não assumir 5432.
PGPORT="${PGPORT:-5433}"
export PGPORT

psql_as_postgres() {
  sudo -u postgres env PGPORT="$PGPORT" psql -v ON_ERROR_STOP=1 "$@"
}

echo "==> ensure_postgis_template (porta PGPORT=$PGPORT, template=$TEMPLATE)"
echo "    (idempotente; sem DROP; sem tocar em napi_geoai)"

exists="$(
  psql_as_postgres -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '${TEMPLATE}'" | tr -d '[:space:]'
)"

if [[ "$exists" == "1" ]]; then
  echo "==> Template já existe — verificando estado (sem alterar)"
  meta="$(
    psql_as_postgres -d postgres -tAc \
      "SELECT datistemplate::text || '|' || pg_catalog.pg_get_userbyid(datdba)
       FROM pg_database WHERE datname = '${TEMPLATE}'" | tr -d '[:space:]'
  )"
  is_template="${meta%%|*}"
  db_owner="${meta#*|}"

  problems=()
  if [[ "$is_template" != "true" ]]; then
    problems+=("datistemplate=$is_template (esperado true)")
  fi
  if [[ "$db_owner" != "$OWNER" ]]; then
    problems+=("owner=$db_owner (esperado $OWNER)")
  fi

  postgis_ok="$(
    psql_as_postgres -d "$TEMPLATE" -tAc \
      "SELECT 1 FROM pg_extension WHERE extname = 'postgis'" 2>/dev/null \
      | tr -d '[:space:]' || true
  )"
  if [[ "$postgis_ok" != "1" ]]; then
    problems+=("extensão postgis ausente")
  fi

  if ((${#problems[@]} > 0)); then
    echo "ERRO: $TEMPLATE existe mas está inadequado:" >&2
    for p in "${problems[@]}"; do
      echo "  - $p" >&2
    done
    echo >&2
    echo "Não será feito DROP automático. Opções manuais (revisar antes):" >&2
    echo "  1) Corrigir owner/IS_TEMPLATE/PostGIS com SQL supervisionado; ou" >&2
    echo "  2) Após backup e aprovação explícita, dropar e recriar o template." >&2
    echo "Cluster/porta usados: PGPORT=$PGPORT (confirme com pg_lsclusters)." >&2
    exit 2
  fi

  ver="$(psql_as_postgres -d "$TEMPLATE" -tAc "SELECT PostGIS_Version();" | head -n1)"
  echo "==> OK (sem alterações): $TEMPLATE adequado; PostGIS=$ver"
  exit 0
fi

echo "==> Template ausente — criando (sem DROP de nada existente)"
psql_as_postgres -d postgres <<SQL
CREATE DATABASE ${TEMPLATE} OWNER ${OWNER} IS_TEMPLATE true;
SQL

psql_as_postgres -d "$TEMPLATE" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE CONNECT ON DATABASE template_napi_postgis FROM PUBLIC;
GRANT CONNECT ON DATABASE template_napi_postgis TO napi;
SQL

ver="$(psql_as_postgres -d "$TEMPLATE" -tAc "SELECT PostGIS_Version();" | head -n1)"
echo "==> Criado: $TEMPLATE (PostGIS=$ver)"
echo "Pronto para: py -3 scripts/db_ops.py restore-verify --dump ..."
