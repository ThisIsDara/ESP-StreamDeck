"""
Stream Deck PC Agent v2
Reads serial commands from ESP32, executes them on Windows.
"""

import sys, time, argparse, logging, subprocess, ctypes, os, re
from ctypes import wintypes

try:
    import serial, serial.tools.list_ports
except ImportError:
    print("Missing pyserial. Install: pip install pyserial")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S", level=logging.INFO)

_script_dir = os.path.dirname(os.path.abspath(__file__))
_esp_ip_file = os.path.join(_script_dir, 'esp_ip.txt')
_config_file = os.path.join(_script_dir, 'config.json')

def load_config():
    default = {
        "mdns_name": "streamdeck",
        "serial_port": "auto",
        "serial_baud": 115200,
        "serial_timeout": 0.05,
        "volume_step": 0.05
    }
    try:
        with open(_config_file) as f:
            import json
            cfg = json.load(f)
            default.update(cfg)
    except:
        pass
    return default

cfg = load_config()
MDNS_NAME = cfg["mdns_name"]
SERIAL_PORT = cfg["serial_port"]
SERIAL_BAUD = cfg["serial_baud"]
SERIAL_TIMEOUT = cfg["serial_timeout"]
VOLUME_STEP = cfg["volume_step"]

# --- mDNS registration ---
_mdns = None
try:
    from zeroconf import Zeroconf, ServiceInfo
    import socket as _sock
    def start_mdns(ip):
        global _mdns
        try:
            if _mdns:
                _mdns.close()
            host = f"{MDNS_NAME}.local."
            info = ServiceInfo("_http._tcp.local.", f"{MDNS_NAME}._http._tcp.local.",
                               addresses=[_sock.inet_aton(ip)], port=80, server=host)
            _mdns = Zeroconf()
            _mdns.register_service(info)
            logging.info(f"mDNS: {MDNS_NAME}.local -> {ip}")
        except Exception as e:
            logging.warning(f"mDNS failed: {e}")
    def stop_mdns():
        global _mdns
        if _mdns:
            _mdns.close()
            _mdns = None
except ImportError:
    def start_mdns(ip): pass
    def stop_mdns(): pass
    logging.info("mDNS: pip install zeroconf to enable")

# --- DNS forwarder (zero deps) ---
_dns_stop = None
_dns_thread = None
import socket as _sock2, threading, struct as _struct

def _dns_build_response(tid, qname_raw, qtype, qclass, answer_ip):
    flags = _struct.pack('>H', 0x8180)  # response, no error
    qdcount = _struct.pack('>H', 1)
    ancount = _struct.pack('>H', 1)
    nscount = _struct.pack('>H', 0)
    arcount = _struct.pack('>H', 0)
    header = _struct.pack('>H', tid) + flags + qdcount + ancount + nscount + arcount
    answer_name = qname_raw
    answer_type = _struct.pack('>H', qtype)
    answer_class = _struct.pack('>H', qclass)
    ttl = _struct.pack('>I', 30)
    rdlen = _struct.pack('>H', 4)
    rdata = _sock2.inet_aton(answer_ip)
    answer = answer_name + answer_type + answer_class + ttl + rdlen + rdata
    return header + qname_raw + answer

def _dns_parse_question(data):
    pos = 12
    qname_parts = []
    while pos < len(data):
        l = data[pos]
        if l == 0:
            pos += 1
            break
        pos += 1
        qname_parts.append(data[pos:pos+l].decode('ascii', errors='ignore'))
        pos += l
    qname = '.'.join(qname_parts)
    qtype, qclass = _struct.unpack('>HH', data[pos:pos+4])
    return qname, qtype, qclass, data[12:pos+4]

def start_dns(ip):
    global _dns_stop, _dns_thread
    if _dns_thread and _dns_thread.is_alive():
        _dns_stop.set()
        _dns_thread.join(timeout=3)
    _dns_stop = threading.Event()
    _dns_thread = threading.Thread(target=_dns_worker, args=(ip, _dns_stop), daemon=True)
    _dns_thread.start()

