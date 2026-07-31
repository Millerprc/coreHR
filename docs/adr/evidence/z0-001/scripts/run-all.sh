#!/usr/bin/env bash
# Z0-001 复跑脚本 (POSIX / Git Bash)
# 在干净 Docker 环境中拉取镜像、起 PG/Redis、跑后端测试、跑前端测试与构建。
# 失败或成功都执行 docker compose down -v，避免残留容器。

set -euo pipefail

cd "$(dirname "$0")/.."

cleanup() {
  echo "[cleanup] docker compose down -v"
  docker compose down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "[1/4] pull images"
docker pull --quiet postgres:16.14-alpine
docker pull --quiet redis:7.4.10-alpine
docker pull --quiet python:3.13.14-slim
docker pull --quiet node:24.18.1-alpine

echo "[2/4] start pg + redis (wait healthy)"
docker compose up -d --wait pg redis

echo "[3/4] run backend (pip install --require-hashes + pytest + db verify)"
docker compose run --rm backend

echo "[4/4] run web (npm ci + vitest --maxWorkers=1 + build)"
docker compose run --rm --no-deps web

echo "Z0-001 verify: OK"
