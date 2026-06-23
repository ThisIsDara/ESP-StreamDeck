@echo off
schtasks /delete /tn "StreamDeckAgent" /f >nul 2>nul
if %errorlevel% equ 0 (
    echo Agent removed from startup.
) else (
    echo Agent was not installed or could not be removed.
)
pause
