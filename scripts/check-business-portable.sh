#!/usr/bin/env bash

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

# 许可证声明守卫：公开仓里每一份源文件都必须带版权与许可证指向（Requirement: D-108）。
# 在容器里跑是因为它需要遍历整个仓库（apps/** 与 scripts/**），而不是只有 apps/web。
docker run --rm \
  -v "${project_root}:/repo" \
  -w /repo \
  corehr-web \
  node scripts/check-license-header.mjs

# 私有实现防误发守卫（Requirement: D-108）：在公开仓分发前抓到 packages/ 误入版本控制。
# 这一条在**宿主机**跑 —— 守卫要读 git 的已跟踪文件清单，而镜像里没有 git。
# 前提：宿主机装了 node 与 git。
if ! command -v node >/dev/null 2>&1; then
  echo "Private package isolation guard requires Node.js on the host." >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo "Private package isolation guard requires git on the host." >&2
  exit 1
fi
node "${project_root}/scripts/check-private-package-isolation.mjs"

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
