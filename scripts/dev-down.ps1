$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "deploy/compose.yaml"

docker compose -f $ComposeFile down
if ($LASTEXITCODE -ne 0) { throw "coreHR services failed to stop with exit code $LASTEXITCODE." }
