#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_compose="${project_root}/deploy/compose.yaml"

docker compose -f "${base_compose}" build api web
docker compose -f "${base_compose}" up -d --wait db redis

docker run --rm \
  -v "${project_root}/apps/api:/work" \
  -w /work \
  -e PYTHONPATH=/work/src \
  corehr-api \
  sh -c "python -m compileall -q src && pytest -q"

docker run --rm corehr-web \
  sh -c "npm run test:run && npx tsc -b && npx vite build --config vite.business.config.ts"

docker compose -f "${base_compose}" run --rm \
  -v "${project_root}/apps/api:/work" \
  -w /work \
  -e PYTHONPATH=/work/src \
  api \
  alembic -c alembic-business.ini check
