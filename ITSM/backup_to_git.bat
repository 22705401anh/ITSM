@echo off
color 0B
echo =======================================================
echo          ITSM Project Git Backup Utility
echo =======================================================
echo.

:: Ensure we are in the script's directory
cd /d "%~dp0"

echo [1/4] Checking git status and branch...
git checkout master
git status -s
echo.

set /p commit_msg="Enter commit message (or press Enter for automated timestamp): "

if "%commit_msg%"=="" (
    :: Build a safe timestamp string
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
    set commit_msg=Automated backup on %date% at %time%
)

echo.
echo [2/4] Staging all changes...
git add .

echo.
echo [3/4] Committing changes...
git commit -m "%commit_msg%"

echo.
echo [4/4] Pushing to remote repository...
git push origin HEAD:master

echo.
echo =======================================================
echo               Backup Process Finished!
echo =======================================================
pause
