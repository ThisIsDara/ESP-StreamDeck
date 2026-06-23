@echo off
cd /d "%~dp0"
pip install zeroconf dnslib >nul 2>nul
set TASK_NAME=StreamDeckAgent

schtasks /query /tn "%TASK_NAME%" >nul 2>nul
if %errorlevel% equ 0 (
    echo Removing previous installation...
    schtasks /end /tn "%TASK_NAME%" >nul 2>nul
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>nul
    taskkill /F /IM pythonw.exe >nul 2>nul
    timeout /t 2 /nobreak >nul
)

schtasks /create /tn "%TASK_NAME%" /tr "\"%~dp0agent_runner.bat\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo Installed! Agent will auto-start on next login.
    echo Starting it now...
    start "" "%~dp0agent_runner.bat"
    echo.
    echo After the ESP32 boots, run:  open_web.bat
) else (
    echo Failed. Right-click and run "Run as Administrator".
)
timeout /t 5 /nobreak >nul
