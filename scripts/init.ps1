$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path -LiteralPath ".env")) {
  Copy-Item -LiteralPath ".env.example" -Destination ".env"
  Write-Host "Created .env from .env.example"
}

Write-Host "Installing backend dependencies..."
Push-Location "backend"
uv sync
Pop-Location

Write-Host "Installing frontend dependencies..."
pnpm --dir frontend install

Write-Host "Project initialized."
