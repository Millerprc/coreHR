#!/usr/bin/env bash

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
docker compose -f "$repository_root/deploy/compose.yaml" down

