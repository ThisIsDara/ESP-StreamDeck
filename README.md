# ESP-StreamDeck

ESP32-powered wireless Stream Deck — **work in progress**.

Currently prototyping with a phone browser as the touchscreen UI. Plan to add a physical TFT display, rotary knobs, and tactile buttons later for a self-contained device.

![Status](https://img.shields.io/badge/Status-WIP-yellow)
![Hardware](https://img.shields.io/badge/Hardware-ESP32--WROOM-blue)
![Web](https://img.shields.io/badge/UI-Web%20SPA-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## How It Works

```
┌──────────────┐      WiFi      ┌──────────┐    Serial    ┌──────────────────┐
│ Phone/Browser │ ──────────────> │  ESP32   │ ───────────> │  PC Agent        │
│ (SPA web UI)  │   WebSocket    │ (Web GUI) │   COM3       │  (action runner) │
│               │ <────────────── │          │ <─────────── │                  │
└──────────────┘                └──────────┘              └──────────────────┘
```

- **Phone/browser**: Touchscreen Stream Deck UI via WebSocket (placeholder until physical TFT arrives)
- **ESP32**: Serves the web UI, relays button presses over serial
- **PC Agent** (`pc_agent.py`): Receives serial commands and executes them on Windows

## Features

- Configurable buttons: media keys, volume, keyboard shortcuts, app launcher, text typer
- Hold-to-repeat: hold a button for 350ms → repeats every 80ms
- Volume slider: real-time, no Windows OSD popup (Core Audio COM)
- Glassmorphism UI: dark amber theme, adaptive grid, landscape-optimized
- WiFi Manager: captive portal for first-time WiFi setup
- OTA updates: upload firmware over the air
- Configurable via `config.json` (mDNS name, serial, volume, etc.)
- Optional `streamdeck.local` via mDNS or DNS forwarder

## Quick Start

### 1. Flash the ESP32

```bash
pio run -t upload && pio run -t uploadfs
```

Connect to serial, follow WiFi Manager captive portal to set up WiFi.

### 2. Run the PC Agent

```bash
python configure.py
```

From the menu: install dependencies, then start the agent.

### 3. Access the Web UI

Open `http://<esp32-ip>/` in your phone browser. Configure via the gear icon.

## Configuration

All settings live in `config.json` in the project root:

| Key | Default | Description |
|---|---|---|
| `mdns_name` | `streamdeck` | mDNS hostname (e.g. `streamdeck.local`) |
| `serial_port` | `auto` | Serial port (`COM3`) or `auto`-detect |
| `serial_baud` | `115200` | Serial baud rate |
| `serial_timeout` | `0.05` | Serial read timeout (seconds) |
| `volume_step` | `0.05` | Volume increment per press (0.0–1.0) |

Edit via `configure.py` or directly in `config.json`.

## Available Actions

| Action | Description |
|---|---|
| `PLAY_PAUSE` | Media play/pause |
| `NEXT_TRACK` | Media next track |
| `PREV_TRACK` | Media previous track |
| `VOL_UP` | Volume up |
| `VOL_DOWN` | Volume down |
| `SET_VOLUME` | Set volume to percentage (0-100) |
| `MUTE` | Toggle mute |
| `KEY_COMBO` | Send keyboard shortcut (e.g. `Ctrl+S`) |
| `OPEN_APP` | Launch application (e.g. `notepad.exe`) |
| `TYPE_TEXT` | Type a string of text |

## Project Structure

```
├── config.json          # PC agent settings
├── configure.py         # TUI installer & configurator
├── pc_agent.py          # Windows action runner
├── src/main.cpp         # ESP32 firmware
├── data/                # Web UI & ESP32 config
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── settings.json    # ESP32 runtime settings (mDNS name)
├── default_config.json  # Default button layout
└── platformio.ini       # PlatformIO config
```

## License

MIT
