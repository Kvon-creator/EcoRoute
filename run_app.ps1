# Start EcoRoute, or open the existing local Streamlit server in your browser.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$ecoRouteUrl = "http://127.0.0.1:8501"
$ecoRouteReady = $false
try {
    $ecoRouteResponse = Invoke-WebRequest -UseBasicParsing "$ecoRouteUrl/_stcore/health" -TimeoutSec 2
    $ecoRouteReady = $ecoRouteResponse.StatusCode -eq 200 -and $ecoRouteResponse.Content.Trim() -eq "ok"
} catch {
    # No responding local Streamlit server: start the project below.
}
if ($ecoRouteReady) {
    Start-Process $ecoRouteUrl
    Write-Host "Opened the running app: $ecoRouteUrl"
    return
}
$ecoRoutePython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $ecoRoutePython)) {
    throw "Create the project's .venv and install requirements.txt first; see README.md."
}
& $ecoRoutePython -m streamlit run app.py --server.headless=false
