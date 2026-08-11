#!/usr/bin/env bash
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
