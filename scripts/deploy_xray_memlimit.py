#!/usr/bin/env python3
"""Deploy MemoryMax limit to xray.service on all servers to prevent OOM."""
import os, sys, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/home/newkorea/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django; django.setup()
from django.db import connections

SSH_OPTS = '-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes'

# xray.service with MemoryMax limit
XRAY_SERVICE = """[Unit]
Description=Xray Service
After=network.target

[Service]
Type=simple
Environment="XRAY_VMESS_AEAD_FORCED=false"
ExecStart=/usr/local/xray/xray run -config /usr/local/xray/config.json
Restart=on-failure
RestartSec=3
LimitNOFILE=65535
MemoryMax=1500M
MemoryHigh=1200M

[Install]
WantedBy=multi-agent.target
"""

def get_servers():
    cursor = connections['default'].cursor()
    cursor.execute('''
        SELECT hostip, name FROM tbl_agent3 
        WHERE is_active = 1 AND v2_port = 9999 AND protocol LIKE '%%V2RAY%%'
        ORDER BY name
    ''')
    return cursor.fetchall()

def deploy_limit(ip, name):
    try:
        # Check if MemoryMax already set
        cmd = f"ssh {SSH_OPTS} root@{ip} 'grep -c MemoryMax /etc/systemd/system/xray.service 2>/dev/null || echo 0'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.stdout.strip() != '0':
            return (name, ip, 'SKIP', 'MemoryMax already set')
        
        # Check if systemd supports MemoryMax (cgroup v2 or unified)
        # CentOS 7 uses cgroup v1 - need MemoryLimit instead
        cmd = f"ssh {SSH_OPTS} root@{ip} 'cat /etc/os-release 2>/dev/null | head -1; stat /sys/fs/cgroup/memory 2>/dev/null | head -1 || echo NO_CGROUPV1'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        is_centos7 = 'centos' in result.stdout.lower() or 'CentOS' in result.stdout
        has_cgroupv1 = '/sys/fs/cgroup/memory' in result.stdout
        
        # For CentOS 7 (cgroup v1), use MemoryLimit instead of MemoryMax
        if has_cgroupv1:
            mem_directive = 'MemoryLimit=1500M'
        else:
            mem_directive = 'MemoryMax=1500M'
        
        # Add MemoryLimit/MemoryMax to existing service file
        cmd = f"""ssh {SSH_OPTS} root@{ip} '
            if ! grep -q "MemoryMax\\|MemoryLimit" /etc/systemd/system/xray.service 2>/dev/null; then
                sed -i "/\\[Service\\]/a {mem_directive}" /etc/systemd/system/xray.service
                systemctl daemon-reload
                echo "ADDED"
            else
                echo "ALREADY_SET"
            fi
        '"""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        output = result.stdout.strip()
        
        if 'ADDED' in output:
            return (name, ip, 'OK', f'{mem_directive} added')
        elif 'ALREADY_SET' in output:
            return (name, ip, 'SKIP', 'Already configured')
        else:
            return (name, ip, 'FAIL', f'{result.stderr.strip()[:80]}')
            
    except subprocess.TimeoutExpired:
        return (name, ip, 'TIMEOUT', '')
    except Exception as e:
        return (name, ip, 'ERROR', str(e)[:80])

servers = get_servers()
print(f"Deploying MemoryLimit to {len(servers)} servers...")

ok = fail = skip = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(deploy_limit, ip, name): (ip, name) for ip, name in servers}
    for f in as_completed(futures):
        name, ip, status, msg = f.result()
        if status == 'OK':
            ok += 1
            print(f"  ✓ {name:20s} ({ip:18s}) → {msg}")
        elif status == 'SKIP':
            skip += 1
            print(f"  - {name:20s} ({ip:18s}) → {msg}")
        else:
            fail += 1
            print(f"  ✗ {name:20s} ({ip:18s}) → {status}: {msg}")

print(f"\nResult: {ok} updated, {skip} skipped, {fail} failed / {len(servers)} total")
