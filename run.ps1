<#
Launches the Capital Infusion web app from this checkout, using the project venv.

Usage:
  .\run.ps1                            # http://127.0.0.1:5000, the default data directory
  .\run.ps1 -Port 5050                 # serve on a different loopback port
  .\run.ps1 -DataDir D:\statement-data # another data directory (absolute, outside this checkout)
  .\run.ps1 -BindAll                   # all interfaces: a trusted network only (see below)

Statements are read on this machine only: native PDF text first, then local
Tesseract for scans. No model runs and no endpoint is configured.

Without -DataDir the data directory is $env:WEBAPP_DATA_DIR when the shell sets
it, otherwise %USERPROFILE%\.local\share\bank-statement-analysis\phase31-private\webapp_data.
The launcher passes the folder it prints to the app, so a WEBAPP_DATA_DIR line
in .env is not used here. The app refuses a data directory that is relative or
inside the checkout.

The app serves through waitress on 127.0.0.1 only. It has no authentication
yet, and the statements it holds are the applicant's full banking history, so
-BindAll must stay a deliberate choice on a trusted network, never a default.
#>
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5000,
    [string]$DataDir = "",
    [switch]$BindAll
)

$root = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')

function Get-DataDirProblem([string]$Path) {
    # The app repeats this check with symlinks resolved and refuses to start on a bad path;
    # checking here only gives the message before anything starts.
    if ($Path -notmatch '^(?:[A-Za-z]:[\\/]|[\\/]{2})') { return "it must be an absolute path" }
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full -ieq $root -or $full.StartsWith("$root\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return "it must be outside this checkout"
    }
    return ""
}

# The data directory the app will use, checked before anything starts.
if ($DataDir) {
    $dataSource = "-DataDir"
    $dataPath = $DataDir
} elseif ($env:WEBAPP_DATA_DIR) {
    $dataSource = "WEBAPP_DATA_DIR"
    $dataPath = $env:WEBAPP_DATA_DIR
} else {
    $dataSource = "default"
    $privateRoot = if ($env:VISUAL_PAIR_PRIVATE_ROOT) { $env:VISUAL_PAIR_PRIVATE_ROOT } else {
        Join-Path $env:USERPROFILE ".local\share\bank-statement-analysis\phase31-private"
    }
    $dataPath = Join-Path $privateRoot "webapp_data"
}
$problem = Get-DataDirProblem $dataPath
if ($problem) {
    Write-Host "Data directory refused ($dataSource): $problem." -ForegroundColor Red
    exit 1
}
$dataFull = [System.IO.Path]::GetFullPath($dataPath)

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "venv Python not found at $py" -ForegroundColor Red
    Write-Host "Create it once:  py -3.12 -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-analysis.txt"
    exit 1
}

# On Windows the app runs pdfinfo from POPPLER_PATH (or its default folder) and never searches PATH.
# Without it every upload is refused. This check reads the shell's POPPLER_PATH, not .env.
$poppler = if ($env:POPPLER_PATH) { $env:POPPLER_PATH } else { "C:\poppler-24.08.0\Library\bin" }
if (-not (Test-Path (Join-Path $poppler "pdfinfo.exe"))) {
    Write-Host "pdfinfo.exe not found in $poppler" -ForegroundColor Red
    Write-Host "Install poppler there, or set `$env:POPPLER_PATH in this shell to the folder that holds pdfinfo.exe."
    exit 1
}

# Tesseract is optional: without it scanned statements are not read (digital ones still are).
$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue

# The retired model switches. Each one turns a model path on only at "1" or an exact opt-in literal.
$retired = "OCR_ALLOW_VISUAL_PAIR", "OCR_VISUAL_PAIR_LEGACY_VISUAL", "OCR_REMOTE_OPT_IN",
           "HOSTED_EXTRACTION_OPT_IN", "VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN"

# Saved and restored, so this session's environment is left as it was found.
# (Remove-Item, not SetEnvironmentVariable with $null: PowerShell 7 would leave an empty variable behind.)
$names = @("WEBAPP_HOST", "WEBAPP_PORT", "WEBAPP_DATA_DIR") + $retired
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }

$code = 0
Push-Location $root
try {
    # Pinned to "0" for this run, not removed: the app's .env loader never overrides a variable
    # that is set, so neither an inherited shell value nor a .env line can turn a model path on.
    foreach ($name in $retired) { Set-Item "Env:$name" "0" }
    $env:WEBAPP_PORT = "$Port"
    $env:WEBAPP_HOST = if ($BindAll) { "0.0.0.0" } else { "127.0.0.1" }
    $env:WEBAPP_DATA_DIR = $dataFull

    Write-Host ""
    Write-Host "Server : waitress on $($env:WEBAPP_HOST):$Port" -ForegroundColor Cyan
    Write-Host "Data   : $dataFull ($dataSource)" -ForegroundColor Cyan
    if ($tesseract) {
        Write-Host "Scans  : local Tesseract ($($tesseract.Source))" -ForegroundColor Cyan
    } else {
        Write-Host "Scans  : tesseract is not on PATH, so scanned statements will not be read" -ForegroundColor Yellow
    }
    if ($BindAll) {
        Write-Host "WARNING: bound to all interfaces with no authentication." -ForegroundColor Red
    }
    Write-Host "Open http://127.0.0.1:$Port   (Ctrl+C to stop)" -ForegroundColor Green
    Write-Host ""

    & $py -m webapp.app
    $code = $LASTEXITCODE
} finally {
    foreach ($name in $names) {
        if ($null -eq $saved[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
        else { Set-Item "Env:$name" $saved[$name] }
    }
    Pop-Location
}
exit $code
