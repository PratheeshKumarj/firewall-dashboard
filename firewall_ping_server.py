"""
Firewall Ping Status Server
============================
Pings all firewalls every 30 seconds and serves results via HTTP.
Deployable on Railway.app (free tier).

Local usage:
    pip install flask flask-cors
    python firewall_ping_server.py

Cloud (Railway):
    Just push this folder to GitHub and connect to Railway.
"""

import os
import subprocess
import platform
import threading
import time
import re
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

# ── Firewall list ─────────────────────────────────────────────────────────────

FIREWALLS = [
    {"no": 1, "brand": "Fortigate", "model": "FGT 80E",       "sn": "FGT80ETK20024949",  "ip": "192.168.107.1",   "fw": "v6.2.3 build1066 (GA)",           "loc": "Kadappa (Chakarayepeta)",          "lic": False},
    {"no": 2, "brand": "Sophose",   "model": "XG86",           "sn": "C0A102CFDVCFM22",   "ip": "172.16.0.100",    "fw": "SFOS 20.0.3 MR-3-Build427",       "loc": "Kovilpatti (TN)",                  "lic": False},
    {"no": 3, "brand": "Sophose",   "model": "Sophos xgs107",  "sn": "X1012162JMRKM59",   "ip": "10.10.0.10",      "fw": "SONICOS Enhanced 6.5.4.4-44n",    "loc": "Gondal",                           "lic": True },
    {"no": 4, "brand": "Fortigate", "model": "FGT 40F",        "sn": "FGT40FTK24096781",  "ip": "10.10.20.1",      "fw": "v7.2.6 build1575 (Feature)",      "loc": "Pavagada, Tumkur (Dist)",          "lic": True },
    {"no": 5, "brand": "Fortigate", "model": "Fortigate 40F",  "sn": "FGT40FTK2309AQ5X",  "ip": "192.168.1.105",   "fw": "v7.2.11 build1740 (Mature)",      "loc": "Melathulukkankkulam Village, TN", "lic": True },
    {"no": 6, "brand": "Fortigate", "model": "FortiGate-40F",  "sn": "FGT40FTK2409AB2A",  "ip": "192.168.1.241",   "fw": "v7.2.6 build1575 (Feature)",      "loc": "Saharanpur",                       "lic": True },
    {"no": 7, "brand": "Fortigate", "model": "Fortigate 30E",  "sn": "FGT30E5619076193",  "ip": "115.244.235.198", "fw": "v6.0.6 build0272 (GA)",           "loc": "Katol",                            "lic": False},
    {"no": 8, "brand": "Sophos",    "model": "SOHO250",        "sn": "2CB8ED473ACC",       "ip": "172.16.0.100",    "fw": "SonicOS Enhanced 6.5.4.15-117n", "loc": "UP (Shahjahanpur)",                "lic": True },
    {"no": 9, "brand": "Sophos",    "model": "SOHO250",        "sn": "2CB8ED9A4460",       "ip": "172.16.0.100",    "fw": "SONICOS Enhanced 6.5.4.4-44n",   "loc": "Atharga (Karnataka)",              "lic": False},
]

# ── Ping logic ────────────────────────────────────────────────────────────────

def ping(ip: str) -> dict:
    system = platform.system().lower()
    cmd = ["ping", "-n", "1", "-w", "1000", ip] if system == "windows" \
          else ["ping", "-c", "1", "-W", "1", ip]
    try:
        start = time.time()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        elapsed_ms = round((time.time() - start) * 1000)
        if result.returncode == 0:
            output = result.stdout.decode(errors="ignore")
            m = re.search(r"[Tt]ime[=<](\d+)", output)
            latency = int(m.group(1)) if m else elapsed_ms
            return {"online": True, "latency_ms": latency}
        return {"online": False, "latency_ms": None}
    except Exception:
        return {"online": False, "latency_ms": None}

# ── Shared state ──────────────────────────────────────────────────────────────

status_store = {}
store_lock   = threading.Lock()

def ping_all():
    unique_ips = list({fw["ip"] for fw in FIREWALLS})
    for ip in unique_ips:
        result = ping(ip)
        with store_lock:
            status_store[ip] = {**result, "last_checked": datetime.now().strftime("%H:%M:%S")}
        state = "ONLINE" if result["online"] else "OFFLINE"
        lat   = f"{result['latency_ms']} ms" if result["latency_ms"] else "—"
        print(f"  {ip:<20} {state:<8} {lat}", flush=True)

def background_pinger(interval=30):
    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Pinging {len(FIREWALLS)} firewalls…", flush=True)
        ping_all()
        time.sleep(interval)

# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route("/status")
def get_status():
    with store_lock:
        snap = dict(status_store)
    result = []
    for fw in FIREWALLS:
        s = snap.get(fw["ip"], {"online": None, "latency_ms": None, "last_checked": "—"})
        result.append({**fw, **s})
    return jsonify({"firewalls": result, "server_time": datetime.now().strftime("%H:%M:%S")})

@app.route("/ping/<ip>")
def ping_one(ip):
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return jsonify({"error": "Invalid IP"}), 400
    result = ping(ip)
    with store_lock:
        status_store[ip] = {**result, "last_checked": datetime.now().strftime("%H:%M:%S")}
    return jsonify(result)

# Serve dashboard HTML directly from the server URL
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))   # Railway sets PORT automatically
    print("=" * 50, flush=True)
    print(f"  Firewall Ping Server — port {port}", flush=True)
    print("=" * 50, flush=True)
    t = threading.Thread(target=background_pinger, args=(30,), daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=port, debug=False)
