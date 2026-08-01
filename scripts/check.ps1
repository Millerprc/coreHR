$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "deploy/compose.yaml"

try {
    docker compose -f $ComposeFile up -d --build --wait db redis
    docker compose -f $ComposeFile run --rm api alembic upgrade head
    docker compose -f $ComposeFile run --rm api pytest -q
    docker compose -f $ComposeFile run --rm --no-deps web npm run test:run
    docker compose -f $ComposeFile run --rm --no-deps web npm run build
}
finally {
    docker compose -f $ComposeFile down
}

