#!/usr/bin/env python3
"""
deploy_cleanup_all.py
모든 VPN NAS 서버에 cleanup_stale_qos.sh 배포 + cron 등록 + threads 설정 수정

작업 내용:
1. cleanup_stale_qos.sh → /etc/strongswan/cleanup_stale_qos.sh (SCP)
2. chmod +x + cron 등록 (*/5 * * * *)
3. strongswan.conf threads 설정 확인/수정 (재시작 없음!)
4. 즉시 1회 실행 (현재 stale 규칙 정리)
5. 현황 리포트

사용법: python3 deploy_cleanup_all.py
"""

import os
import sys
import subprocess
import time

# Django DB 연결
sys.path.insert(0, '/home/newkorea/project/titan-admin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()
from django.db import connections

SCRIPT_LOCAL = '/home/newkorea/project/scripts/cleanup_stale_qos.sh'
SCRIPT_REMOTE = '/etc/strongswan/cleanup_stale_qos.sh'
CRON_LINE = '*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh'
DESIRED_THREADS = 32
SSH_TIMEOUT = 12


def get_all_servers():
    """tbl_agent3에서 활성 서버 목록 조회"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT name, hostip, password
        FROM tbl_agent3
        WHERE is_active = 1
        ORDER BY name
    """)
    rows = cursor.fetchall()
    return [{'name': r[0], 'ip': r[1], 'pw': r[2]} for r in rows]


def ssh_cmd(ip, pw, cmd, timeout=SSH_TIMEOUT):
    """SSH 명령 실행"""
    full = (
        f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
        f"-o ConnectTimeout={timeout} -o ServerAliveInterval=5 "
        f"root@{ip} \"{cmd}\""
    )
    try:
        r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout + 5)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', 'TIMEOUT', -1


def scp_file(ip, pw, local, remote, timeout=SSH_TIMEOUT):
    """SCP 파일 전송"""
    full = (
        f"sshpass -p '{pw}' scp -o StrictHostKeyChecking=no "
        f"-o ConnectTimeout={timeout} "
        f"{local} root@{ip}:{remote}"
    )
    try:
        r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout + 5)
        return r.returncode == 0, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, 'TIMEOUT'


def deploy_one(server):
    """한 서버에 배포"""
    name = server['name']
    ip = server['ip']
    pw = server['pw']
    result = {
        'name': name, 'ip': ip,
        'ssh': False, 'has_strongswan': False,
        'script_deployed': False, 'cron_set': False,
        'threads_before': '?', 'threads_fixed': False,
        'cleanup_ran': False, 'stale_before': '?', 'stale_after': '?',
        'error': ''
    }

    # 1. SSH 연결 테스트 + strongswan 존재 확인
    out, err, rc = ssh_cmd(ip, pw, 'which strongswan 2>/dev/null && echo HAS_SS || echo NO_SS')
    if rc != 0 and 'TIMEOUT' in err:
        result['error'] = 'SSH timeout'
        return result
    if rc != 0:
        result['error'] = f'SSH failed: {err[:80]}'
        return result
    result['ssh'] = True

    if 'NO_SS' in out:
        result['error'] = 'No strongswan'
        return result
    result['has_strongswan'] = True

    # 2. SCP 스크립트 업로드
    ok, err = scp_file(ip, pw, SCRIPT_LOCAL, SCRIPT_REMOTE)
    if not ok:
        result['error'] = f'SCP failed: {err[:80]}'
        return result
    result['script_deployed'] = True

    # 3. chmod + cron 등록 + threads 확인 + 현황 수집 (한번의 SSH로)
    commands = f"""
# chmod
chmod +x {SCRIPT_REMOTE}

# cron 등록 (중복 방지)
CRON_EXISTS=$(crontab -l 2>/dev/null | grep -c 'cleanup_stale_qos')
if [ "$CRON_EXISTS" = "0" ]; then
    (crontab -l 2>/dev/null; echo '{CRON_LINE}') | crontab -
    echo 'CRON_ADDED'
else
    echo 'CRON_EXISTS'
fi

# threads 확인
THREADS=$(grep -oP 'threads\\s*=\\s*\\K[0-9]+' /etc/strongswan/strongswan.conf 2>/dev/null | head -1)
echo "THREADS_BEFORE=$THREADS"

# threads < {DESIRED_THREADS}이면 수정 (재시작 없음!)
if [ -n "$THREADS" ] && [ "$THREADS" -lt {DESIRED_THREADS} ] 2>/dev/null; then
    cp /etc/strongswan/strongswan.conf /etc/strongswan/strongswan.conf.bak_threads 2>/dev/null
    sed -i "s/threads\\s*=\\s*$THREADS/threads = {DESIRED_THREADS}/" /etc/strongswan/strongswan.conf
    NEW_THREADS=$(grep -oP 'threads\\s*=\\s*\\K[0-9]+' /etc/strongswan/strongswan.conf 2>/dev/null | head -1)
    echo "THREADS_AFTER=$NEW_THREADS"
else
    echo "THREADS_OK"
fi

# 현재 stale 현황
echo "TC_BEFORE=$(tc class show dev eth0 2>/dev/null | grep -c 'parent 1:1 ')"
echo "IPTABLES_BEFORE=$(iptables -t mangle -S PREROUTING 2>/dev/null | grep -c 'set-xmark')"
echo "TUNNELS=$(strongswan statusall 2>/dev/null | grep -c 'ESTABLISHED')"

# cleanup 즉시 실행
bash {SCRIPT_REMOTE} 2>/dev/null
sleep 1

# 정리 후 현황
echo "TC_AFTER=$(tc class show dev eth0 2>/dev/null | grep -c 'parent 1:1 ')"
echo "IPTABLES_AFTER=$(iptables -t mangle -S PREROUTING 2>/dev/null | grep -c 'set-xmark')"
"""
    out, err, rc = ssh_cmd(ip, pw, commands, timeout=30)

    # 결과 파싱
    if 'CRON_ADDED' in out or 'CRON_EXISTS' in out:
        result['cron_set'] = True

    for line in out.split('\n'):
        line = line.strip()
        if line.startswith('THREADS_BEFORE='):
            result['threads_before'] = line.split('=', 1)[1]
        elif line.startswith('THREADS_AFTER='):
            result['threads_fixed'] = True
        elif line == 'THREADS_OK':
            result['threads_fixed'] = False  # 이미 OK
        elif line.startswith('TC_BEFORE='):
            tc_b = line.split('=', 1)[1]
            result['stale_before'] = f"tc={tc_b}"
        elif line.startswith('IPTABLES_BEFORE='):
            ipt_b = line.split('=', 1)[1]
            result['stale_before'] += f",ipt={ipt_b}"
        elif line.startswith('TUNNELS='):
            result['stale_before'] += f",tunnels={line.split('=',1)[1]}"
        elif line.startswith('TC_AFTER='):
            tc_a = line.split('=', 1)[1]
            result['stale_after'] = f"tc={tc_a}"
        elif line.startswith('IPTABLES_AFTER='):
            ipt_a = line.split('=', 1)[1]
            result['stale_after'] += f",ipt={ipt_a}"

    result['cleanup_ran'] = 'TC_AFTER=' in out
    return result


