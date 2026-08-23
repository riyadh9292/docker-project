"""
Metrics Collector
A tiny dependency-free HTTP API (stdlib only) that exposes system metrics.

Endpoints:
    GET /status  -> JSON with hostname, uptime, disk usage, memory usage
    GET /health  -> simple liveness probe

Every successful /status call is appended to /data/access.log so the
data survives container restarts as long as /data is a mounted volume.
"""

import json
import os
import shutil
import socket
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 6000
DATA_DIR = "/data"
LOG_FILE = os.path.join(DATA_DIR, "access.log")


def get_uptime_seconds():
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.readline().split()[0])
    except FileNotFoundError:
        return None


def get_memory_info():
    mem = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, value = line.split(":", 1)
                mem[key.strip()] = value.strip()
        total_kb = int(mem.get("MemTotal", "0 kB").split()[0])
        avail_kb = int(mem.get("MemAvailable", "0 kB").split()[0])
        used_kb = total_kb - avail_kb
        return {
            "total_mb": round(total_kb / 1024, 1),
            "used_mb": round(used_kb / 1024, 1),
            "available_mb": round(avail_kb / 1024, 1),
        }
    except FileNotFoundError:
        return None


def get_disk_usage():
    total, used, free = shutil.disk_usage("/")
    return {
        "total_gb": round(total / (1024 ** 3), 2),
        "used_gb": round(used / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
    }


def build_status_payload():
    return {
        "service": "metrics-collector",
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": get_uptime_seconds(),
        "disk": get_disk_usage(),
        "memory": get_memory_info(),
    }


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def log_request(payload):
    ensure_data_dir()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(payload) + "\n")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            payload = build_status_payload()
            log_request(payload)
            self._send_json(200, payload)
        elif self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found", "path": self.path})

    def log_message(self, fmt, *args):
        # Keep container logs quiet/clean; access.log in the volume has detail.
        print("[collector] %s - %s" % (self.address_string(), fmt % args))


def main():
    ensure_data_dir()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[collector] listening on 0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
