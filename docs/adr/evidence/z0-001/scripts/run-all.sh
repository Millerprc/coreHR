#!/usr/bin/env bash
# Z0-001 复跑脚本 (POSIX / Git Bash)
# 在干净环境中重新拉取镜像、安装依赖、运行测试与构建。

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] pull images"
docker pull --quiet postgres:16.14-alpine
docker pull --quiet redis:7.4.10-alpine
docker pull --quiet python:3.13-slim
docker pull --quiet node:24.18.1-alpine

echo "[2/4] start pg + redis"
docker compose up -d pg redis
docker compose wait pg redis

echo "[3/4] run backend (pytest + db verify)"
docker compose run --rm backend

echo "[4/4] run web (vitest + build)"
docker compose run --rm web

echo "Z0-001 verify: OK"
