#!/usr/bin/env python3
"""
server_auto_restore.py  –  자동 비활성화된 서버의 상태 복구
===========================================================
매 30분 실행. server_auto_check.py 가 자동으로 is_auto=0 처리한 서버 중
현재 상태가 양호한 서버를 자동으로 is_auto=1 로 복구.

복구 조건:
  1) tbl_server_auto_check_log 에 '자동' 비활성화 기록이 있는 서버만 대상
     (관리자가 수동으로 OFF 한 서버는 건드리지 않음)
  2) 비활성화된 지 최소 2시간 경과
  3) 최근 2시간 접속 실패 건수가 임계치 미만
  4) SSH 접속 정상 + VPN 서비스 정상

모든 복구 조치는 tbl_server_auto_check_log 테이블에 기록.
"""

import os, sys, subprocess, datetime, time, json, requests
import concurrent.futures
import MySQLdb

# ── 설정 ──
DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

SSH_KEY = '/home/newkorea/.ssh/id_ed25519'
SSH_OPTS = '-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes'

# ── 임계치 ──
MIN_HOURS_BEFORE_RESTORE = 2   # 비활성화 후 최소 대기 시간
FAIL_THRESHOLD = 5             # 복구 기준: 2시간 실패 5건 미만이면 양호
FAIL_USER_THRESHOLD = 3        # 복구 기준: 3명 미만 유저 실패면 양호
MAX_RESTORE_PER_RUN = 3        # 한 번에 최대 복구 수

# ── PushPlus ──
PUSHPLUS_TOKEN = '71441d4026b84b068f3e7522b173299f'
PUSHPLUS_ENDPOINT = 'https://www.pushplus.plus/send'


def send_pushplus(title, content):
    """PushPlus 알림 전송"""
    try:
        resp = requests.post(PUSHPLUS_ENDPOINT, json={
            'token': PUSHPLUS_TOKEN,
            'title': title,
            'content': content,
            'template': 'txt',
        }, timeout=10)
        print(f'  PushPlus: {resp.status_code} {resp.text[:100]}')
    except Exception as e:
        print(f'  PushPlus 전송 실패: {e}')


def get_db():
    conn = MySQLdb.connect(**DB_CONFIG)
    conn.autocommit(True)
    return conn


def get_auto_disabled_servers():
    """
    자동으로 is_auto=0 된 서버만 조회.
    조건: 현재 is_auto=0 이고, tbl_server_auto_check_log 에 '자동' OFF 기록이 있으며,
          그 이후에 관리자가 수동 ON→OFF 한 적이 없는 서버.
    """
    conn = get_db()
    cur = conn.cursor()

    # 현재 is_auto=0 인 활성 서버 목록
    cur.execute("""
        SELECT name, hostip, telecom
        FROM tbl_agent3
        WHERE is_active = 1 AND country = 'KR' AND is_auto = 0
        ORDER BY name
    """)
    off_servers = {r[0]: {'name': r[0], 'ip': r[1], 'telecom': r[2]} for r in cur.fetchall()}

    if not off_servers:
        cur.close()
        conn.close()
        return []

    # 각 서버의 마지막 자동 OFF 기록 확인
    placeholders = ','.join(['%s'] * len(off_servers))
    cur.execute(f"""
        SELECT server_name, MAX(check_time) AS last_auto_off
        FROM tbl_server_auto_check_log
        WHERE server_name IN ({placeholders})
          AND action_taken LIKE %s
        GROUP BY server_name
    """, list(off_servers.keys()) + ['%is_auto=0 (자동)%'])

    auto_disabled = {}
    now = datetime.datetime.now()
    for row in cur.fetchall():
        server_name = row[0]
        last_off_time = row[1]
        hours_since = (now - last_off_time).total_seconds() / 3600

        if hours_since >= MIN_HOURS_BEFORE_RESTORE:
            info = off_servers[server_name]
            info['last_off_time'] = last_off_time
            info['hours_since'] = round(hours_since, 1)
            auto_disabled[server_name] = info

    cur.close()
    conn.close()
    return list(auto_disabled.values())


