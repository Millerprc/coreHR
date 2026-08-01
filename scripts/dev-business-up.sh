#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_compose="${project_root}/deploy/compose.yaml"
business_compose="${project_root}/deploy/compose.business.yaml"

docker compose -f "${base_compose}" -f "${business_compose}" up -d --build --wait
docker compose -f "${base_compose}" -f "${business_compose}" exec api alembic upgrade head

echo "coreHR business stack is ready"
echo "Web: http://127.0.0.1:5173"
echo "API docs: http://127.0.0.1:8000/docs"
