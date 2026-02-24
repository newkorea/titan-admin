#!/usr/bin/env python3
"""Deploy MemoryLimit to xray.service on all servers."""
import os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/home/newkorea/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django; django.setup()
from django.db import connections

SSH = '-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes'

def get_servers():
    cursor = connections['default'].cursor()
    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1 AND v2_port=9999 AND protocol LIKE '%%V2RAY%%' ORDER BY name")
    return cursor.fetchall()

def deploy(ip, name):
    try:
        # Read current service file
        r = subprocess.run(f"ssh {SSH} root@{ip} cat /etc/systemd/system/xray.service",
                          shell=True, capture_output=True, text=True, timeout=15)
        content = r.stdout
        if not content or '[Service]' not in content:
            return (name, ip, 'FAIL', 'Cannot read xray.service')
        
        if 'MemoryLimit' in content or 'MemoryMax' in content:
            return (name, ip, 'SKIP', 'Already has memory limit')
        
        # Add MemoryLimit after LimitNOFILE line
        new_content = content.replace('LimitNOFILE=65535', 'LimitNOFILE=65535\nMemoryLimit=1500M')
        
        # Write back via SSH
        escaped = new_content.replace("'", "'\\''")
        cmd = f"ssh {SSH} root@{ip} \"echo '{escaped}' > /etc/systemd/system/xray.service && systemctl daemon-reload\""
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        # Verify
        r = subprocess.run(f"ssh {SSH} root@{ip} grep -c MemoryLimit /etc/systemd/system/xray.service",
                          shell=True, capture_output=True, text=True, timeout=10)
        if r.stdout.strip() == '1':
            return (name, ip, 'OK', 'MemoryLimit=1500M added')
        else:
            return (name, ip, 'FAIL', f'Verify failed: {r.stdout.strip()}')
    except subprocess.TimeoutExpired:
        return (name, ip, 'TIMEOUT', '')
    except Exception as e:
        return (name, ip, 'ERROR', str(e)[:80])

servers = get_servers()
print(f"Deploying MemoryLimit=1500M to {len(servers)} servers...")

ok = fail = skip = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(deploy, ip, name): name for ip, name in servers}
    for f in as_completed(futures):
        name, ip, status, msg = f.result()
        sym = '✓' if status == 'OK' else '-' if status == 'SKIP' else '✗'
        print(f"  {sym} {name:20s} ({ip:18s}) → {msg}")
        if status == 'OK': ok += 1
        elif status == 'SKIP': skip += 1
        else: fail += 1

print(f"\nDone: {ok} updated, {skip} skipped, {fail} failed / {len(servers)} total")
