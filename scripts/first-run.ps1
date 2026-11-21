$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Check .env for local-only settings before continuing."
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed." }
docker compose ps
Invoke-RestMethod http://localhost:8000/api/v1/health/live
