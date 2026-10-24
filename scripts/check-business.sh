#!/usr/bin/env bash

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

docker run --rm \
  --network corehr_default \
  -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr \
  -e PYTHONPATH=/work/src \
  -v "${project_root}/apps/api:/work" \
  -w /work \
  corehr-api \
  alembic -c alembic-business.ini check
