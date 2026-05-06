<#
.SYNOPSIS
    KOSTAL ITSM Network Printer Discovery Service
.DESCRIPTION
    Scans a specific VLAN (e.g. VLAN 41) for network printers via SNMP and
    syncs the discovered hardware (Model, Serial, IP) to the KOSTAL ITSM API.
#>

[CmdletBinding()]
param (
    [string]$ApiBaseUrl = "http://localhost:8000/api",
    [string]$ApiUsername = "admin",
    [string]$ApiPassword = "admin123",
    [string]$LogDirectory = "C:\Logs\ITSM-Discovery"
)

# --- Logging Initialization ---
if (-not (Test-Path $LogDirectory)) { New-Item -ItemType Directory -Path $LogDirectory | Out-Null }
$LogFile = Join-Path $LogDirectory "printer_discovery_$(Get-Date -Format 'yyyyMMdd').log"

function Write-Log {
    param (
        [Parameter(Mandatory=$true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO"
    )
    $LogEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Host $LogEntry
    try {
        [System.IO.File]::AppendAllText($LogFile, "$LogEntry`r`n")
    } catch {}
}

# --- Module Checks ---
try {
    Import-Module SNMP -ErrorAction Stop
} catch {
    Write-Log "SNMP module missing. Printer scanning will fail. Install it first." -Level ERROR
    exit
}

# --- Helper Functions ---
function Get-FirstSnmpValue {
    param (
        [string]$IP,
        [string]$Community,
        [string[]]$OIDs
    )

    foreach ($OID in $OIDs) {
        try {
            $Result = Get-SnmpData -IP $IP -Community $Community -OID $OID -ErrorAction SilentlyContinue -WarningAction SilentlyContinue

            if ($Result.Data -and
                $Result.Data -ne "NoSuchObject" -and
                $Result.Data -ne "NoSuchInstance") {
                return $Result.Data
            }
        }
        catch {
            continue
        }
    }

    return "Not found"
}

function Get-MacSnmpValue {
    param (
        [string]$IP,
        [string]$Community,
        [string[]]$OIDs
    )

    $IPAddress = [Net.IPAddress]$IP
    $endpoint = New-Object Net.IpEndPoint $IPAddress, 161

    foreach ($OID in $OIDs) {
        $variableList = New-Object Collections.Generic.List[Lextm.SharpSnmpLib.Variable]
        $variableList.Add($(New-Object Lextm.SharpSnmpLib.ObjectIdentifier $OID))
        
        try {
            $message = [Lextm.SharpSnmpLib.Messaging.Messenger]::Get("V2", $endpoint, $Community, $variableList, 2000)
            $data = $message[0].Data
            if ($data.TypeCode -ne [Lextm.SharpSnmpLib.SnmpType]::NoSuchObject -and
                $data.TypeCode -ne [Lextm.SharpSnmpLib.SnmpType]::NoSuchInstance) {
                if ($data.TypeCode -eq [Lextm.SharpSnmpLib.SnmpType]::OctetString) {
                    $raw = $data.GetRaw()
                    if ($raw.Length -eq 6) {
                        return ($raw | ForEach-Object { '{0:X2}' -f $_ }) -join ':'
                    } elseif ($raw.Length -gt 0) {
                        return ($raw | ForEach-Object { '{0:X2}' -f $_ }) -join ':'
                    }
                }
            }
        } catch {
            continue
        }
    }
    return "Not found"
}

# --- Main Execution ---
while ($true) {
    Write-Log "Starting Network Printer Discovery Cycle"

    # --- Authentication ---
    Write-Log "Authenticating to KOSTAL ITSM API..."
    $ApiToken = ""
    try {
        $LoginBody = @{ username = $ApiUsername; password = $ApiPassword } | ConvertTo-Json
        $LoginResponse = Invoke-RestMethod -Uri "$ApiBaseUrl/auth/login" -Method Post -Headers @{"Content-Type"="application/json"} -Body $LoginBody -ErrorAction Stop
        $ApiToken = $LoginResponse.access_token
        Write-Log "Successfully authenticated to API."
    } catch {
        Write-Log "Failed to authenticate to ITSM API: $_" -Level ERROR
        exit
    }

    # --- Printer SNMP Scan on VLAN 41 ---
    Write-Log "Starting SNMP Printer sweep on VLAN 41 (10.141.41.x)..."
    $NetworkPrinters = @()
    $ModelOIDs = @(
        "1.3.6.1.2.1.25.3.2.1.3.1",
        "1.3.6.1.2.1.1.1.0",
        "1.3.6.1.2.1.43.5.1.1.16.1"
    )

$SerialOIDs = @(
        "1.3.6.1.2.1.43.5.1.1.17.1",
        "1.3.6.1.2.1.43.5.1.1.17.1.1",
        "1.3.6.1.4.1.11.2.4.3.1.10.0",
        "1.3.6.1.4.1.10642.1.3.0"
    )

    $MacOIDs = @(
        "1.3.6.1.2.1.2.2.1.6.1",
        "1.3.6.1.2.1.2.2.1.6.2",
        "1.3.6.1.2.1.2.2.1.6.3",
        "1.3.6.1.2.1.2.2.1.6.4"
    )

    for ($i = 1; $i -le 254; $i++) {
        $PrinterIP = "10.141.41.$i"
        
        # Asynchronous Pause Check
        if ([System.Console]::KeyAvailable) {
            $Key = [System.Console]::ReadKey($true)
            if ($Key.Key -eq 'H' -or $Key.Key -eq 'P') { 
                Write-Host "`n[!] SCRIPT PAUSED (Ctrl+H detected) [!]" -ForegroundColor Yellow
                Read-Host "Press ENTER to resume scanning"
                Write-Host "Resuming scan...`n" -ForegroundColor Green
            }
        }

        if (Test-Connection -ComputerName $PrinterIP -Count 1 -Quiet -ErrorAction SilentlyContinue) {
            $Model = Get-FirstSnmpValue -IP $PrinterIP -Community "public" -OIDs $ModelOIDs
$Serial = Get-FirstSnmpValue -IP $PrinterIP -Community "public" -OIDs $SerialOIDs
            
            $MacHex = Get-MacSnmpValue -IP $PrinterIP -Community "public" -OIDs $MacOIDs
            $Mac = $null
            if ($MacHex -and $MacHex -ne "Not found") {
                # Format MAC properly if it comes back as space-separated hex or similar
                $Mac = $MacHex -replace " ", ":"
            }
            
            if ($Serial -and $Serial -ne "Not found") {
                $PrinterObj = @{
                    ip_address = $PrinterIP
                    mac_address = $Mac
                    model = if ($Model -and $Model -ne "Not found") { $Model } else { "Unknown Printer" }
                    serial_number = $Serial
                }
                Write-Log "Found Printer at $($PrinterIP): Model=$Model, Serial=$Serial, MAC=$Mac"
                
                Write-Log "Syncing printer $Serial to ITSM immediately..."
                try {
                    $PrinterPayload = @{ network_printers = @($PrinterObj); devices = @() } | ConvertTo-Json -Depth 5 -Compress
                    $PayloadBytes = [System.Text.Encoding]::UTF8.GetBytes($PrinterPayload)
                    $ApiUrl = "$ApiBaseUrl/hardware/discovery/sync"
                    $Headers = @{ "Content-Type" = "application/json; charset=utf-8"; "Authorization" = "Bearer $ApiToken" }
                    $Response = Invoke-RestMethod -Uri $ApiUrl -Method Post -Headers $Headers -Body $PayloadBytes -ErrorAction Stop
                    Write-Log "Successfully synced $Serial to ITSM."
                } catch {
                    Write-Log "Failed to sync printer $($Serial): $_" -Level ERROR
                }
            }
        }
    }

    Write-Log "Printer Discovery Cycle Finished."

    $UserInput = Read-Host "`nDiscovery complete. Press ENTER to run another scan, or type 'exit' to close"
    if ($UserInput -eq 'exit') {
        break
    }
    Write-Log "--------------------------------------------------------"
}
