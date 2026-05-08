#!/usr/bin/env bash
# INI-1: Migration smoke test contra PostgreSQL real (Docker).
#
# Sobe um postgres:16 efêmero, aplica todas as migrations (upgrade),
# valida head único, e testa reversibilidade (downgrade base).
# Derruba o container ao final (sucesso ou falha).
#
# Uso:
#   bash scripts/test_migrations_local.sh
#
# Pré-requisitos: Docker, .venv ativo ou flask no PATH.
#
# Docs: docs/wiki/Post-Mortem-PR1174-Bootstrap-Migration.md (INI-1)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="auraxis-pg-migration-test"
PG_PORT="${MIGRATION_TEST_PG_PORT:-5433}"
PG_PASSWORD="migration_test_secret"
PG_DB="migration_testdb"
PG_USER="postgres"
DATABASE_URL="postgresql://${PG_USER}:${PG_PASSWORD}@localhost:${PG_PORT}/${PG_DB}"

FLASK_CMD="${FLASK_CMD:-scripts/python_tool.sh flask}"

cleanup() {
  echo "[migration-test] Removendo container ${CONTAINER}..."
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[migration-test] Subindo postgres:16 em porta ${PG_PORT}..."
docker run -d \
  --name "${CONTAINER}" \
  -e POSTGRES_PASSWORD="${PG_PASSWORD}" \
  -e POSTGRES_DB="${PG_DB}" \
  -e POSTGRES_USER="${PG_USER}" \
  -p "${PG_PORT}:5432" \
  --tmpfs /var/lib/postgresql/data \
  public.ecr.aws/docker/library/postgres:16 >/dev/null

echo "[migration-test] Aguardando PostgreSQL ficar pronto..."
for i in $(seq 1 30); do
  if docker exec "${CONTAINER}" pg_isready -U "${PG_USER}" -q 2>/dev/null; then
    echo "[migration-test] PostgreSQL pronto."
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "[migration-test] ERRO: PostgreSQL não ficou pronto em 30s." >&2
    exit 1
  fi
done

cd "${ROOT_DIR}"

echo "[migration-test] Aplicando migrations (upgrade head)..."
DATABASE_URL="${DATABASE_URL}" ${FLASK_CMD} --app run db upgrade

echo "[migration-test] Validando head único..."
HEAD_COUNT=$(DATABASE_URL="${DATABASE_URL}" ${FLASK_CMD} --app run db heads 2>/dev/null | grep -c "(head)" || true)
if [ "${HEAD_COUNT}" -ne 1 ]; then
  echo "[migration-test] ERRO: esperado 1 head, encontrado ${HEAD_COUNT}." >&2
  exit 1
fi
echo "[migration-test] Head único confirmado."

echo "[migration-test] Testando reversibilidade (downgrade base)..."
DATABASE_URL="${DATABASE_URL}" ${FLASK_CMD} --app run db downgrade base

echo ""
echo "[migration-test] ✅ Todas as migrations: upgrade ✓  head único ✓  downgrade ✓"
