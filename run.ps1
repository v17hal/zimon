# ZIMON Launcher Script (PowerShell)
# This script activates the virtual environment and runs ZIMON

Write-Host "Starting ZIMON..." -ForegroundColor Cyan
Write-Host ""

# Navigate to parent directory where .venv is located
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$parentDir = Split-Path -Parent $scriptPath
Set-Location $parentDir

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
    Write-Host "Virtual environment activated." -ForegroundColor Green
    Write-Host ""
    
    # Navigate back to ZEBB_code directory
    Set-Location "ZEBB_code"
    
    # Run the application
    python main.py
} else {
    Write-Host "Error: Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please create a virtual environment first."
    Read-Host "Press Enter to exit"
    exit 1
}




