#Requires -Version 5.1
<#
.SYNOPSIS
    Lanvan Docker launcher for Windows.
    Detects the active physical LAN IPv4 and injects it as LANVAN_ADVERTISE_HOST
    before starting the Docker container, enabling mobile QR code scanning.

.DESCRIPTION
    A Linux container running under Docker Desktop cannot discover the Windows host's
    physical Wi-Fi/Ethernet IP from inside the bridge network. This script detects
    the correct IP on the Windows host and passes it into Docker Compose via the
    LANVAN_ADVERTISE_HOST environment variable.

.EXAMPLE
    .\start-lanvan.ps1

.EXAMPLE
    # Manual override (skips auto-detection):
    $env:LANVAN_ADVERTISE_HOST = "192.168.1.34"
    .\start-lanvan.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Lanvan Docker Launcher" -ForegroundColor Cyan
Write-Host "  ======================" -ForegroundColor Cyan
Write-Host ""

# ----- 1. Respect a pre-set manual override -----
if ($env:LANVAN_ADVERTISE_HOST -and $env:LANVAN_ADVERTISE_HOST.Trim() -ne "") {
    $detectedIP = $env:LANVAN_ADVERTISE_HOST.Trim()
    Write-Host "  [OVERRIDE] Using manually configured LANVAN_ADVERTISE_HOST: $detectedIP" -ForegroundColor Yellow
}
else {
    # ----- 2. Auto-detect the real physical LAN IPv4 on the Windows host -----
    # Strategy: find the IP on the active interface that owns the default route.
    # Exclude virtual/overlay adapters: Docker, WSL, Hyper-V, loopback, APIPA.

    $excludedPrefixes = @(
        "127.",       # Loopback
        "169.254.",   # APIPA / link-local
        "172.17.",    # Docker default bridge
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31."     # Docker bridge range end
    )

    $excludedAdapterKeywords = @(
        "Docker",
        "WSL",
        "Hyper-V",
        "HyperV",
        "vEthernet",
        "VirtualBox",
        "VMware",
        "Loopback",
        "Bluetooth",
        "Pseudo",
        "Teredo",
        "6to4"
    )

    $detectedIP = $null

    try {
        # Method 1: Find the interface associated with the default gateway (most reliable)
        $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
            Where-Object { $_.NextHop -ne "0.0.0.0" } |
            Sort-Object RouteMetric |
            Select-Object -First 1

        if ($defaultRoute) {
            $ifIndex = $defaultRoute.InterfaceIndex
            $addr = Get-NetIPAddress -InterfaceIndex $ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                Where-Object { $_.IPAddress -notmatch "^169\.254\." -and $_.IPAddress -ne "127.0.0.1" } |
                Select-Object -First 1

            if ($addr) {
                $ip = $addr.IPAddress

                # Verify this adapter is not a virtual one
                $adapter = Get-NetAdapter -InterfaceIndex $ifIndex -ErrorAction SilentlyContinue
                $isVirtual = $false
                if ($adapter) {
                    foreach ($kw in $excludedAdapterKeywords) {
                        if ($adapter.Name -match $kw -or $adapter.InterfaceDescription -match $kw) {
                            $isVirtual = $true
                            break
                        }
                    }
                }

                $isExcludedPrefix = $false
                foreach ($prefix in $excludedPrefixes) {
                    if ($ip.StartsWith($prefix)) {
                        $isExcludedPrefix = $true
                        break
                    }
                }

                if (-not $isVirtual -and -not $isExcludedPrefix) {
                    $detectedIP = $ip
                }
            }
        }
    }
    catch {
        Write-Host "  [WARN] Default route detection failed: $_" -ForegroundColor Yellow
    }

    # Method 2: Scan all physical adapters if default route method failed
    if (-not $detectedIP) {
        try {
            $adapters = Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
                Where-Object { $_.Status -eq "Up" }

            foreach ($adapter in $adapters) {
                $isVirtual = $false
                foreach ($kw in $excludedAdapterKeywords) {
                    if ($adapter.Name -match $kw -or $adapter.InterfaceDescription -match $kw) {
                        $isVirtual = $true
                        break
                    }
                }
                if ($isVirtual) { continue }

                $addrs = Get-NetIPAddress -InterfaceIndex $adapter.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                    Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.IPAddress -notmatch "^169\.254\." }

                foreach ($addr in $addrs) {
                    $ip = $addr.IPAddress
                    $isExcludedPrefix = $false
                    foreach ($prefix in $excludedPrefixes) {
                        if ($ip.StartsWith($prefix)) {
                            $isExcludedPrefix = $true
                            break
                        }
                    }
                    if (-not $isExcludedPrefix) {
                        $detectedIP = $ip
                        break
                    }
                }
                if ($detectedIP) { break }
            }
        }
        catch {
            Write-Host "  [WARN] Physical adapter scan failed: $_" -ForegroundColor Yellow
        }
    }

    if (-not $detectedIP) {
        Write-Host ""
        Write-Host "  [ERROR] Could not automatically detect a physical LAN IPv4 address." -ForegroundColor Red
        Write-Host "  Please set it manually and retry:" -ForegroundColor Red
        Write-Host ""
        Write-Host '    $env:LANVAN_ADVERTISE_HOST = "192.168.x.x"' -ForegroundColor White
        Write-Host "    .\start-lanvan.ps1" -ForegroundColor White
        Write-Host ""
        exit 1
    }

    Write-Host "  [OK] Detected Windows LAN IP: $detectedIP" -ForegroundColor Green
}

# ----- 3. Validate IPv4 format -----
if ($detectedIP -notmatch "^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") {
    Write-Host "  [ERROR] '$detectedIP' is not a valid IPv4 address." -ForegroundColor Red
    exit 1
}

# ----- 4. Inject into environment and launch Docker Compose -----
$env:LANVAN_ADVERTISE_HOST = $detectedIP

Write-Host ""
Write-Host "  Starting Lanvan..." -ForegroundColor Cyan
Write-Host "  LANVAN_ADVERTISE_HOST = $detectedIP"
Write-Host ""

docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  Lanvan is running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Local access  : http://localhost" -ForegroundColor Cyan
    Write-Host "  LAN access    : http://$detectedIP" -ForegroundColor Cyan
    Write-Host "  (Scan the QR code in the Lanvan Connect panel from your phone)" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "  [ERROR] Docker Compose failed to start. Check the output above." -ForegroundColor Red
    Write-Host ""
    exit $LASTEXITCODE
}
