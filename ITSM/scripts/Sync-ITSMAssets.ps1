<#
.SYNOPSIS
    KOSTAL ITSM Network Discovery & Synchronization Service
.DESCRIPTION
    Scans Active Directory for computer objects, verifies reachability, extracts WMI 
    hardware inventory (PC and Monitor), resolves the logged-in user, and syncs 
    all data with the KOSTAL ITSM API.
#>

[CmdletBinding()]
param (
    [string]$ApiBaseUrl = "http://localhost:8000/api",
    [string]$ApiUsername = "admin",
    [string]$ApiPassword = "admin123", # Ensure this is secure in production
    [string]$SearchBase = "", # Optional: Restrict AD search to a specific OU
    [string]$TargetComputer = "", # Optional: Scan a single computer instead of AD
    [string]$LogDirectory = "C:\Logs\ITSM-Discovery"
)

# --- Logging Initialization ---
if (-not (Test-Path $LogDirectory)) { New-Item -ItemType Directory -Path $LogDirectory | Out-Null }
$LogFile = Join-Path $LogDirectory "discovery_$(Get-Date -Format 'yyyyMMdd').log"

function Write-Log {
    param (
        [Parameter(Mandatory=$true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO"
    )
    $LogEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Host $LogEntry
    try {
        [System.IO.File]::AppendAllText($LogFile, "$LogEntry`r`n")
    } catch {
        # Silently fail if log is locked momentarily
    }
}

# --- Module Checks ---
try {
    Import-Module ActiveDirectory -ErrorAction Stop
} catch {
    Write-Log "ActiveDirectory module missing. RSAT must be installed." -Level ERROR
    exit
}

# --- Helper Functions ---

function Get-LoggedOnUser {
    param($CimSession)
    try {
        $CS = Get-CimInstance -ClassName Win32_ComputerSystem -CimSession $CimSession -ErrorAction Stop
        return $CS.UserName # Returns DOMAIN\Username
    } catch {
        return $null
    }
}

function Get-Monitors {
    param($CimSession)
    $Monitors = @()
    try {
        # Fetching monitors via WmiMonitorID namespace
        $WmiMonitors = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -CimSession $CimSession -ErrorAction Stop
        foreach ($Mon in $WmiMonitors) {
            try {
                $Manufacturer = ""
                $Model = ""
                $Serial = ""
                
                if ($null -ne $Mon.ManufacturerName) {
                    $Manufacturer = [System.Text.Encoding]::ASCII.GetString([byte[]]$Mon.ManufacturerName).TrimEnd([char]0)
                }
                if ($null -ne $Mon.UserFriendlyName) {
                    $Model = [System.Text.Encoding]::ASCII.GetString([byte[]]$Mon.UserFriendlyName).TrimEnd([char]0)
                }
                if ($null -ne $Mon.SerialNumberID) {
                    $Serial = [System.Text.Encoding]::ASCII.GetString([byte[]]$Mon.SerialNumberID).TrimEnd([char]0)
                }
                
                if ($Serial) {
                    $Monitors += @{
                        model = $Model
                        serial_number = $Serial
                        manufacturer = $Manufacturer
                    }
                }
            } catch {
                # Prevent a failure on one monitor from aborting the entire loop
            }
        }
    } catch {
        # Monitor extraction fails on some headless VMs or laptops
    }
    return $Monitors
}

function Get-NetworkDetails {
    param($CimSession)
    try {
        $Adapters = Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -CimSession $CimSession -Filter "IPEnabled = 'True'" -ErrorAction Stop
        
        $IPs = @()
        $MACs = @()
        foreach ($Adapter in $Adapters) {
            if ($Adapter.IPAddress) {
                foreach ($ip in $Adapter.IPAddress) {
                    # Filter for IPv4 to keep it clean, or keep all
                    if ($ip -match "^[\d\.]+$") { $IPs += $ip }
                }
            }
            if ($Adapter.MACAddress -and $MACs -notcontains $Adapter.MACAddress) {
                $MACs += $Adapter.MACAddress
            }
        }
        
        return @{
            ip_address = if ($IPs.Count -gt 0) { $IPs -join ", " } else { $null }
            mac_address = if ($MACs.Count -gt 0) { $MACs -join ", " } else { $null }
        }
    } catch {
        return @{ ip_address = $null; mac_address = $null }
    }
}

function Get-WindowsVersion {
    param($CimSession)
    try {
        $OS = Get-CimInstance -ClassName Win32_OperatingSystem -CimSession $CimSession -ErrorAction Stop
        return "$($OS.Caption) ($($OS.Version))"
    } catch {
        return $null
    }
}

function Get-Antivirus {
    param($CimSession)
    try {
        $AV = Get-CimInstance -Namespace "root\SecurityCenter2" -ClassName AntiVirusProduct -CimSession $CimSession -ErrorAction Stop | Select-Object -First 1
        if ($AV) { return $AV.displayName }
        return "None Detected"
    } catch {
        return "Unknown/Server"
    }
}

function Get-IntuneStatus {
    param($CimSession)
    try {
        $Hklm = [uint32]2147483650
        $Key = "SOFTWARE\Microsoft\Enrollments"
        
        $MethodParams = @{ hDefKey = $Hklm; sSubKeyName = $Key }
        $Result = Invoke-CimMethod -ClassName StdRegProv -Namespace "root\default" -CimSession $CimSession -MethodName EnumKey -Arguments $MethodParams -ErrorAction SilentlyContinue
        if ($Result.sNames) {
            foreach ($SubKey in $Result.sNames) {
                $ValueParams = @{ hDefKey = $Hklm; sSubKeyName = "$Key\$SubKey"; sValueName = "EnrollmentState" }
                $ValResult = Invoke-CimMethod -ClassName StdRegProv -Namespace "root\default" -CimSession $CimSession -MethodName GetDWORDValue -Arguments $ValueParams -ErrorAction SilentlyContinue
                if ($ValResult.uValue -eq 1) { return "Enrolled" }
            }
        }
        return "Not Enrolled"
    } catch {
        return "Unknown"
    }
}

function Get-InstalledSoftware {
    param($CimSession)
    $Software = @()
    try {
        $Hklm = [uint32]2147483650
        $Paths = @("SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        
        foreach ($Path in $Paths) {
            $MethodParams = @{ hDefKey = $Hklm; sSubKeyName = $Path }
            $Result = Invoke-CimMethod -ClassName StdRegProv -Namespace "root\default" -CimSession $CimSession -MethodName EnumKey -Arguments $MethodParams -ErrorAction SilentlyContinue
            if ($Result.sNames) {
                foreach ($SubKey in $Result.sNames) {
                    $KeyPath = "$Path\$SubKey"
                    $NameParams = @{ hDefKey = $Hklm; sSubKeyName = $KeyPath; sValueName = "DisplayName" }
                    $NameResult = Invoke-CimMethod -ClassName StdRegProv -Namespace "root\default" -CimSession $CimSession -MethodName GetStringValue -Arguments $NameParams -ErrorAction SilentlyContinue
                    
                    if ($NameResult.sValue) {
                        $VerParams = @{ hDefKey = $Hklm; sSubKeyName = $KeyPath; sValueName = "DisplayVersion" }
                        $VerResult = Invoke-CimMethod -ClassName StdRegProv -Namespace "root\default" -CimSession $CimSession -MethodName GetStringValue -Arguments $VerParams -ErrorAction SilentlyContinue
                        
                        $Software += @{
                            name = $NameResult.sValue
                            version = if ($VerResult.sValue) { $VerResult.sValue } else { "" }
                        }
                    }
                }
            }
        }
    } catch {
        # Silently fail
    }
    
    # Deduplicate
    $UniqueSoftware = @{}
    foreach ($sw in $Software) { $UniqueSoftware[$sw.name] = $sw }
    
    $ResultArray = @()
    foreach ($val in $UniqueSoftware.Values) { $ResultArray += $val }
    return $ResultArray
}

function Get-InstalledPrinters {
    param($CimSession)
    $Printers = @()
    try {
        # 1. Get WMI Printers (Local/System)
        $WmiPrinters = Get-CimInstance -ClassName Win32_Printer -CimSession $CimSession -ErrorAction SilentlyContinue
        if ($WmiPrinters) {
            foreach ($p in $WmiPrinters) {
                $Printers += @{
                    name = $p.Name
                    driver_name = $p.DriverName
                    port_name = $p.PortName
                    is_network = [bool]$p.Network
                    is_default = [bool]$p.Default
                }
            }
        }
        
        # 2. Get Per-User Network Printers via Registry
        [uint32]$HKU = 2147483651 # HKEY_USERS
        $SIDs = Invoke-CimMethod -ClassName StdRegProv -MethodName EnumKey -CimSession $CimSession -Arguments @{ hDefKey = $HKU; sSubKeyName = "" } -ErrorAction SilentlyContinue
        
        if ($SIDs -and $SIDs.sNames) {
            foreach ($SID in $SIDs.sNames) {
                if ($SID -match '^S-1-5-21-.*$' -and $SID -notmatch '_Classes$') {
                    $PrinterPath = "$SID\Printers\Connections"
                    $Keys = Invoke-CimMethod -ClassName StdRegProv -MethodName EnumKey -CimSession $CimSession -Arguments @{ hDefKey = $HKU; sSubKeyName = $PrinterPath } -ErrorAction SilentlyContinue
                    
                    if ($Keys -and $Keys.sNames) {
                        foreach ($key in $Keys.sNames) {
                            $cleanName = $key -replace '^,,', '\\' -replace ',', '\'
                            
                            # Check if already found
                            $exists = $false
                            foreach ($p in $Printers) { if ($p.name -eq $cleanName) { $exists = $true; break } }
                            if ($exists) { continue }

                            # Check if default
                            $DefStr = (Invoke-CimMethod -ClassName StdRegProv -MethodName GetStringValue -CimSession $CimSession -Arguments @{ hDefKey = $HKU; sSubKeyName = "$SID\Software\Microsoft\Windows NT\CurrentVersion\Windows"; sValueName = "Device" } -ErrorAction SilentlyContinue).sValue
                            $IsDef = $false
                            if ($DefStr -and $DefStr -match "^$([regex]::Escape($cleanName))") {
                                $IsDef = $true
                            }

                            $Printers += @{
                                name = $cleanName
                                port_name = "Network Port"
                                driver_name = "Network Driver"
                                is_network = $true
                                is_default = $IsDef
                            }
                        }
                    }
                }
            }
        }
    } catch { }
    return $Printers
}

function Get-PrintVolume {
    param($Computer, $CimSession)
    try {
        # Ensure Print Logging is enabled
        Invoke-CimMethod -ClassName Win32_Process -MethodName Create -CimSession $CimSession -Arguments @{ CommandLine = "wevtutil sl Microsoft-Windows-PrintService/Operational /e:true" } -ErrorAction SilentlyContinue | Out-Null
        
        $ThirtyDaysAgo = (Get-Date).AddDays(-30)
        $Events = Get-WinEvent -ComputerName $Computer -FilterHashTable @{LogName='Microsoft-Windows-PrintService/Operational'; ID=307; StartTime=$ThirtyDaysAgo} -ErrorAction SilentlyContinue
        
        $TotalPages = 0
        if ($Events) {
            foreach ($Event in $Events) {
                # Event ID 307 Properties: [7] is Pages, [4] is Printer Name
                if ($Event.Properties.Count -gt 7) {
                    $PagesStr = $Event.Properties[7].Value
                    if ($PagesStr -match "\d+") {
                        $TotalPages += [int]$PagesStr
                    }
                }
            }
        }
        return $TotalPages
    } catch { return 0 }
}

# --- Main Execution ---

while ($true) {
    Write-Log "Starting KOSTAL ITSM Network Discovery Cycle"

$Payload = @{ devices = @() }

# 1. Discover targets
$Computers = @()
if ($TargetComputer) {
    Write-Log "Targeting single computer: $TargetComputer"
    $Computers += $TargetComputer
} else {
    $ADParams = @{ Filter = "OperatingSystem -like '*Windows*'" }
    if ($SearchBase) { $ADParams.SearchBase = $SearchBase }

    Write-Log "Querying Active Directory for target computers..."
    $Computers = Get-ADComputer @ADParams | Select-Object -ExpandProperty Name
    Write-Log "Found $($Computers.Count) computer objects."
}

# --- Authentication ---
Write-Log "Authenticating to KOSTAL ITSM API..."
$ApiToken = ""
try {
    $LoginBody = @{ username = $ApiUsername; password = $ApiPassword } | ConvertTo-Json
    $LoginResponse = Invoke-RestMethod -Uri "$ApiBaseUrl/auth/login" -Method Post -Headers @{"Content-Type"="application/json"} -Body $LoginBody -ErrorAction Stop
    $ApiToken = $LoginResponse.access_token
    $TokenExpiresAt = (Get-Date).AddMinutes(25)
    Write-Log "Successfully authenticated to API."
} catch {
    Write-Log "Failed to authenticate to ITSM API: $_" -Level ERROR
    exit
}

foreach ($Computer in $Computers) {
    # Asynchronous Pause Check
    if ([System.Console]::KeyAvailable) {
        $PauseRequested = $false
        while ([System.Console]::KeyAvailable) {
            $Key = [System.Console]::ReadKey($true)
            if ($Key.Key -eq 'H' -or $Key.Key -eq 'P') { $PauseRequested = $true }
        }
        if ($PauseRequested) {
            Write-Host "`n[!] SCRIPT PAUSED (Ctrl+H detected) [!]" -ForegroundColor Yellow
            Read-Host "Press ENTER to resume scanning"
            Write-Host "Resuming scan...`n" -ForegroundColor Green
        }
    }

    if (Test-Connection -ComputerName $Computer -Count 1 -Quiet) {
        Write-Log "[$Computer] Online. Initiating WMI scan..."
        
        $Session = $null
        try {
            # Use DCOM protocol to bypass the 4-minute WSMan reconnect bug in Windows PowerShell 5.1
            $CimOption = New-CimSessionOption -Protocol DCOM
            $Session = New-CimSession -ComputerName $Computer -SessionOption $CimOption -ErrorAction Stop

            $CS = Get-CimInstance -ClassName Win32_ComputerSystem -CimSession $Session -ErrorAction Stop
            $BIOS = Get-CimInstance -ClassName Win32_BIOS -CimSession $Session -ErrorAction Stop
            $Net = Get-NetworkDetails -CimSession $Session
            $User = Get-LoggedOnUser -CimSession $Session
            $AttachedMonitors = @(Get-Monitors -CimSession $Session)
            $WinVer = Get-WindowsVersion -CimSession $Session
            $Intune = Get-IntuneStatus -CimSession $Session
            $AntiVirus = Get-Antivirus -CimSession $Session
            $InstalledSW = @(Get-InstalledSoftware -CimSession $Session)
            $Printers = @(Get-InstalledPrinters -CimSession $Session)
            $PrintVolume = Get-PrintVolume -Computer $Computer -CimSession $Session

            $RAM = "$([math]::Round($CS.TotalPhysicalMemory / 1GB)) GB"
            $Disks = Get-CimInstance -ClassName Win32_LogicalDisk -CimSession $Session -Filter "DriveType=3" -ErrorAction SilentlyContinue
            $StorageStr = "Unknown"
            if ($Disks) { 
                $TotalSize = 0; $TotalFree = 0
                foreach ($Disk in $Disks) { 
                    $TotalSize += $Disk.Size
                    $TotalFree += $Disk.FreeSpace
                }
                if ($TotalSize -gt 0) {
                    $Pct = [math]::Round((($TotalSize - $TotalFree) / $TotalSize) * 100)
                    $TotalGB = [math]::Round($TotalSize / 1GB)
                    $StorageStr = "$TotalGB GB ($Pct% Full)"
                }
            }

            $DeviceData = @{
                hostname = $CS.Name
                ip_address = $Net.ip_address
                mac_address = $Net.mac_address
                model = $CS.Model
                serial_number = $BIOS.SerialNumber
                vendor = $CS.Manufacturer
                logged_in_user = $User
                windows_version = $WinVer
                intune_status = $Intune
                antivirus_status = $AntiVirus
                ram = $RAM
                storage = $StorageStr
                print_volume_30d = $PrintVolume
                monitors = $AttachedMonitors
                software = $InstalledSW
                printers = $Printers
            }
            Write-Log "[$Computer] Scan complete. Found user: $($User -replace '^$','None'), Monitors: $($AttachedMonitors.Count), SW: $($InstalledSW.Count), Printers: $($Printers.Count), Volume: $PrintVolume."            
            # Token Refresh Check
            if ((Get-Date) -gt $TokenExpiresAt) {
                Write-Log "API token expiring soon. Re-authenticating..."
                try {
                    $LoginBody = @{ username = $ApiUsername; password = $ApiPassword } | ConvertTo-Json
                    $LoginResponse = Invoke-RestMethod -Uri "$ApiBaseUrl/auth/login" -Method Post -Headers @{"Content-Type"="application/json"} -Body $LoginBody -ErrorAction Stop
                    $ApiToken = $LoginResponse.access_token
                    $TokenExpiresAt = (Get-Date).AddMinutes(25)
                    Write-Log "Token refreshed successfully."
                } catch {
                    Write-Log "Failed to refresh token: $_" -Level ERROR
                }
            }

            # Sync Immediately
            try {
                $SinglePayload = @{ devices = @($DeviceData) } | ConvertTo-Json -Depth 5 -Compress
                $PayloadBytes = [System.Text.Encoding]::UTF8.GetBytes($SinglePayload)
                $ApiUrl = "$ApiBaseUrl/hardware/discovery/sync"
                $Headers = @{ "Content-Type" = "application/json; charset=utf-8"; "Authorization" = "Bearer $ApiToken" }
                $Response = Invoke-RestMethod -Uri $ApiUrl -Method Post -Headers $Headers -Body $PayloadBytes -ErrorAction Stop
                Write-Log "[$Computer] Synced successfully to ITSM."
            } catch {
                Write-Log "[$Computer] ITSM API Sync Failed: $_" -Level ERROR
            }

        } catch {
            Write-Log "[$Computer] WMI query failed. Access denied or RPC blocked." -Level ERROR
        } finally {
            if ($Session) { Remove-CimSession $Session -ErrorAction SilentlyContinue }
        }
} else {
        Write-Log "[$Computer] Offline or unreachable." -Level WARN
    }
}

    Write-Log "Discovery Cycle Finished."

    $UserInput = Read-Host "`nDiscovery complete. Press ENTER to run another scan, or type 'exit' to close"
    if ($UserInput -eq 'exit') {
        break
    }
    Write-Log "--------------------------------------------------------"
}
