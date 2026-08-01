#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
docker compose -f "$repository_root/deploy/compose.yaml" down

