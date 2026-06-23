@echo off
cd /d "%~dp0"
if exist esp_ip.txt (
    set /p URL=<esp_ip.txt
    echo Opening %URL%
    start "" "%URL%"
) else (
    echo ESP32 IP not found yet.
    echo Make sure the agent is running (pythonw pc_agent.py)
    echo and the ESP32 has finished booting.
    pause
)
