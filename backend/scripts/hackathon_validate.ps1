param(
  [string]$ApiBase = $env:API_BASE,
  [string]$UserId = $env:USER_ID,
  [string]$AuthToken = $env:AUTH_TOKEN,
  [string]$TargetJob = "software engineer",
  [string]$Location = "united states",
  [int]$AvailabilityHoursPerWeek = 20,
  [string]$RepoUrl = $env:GITHUB_REPO_URL
)

$ErrorActionPreference = "Stop"

if (-not $ApiBase) {
  $ApiBase = "http://127.0.0.1:8000"
}

if (-not $UserId) {
  $UserId = "demo-user"
}

if (-not $RepoUrl) {
  $RepoUrl = "https://github.com/$UserId"
}

$ApiBase = $ApiBase.TrimEnd("/")

function Get-BaseCandidates([string]$base) {
  $candidates = New-Object System.Collections.Generic.List[string]
  $candidates.Add($base)
  if ($base.EndsWith("/api")) {
    $candidates.Add($base.Substring(0, $base.Length - 4))
  } else {
    $candidates.Add("$base/api")
  }
  return $candidates | Select-Object -Unique
}

function Invoke-ApiPost([string]$path, [hashtable]$body, [hashtable]$headers) {
  $json = $body | ConvertTo-Json -Depth 20
  $lastErr = $null
  foreach ($base in (Get-BaseCandidates $ApiBase)) {
    try {
      return Invoke-RestMethod -Uri "$base$path" -Method Post -Headers $headers -Body $json -ContentType "application/json"
    } catch {
      $statusCode = $null
      try { $statusCode = [int]$_.Exception.Response.StatusCode } catch {}
      if ($statusCode -eq 404) {
        $lastErr = $_
        continue
      }
      throw
    }
  }
  if ($lastErr) { throw $lastErr }
  throw "No API base candidate resolved for $path"
}

function Ensure-HasField([object]$obj, [string]$fieldName, [string]$context) {
  if (-not ($null -ne $obj.PSObject.Properties[$fieldName])) {
    throw "$context missing field '$fieldName'."
  }
}

function Ensure-Array([object]$obj, [string]$fieldName, [string]$context) {
  Ensure-HasField $obj $fieldName $context
  $value = $obj.$fieldName
  if (-not ($value -is [System.Collections.IEnumerable])) {
    throw "$context field '$fieldName' is not an array."
  }
}

$headers = @{
  "X-User-Id" = $UserId
}
if ($AuthToken) {
  $headers["X-Auth-Token"] = $AuthToken
}

$report = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  api_base = $ApiBase
  user_id = $UserId
  target_job = $TargetJob
  location = $Location
  checks = [ordered]@{}
  pass = $true
}

function Add-Check([string]$name, [bool]$pass, [string]$detail, [hashtable]$data = @{}) {
  $report.checks[$name] = [ordered]@{
    pass = $pass
    detail = $detail
    data = $data
  }
  if (-not $pass) {
    $report.pass = $false
  }
}

try {
  $stress = Invoke-ApiPost "/user/ai/market-stress-test" @{
    target_job = $TargetJob
    location = $Location
  } $headers

  Ensure-HasField $stress "score" "market-stress-test"
  Ensure-HasField $stress "source_mode" "market-stress-test"
  Ensure-HasField $stress "mri_formula" "market-stress-test"
  Ensure-HasField $stress "components" "market-stress-test"
  Ensure-HasField $stress "market_volatility_points" "market-stress-test"
  Ensure-HasField $stress "top_hiring_companies" "market-stress-test"

  if (($stress.market_volatility_points | Measure-Object).Count -lt 1) {
    throw "market-stress-test returned empty market_volatility_points."
  }
  if (($stress.top_hiring_companies | Measure-Object).Count -gt 5) {
    throw "market-stress-test returned more than 5 top_hiring_companies."
  }

  Add-Check "market_stress_test" $true "Field contract + volatility/hero-list checks passed." @{
    score = $stress.score
    source_mode = $stress.source_mode
    snapshot_timestamp = $stress.snapshot_timestamp
  }
} catch {
  $message = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Check "market_stress_test" $false $message
}

try {
  $proof = Invoke-ApiPost "/user/ai/proof-checker" @{
    target_job = $TargetJob
    location = $Location
    repo_url = $RepoUrl
  } $headers

  Ensure-HasField $proof "required_skills_count" "proof-checker"
  Ensure-HasField $proof "match_count" "proof-checker"
  Ensure-HasField $proof "repo_confidence" "proof-checker"
  Ensure-HasField $proof "verified_by_repo_skills" "proof-checker"
  Ensure-HasField $proof "source_mode" "proof-checker"
  Ensure-Array $proof "files_checked" "proof-checker"
  Ensure-Array $proof "repos_checked" "proof-checker"
  Ensure-Array $proof "languages_detected" "proof-checker"

  $proofSignals = @(
    ($proof.files_checked | Measure-Object).Count,
    ($proof.repos_checked | Measure-Object).Count,
    ($proof.languages_detected | Measure-Object).Count
  ) | Measure-Object -Maximum

  if ($proofSignals.Maximum -lt 1) {
    throw "proof-checker returned no repo evidence points (files/repos/languages all empty)."
  }

  Add-Check "proof_checker" $true "Field contract + evidence checks passed." @{
    match_count = $proof.match_count
    required_skills_count = $proof.required_skills_count
    source_mode = $proof.source_mode
    snapshot_timestamp = $proof.snapshot_timestamp
  }
} catch {
  $message = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Check "proof_checker" $false $message
}

try {
  $orch = Invoke-ApiPost "/user/ai/orchestrator" @{
    target_job = $TargetJob
    location = $Location
    availability_hours_per_week = $AvailabilityHoursPerWeek
    pivot_requested = $true
  } $headers

  Ensure-HasField $orch "market_alert" "orchestrator"
  Ensure-HasField $orch "mission_dashboard" "orchestrator"
  Ensure-HasField $orch "pivot_applied" "orchestrator"
  Ensure-HasField $orch "pivot_target_role" "orchestrator"
  Ensure-HasField $orch "top_missing_skills" "orchestrator"

  if ([string]::IsNullOrWhiteSpace([string]$orch.market_alert)) {
    throw "orchestrator market_alert is empty."
  }

  $mission = $orch.mission_dashboard
  Ensure-HasField $mission "day_0_30" "orchestrator.mission_dashboard"
  Ensure-HasField $mission "day_31_60" "orchestrator.mission_dashboard"
  Ensure-HasField $mission "day_61_90" "orchestrator.mission_dashboard"

  if ((($mission.day_0_30 | Measure-Object).Count + ($mission.day_31_60 | Measure-Object).Count + ($mission.day_61_90 | Measure-Object).Count) -lt 1) {
    throw "orchestrator mission dashboard contains no task items."
  }

  Add-Check "orchestrator" $true "Field contract + mission payload checks passed." @{
    market_alert = $orch.market_alert
    pivot_applied = $orch.pivot_applied
    pivot_target_role = $orch.pivot_target_role
    pivot_delta = $orch.pivot_delta
  }
} catch {
  $message = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Check "orchestrator" $false $message
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$reportPath = Join-Path $repoRoot "backend\validation_report.json"
$report | ConvertTo-Json -Depth 20 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "Validation report written to $reportPath"
Write-Host ("Overall: " + ($(if ($report.pass) { "PASS" } else { "FAIL" })))

if (-not $report.pass) {
  exit 1
}
