"""
ESP-StreamDeck TUI Installer & Configurator
Run: python configure.py
"""

import os, sys, json, subprocess, shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
ESP_IP_FILE = os.path.join(SCRIPT_DIR, "esp_ip.txt")
TASK_NAME = "StreamDeckAgent"

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

def p(title, msg="", color=CYAN):
    print(f"{color}{BOLD}{title}{RESET} {msg}")

def load_config():
    default = {
        "mdns_name": "streamdeck",
        "serial_port": "auto",
        "serial_baud": 115200,
        "serial_timeout": 0.05,
        "volume_step": 0.05
    }
    try:
        with open(CONFIG_FILE) as f:
            default.update(json.load(f))
    except:
        pass
    return default

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
    p("Saved", CONFIG_FILE, GREEN)

def run(cmd, capture=False):
    try:
        if capture:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=SCRIPT_DIR)
            return r.stdout, r.stderr, r.returncode
        r = subprocess.run(cmd, shell=True, cwd=SCRIPT_DIR)
        return r.returncode == 0
    except:
        return ("", "", -1) if capture else False

def edit_settings():
    cfg = load_config()
    fields = [
        ("mdns_name", "mDNS name", "streamdeck"),
        ("serial_port", "Serial port (auto or COMx)", "auto"),
        ("serial_baud", "Serial baud rate", "115200"),
        ("serial_timeout", "Serial timeout (seconds)", "0.05"),
        ("volume_step", "Volume step (0.0-1.0)", "0.05"),
    ]
    for key, label, default in fields:
        current = cfg.get(key, default)
        val = input(f"  {label} [{current}]: ").strip()
        if val:
            if key in ("serial_baud",):
                cfg[key] = int(val)
            elif key in ("serial_timeout", "volume_step"):
                cfg[key] = float(val)
            else:
                cfg[key] = val
    save_config(cfg)

def install_deps():
    pkgs = ["pyserial", "comtypes", "pycaw", "zeroconf"]
    p("Installing dependencies...", color=YELLOW)
    for pkg in pkgs:
        print(f"  {pkg}...", end=" ", flush=True)
        ok = run(f'pip install {pkg}')
        print(f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}")

def install_service():
    p("Installing Windows scheduled task...", color=YELLOW)
    script = os.path.join(SCRIPT_DIR, "pc_agent.py")
    runner = f'"{sys.executable}" "{script}"'

    subprocess.run(
        f'schtasks /create /tn "{TASK_NAME}" '
        f'/tr "{runner}" /sc onlogon /rl highest /f',
        shell=True
    )
    p("Scheduled task created. Will auto-start on next login.", GREEN)
    ans = input("  Start now? [Y/n]: ").strip().lower()
    if ans != "n":
        subprocess.Popen(f'start "" "{sys.executable}" "{script}"', shell=True)
        p("Agent started.", GREEN)

def remove_service():
    p("Removing scheduled task...", color=YELLOW)
    subprocess.run(f"schtasks /end /tn {TASK_NAME}", shell=True, capture_output=True)
    subprocess.run(f"schtasks /delete /tn {TASK_NAME} /f", shell=True, capture_output=True)
    subprocess.run("taskkill /F /IM pythonw.exe", shell=True, capture_output=True)
    p("Scheduled task removed.", GREEN)

def flash_esp32():
    p("Flashing ESP32 firmware...", color=YELLOW)
    if not shutil.which("pio"):
        p("PlatformIO CLI not found. Install: pip install platformio", RED)
        return
    ok = run("pio run -t upload")
    if not ok:
        p("Firmware upload failed.", RED)
        return
    p("Uploading filesystem...", color=YELLOW)
    run("pio run -t uploadfs")
    p("ESP32 flashed!", GREEN)

def show_status():
    cfg = load_config()
    print(f"\n  {BOLD}Config:{RESET}")
    for k, v in cfg.items():
        print(f"    {k}: {v}")
    print(f"  {BOLD}Scheduled task:{RESET}", end=" ")
    r = subprocess.run(f"schtasks /query /tn {TASK_NAME}", shell=True, capture_output=True, text=True)
    print(f"{GREEN}Installed{RESET}" if r.returncode == 0 else f"{RED}Not installed{RESET}")
    print(f"  {BOLD}ESP IP:{RESET}", end=" ")
    try:
        with open(ESP_IP_FILE) as f:
            print(f"{GREEN}{f.read().strip()}{RESET}")
    except:
        print(f"{YELLOW}Unknown (run agent to detect){RESET}")
    print(f"  {BOLD}Dependencies:{RESET}")
    for pkg in ["serial", "zeroconf", "comtypes", "pycaw"]:
        try:
            __import__(pkg)
            print(f"    {pkg}: {GREEN}OK{RESET}")
        except:
            print(f"    {pkg}: {RED}Missing{RESET}")

def open_web():
    try:
        with open(ESP_IP_FILE) as f:
            url = f.read().strip()
        subprocess.run(f'start "" "{url}"', shell=True)
        p(f"Opened {url}", GREEN)
    except:
        p("No ESP IP found. Start the agent first.", RED)

def menu():
    items = [
        ("Edit settings", edit_settings),
        ("Install dependencies", install_deps),
        ("Install Windows scheduled task", install_service),
        ("Remove scheduled task", remove_service),
        ("Flash ESP32 firmware", flash_esp32),
        ("Show status", show_status),
        ("Open web UI", open_web),
        ("Exit", None),
    ]
    while True:
        print(f"\n{CYAN}{BOLD}═══ ESP-StreamDeck Configuration ═══{RESET}\n")
        for i, (label, _) in enumerate(items, 1):
            print(f"  {i}. {label}")
        try:
            choice = input(f"\n  Choice [1-{len(items)}]: ").strip()
            if not choice:
                continue
            idx = int(choice) - 1
            if idx < 0 or idx >= len(items):
                continue
            _, fn = items[idx]
            if fn is None:
                print()
                break
            fn()
            input(f"\n  {YELLOW}Press Enter to continue...{RESET}")
        except (ValueError, EOFError, KeyboardInterrupt):
            print()
            break

if __name__ == "__main__":
    menu()
