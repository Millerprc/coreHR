# Z0-001 复跑脚本 (PowerShell)
# 在干净环境中重新拉取镜像、安装依赖、运行测试与构建。

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSCommandPath) | Split-Path -Parent

Write-Output '[1/4] pull images'
docker pull --quiet postgres:16.14-alpine | Out-Null
docker pull --quiet redis:7.4.10-alpine | Out-Null
docker pull --quiet python:3.13-slim | Out-Null
docker pull --quiet node:24.18.1-alpine | Out-Null

Write-Output '[2/4] start pg + redis'
docker compose up -d pg redis
docker compose wait pg redis

Write-Output '[3/4] run backend (pytest + db verify)'
docker compose run --rm backend

Write-Output '[4/4] run web (vitest + build)'
docker compose run --rm web

Write-Output 'Z0-001 verify: OK'
