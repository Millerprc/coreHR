$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "deploy/compose.yaml"

docker compose -f $ComposeFile up -d --build --wait db redis
if ($LASTEXITCODE -ne 0) { throw "Docker dependencies failed to start with exit code $LASTEXITCODE." }

docker compose -f $ComposeFile run --rm api alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed with exit code $LASTEXITCODE." }

docker compose -f $ComposeFile up -d --build --wait api web
if ($LASTEXITCODE -ne 0) { throw "coreHR services failed to start with exit code $LASTEXITCODE." }

docker compose -f $ComposeFile ps
if ($LASTEXITCODE -ne 0) { throw "Docker service status check failed with exit code $LASTEXITCODE." }

Write-Output "coreHR API: http://127.0.0.1:8000/docs"
Write-Output "coreHR Web: http://127.0.0.1:5173"
