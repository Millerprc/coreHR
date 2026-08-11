$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$baseCompose = Join-Path $projectRoot "deploy/compose.yaml"
$testDatabase = "corehr_test_$PID"
$testDatabaseCreated = $false
$verificationError = $null
$cleanupExitCode = 0

Push-Location $projectRoot
try {
    docker compose -f $baseCompose build api web
    if ($LASTEXITCODE -ne 0) { throw "Docker image build failed with exit code $LASTEXITCODE." }

    docker compose -f $baseCompose up -d --wait db redis
    if ($LASTEXITCODE -ne 0) { throw "Docker dependencies failed to start with exit code $LASTEXITCODE." }

    docker compose -f $baseCompose exec -T db createdb --username corehr $testDatabase
    if ($LASTEXITCODE -ne 0) { throw "Dedicated test database creation failed with exit code $LASTEXITCODE." }
    $testDatabaseCreated = $true

    $databasePassword = if ($env:COREHR_DB_PASSWORD) { $env:COREHR_DB_PASSWORD } else { "corehr_dev_only" }
    $encodedPassword = [System.Uri]::EscapeDataString($databasePassword)
    $testDatabaseUrl = "postgresql+psycopg://corehr:${encodedPassword}@db:5432/$testDatabase"

    docker run --rm `
        --network corehr_default `
        -v "${projectRoot}/apps/api:/work" `
        -w /work `
        -e PYTHONPATH=/work/src `
        -e "DATABASE_URL=$testDatabaseUrl" `
        -e "TEST_DATABASE_URL=$testDatabaseUrl" `
        corehr-api `
        sh -c "alembic -c alembic-business.ini upgrade head && python -m compileall -q src && pytest -q && alembic -c alembic-business.ini check"
    if ($LASTEXITCODE -ne 0) { throw "Backend checks failed with exit code $LASTEXITCODE." }

    docker run --rm corehr-web `
        sh -c "npm run test:run && npx tsc -b && npx vite build --config vite.business.config.ts"
    if ($LASTEXITCODE -ne 0) { throw "Frontend checks failed with exit code $LASTEXITCODE." }

} catch {
    $verificationError = $_
} finally {
    if ($testDatabaseCreated) {
        docker compose -f $baseCompose exec -T db dropdb --username corehr --if-exists --force $testDatabase
        $cleanupExitCode = $LASTEXITCODE
    }
    Pop-Location
}

if ($null -ne $verificationError) { throw $verificationError }
if ($cleanupExitCode -ne 0) { throw "Dedicated test database cleanup failed with exit code $cleanupExitCode." }
