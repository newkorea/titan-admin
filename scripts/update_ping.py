#!/usr/bin/env python3
import os
import sys
import subprocess
import re
from typing import Optional

# Bootstrap Django
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django  # type: ignore
from django.db import connections  # type: ignore

django.setup()

PING_RE = re.compile(r'time[=<]([0-9]+\.?[0-9]*)\s*ms')

def parse_ping_output(out: str) -> Optional[int]:
    """Parse ping output; return slowest RTT in ms as int, or None if no reply.
    We collect all 'time=XX ms' numbers and return ceil of max.
    """
    times = [float(m.group(1)) for m in PING_RE.finditer(out)]
    if not times:
        return None
    return int(round(max(times)))


def ping_ip(ip: str) -> Optional[int]:
    try:
        # Use absolute /usr/bin/ping to avoid PATH issues under cron/systemd
        ping_bin = '/usr/bin/ping'
        # -c 3: 3 packets, -w 3: deadline 3s
        res = subprocess.run([ping_bin, '-c', '3', '-w', '3', ip], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return parse_ping_output(res.stdout)
    except Exception:
        return None


def ensure_ping_column():
    """Ensure titan.tbl_agent3 has a 'ping' column after 'config' with default 0 (INT NOT NULL DEFAULT 0)."""
    with connections['default'].cursor() as cur:
        cur.execute("SHOW COLUMNS FROM titan.tbl_agent3")
        cols = [r[0] for r in cur.fetchall()]
        if 'ping' not in cols:
            # Try add with default and NOT NULL
            try:
                cur.execute("ALTER TABLE titan.tbl_agent3 ADD COLUMN ping INT NOT NULL DEFAULT 0 AFTER config")
            except Exception:
                # If AFTER fails, try without AFTER
                try:
                    cur.execute("ALTER TABLE titan.tbl_agent3 ADD COLUMN ping INT NOT NULL DEFAULT 0")
                except Exception:
                    pass
        else:
            # Ensure default 0 and not null
            try:
                cur.execute("ALTER TABLE titan.tbl_agent3 MODIFY COLUMN ping INT NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("UPDATE titan.tbl_agent3 SET ping=0 WHERE ping IS NULL")
            except Exception:
                pass


def update_all_pings():
    with connections['default'].cursor() as cur:
        cur.execute("SELECT id, hostip FROM titan.tbl_agent3 WHERE IFNULL(hostip,'') <> ''")
        rows = cur.fetchall()
    for _id, ip in rows:
        ms = ping_ip(ip)
        with connections['default'].cursor() as cur:
            cur.execute("UPDATE titan.tbl_agent3 SET ping=%s WHERE id=%s", [ms if ms is not None else 0, _id])


def main():
    ensure_ping_column()
    update_all_pings()

if __name__ == '__main__':
    main()
