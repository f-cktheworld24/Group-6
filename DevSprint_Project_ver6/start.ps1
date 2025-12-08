$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
$runner = $python.Path
& $runner -m pip install -r (Join-Path $root "backend\requirements.txt")
& $runner -m pip install uvicorn
$env:DATABASE_URL = "sqlite:///./devsprint.db"
$env:DEVSPRINT_REVIEWERS = "alice,bob,carol"
$env:DEVSPRINT_REVIEW_SLA_DAYS = "2"
$env:DEVSPRINT_WIP_IN_PROGRESS = "3"
$env:DEVSPRINT_WIP_CODE_REVIEW = "2"
Start-Process -FilePath $runner -ArgumentList "-m","uvicorn","backend.main:app","--reload" -WorkingDirectory $root
$nodeDir = Join-Path $root ".node_portable\node-v20.16.0-win-x64"
if (-not (Test-Path $nodeDir)) {
  $zip = Join-Path $root ".node_portable.zip"
  Invoke-WebRequest -Uri "https://nodejs.org/dist/v20.16.0/node-v20.16.0-win-x64.zip" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath (Join-Path $root ".node_portable")
  Remove-Item $zip -Force
}
$npm = Join-Path $nodeDir "npm.cmd"
$env:REACT_APP_API_BASE = "http://127.0.0.1:8000"
Start-Process -FilePath $npm -ArgumentList "install","--no-fund","--no-audit" -WorkingDirectory (Join-Path $root "frontend") -Wait
Start-Process -FilePath $npm -ArgumentList "start" -WorkingDirectory (Join-Path $root "frontend")
Start-Process "http://localhost:3000"
