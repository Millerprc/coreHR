$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$baseCompose = Join-Path $projectRoot "deploy/compose.yaml"
$businessCompose = Join-Path $projectRoot "deploy/compose.business.yaml"

docker compose -f $baseCompose -f $businessCompose up -d --build --wait
docker compose -f $baseCompose -f $businessCompose exec api alembic upgrade head

Write-Host "coreHR business stack is ready"
Write-Host "Web: http://127.0.0.1:5173"
Write-Host "API docs: http://127.0.0.1:8000/docs"
