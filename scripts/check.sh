#!/usr/bin/env bash

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${repository_root}/deploy/compose.yaml"

cleanup() {
  status=$?
  trap - EXIT
  if ! docker compose -f "${compose_file}" down; then
    echo "Docker cleanup failed." >&2
    if [[ ${status} -eq 0 ]]; then
      status=1
    fi
  fi
  exit "${status}"
}
trap cleanup EXIT

"${repository_root}/scripts/check-business-portable.sh"
