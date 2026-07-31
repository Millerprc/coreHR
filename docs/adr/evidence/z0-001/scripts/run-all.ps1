# Z0-001 复跑脚本 (PowerShell)
# 在干净 Docker 环境中拉取镜像、起 PG/Redis、跑后端测试、跑前端测试与构建。
# 失败或成功都执行 docker compose down -v，避免残留容器。

$ErrorActionPreference = 'Stop'

# 明确切换到 evidence 根目录
$ScriptDir = Split-Path -Parent $PSCommandPath
$EvidenceDir = Split-Path -Parent $ScriptDir
Set-Location $EvidenceDir

# finally 风格清理
$Cleanup = {
  Write-Output '[cleanup] docker compose down -v'
  docker compose down -v 2>&1 | Out-Null
}
try {
  Write-Output '[1/4] pull images'
  docker pull --quiet postgres:16.14-alpine | Out-Null
  docker pull --quiet redis:7.4.10-alpine | Out-Null
  docker pull --quiet python:3.13.14-slim | Out-Null
  docker pull --quiet node:24.18.1-alpine | Out-Null

  Write-Output '[2/4] start pg + redis (wait healthy)'
  docker compose up -d --wait pg redis

  Write-Output '[3/4] run backend (pip install --require-hashes + pytest + db verify)'
  docker compose run --rm backend

  Write-Output '[4/4] run web (npm ci + vitest --maxWorkers=1 + build)'
  docker compose run --rm --no-deps web

  Write-Output 'Z0-001 verify: OK'
}
finally {
  & $Cleanup
}
