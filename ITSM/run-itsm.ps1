#!/usr/bin/env pwsh
<#
.SYNOPSIS
    ITSM Platform - Unified Startup Script
    Runs frontend and backend simultaneously in a single terminal

.DESCRIPTION
    This script starts the ITSM Platform with both frontend and backend
    running together on port 8000. Everything is integrated in one FastAPI app.

.EXAMPLE
    .\run-itsm.ps1

.NOTES
    Requirements:
    - Python 3.10+
    - Virtual environment in ./venv
    - Dependencies installed
    Author: ITSM Platform Team
    Version: 1.1
#>

param(
    [switch]$NoReload,
    [int]$Port = 8000,
    [string]$ServerHost = "0.0.0.0", # Renamed from $Host to avoid conflict
    [switch]$Help
)

# Display help
if ($Help) {
    Write-Host @"
??????????????????????????????????????????????????????
?     ITSM Platform - Unified Startup Script        ?
??????????????????????????????????????????????????????

USAGE:
    .\run-itsm.ps1 [options]

OPTIONS:
    -NoReload           Disable auto-reload (production mode)
    -Port <number>      Use custom port (default: 8000)
    -ServerHost <host>  Bind to host (default: 0.0.0.0)
    -Help               Show this help message

EXAMPLES:
    # Normal usage (with auto-reload)
    .\run-itsm.ps1

    # Production mode (no reload)
    .\run-itsm.ps1 -NoReload

    # Custom port
    .\run-itsm.ps1 -Port 9000

    # Localhost only
    .\run-itsm.ps1 -ServerHost localhost

ONCE STARTED, VISIT:
    ?? http://localhost:$Port/              (Frontend)
    ?? http://localhost:$Port/docs          (API Documentation)
    ?? http://localhost:$Port/redoc         (Alternative API Docs)

SHORTCUTS:
    Press Ctrl+C to stop the server
    All changes auto-reload (unless -NoReload specified)

FOR MORE INFORMATION:
    See START_HERE.md or QUICK_START.md
"@
    exit 0
}

# Colors for output
$colors = @{
    Success = 'Green'
    Error   = 'Red'
    Warning = 'Yellow'
    Info    = 'Cyan'
    Header  = 'Magenta'
}

function Write-Info {
    param([string]$Message)
    Write-Host "??  $Message" -ForegroundColor $colors.Info
}

function Write-Success {
    param([string]$Message)
    Write-Host "? $Message" -ForegroundColor $colors.Success
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "? $Message" -ForegroundColor $colors.Error
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "??  $Message" -ForegroundColor $colors.Warning
}

function Write-Header {
    param([string]$Message)
    Write-Host "`n$Message" -ForegroundColor $colors.Header
}

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Ensure console uses UTF-8 so Unicode box/line characters render correctly
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = New-Object System.Text.UTF8Encoding
} catch {
    # If the host doesn't support setting encoding, continue without failing
}

# Clear screen
Clear-Host

# Display banner
Write-Host @"
????????????????????????????????????????????????????????????????
?                                                              ?
?          ?? ITSM PLATFORM - STARTING UP ??                 ?
?                                                              ?
?        Frontend & Backend Running Together                  ?
?        All on Port $Port                                      ?
?                                                              ?
????????????????????????????????????????????????????????????????
"@ -ForegroundColor Cyan

# Step 1: Check Python
Write-Header "[STEP 1] Checking Python Installation..."
try {
    $pythonVersion = python --version 2>&1
    Write-Success "Python found: $pythonVersion"
} catch {
    Write-Error-Custom "Python not found! Please install Python 3.10+"
    Write-Info "Download from: https://www.python.org/downloads/"
    exit 1
}

# Step 2: Check virtual environment
Write-Header "[STEP 2] Checking Virtual Environment..."
$venvPath = ".\venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvPath)) {
    Write-Error-Custom "Virtual environment not found!"
    Write-Info "Creating virtual environment..."
    python -m venv venv
    if ($?) {
        Write-Success "Virtual environment created"
    } else {
        Write-Error-Custom "Failed to create virtual environment"
        exit 1
    }
}

# Step 3: Activate virtual environment
Write-Header "[STEP 3] Activating Virtual Environment..."
& $venvPath
if ($?) {
    Write-Success "Virtual environment activated"
} else {
    Write-Error-Custom "Failed to activate virtual environment"
    exit 1
}

# Step 4: Check dependencies
Write-Header "[STEP 4] Checking Dependencies..."
$requiredPackages = @('fastapi', 'uvicorn', 'sqlalchemy', 'pydantic', 'python-dotenv')
$missingPackages = @()

foreach ($package in $requiredPackages) {
    try {
        python -c "import $($package -replace '-', '_')" 2>&1 | Out-Null
        Write-Success "$package ?"
    } catch {
        $missingPackages += $package
        Write-Warning-Custom "$package ?"
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Header "[INSTALLING] Missing Packages..."
    Write-Info "Installing: $($missingPackages -join ', ')"
    pip install $missingPackages
    if ($?) {
        Write-Success "Dependencies installed successfully"
    } else {
        Write-Error-Custom "Failed to install dependencies"
        exit 1
    }
}

# Step 5: Check database
Write-Header "[STEP 5] Checking Database..."
if (Test-Path "app.db") {
    Write-Success "Database found (app.db)"
} else {
    Write-Info "Database will be auto-created on startup"
}

# Step 6: Display startup information
Write-Header "[STEP 6] Startup Information..."
Write-Host @"

?? FRONTEND:
   • Dashboard:  http://localhost:$Port/
   • Login:      http://localhost:$Port/login
   • Tickets:    http://localhost:$Port/tickets
   • All pages:  http://localhost:$Port/ (use sidebar)

?? BACKEND:
   • API Root:   http://localhost:$Port/api/
   • Docs:       http://localhost:$Port/docs (Swagger)
   • ReDoc:      http://localhost:$Port/redoc

?? DATABASE:
   • Type:       SQLite3
   • Location:   ./app.db
   • Status:     Auto-initialized

??  SERVER:
   • Host:       $ServerHost
   • Port:       $Port
   • Reload:     $(if ($NoReload) { "Disabled" } else { "Enabled" })
   • Workers:    1

"@ -ForegroundColor Cyan

# Step 7: Start application
Write-Header "[STEP 7] Starting Application..."
Write-Info "Initializing FastAPI application..."

$reloadOption = if ($NoReload) { "--no-reload" } else { "--reload" }

Write-Host ""
Write-Host "????????????????????????????????????????????????????????????????" -ForegroundColor Green
Write-Host "?                   APPLICATION STARTING                      ?" -ForegroundColor Green
Write-Host "?                   Waiting for server...                     ?" -ForegroundColor Green
Write-Host "????????????????????????????????????????????????????????????????" -ForegroundColor Green
Write-Host ""

# Execute uvicorn
if ($NoReload) {
    uvicorn app.main:app --host $ServerHost --port $Port --no-reload
} else {
    uvicorn app.main:app --host $ServerHost --port $Port --reload
}

# If we get here, server was stopped
Write-Host ""
Write-Host "????????????????????????????????????????????????????????????????" -ForegroundColor Yellow
Write-Host "?                   SERVER STOPPED                            ?" -ForegroundColor Yellow
Write-Host "?              Thank you for using ITSM Platform!             ?" -ForegroundColor Yellow
Write-Host "????????????????????????????????????????????????????????????????" -ForegroundColor Yellow