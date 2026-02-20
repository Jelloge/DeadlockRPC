@echo off
REM ═══════════════════════════════════════════════════════════════
REM  Build Deadlock Discord Rich Presence into a standalone .exe
REM ═══════════════════════════════════════════════════════════════

echo.
echo  Building Deadlock Discord Rich Presence...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download from https://python.org
    pause
    exit /b 1
)

REM Install dependencies
echo  [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

REM Check that DISCORD_APP_ID was set
findstr /C:"YOUR_DISCORD_APP_ID_HERE" deadlock_rpc.py >nul 2>&1
if not errorlevel 1 (
    echo.
    echo  WARNING: You haven't set your Discord Application ID yet!
    echo  Open deadlock_rpc.py and replace YOUR_DISCORD_APP_ID_HERE
    echo  with your actual Application ID from:
    echo  https://discord.com/developers/applications
    echo.
    pause
    exit /b 1
)

REM Build
echo  [2/3] Building executable...
pyinstaller deadlock_rpc.spec --noconfirm --clean

echo.
echo  [3/3] Done!
echo.
echo  Your executable is at: dist\DeadlockRPC.exe
echo  Distribute this file to your users.
echo.
pause
