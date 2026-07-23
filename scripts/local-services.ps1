param(
  [Parameter(Position = 0)]
  [ValidateSet("up", "down", "status", "logs")]
  [string]$Action = "up"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$runtimeDir = Join-Path ([System.IO.Path]::GetTempPath()) "fast-vben-admin-local"
$stateFile = Join-Path $runtimeDir "processes.json"

function Get-LocalState {
  if (-not (Test-Path -LiteralPath $stateFile)) {
    return @()
  }
  return @(Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json)
}

function Test-StateProcess {
  param($Entry)

  $process = Get-Process -Id $Entry.pid -ErrorAction SilentlyContinue
  if (-not $process) {
    return $false
  }
  try {
    return $process.StartTime.ToFileTimeUtc() -eq [long]$Entry.startedAt
  }
  catch {
    return $false
  }
}

function Stop-LocalProcesses {
  $state = Get-LocalState
  foreach ($entry in @($state | Sort-Object pid -Descending)) {
    if (-not (Test-StateProcess $entry)) {
      continue
    }
    Write-Host "Stopping $($entry.name) (PID $($entry.pid))..."
    & taskkill.exe /PID $entry.pid /T /F 2>$null | Out-Null
  }
  Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
}

function Show-LocalStatus {
  $state = Get-LocalState
  if ($state.Count -eq 0) {
    Write-Host "No locally managed services are recorded."
    return
  }
  foreach ($entry in $state) {
    $status = if (Test-StateProcess $entry) { "running" } else { "stopped" }
    Write-Host ("{0,-18} {1,-8} PID {2}" -f $entry.name, $status, $entry.pid)
  }
}

function Show-LocalLogs {
  $state = Get-LocalState
  if ($state.Count -eq 0) {
    $logFiles = @(Get-ChildItem -LiteralPath $runtimeDir -Filter "*.log" -ErrorAction SilentlyContinue)
    if ($logFiles.Count -eq 0) {
      Write-Host "No local service logs are available."
      return
    }
    foreach ($logFile in $logFiles) {
      if ($logFile.Length -gt 0) {
        Write-Host "`n[$($logFile.BaseName)] $($logFile.FullName)"
        Get-Content -LiteralPath $logFile.FullName -Tail 30
      }
    }
    return
  }
  foreach ($entry in $state) {
    foreach ($path in @($entry.stdout, $entry.stderr)) {
      if ((Test-Path -LiteralPath $path) -and (Get-Item $path).Length -gt 0) {
        Write-Host "`n[$($entry.name)] $path"
        Get-Content -LiteralPath $path -Tail 30
      }
    }
  }
}

function Import-DotEnv {
  $envPath = Join-Path $root ".env"
  if (-not (Test-Path -LiteralPath $envPath)) {
    throw ".env is missing. Create it before starting local services."
  }
  foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
      continue
    }
    $name = $Matches[1]
    $value = $Matches[2]
    Set-Item -Path "Env:$name" -Value $value
  }
}

function Assert-Command {
  param([string]$Name)

  $command = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "Required command '$Name' was not found in PATH."
  }
  return $command.Source
}

function Test-TcpPort {
  param(
    [string]$ComputerName,
    [int]$Port
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $connect = $client.ConnectAsync($ComputerName, $Port)
    return $connect.Wait(2000) -and $client.Connected
  }
  catch {
    return $false
  }
  finally {
    $client.Dispose()
  }
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList
  )

  & $FilePath @ArgumentList
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
  }
}

function Start-ManagedProcess {
  param(
    [string]$Name,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory
  )

  $stdout = Join-Path $runtimeDir "$Name.out.log"
  $stderr = Join-Path $runtimeDir "$Name.err.log"
  Set-Content -LiteralPath $stdout -Value ""
  Set-Content -LiteralPath $stderr -Value ""
  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru
  return [pscustomobject]@{
    name = $Name
    pid = $process.Id
    startedAt = $process.StartTime.ToFileTimeUtc()
    stdout = $stdout
    stderr = $stderr
  }
}

function Wait-ForHttp {
  param(
    [string]$Name,
    [string]$Url,
    [int]$TimeoutSeconds,
    $ProcessEntry
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (-not (Test-StateProcess $ProcessEntry)) {
      throw "$Name exited before becoming ready. Run 'pnpm local:logs' for details."
    }
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return
      }
    }
    catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "$Name did not become ready within $TimeoutSeconds seconds."
}

switch ($Action) {
  "down" {
    Stop-LocalProcesses
    Write-Host "Local application services stopped. PostgreSQL and Redis were left running."
    exit 0
  }
  "status" {
    Show-LocalStatus
    exit 0
  }
  "logs" {
    Show-LocalLogs
    exit 0
  }
}

