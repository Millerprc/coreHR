$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$baseCompose = Join-Path $projectRoot "deploy/compose.yaml"

Push-Location $projectRoot
try {
    docker compose -f $baseCompose build api web
    docker compose -f $baseCompose up -d --wait db redis

    docker run --rm `
        -v "${projectRoot}/apps/api:/work" `
        -w /work `
        -e PYTHONPATH=/work/src `
        corehr-api `
        sh -c "python -m compileall -q src && pytest -q"

    docker run --rm corehr-web `
        sh -c "npm run test:run && npx tsc -b && npx vite build --config vite.business.config.ts"

    docker run --rm `
        --network corehr_default `
        -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr `
        -e PYTHONPATH=/work/src `
        -v "${projectRoot}/apps/api:/work" `
        -w /work `
        corehr-api `
        alembic -c alembic-business.ini check
} finally {
    Pop-Location
}
