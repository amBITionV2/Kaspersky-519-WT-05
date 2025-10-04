# One-click launcher for the Flask Community Help Platform (PowerShell version)
# This script activates the virtual environment, installs requirements, and runs the app

Write-Host "Flask Community Help Platform Launcher" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# Check if virtual environment exists
if (!(Test-Path "myenv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv myenv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create virtual environment. Please ensure Python is installed." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\myenv\Scripts\Activate.ps1"

# Check if activation was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to activate virtual environment." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install/update requirements
Write-Host "Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.app.txt

# Check if pip install was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install requirements. Please check your requirements.app.txt file." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Run the Flask application
Write-Host "Starting Flask application..." -ForegroundColor Green
Write-Host ""
Write-Host "The app will be available at: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""
python app.py

# If the app exits, keep the window open
Read-Host "Press Enter to exit"