$existing = @(Get-LocalState | Where-Object { Test-StateProcess $_ })
if ($existing.Count -gt 0) {
  Show-LocalStatus
  throw "Local services are already running. Use 'pnpm local:down' first."
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
Import-DotEnv

$uv = Assert-Command "uv"
$pnpm = Assert-Command "pnpm.cmd"
$node = Assert-Command "node"

$requiredVariables = @(
  "POSTGRES_SERVER",
  "POSTGRES_PORT",
  "POSTGRES_DB",
  "POSTGRES_USER",
  "POSTGRES_PASSWORD",
  "APP_RUNTIME_DB_USER",
  "APP_RUNTIME_DB_PASSWORD",
  "REDIS_URL"
)
foreach ($name in $requiredVariables) {
  if ([string]::IsNullOrWhiteSpace((Get-Item -Path "Env:$name").Value)) {
    throw "Required environment variable '$name' is empty."
  }
}

if (-not (Test-TcpPort $env:POSTGRES_SERVER ([int]$env:POSTGRES_PORT))) {
  throw "PostgreSQL is not reachable at $($env:POSTGRES_SERVER):$($env:POSTGRES_PORT)."
}
$redisUri = [Uri]$env:REDIS_URL
if (-not (Test-TcpPort $redisUri.Host $redisUri.Port)) {
  throw "Redis is not reachable at $($redisUri.Host):$($redisUri.Port)."
}
if (Test-TcpPort "127.0.0.1" 8001) {
  throw "Port 8001 is already in use."
}
if (Test-TcpPort "127.0.0.1" 5173) {
  throw "Port 5173 is already in use."
}

Write-Host "Synchronizing backend dependencies..."
Push-Location $backend
try {
  Invoke-Checked $uv @("sync")
}
finally {
  Pop-Location
}

Write-Host "Installing frontend dependencies..."
Invoke-Checked $pnpm @("--dir", $frontend, "install")

Write-Host "Generating frontend contracts for the $($env:APP_EDITION) edition..."
Invoke-Checked $node @(
  (Join-Path $root "scripts\generate-openapi.mjs"),
  "--edition",
  $env:APP_EDITION
)

$python = Join-Path $backend ".venv\Scripts\python.exe"
$adminUser = $env:POSTGRES_USER
$adminPassword = $env:POSTGRES_PASSWORD

Write-Host "Provisioning database role and applying suite migrations..."
Push-Location $backend
try {
  Invoke-Checked $python @("-m", "app.platform.provision_db_roles")
  Invoke-Checked $python @("-m", "app.modules.migrate", "--edition", $env:APP_EDITION)
  Invoke-Checked $python @("-m", "app.platform.provision_db_roles")

  $env:POSTGRES_USER = $env:APP_RUNTIME_DB_USER
  $env:POSTGRES_PASSWORD = $env:APP_RUNTIME_DB_PASSWORD
  Invoke-Checked $python @("-m", "app.initial_data")
}
catch {
  $env:POSTGRES_USER = $adminUser
  $env:POSTGRES_PASSWORD = $adminPassword
  Pop-Location
  throw
}
Pop-Location

$processes = @()
try {
  Write-Host "Starting API, workers, and frontend..."
  $processes += Start-ManagedProcess "backend" $python @(
    "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"
  ) $backend
  $processes += Start-ManagedProcess "outbox-worker" $python @(
    "-m", "app.modules.outbox_worker"
  ) $backend
  $processes += Start-ManagedProcess "schedule-worker" $python @(
    "-m", "app.modules.schedule_worker"
  ) $backend
  $processes += Start-ManagedProcess "frontend" $pnpm @(
    "--dir", $frontend, "-F", "@vben/web-antd", "run", "dev"
  ) $root

  $processes | ConvertTo-Json | Set-Content -LiteralPath $stateFile
  Wait-ForHttp "Backend" "http://127.0.0.1:8001/api/v1/utils/health-check" 90 $processes[0]
  Wait-ForHttp "Frontend" "http://127.0.0.1:5173" 120 $processes[3]
}
catch {
  $processes | ConvertTo-Json | Set-Content -LiteralPath $stateFile
  Stop-LocalProcesses
  throw
}

Write-Host ""
Write-Host "All local services are running."
Write-Host "Frontend: http://localhost:5173"
Write-Host "API docs: http://localhost:8001/docs"
Write-Host "Use 'pnpm local:status', 'pnpm local:logs', or 'pnpm local:down'."