def stop_dns():
    if _dns_stop:
        _dns_stop.set()

def _dns_worker(ip, stop):
    sock = _sock2.socket(_sock2.AF_INET, _sock2.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', 53))
    except PermissionError:
        return
    sock.settimeout(1)
    fqdn = f"{MDNS_NAME}.local"
    names = (fqdn.lower(), MDNS_NAME.lower())
    logging.info(f"DNS: {fqdn} -> {ip}")
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(512)
            tid = _struct.unpack('>H', data[:2])[0]
            qname, qtype, qclass, qraw = _dns_parse_question(data)
            if qtype == 1 and qclass == 1 and qname.lower() in names:
                reply = _dns_build_response(tid, qraw, qtype, qclass, ip)
                sock.sendto(reply, addr)
            else:
                fs = _sock2.socket(_sock2.AF_INET, _sock2.SOCK_DGRAM)
                fs.settimeout(2)
                try:
                    fs.sendto(data, ('8.8.8.8', 53))
                    rd, _ = fs.recvfrom(512)
                    sock.sendto(rd, addr)
                except: pass
                finally: fs.close()
        except _sock2.timeout: continue
        except Exception as e: logging.warning(f"DNS: {e}")

# --- Core Audio COM volume (silent, no OSD) ---
user32 = ctypes.windll.user32
WM_APPCOMMAND = 0x0319
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_MEDIA_NEXT_TRACK = 11
APPCOMMAND_MEDIA_PREV_TRACK = 12

try:
    import comtypes
    from comtypes import CLSCTX_ALL, POINTER, cast
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    comtypes.CoInitialize()
    _vol = cast(
        AudioUtilities.GetDeviceEnumerator()
        .GetDefaultAudioEndpoint(0, 0)
        .Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
        POINTER(IAudioEndpointVolume)
    )
    def vol_up(v=None): _vol.SetMasterVolumeLevelScalar(min(1.0, _vol.GetMasterVolumeLevelScalar() + VOLUME_STEP), None)
    def vol_down(v=None): _vol.SetMasterVolumeLevelScalar(max(0.0, _vol.GetMasterVolumeLevelScalar() - VOLUME_STEP), None)
    def vol_set(v): _vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, float(v) / 100.0)), None)
    def mute(v=None): _vol.SetMute(not bool(_vol.GetMute()), None)
    logging.info("Volume: Core Audio")
except Exception as e:
    logging.warning(f"Volume unavailable: {e}")
    vol_up = vol_down = mute = lambda v: None
    vol_set = lambda v: None

# --- Keyboard simulation via SendInput ---
SendInput = ctypes.windll.user32.SendInput
VK_MAP = {
    'ctrl':0x11,'control':0x11,'alt':0x12,'shift':0x10,'win':0x5B,'windows':0x5B,'gui':0x5B,
    'escape':0x1B,'esc':0x1B,'enter':0x0D,'return':0x0D,'tab':0x09,'space':0x20,'backspace':0x08,
    'delete':0x2E,'del':0x2E,'insert':0x2D,'home':0x24,'end':0x23,
    'pageup':0x21,'pagedown':0x22,'up':0x26,'down':0x28,'left':0x25,'right':0x27,
    'capslock':0x14,'f1':0x70,'f2':0x71,'f3':0x72,'f4':0x73,'f5':0x74,'f6':0x75,
    'f7':0x76,'f8':0x77,'f9':0x78,'f10':0x79,'f11':0x7A,'f12':0x7B,
}

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk",wintypes.WORD),("wScan",wintypes.WORD),("dwFlags",wintypes.DWORD),("time",wintypes.DWORD),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki",KEYBDINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type",wintypes.DWORD),("union",INPUT_UNION)]

def _inp(vk, up=False):
    i = INPUT(type=1)
    i.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0x0002 if up else 0, time=0, dwExtraInfo=None)
    return i

