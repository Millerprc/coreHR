# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

$ErrorActionPreference = "Stop"
$composeFile = Join-Path (Split-Path -Parent $PSScriptRoot) "deploy/compose.yaml"
$verificationError = $null
$cleanupExitCode = 0

try {
    & (Join-Path $PSScriptRoot "check-business-portable.ps1")
} catch {
    $verificationError = $_
} finally {
    docker compose -f $composeFile down
    $cleanupExitCode = $LASTEXITCODE
}

if ($null -ne $verificationError) { throw $verificationError }
if ($cleanupExitCode -ne 0) { throw "Docker cleanup failed with exit code $cleanupExitCode." }
