@echo off
cd /d "C:\Users\Trick\Desktop\ESP32\Stream Deck"
:retry
pythonw pc_agent.py
timeout /t 5 /nobreak >nul
goto retry
