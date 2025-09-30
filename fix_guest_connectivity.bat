@echo off
echo ========================================
echo LANVAN Guest Device Connectivity Fix
echo ========================================
echo.
echo This script will configure Windows Firewall
echo to allow guest devices to connect to your
echo LANVAN file server.
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [STEP 1] Checking current firewall status...
netsh advfirewall show allprofiles state | findstr "State"
echo.

echo [STEP 2] Adding firewall rules for LANVAN server...

REM Add rule for HTTP port 80
echo - Adding HTTP port 80 rule...
netsh advfirewall firewall add rule name="LANVAN File Server HTTP" dir=in action=allow protocol=TCP localport=80 description="Allow incoming HTTP connections for LANVAN file server"

REM Add rule for HTTPS port 443 (if needed)
echo - Adding HTTPS port 443 rule...
netsh advfirewall firewall add rule name="LANVAN File Server HTTPS" dir=in action=allow protocol=TCP localport=443 description="Allow incoming HTTPS connections for LANVAN file server"

REM Add rule for Python executable
echo - Adding Python executable rules...
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo   Adding rule for Python at: %%i
    netsh advfirewall firewall add rule name="LANVAN Python Process" dir=in action=allow program="%%i" enable=yes description="Allow LANVAN Python server process"
)

REM Add rule for common Python paths
if exist "C:\Program Files\Python*\python.exe" (
    netsh advfirewall firewall add rule name="LANVAN Python System" dir=in action=allow program="C:\Program Files\Python*\python.exe" enable=yes
)

echo.
echo [STEP 3] Verifying firewall rules...
netsh advfirewall firewall show rule name="LANVAN File Server HTTP" | findstr "Rule Name\|Enabled\|Direction\|Action"
echo.

echo [STEP 4] Testing network configuration...
echo Your computer's IP address:
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr "IPv4"') do echo%%i
echo.

echo [STEP 5] Getting network information...
python -c "import socket; print('Hostname:', socket.gethostname()); print('IP Address:', socket.gethostbyname(socket.gethostname()))" 2>nul
echo.

echo ========================================
echo GUEST CONNECTIVITY FIX COMPLETED!
echo ========================================
echo.
echo Guest devices can now connect using:
echo 1. http://lanvan.local (recommended)
echo 2. Direct IP address (backup)
echo.
echo Next steps:
echo 1. Start LANVAN server: python run.py
echo 2. Test connectivity: python test_guest_connectivity.py
echo 3. Share the connection details with guests
echo.
echo Troubleshooting:
echo - Ensure all devices are on same WiFi network
echo - Some routers have "guest isolation" - disable it
echo - Corporate networks may block device connections
echo.
echo ========================================
pause