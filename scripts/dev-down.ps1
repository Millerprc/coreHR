# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "deploy/compose.yaml"

docker compose -f $ComposeFile down
if ($LASTEXITCODE -ne 0) { throw "coreHR services failed to stop with exit code $LASTEXITCODE." }
