$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "deploy/compose.yaml"

docker compose -f $ComposeFile up -d --build --wait db redis
docker compose -f $ComposeFile run --rm api alembic upgrade head
docker compose -f $ComposeFile up -d --build --wait api web
docker compose -f $ComposeFile ps

Write-Output "coreHR API: http://127.0.0.1:8000/docs"
Write-Output "coreHR Web: http://127.0.0.1:5173"

