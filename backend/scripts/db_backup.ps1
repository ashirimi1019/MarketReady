param(
  [string]$OutputFile = "backups/market_pathways_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
)

if (-not $env:DATABASE_URL) {
  Write-Error "DATABASE_URL is not set."
  exit 1
}

$outputDir = Split-Path -Path $OutputFile -Parent
if ($outputDir -and -not (Test-Path $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir | Out-Null
}

pg_dump $env:DATABASE_URL --format=plain --no-owner --no-privileges --file $OutputFile
if ($LASTEXITCODE -ne 0) {
  Write-Error "Backup failed."
  exit 1
}

Write-Output "Backup created: $OutputFile"
