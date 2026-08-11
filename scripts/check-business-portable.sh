#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_compose="${project_root}/deploy/compose.yaml"
test_database="corehr_test_$$"
test_database_created=false

cleanup() {
  status=$?
  trap - EXIT
  if [[ "${test_database_created}" == "true" ]]; then
    if ! docker compose -f "${base_compose}" exec -T db \
      dropdb --username corehr --if-exists --force "${test_database}"; then
      echo "Dedicated test database cleanup failed." >&2
      if [[ ${status} -eq 0 ]]; then
        status=1
      fi
    fi
  fi
  exit "${status}"
}
trap cleanup EXIT

docker compose -f "${base_compose}" build api web
docker compose -f "${base_compose}" up -d --wait db redis

docker compose -f "${base_compose}" exec -T db \
  createdb --username corehr "${test_database}"
test_database_created=true

database_password="${COREHR_DB_PASSWORD:-corehr_dev_only}"
encoded_password="$(
  docker run --rm -e "VALUE=${database_password}" corehr-api \
    python -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["VALUE"], safe=""))'
)"
test_database_url="postgresql+psycopg://corehr:${encoded_password}@db:5432/${test_database}"

docker run --rm \
  --network corehr_default \
  -v "${project_root}/apps/api:/work" \
  -w /work \
  -e PYTHONPATH=/work/src \
  -e "DATABASE_URL=${test_database_url}" \
  -e "TEST_DATABASE_URL=${test_database_url}" \
  corehr-api \
  sh -c "alembic -c alembic-business.ini upgrade head && python -m compileall -q src && pytest -q && alembic -c alembic-business.ini check"

docker run --rm corehr-web \
  sh -c "npm run test:run && npx tsc -b && npx vite build --config vite.business.config.ts"
