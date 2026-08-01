#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
compose_file="$repository_root/deploy/compose.yaml"

cleanup() {
  docker compose -f "$compose_file" down
}
trap cleanup EXIT

docker compose -f "$compose_file" up -d --build --wait db redis
docker compose -f "$compose_file" run --rm api alembic upgrade head
docker compose -f "$compose_file" run --rm api pytest -q
docker compose -f "$compose_file" run --rm --no-deps web npm run test:run
docker compose -f "$compose_file" run --rm --no-deps web npm run build

