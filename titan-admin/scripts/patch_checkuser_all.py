#!/usr/bin/env python3
"""
patch_checkuser_all.py — 전체 VPN 서버의 checkuser.py에 acctsessiontime 패치 적용
patch_checkuser.sh를 scp로 전송 후 실행하는 방식
"""
import django, os, subprocess, socket, sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
sys.path.insert(0, '/home/newkorea/project/titan-admin')
django.setup()

from django.db import connections
from backend.djangoapps.common.views import dictfetchall

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATCH_SCRIPT = os.path.join(SCRIPT_DIR, 'patch_checkuser.sh')

cursor = connections['default'].cursor()
cursor.execute("""
    SELECT name, hostip, username, password
    FROM tbl_agent3
    WHERE hostip IS NOT NULL AND hostip != ''
    ORDER BY name
""")
rows = dictfetchall(cursor)

servers = []
for r in rows:
    ip = r['hostip']
    if not all(c.isdigit() or c == '.' for c in ip):
        try:
            ip = socket.gethostbyname(ip)
        except Exception:
            print(f"  [SKIP] {r['name']:20s} — DNS resolve failed for {r['hostip']}")
            continue
    servers.append((r['name'], ip, r['username'], r['password']))

print(f"총 {len(servers)}개 서버 패치 시작\n")

SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=8 -o ServerAliveInterval=5"

results = {'ok': [], 'already': [], 'nofile': [], 'warning': [], 'error': [], 'timeout': []}

for name, ip, user, passwd in servers:
    try:
        # 1) scp patch script
        scp_cmd = f"sshpass -p '{passwd}' scp {SSH_OPTS} {PATCH_SCRIPT} {user}@{ip}:/tmp/patch_checkuser.sh"
        r1 = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=15)
        if r1.returncode != 0:
            results['error'].append((name, f"SCP failed: {r1.stderr[:80]}"))
            print(f"  {name:20s} ({ip:18s}): ❌ SCP FAILED")
            continue

        # 2) execute
        ssh_cmd = f"sshpass -p '{passwd}' ssh {SSH_OPTS} {user}@{ip} 'bash /tmp/patch_checkuser.sh && rm -f /tmp/patch_checkuser.sh'"
        r2 = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = r2.stdout.strip().split('\n')[-1] if r2.stdout.strip() else 'EMPTY'

        if 'ALREADY_PATCHED' in out:
            results['already'].append(name)
            status = '✅ ALREADY'
        elif 'PATCHED_OK' in out:
            results['ok'].append(name)
            status = '✅ OK'
        elif 'NOFILE' in out:
            results['nofile'].append(name)
            status = '⚠️ NOFILE'
        elif 'PATCH_WARNING' in out:
            results['warning'].append(name)
            status = f'⚠️ WARNING: {out}'
        else:
            results['error'].append((name, out))
            status = f'❌ ERROR: {out[:60]}'

        print(f"  {name:20s} ({ip:18s}): {status}")
    except subprocess.TimeoutExpired:
        results['timeout'].append(name)
        print(f"  {name:20s} ({ip:18s}): ⏱️ TIMEOUT")
    except Exception as e:
        results['error'].append((name, str(e)))
        print(f"  {name:20s} ({ip:18s}): ❌ {e}")

# 결과 요약
print(f"\n{'='*60}")
print(f"패치 결과 요약")
print(f"{'='*60}")
print(f"  ✅ 패치 성공:     {len(results['ok'])}개")
print(f"  ✅ 이미 패치됨:   {len(results['already'])}개")
print(f"  ⚠️  파일 없음:    {len(results['nofile'])}개")
print(f"  ⚠️  부분 패치:    {len(results['warning'])}개")
print(f"  ❌ 오류:          {len(results['error'])}개")
print(f"  ⏱️  타임아웃:     {len(results['timeout'])}개")

if results['ok']:
    print(f"\n✅ 패치된 서버: {', '.join(results['ok'])}")
if results['already']:
    print(f"\n✅ 이미 패치됨: {', '.join(results['already'])}")
if results['warning']:
    print(f"\n⚠️ 부분 패치 서버 (수동 확인 필요): {', '.join(results['warning'])}")
if results['error']:
    print(f"\n❌ 오류 서버:")
    for n, e in results['error']:
        print(f"    {n}: {e}")
if results['timeout']:
    print(f"\n⏱️ 타임아웃 서버: {', '.join(results['timeout'])}")
