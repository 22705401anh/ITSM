@echo off
echo ============================================
echo  KOSTAL Print Agent - Service Installation
echo ============================================
echo.
echo Installing KOSTAL Print Agent as a Windows Service...
python "%~dp0kostal_print_agent.py" install
echo.
echo Starting KOSTAL Print Agent service...
python "%~dp0kostal_print_agent.py" start
echo.
echo Done. Check Services (services.msc) for "KOSTAL Print Agent".
pause
