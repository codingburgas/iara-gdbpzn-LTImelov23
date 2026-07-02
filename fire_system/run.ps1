$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $scriptDir

$python = Join-Path $scriptDir "venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python app.py
} else {
    Write-Host "Virtual environment not found. Run setup.bat first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
