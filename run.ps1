<#
Launches the local Unlimited-OCR web app using the project venv.

Usage:
  .\run.ps1 -PodId jy39vysntpffa0     # derive endpoint + key from a RunPod pod id
  .\run.ps1                           # use existing $env:OCR_BASE_URL / $env:OCR_API_KEY
  .\run.ps1 -Port 5050                # serve on a different loopback port

The RunPod proxy URL is https://<PodId>-8000.proxy.runpod.net and the vLLM key
is sk-<PodId>, so passing -PodId is all you need after (re)starting a pod.

The app serves through waitress on 127.0.0.1 only. It has no authentication
yet, and the statements it holds are the applicant's full banking history, so
-BindAll must stay a deliberate choice on a trusted network — never a default.
#>
param(
    [string]$PodId = "",
    [int]$Port = 5000,
    [switch]$BindAll
)

Set-Location $PSScriptRoot

if ($PodId -ne "") {
    $env:OCR_BASE_URL = "https://$PodId-8000.proxy.runpod.net/v1"
    $env:OCR_API_KEY  = "sk-$PodId"
}

if (-not $env:OCR_BASE_URL) {
    Write-Host "No endpoint configured." -ForegroundColor Yellow
    Write-Host "Pass the RunPod pod id:  .\run.ps1 -PodId <pod-id>" -ForegroundColor Yellow
    Write-Host "or set `$env:OCR_BASE_URL and `$env:OCR_API_KEY yourself first."
    exit 1
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "venv Python not found at $py" -ForegroundColor Red
    Write-Host "Create it once:  py -3.12 -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

$env:WEBAPP_PORT = "$Port"
if ($BindAll) {
    $env:WEBAPP_HOST = "0.0.0.0"
} else {
    $env:WEBAPP_HOST = "127.0.0.1"
}

$model = if ($env:OCR_MODEL) { $env:OCR_MODEL } else { "baidu/Unlimited-OCR (default)" }
Write-Host ""
Write-Host "Endpoint : $env:OCR_BASE_URL" -ForegroundColor Cyan
Write-Host "Model    : $model" -ForegroundColor Cyan
Write-Host "Server   : waitress on $env:WEBAPP_HOST`:$Port" -ForegroundColor Cyan
if ($BindAll) {
    Write-Host "WARNING: bound to all interfaces with no authentication." -ForegroundColor Red
}
Write-Host "Open http://localhost:$Port   (Ctrl+C to stop)" -ForegroundColor Green
Write-Host ""

& $py -m webapp.app
