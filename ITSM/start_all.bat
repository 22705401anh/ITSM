@echo off
cd /d "%~dp0"
echo =======================================================
echo          Starting ITSM Platform Services
echo =======================================================
echo.

echo [1/4] Starting FastAPI Web Server...
start "FastAPI Web Server" cmd /k "venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/4] Starting Network Telemetry Worker...
start "Network Telemetry Worker" cmd /k "venv\Scripts\activate && python scripts\network_telemetry_worker.py"

echo.
echo Waiting 5 seconds for the FastAPI server to boot up before launching API sync scripts...
timeout /t 5 /nobreak >nul
echo.

echo [3/5] Starting Asset Inventory Sync...
start "Asset Inventory Sync" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\Sync-ITSMAssets.ps1"

echo [4/5] Starting Printer Inventory Sync...
start "Printer Inventory Sync" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\Sync-ITSMPrinters.ps1"

echo [5/5] Starting Print SNMP Worker...
start "Print SNMP Worker" cmd /k "venv\Scripts\activate && python scripts\print_snmp_worker.py"

echo.
echo =======================================================
echo All services have been launched in separate windows!
echo Keep the windows open to allow background processing.
echo You can close individual windows to stop specific services.
echo =======================================================
pause
