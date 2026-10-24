# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

    # 许可证声明守卫：公开仓里每一份源文件都必须带版权与许可证指向（Requirement: D-108）。
    # 在容器里跑是因为它需要遍历整个仓库（apps/** 与 scripts/**），而不是只有 apps/web。
    docker run --rm `
        -v "${projectRoot}:/repo" `
        -w /repo `
        corehr-web `
        node scripts/check-license-header.mjs
    if ($LASTEXITCODE -ne 0) { throw "License header guard failed with exit code $LASTEXITCODE." }

    # 私有实现防误发守卫（Requirement: D-108）：在公开仓分发前抓到 packages/ 误入版本控制。
    # 这一条在宿主机跑 —— 守卫要读 git 的已跟踪文件清单，而镜像里没有 git。
    # 前提：宿主机装了 node 与 git。
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "Private package isolation guard requires Node.js on the host."
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Private package isolation guard requires git on the host."
    }
    node (Join-Path $projectRoot "scripts/check-private-package-isolation.mjs")
    if ($LASTEXITCODE -ne 0) { throw "Private package isolation guard failed with exit code $LASTEXITCODE." }

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
        sh -c "node scripts/check-antd-usage.mjs && npm run test:run && npx tsc -b && npx vite build --config vite.business.config.ts"
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
