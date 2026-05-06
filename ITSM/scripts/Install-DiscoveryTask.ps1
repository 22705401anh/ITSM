<#
.SYNOPSIS
    Installs the KOSTAL ITSM Network Discovery script as a Windows Scheduled Task.
.DESCRIPTION
    This script registers a scheduled task that runs the Sync-ITSMAssets.ps1 script 
    every 4 hours as the SYSTEM account (or configured service account), ensuring 
    constant network discovery in the background.
#>

$TaskName = "KOSTAL ITSM Network Discovery"
$ScriptPath = Join-Path $PSScriptRoot "Sync-ITSMAssets.ps1"

if (-not (Test-Path $ScriptPath)) {
    Write-Host "Error: Cannot find $ScriptPath" -ForegroundColor Red
    exit 1
}

$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""
# Run every 4 hours, indefinitely
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 4)

# Run with highest privileges (System) so it can use WMI and AD modules seamlessly
$Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Write-Host "Registering Scheduled Task '$TaskName'..." -ForegroundColor Cyan

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

Write-Host "Scheduled Task installed successfully!" -ForegroundColor Green
Write-Host "The task will run every 4 hours automatically."
Write-Host "You can manually trigger it anytime via Task Scheduler (taskschd.msc)."
