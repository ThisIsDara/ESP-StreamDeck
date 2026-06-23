# ESP-StreamDeck

ESP32-powered wireless Stream Deck controlled from any device with a browser — no proprietary hardware needed.

![Hardware](https://img.shields.io/badge/Hardware-ESP32--WROOM-blue)
![Web](https://img.shields.io/badge/UI-Web%20SPA-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## How It Works

```
┌──────────────┐      WiFi      ┌──────────┐    Serial    ┌──────────────────┐
│ Android/PC   │ ──────────────> │  ESP32   │ ───────────> │  PC Agent        │
│ Browser      │   WebSocket    │ (Web GUI) │   COM3       │  (action runner) │
│ (SPA)        │ <────────────── │          │ <─────────── │                  │
└──────────────┘                └──────────┘              └──────────────────┘
```

- **Android phone (or any browser)**: Touchscreen Stream Deck UI via WebSocket
- **ESP32**: Serves the web UI, relays button presses over serial
- **PC Agent** (`pc_agent.py`): Receives serial commands and executes them on Windows

## Features

- **8 configurable buttons**: media keys, volume, keyboard shortcuts, app launcher, text typer
- **Hold-to-repeat**: hold a button for 350ms → repeats every 80ms
- **Volume slider**: real-time, no Windows OSD popup (Core Audio COM)
- **Glassmorphism UI**: dark amber theme, adaptive grid, landscape-optimized
- **WiFi Manager**: captive portal for first-time WiFi setup
- **OTA updates**: upload firmware over the air via ArduinoOTA
- **Auto-start on Windows**: scheduled task launches agent on login
- **mDNS & DNS forwarder**: optional `streamdeck.local` resolution

## Getting Started

### Hardware
- ESP32-WROOM (or any ESP32 dev board)
- Mini-USB cable for serial connection to PC

### Flash the ESP32

1. Install [PlatformIO](https://platformio.org/)
2. Clone and build:

```bash
git clone https://github.com/ThisIsDara/ESP-StreamDeck.git
cd ESP-StreamDeck
pio run -t upload && pio run -t uploadfs
```

3. Connect to serial monitor, wait for WiFi Manager captive portal, configure WiFi
4. Note the IP address printed on boot

### Set Up the PC Agent

```bash
pip install pyserial comtypes pycaw zeroconf dnslib
python pc_agent.py
```

Or for auto-start on login, run `install_service.bat` as Administrator.

### Access the Web UI

```
http://<esp32-ip>/
```

Open `open_web.bat` on the PC, or bookmark the URL on your phone.

## Available Actions

| Action | Description |
|---|---|
| `PLAY_PAUSE` | Media play/pause |
| `NEXT_TRACK` | Media next track |
| `PREV_TRACK` | Media previous track |
| `VOL_UP` | Volume up (+5%) |
| `VOL_DOWN` | Volume down (-5%) |
| `SET_VOLUME` | Set volume to percentage (0-100) |
| `MUTE` | Toggle mute |
| `KEY_COMBO` | Send keyboard shortcut (e.g. `Ctrl+S`) |
| `OPEN_APP` | Launch application (e.g. `notepad.exe`) |
| `TYPE_TEXT` | Type a string of text |

## Configuring Buttons

The button layout and actions are stored in ESP32's LittleFS as `config.json`. A `default_config.json` is included. Edit from the web UI by tapping the gear icon, or flash a custom config.

## Tech Stack

- **ESP32**: Arduino framework, ESPAsyncWebServer, WiFiManager, LittleFS, ArduinoOTA
- **Web UI**: Vanilla JS SPA, WebSocket, CSS glassmorphism
- **PC Agent**: Python, pyserial, Core Audio COM, SendInput

## License

MIT
