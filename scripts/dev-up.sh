#!/usr/bin/env bash

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
compose_file="$repository_root/deploy/compose.yaml"

docker compose -f "$compose_file" up -d --build --wait db redis
docker compose -f "$compose_file" run --rm api alembic upgrade head
docker compose -f "$compose_file" up -d --build --wait api web
docker compose -f "$compose_file" ps

echo "coreHR API: http://127.0.0.1:8000/docs"
echo "coreHR Web: http://127.0.0.1:5173"

