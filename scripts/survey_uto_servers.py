#!/usr/bin/env python3
"""Survey all UTO strongSwan servers for dbsync.py status."""
import subprocess

SERVERS = [
    "125.132.9.175", "218.233.115.163", "14.51.2.181", "218.49.179.88",
    "218.49.179.85", "218.49.179.84", "218.49.179.87", "218.49.179.89",
    "211.46.6.242", "218.158.57.67", "218.49.179.86", "112.218.79.74",
    "218.49.179.81", "125.132.9.174", "218.49.179.83", "218.49.179.80",
    "218.158.57.91", "211.46.6.241", "218.233.115.162", "125.132.9.170",
    "218.49.179.90", "14.51.2.182", "211.46.6.243", "125.132.9.171",
    "218.233.115.164", "125.132.9.173", "218.236.231.229", "218.236.231.230",
    "118.34.105.238",
]

CMD = "wc -l /etc/strongswan/dbsync.py 2>/dev/null || echo '0 NONE'; grep -c insert_radacct_row /etc/strongswan/dbsync.py 2>/dev/null || echo 0; crontab -l 2>/dev/null | grep -c 'flock.*dbsync' || echo 0; grep -c openvpn /etc/strongswan/dbsync.py 2>/dev/null || echo 0"

for ip in SERVERS:
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "root@" + ip, CMD],
            capture_output=True, text=True, timeout=12
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split('\n')
            lines = parts[0].split()[0] if parts else '?'
            insert = parts[1] if len(parts) > 1 else '?'
            flock = parts[2] if len(parts) > 2 else '?'
            ovpn = parts[3] if len(parts) > 3 else '?'
            print(f"{ip:20s} lines={lines:>4s} insert={insert} flock={flock} ovpn={ovpn}")
        else:
            print(f"{ip:20s} SSH_ERROR rc={r.returncode}")
    except subprocess.TimeoutExpired:
        print(f"{ip:20s} SSH_TIMEOUT")
    except Exception as e:
        print(f"{ip:20s} ERROR: {e}")