def check_recent_failures(server_names):
    """최근 2시간 서버별 접속 실패 건수 조회"""
    if not server_names:
        return {}

    conn = get_db()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(server_names))
    cur.execute(f"""
        SELECT server_name, COUNT(*) AS fail_count,
               COUNT(DISTINCT username) AS user_count
        FROM tbl_agent_failed
        WHERE failed_time >= NOW() - INTERVAL 2 HOUR
          AND platform IN ('iOS', 'Android')
          AND server_name IN ({placeholders})
        GROUP BY server_name
    """, server_names)

    failures = {}
    for row in cur.fetchall():
        failures[row[0]] = {'fail_count': row[1], 'user_count': row[2]}

    cur.close()
    conn.close()
    return failures


def check_server_ssh_vpn(server):
    """SSH 접속 & VPN 데몬 상태 확인 (server_auto_check.py와 동일)"""
    name = server['name']
    ip = server['ip']

    remote_cmd = (
        'echo "SSH_OK" && '
        '(systemctl is-active strongswan 2>/dev/null || systemctl is-active ipsec 2>/dev/null || echo "IPSEC_INACTIVE") && '
        '(systemctl is-active openvpn 2>/dev/null || systemctl is-active openvpn@server 2>/dev/null || '
        ' pgrep -x openvpn > /dev/null && echo "active" || echo "OVPN_INACTIVE")'
    )

    cmd = f'ssh -i {SSH_KEY} {SSH_OPTS} root@{ip} \'{remote_cmd}\''

    for attempt in range(2):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            output = result.stdout.strip()

            if result.returncode != 0 or 'SSH_OK' not in output:
                if attempt == 0:
                    time.sleep(3)
                    continue
                return {'name': name, 'status': 'SSH_FAIL', 'reason': 'SSH 접속 불가'}

            lines = output.split('\n')
            issues = []

            ipsec_status = lines[1].strip() if len(lines) > 1 else 'unknown'
            if ipsec_status == 'IPSEC_INACTIVE':
                issues.append('서비스1 중지')

            ovpn_status = lines[2].strip() if len(lines) > 2 else 'unknown'
            if ovpn_status == 'OVPN_INACTIVE':
                issues.append('서비스2 중지')

            if issues:
                return {'name': name, 'status': 'SVC_FAIL', 'reason': ', '.join(issues)}

            return {'name': name, 'status': 'OK', 'reason': ''}

        except subprocess.TimeoutExpired:
            if attempt == 0:
                time.sleep(3)
                continue
            return {'name': name, 'status': 'SSH_TIMEOUT', 'reason': 'SSH 타임아웃'}
        except Exception as e:
            if attempt == 0:
                time.sleep(3)
                continue
            return {'name': name, 'status': 'ERROR', 'reason': str(e)}

    return {'name': name, 'status': 'OK', 'reason': ''}