def main():
    servers = get_all_servers()
    print(f"\n{'='*90}")
    print(f"  Cleanup QoS 스크립트 배포 — 대상 서버: {len(servers)}개")
    print(f"  재시작 없음! 설정만 변경 + cleanup 즉시 실행")
    print(f"{'='*90}\n")

    results = []
    for i, srv in enumerate(servers, 1):
        print(f"[{i:2d}/{len(servers)}] {srv['name']:20s} {srv['ip']:18s} ... ", end='', flush=True)
        r = deploy_one(srv)
        results.append(r)

        # 상태 요약 출력
        if not r['ssh']:
            print(f"❌ {r['error']}")
        elif not r['has_strongswan']:
            print(f"⏭️  strongswan 없음")
        elif not r['script_deployed']:
            print(f"❌ SCP 실패: {r['error']}")
        else:
            parts = []
            parts.append('✅ script')
            parts.append('cron' if r['cron_set'] else '❌cron')
            if r['threads_fixed']:
                parts.append(f"threads {r['threads_before']}→{DESIRED_THREADS}")
            else:
                parts.append(f"threads={r['threads_before']}")
            if r['cleanup_ran']:
                parts.append(f"before({r['stale_before']}) → after({r['stale_after']})")
            print(' | '.join(parts))

        time.sleep(0.3)  # SSH 부하 분산

    # ---- 최종 리포트 ----
    print(f"\n{'='*90}")
    print("  최종 리포트")
    print(f"{'='*90}")

    ssh_ok = [r for r in results if r['ssh']]
    has_ss = [r for r in results if r['has_strongswan']]
    deployed = [r for r in results if r['script_deployed']]
    threads_fixed = [r for r in results if r['threads_fixed']]
    failed = [r for r in results if r['ssh'] and r['has_strongswan'] and not r['script_deployed']]

    print(f"  전체: {len(results)}개")
    print(f"  SSH 성공: {len(ssh_ok)}개")
    print(f"  StrongSwan 있음: {len(has_ss)}개")
    print(f"  스크립트 배포 완료: {len(deployed)}개")
    print(f"  threads 수정 ({DESIRED_THREADS}로): {len(threads_fixed)}개")
    print(f"  배포 실패: {len(failed)}개")

    if threads_fixed:
        print(f"\n  ⚠️  threads 수정된 서버 (재시작 시 적용):")
        for r in threads_fixed:
            print(f"    {r['name']:20s} {r['ip']:18s} {r['threads_before']}→{DESIRED_THREADS}")

    if failed:
        print(f"\n  ❌ 배포 실패 서버:")
        for r in failed:
            print(f"    {r['name']:20s} {r['ip']:18s} {r['error']}")

    ssh_fail = [r for r in results if not r['ssh']]
    if ssh_fail:
        print(f"\n  🔌 SSH 접속 불가:")
        for r in ssh_fail:
            print(f"    {r['name']:20s} {r['ip']:18s} {r['error']}")


if __name__ == '__main__':
    main()
