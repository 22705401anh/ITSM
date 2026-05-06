@echo off
echo =======================================================
echo          Starting ITSM Platform Services
echo =======================================================
echo.

echo [1/4] Starting FastAPI Web Server...
start "FastAPI Web Server" cmd /k "venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/4] Starting Network Telemetry Worker...
start "Network Telemetry Worker" cmd /k "venv\Scripts\activate && python scripts\network_telemetry_worker.py"

echo [3/4] Starting Asset Inventory Sync...
start "Asset Inventory Sync" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\Sync-ITSMAssets.ps1"

echo [4/4] Starting Printer Inventory Sync...
start "Printer Inventory Sync" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\Sync-ITSMPrinters.ps1"

echo.
echo =======================================================
echo All services have been launched in separate windows!
echo Keep the windows open to allow background processing.
echo You can close individual windows to stop specific services.
echo =======================================================
pause