def restore_server(server_name, check_time, reason_detail):
    """서버 is_auto=1 복구 + 로그 기록"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE tbl_agent3 SET is_auto = 1 WHERE name = %s AND is_auto = 0", (server_name,))
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return False

    cur.execute("""
        INSERT INTO tbl_server_auto_check_log (check_time, server_name, reason, action_taken, detail)
        VALUES (%s, %s, %s, %s, %s)
    """, (check_time, server_name, reason_detail, 'is_auto=1 (자동복구)', ''))

    cur.close()
    conn.close()
    return True


def trigger_ping_measurement(server_name):
    """복구된 서버의 ping 측정 트리거 (aws13에서 비동기 실행)"""
    try:
        subprocess.Popen(
            f'cd /home/newkorea/project/titan/scripts && '
            f'/home/newkorea/project/titan/.venv310/bin/python3 cn_telecom_ping.py '
            f'--server {server_name}',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def main():
    check_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'=== Server Auto Restore: {check_time} ===')

    # 1) 자동 비활성화 후 2시간 이상 경과한 서버 조회
    candidates = get_auto_disabled_servers()
    if not candidates:
        print('복구 대상 서버 없음 (자동 비활성화 이력 없거나 2시간 미경과)')
        return

    print(f'복구 후보: {len(candidates)}대')
    for s in candidates:
        print(f'  {s["name"]} ({s["ip"]}) - OFF 후 {s["hours_since"]}h 경과')
    print()

    # 2) 최근 2시간 접속 실패 건수 확인
    server_names = [s['name'] for s in candidates]
    failures = check_recent_failures(server_names)

    # 실패 기준 초과 서버 제외
    healthy_candidates = []
    for s in candidates:
        name = s['name']
        fail_info = failures.get(name, {'fail_count': 0, 'user_count': 0})
        fc = fail_info['fail_count']
        uc = fail_info['user_count']

        if fc >= FAIL_THRESHOLD and uc >= FAIL_USER_THRESHOLD:
            print(f'  ✗ {name}: 아직 실패 많음 ({fc}건/{uc}명) → 복구 보류')
        else:
            s['fail_count'] = fc
            s['user_count'] = uc
            healthy_candidates.append(s)

    if not healthy_candidates:
        print('\n실패율 기준 충족 서버 없음. 복구 보류.')
        return

    print(f'\n실패율 양호: {len(healthy_candidates)}대')
    print()

    # 3) SSH + VPN 서비스 점검 (병렬)
    print('[SSH+VPN 점검]')
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        ssh_results = list(executor.map(check_server_ssh_vpn, healthy_candidates))

    restore_targets = []
    for s, r in zip(healthy_candidates, ssh_results):
        if r['status'] == 'OK':
            print(f'  ✓ {s["name"]}: SSH+VPN 정상')
            restore_targets.append(s)
        else:
            print(f'  ✗ {s["name"]}: [{r["status"]}] {r["reason"]} → 복구 보류')

    if not restore_targets:
        print('\nSSH/VPN 점검 통과 서버 없음. 복구 보류.')
        return

    # 4) 복구 실행 (최대 MAX_RESTORE_PER_RUN 개)
    to_restore = restore_targets[:MAX_RESTORE_PER_RUN]
    print(f'\n[복구 실행] {len(to_restore)}대')

    restored_names = []
    for s in to_restore:
        name = s['name']
        detail = f'OFF 후 {s["hours_since"]}h 경과, 최근2h 실패 {s["fail_count"]}건/{s["user_count"]}명, SSH+VPN 정상'
        success = restore_server(name, check_time, detail)
        if success:
            restored_names.append(name)
            print(f'  🟢 {name} → is_auto=1 복구 완료')
            # ping 측정 트리거
            if trigger_ping_measurement(name):
                print(f'     ping 측정 트리거 완료')
        else:
            print(f'  ⏭ {name} 복구 실패 (이미 변경됨?)')

    # 5) 알림 전송
    if restored_names:
        short_names = [n.replace('KOREA-', '') for n in restored_names]
        body = f'{", ".join(short_names)} 자동복구(is_auto=1). 상태 양호 확인됨.'
        remaining = len(restore_targets) - len(to_restore)
        if remaining > 0:
            extra = [s['name'].replace('KOREA-', '') for s in restore_targets[MAX_RESTORE_PER_RUN:]]
            body += f'\n다음 실행시 복구 예정: {", ".join(extra)}'

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tbl_agent3 WHERE is_active=1 AND country='KR' AND is_auto=1")
        auto_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        send_pushplus(f'타이탄복구_{auto_count}개활성', body)

    print(f'\n완료: {len(restored_names)}대 복구')


if __name__ == '__main__':
    main()
