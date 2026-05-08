@echo off
echo ============================================
echo  KOSTAL Print Agent - Service Removal
echo ============================================
echo.
echo Stopping KOSTAL Print Agent service...
python "%~dp0kostal_print_agent.py" stop
echo.
echo Removing KOSTAL Print Agent service...
python "%~dp0kostal_print_agent.py" remove
echo.
echo Done.
pause