def send_key(combo_str):
    parts = [p.strip() for p in combo_str.split('+')]
    vks = []
    for p in parts:
        p = p.lower()
        v = VK_MAP.get(p, ord(p.upper()) if len(p) == 1 else None)
        if v is None: return logging.warning(f"Unknown key: {p}")
        vks.append(v)
    for v in vks:
        SendInput(1, ctypes.byref(_inp(v)), ctypes.sizeof(INPUT))
    for v in reversed(vks):
        SendInput(1, ctypes.byref(_inp(v, True)), ctypes.sizeof(INPUT))

def type_text(text):
    for ch in text:
        vk = ord(ch.upper())
        shift = ch.isupper() or ch in '~!@#$%^&*()_+{}|:"<>?'
        if shift:
            SendInput(1, ctypes.byref(_inp(0x10)), ctypes.sizeof(INPUT))
        SendInput(1, ctypes.byref(_inp(vk)), ctypes.sizeof(INPUT))
        SendInput(1, ctypes.byref(_inp(vk, True)), ctypes.sizeof(INPUT))
        if shift:
            SendInput(1, ctypes.byref(_inp(0x10, True)), ctypes.sizeof(INPUT))
        time.sleep(0.01)

# --- Media keys ---
def press_media(cmd):
    hwnd = user32.GetForegroundWindow()
    user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, (cmd << 16) | 0)

ACTION_MAP = {
    'PLAY_PAUSE': lambda v: press_media(APPCOMMAND_MEDIA_PLAY_PAUSE),
    'NEXT_TRACK': lambda v: press_media(APPCOMMAND_MEDIA_NEXT_TRACK),
    'PREV_TRACK': lambda v: press_media(APPCOMMAND_MEDIA_PREV_TRACK),
    'VOL_UP': vol_up,
    'VOL_DOWN': vol_down,
    'MUTE': mute,
    'SET_VOLUME': lambda v: vol_set(v) if v else None,
    'KEY_COMBO': lambda v: send_key(v) if v else None,
    'OPEN_APP': lambda v: subprocess.Popen(v, shell=True) if v else None,
    'TYPE_TEXT': lambda v: type_text(v) if v else None,
}

# --- Serial handling ---
def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"  {p.device} - {p.description}")

def find_esp32():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        d = p.description.lower()
        if any(x in d for x in ('cp210','ch340','ch341','ft232','silicon')):
            return p.device
    for p in ports:
        if 'serial' in p.description.lower():
            return p.device
    return ports[0].device if ports else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list: return list_ports()

    port = args.port or (SERIAL_PORT if SERIAL_PORT != "auto" else None) or find_esp32()
    if not port:
        logging.error("No ESP32 found")
        list_ports()
        sys.exit(1)

    for attempt in range(30):
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
            break
        except serial.SerialException as e:
            logging.error(f"Failed ({attempt+1}/30): {e}")
            time.sleep(2)
    else:
        logging.error("Giving up on serial port")
        return

    time.sleep(1)
    ser.reset_input_buffer()
    logging.info(f"Listening on {port} ({SERIAL_BAUD} baud)")

    while True:
        try:
            line = ser.readline()
            if not line:
                continue
            line = line.decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            action, _, val = line.partition('|')
            action = action.strip()
            val = val.strip()
            if action in ACTION_MAP:
                logging.info(f"  -> {action}" + (f" | {val}" if val else ""))
                ACTION_MAP[action](val)
            elif 'IP:' in action or 'ip:' in action or 'http://' in action:
                m = re.search(r'(\d+\.\d+\.\d+\.\d+)', action)
                if m:
                    ip = m.group(1)
                    logging.info(f"ESP32 IP: {ip}")
                    try:
                        with open(_esp_ip_file, 'w') as f:
                            f.write(f'http://{ip}/\n')
                    except: pass
                    start_mdns(ip)
                    start_dns(ip)
            else:
                logging.warning(f"Unknown: {action}")
        except KeyboardInterrupt:
            logging.info("Stopped")
            ser.close()
            stop_mdns()
            stop_dns()
            return
        except serial.SerialException:
            logging.error("Lost connection")
            ser.close()
            break

if __name__ == '__main__':
    main()
