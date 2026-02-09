#!/usr/bin/env python3
"""
server_auto_check.py  –  서버 자동 상태 점검 & is_auto OFF 처리
================================================================
매 1시간 실행. 다음 3가지 기준으로 문제 서버를 자동 비활성화(is_auto=0):

  1) 접속 실패율 이상  — 최근 2시간 iOS+Android 실패 건수가 임계치 초과
  2) SSH 접속 불가    — aws13에서 SSH 연결 실패
  3) VPN 서비스 이상  — strongswan(IKEv2) 또는 openvpn 데몬 중지 상태

비활성화된 서버는 관리자가 수동으로 확인 후 ON으로 복구.
모든 조치는 tbl_server_auto_check_log 테이블에 기록.
"""

import os, sys, re, time, datetime, subprocess, json, requests
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
# 최근 2시간 iOS+Android 실패 건수 기준
FAIL_THRESHOLD = 10        # 2시간에 10건 이상이면 의심
FAIL_USER_THRESHOLD = 5    # 5명 이상 다른 유저가 실패해야 (1명 반복은 제외)
# 최소 is_auto=1 유지 서버 수 (너무 많이 꺼지면 안됨)
MIN_AUTO_SERVERS = 20
# 한 번에 최대 비활성화 수
MAX_DISABLE = 2
# 인증서 만료 경고 기준 (일)
CERT_WARN_DAYS = 20

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


def ensure_log_table():
    """로그 테이블 생성 (없으면)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tbl_server_auto_check_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            check_time DATETIME NOT NULL,
            server_name VARCHAR(100) NOT NULL,
            reason VARCHAR(500) NOT NULL,
            action_taken VARCHAR(100) NOT NULL,
            detail TEXT,
            INDEX idx_check_time (check_time),
            INDEX idx_server (server_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.close()
    conn.close()


def get_auto_servers():
    """is_auto=1 인 활성 KR 서버 목록"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, hostip, telecom
        FROM tbl_agent3
        WHERE is_active = 1 AND country = 'KR' AND is_auto = 1
        ORDER BY name
    """)
    rows = [{'name': r[0], 'ip': r[1], 'telecom': r[2]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def get_current_auto_count():
    """현재 is_auto=1 서버 수"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tbl_agent3 WHERE is_active=1 AND country='KR' AND is_auto=1")
    cnt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return cnt


# ─────────────────────────────────────────────
# CHECK 1: 접속 실패율 분석 (iOS + Android만)
# ─────────────────────────────────────────────
def check_failure_rates():
    """최근 2시간 서버별 접속 실패율 분석"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT server_name,
               COUNT(*) AS fail_count,
               COUNT(DISTINCT username) AS user_count,
               GROUP_CONCAT(DISTINCT server_protocol) AS protocols
        FROM tbl_agent_failed
        WHERE failed_time >= NOW() - INTERVAL 2 HOUR
          AND platform IN ('iOS', 'Android')
          AND server_name != ''
        GROUP BY server_name
        HAVING fail_count >= %s AND user_count >= %s
        ORDER BY fail_count DESC
    """, (FAIL_THRESHOLD, FAIL_USER_THRESHOLD))
    
    problem_servers = []
    for row in cur.fetchall():
        problem_servers.append({
            'name': row[0],
            'fail_count': row[1],
            'user_count': row[2],
            'protocols': row[3],
            'reason': f'접속실패 {row[1]}건/{row[2]}명 (2h, iOS+Android)',
        })
    cur.close()
    conn.close()
    return problem_servers


# ─────────────────────────────────────────────
# 인증서 만료일 파싱 헬퍼
# ─────────────────────────────────────────────
def parse_cert_output(output):
    """SSH 출력에서 인증서 만료일 파싱"""
    cert_info = {'status': 'UNKNOWN', 'expiry': None, 'days_left': None}
    
    for line in output.split('\n'):
        line = line.strip()
        if line == 'NO_CERT':
            cert_info['status'] = 'NO_CERT'
            return cert_info
        if line.startswith('notAfter='):
            try:
                date_str = line.replace('notAfter=', '').strip()
                from email.utils import parsedate_to_datetime
                expiry = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                now = datetime.datetime.utcnow()
                days_left = (expiry - now).days
                cert_info['expiry'] = expiry.strftime('%Y-%m-%d')
                cert_info['days_left'] = days_left
                if days_left < 0:
                    cert_info['status'] = 'EXPIRED'
                elif days_left < CERT_WARN_DAYS:
                    cert_info['status'] = 'EXPIRING'
                else:
                    cert_info['status'] = 'OK'
            except Exception as e:
                cert_info['status'] = 'PARSE_ERROR'
            return cert_info
    
    return cert_info


# ─────────────────────────────────────────────
# CHECK 2: SSH 접속 + VPN 서비스 점검
# ─────────────────────────────────────────────
def check_server_ssh_vpn(server):
    """SSH 접속 & VPN 데몬 상태 확인"""
    name = server['name']
    ip = server['ip']
    
    # SSH 접속 + VPN 서비스 + 인증서 상태 한번에 확인
    remote_cmd = (
        'echo "SSH_OK" && '
        '(systemctl is-active strongswan 2>/dev/null || systemctl is-active ipsec 2>/dev/null || echo "IPSEC_INACTIVE") && '
        '(systemctl is-active openvpn 2>/dev/null || systemctl is-active openvpn@server 2>/dev/null || '
        ' pgrep -x openvpn > /dev/null && echo "active" || echo "OVPN_INACTIVE") && '
        'echo "===CERT===" && '
        'cert=$(readlink -f /etc/strongswan/ipsec.d/certs/certificate.pem 2>/dev/null); '
        'if [ -n "$cert" ] && [ -f "$cert" ]; then openssl x509 -enddate -noout -in $cert; '
        'else cert=$(find /etc/letsencrypt/live/ -name fullchain.pem -not -path "*/README" 2>/dev/null | head -1); '
        'if [ -n "$cert" ]; then openssl x509 -enddate -noout -in $cert; else echo NO_CERT; fi; fi'
    )
    
    cmd = f'ssh -i {SSH_KEY} {SSH_OPTS} root@{ip} \'{remote_cmd}\''
    
    for attempt in range(2):  # SSH 2회 시도 (일시적 실패 방지)
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            output = result.stdout.strip()
            
            if result.returncode != 0 or 'SSH_OK' not in output:
                if attempt == 0:
                    time.sleep(3)  # 3초 대기 후 재시도
                    continue
                return {
                    'name': name, 'status': 'SSH_FAIL',
                    'reason': f'SSH 접속 불가 (2회 실패)',
                    'detail': result.stderr.strip()[:200],
                }
        
            lines = output.split('\n')
            issues = []
            
            # 서비스 상태
            ipsec_status = lines[1].strip() if len(lines) > 1 else 'unknown'
            if ipsec_status == 'IPSEC_INACTIVE':
                issues.append('서비스1 중지')
            
            ovpn_status = lines[2].strip() if len(lines) > 2 else 'unknown'
            if ovpn_status == 'OVPN_INACTIVE':
                issues.append('서비스2 중지')
            
            # 인증서 상태 파싱
            cert_info = parse_cert_output(output)
            
            if issues:
                return {
                    'name': name, 'status': 'SVC_FAIL',
                    'reason': ', '.join(issues),
                    'detail': output,
                    'cert': cert_info,
                }
            
            return {'name': name, 'status': 'OK', 'reason': '', 'detail': '', 'cert': cert_info}
    
        except subprocess.TimeoutExpired:
            if attempt == 0:
                time.sleep(3)
                continue
            return {
                'name': name, 'status': 'SSH_TIMEOUT',
                'reason': 'SSH 타임아웃 (2회 실패)',
                'detail': '',
            }
        except Exception as e:
            if attempt == 0:
                time.sleep(3)
                continue
            return {
                'name': name, 'status': 'ERROR',
                'reason': f'점검 오류: {str(e)}',
                'detail': '',
            }
    # should not reach here, but just in case
    return {'name': name, 'status': 'OK', 'reason': '', 'detail': ''}


def check_all_servers_ssh_vpn(servers, workers=10):
    """모든 서버 SSH+VPN 점검 (병렬)"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(check_server_ssh_vpn, servers))
    return results


# ─────────────────────────────────────────────
# 조치: is_auto=0 설정 + 로그 기록
# ─────────────────────────────────────────────
def disable_server(server_name, reason, detail, check_time):
    """서버 is_auto=0 처리 + 로그"""
    conn = get_db()
    cur = conn.cursor()
    
    # 이미 is_auto=0이면 skip
    cur.execute("SELECT is_auto FROM tbl_agent3 WHERE name = %s", (server_name,))
    row = cur.fetchone()
    if not row or row[0] == 0:
        cur.close()
        conn.close()
        return False
    
    cur.execute("UPDATE tbl_agent3 SET is_auto = 0 WHERE name = %s", (server_name,))
    cur.execute("""
        INSERT INTO tbl_server_auto_check_log (check_time, server_name, reason, action_taken, detail)
        VALUES (%s, %s, %s, %s, %s)
    """, (check_time, server_name, reason, 'is_auto=0 (자동)', detail[:1000] if detail else ''))
    
    cur.close()
    conn.close()
    return True


def log_check(check_time, server_name, reason, action, detail=''):
    """점검 결과 로그만 기록 (조치 없이)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tbl_server_auto_check_log (check_time, server_name, reason, action_taken, detail)
        VALUES (%s, %s, %s, %s, %s)
    """, (check_time, server_name, reason, action, detail[:1000] if detail else ''))
    cur.close()
    conn.close()


def main():
    check_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'=== Server Auto Check: {check_time} ===')
    
    ensure_log_table()
    
    servers = get_auto_servers()
    auto_count = get_current_auto_count()
    print(f'현재 is_auto=1 서버: {auto_count}개')
    print()
    
    # ──── CHECK 1: 접속 실패율 ────
    print('[CHECK 1] 접속 실패율 분석 (최근 2h, iOS+Android)...')
    fail_problems = check_failure_rates()
    
    disable_candidates = {}  # name → reason
    
    if fail_problems:
        for p in fail_problems:
            print(f'  ⚠ {p["name"]}: {p["reason"]}')
            disable_candidates[p['name']] = p['reason']
    else:
        print('  ✓ 이상 없음')
    print()
    
    # ──── CHECK 2: SSH + VPN 서비스 ────
    print(f'[CHECK 2] SSH + VPN 서비스 점검 ({len(servers)}대)...')
    ssh_results = check_all_servers_ssh_vpn(servers)
    
    ok_count = 0
    for r in ssh_results:
        if r['status'] == 'OK':
            ok_count += 1
        else:
            print(f'  ⚠ {r["name"]}: [{r["status"]}] {r["reason"]}')
            # SSH/VPN 실패도 비활성화 대상에 추가
            if r['name'] in disable_candidates:
                disable_candidates[r['name']] += f' + {r["reason"]}'
            else:
                disable_candidates[r['name']] = r['reason']
    
    print(f'  SSH+VPN 정상: {ok_count}/{len(servers)}')
    print()
    
    # ──── CHECK 3: 인증서 만료 점검 ────
    print('[CHECK 3] Let\'s Encrypt 인증서 점검...')
    cert_expired = []      # 만료된 서버 → 즉시 비활성화
    cert_expiring = []     # 20일 미만 → 경고
    cert_ok_count = 0
    cert_nocert = 0
    
    for r in ssh_results:
        cert = r.get('cert', {})
        name = r['name']
        short = name.replace('KOREA-', '')
        
        if cert.get('status') == 'EXPIRED':
            days = abs(cert.get('days_left', 0))
            print(f'  🔴 {name}: 인증서 만료됨 ({cert.get("expiry", "?")}), {days}일 경과')
            cert_expired.append({'name': name, 'expiry': cert.get('expiry'), 'days': days})
            # 비활성화 대상에 추가
            reason = f'인증서 만료 ({cert.get("expiry", "?")})'
            if name in disable_candidates:
                disable_candidates[name] += f' + {reason}'
            else:
                disable_candidates[name] = reason
        elif cert.get('status') == 'EXPIRING':
            days = cert.get('days_left', 0)
            print(f'  ⚠ {name}: 인증서 {days}일 남음 ({cert.get("expiry", "?")})')
            cert_expiring.append({'name': name, 'expiry': cert.get('expiry'), 'days': days})
        elif cert.get('status') == 'NO_CERT':
            cert_nocert += 1
        elif cert.get('status') == 'OK':
            cert_ok_count += 1
    
    print(f'  인증서 정상: {cert_ok_count}, 경고: {len(cert_expiring)}, 만료: {len(cert_expired)}, 미설치: {cert_nocert}')
    
    # 인증서 만료 PushPlus (별도 알림 - 만료는 즉시 알림)
    if cert_expired:
        expired_msgs = []
        for c in cert_expired:
            short = c['name'].replace('KOREA-', '')
            expired_msgs.append(f'{short} 인증서만료({c["expiry"]})')
        body = ', '.join(expired_msgs) + ' 작업요망'
        remaining = get_current_auto_count()
        send_pushplus(f'타이탄인증서만료_{remaining}개활성', body)
    
    # 인증서 경고 PushPlus (20일 미만)
    if cert_expiring:
        warn_msgs = []
        for c in cert_expiring:
            short = c['name'].replace('KOREA-', '')
            warn_msgs.append(f'{short}({c["days"]}일)')
        body = '인증서 만료 임박: ' + ', '.join(warn_msgs) + '. 갱신 필요.'
        remaining = get_current_auto_count()
        send_pushplus(f'타이탄인증서경고_{remaining}개활성', body)
    
    print()
    
    # ──── 조치 실행 ────
    if not disable_candidates:
        print('✅ 문제 서버 없음. 조치 불필요.')
        log_check(check_time, 'ALL', '문제없음', '조치없음', f'서버 {len(servers)}대 점검 완료')
        return
    
    print(f'[조치] 비활성화 대상: {len(disable_candidates)}대')
    
    # 심각도 정렬 (실패 건수 내림차순)
    sorted_candidates = sorted(disable_candidates.items(),
        key=lambda x: next((p['fail_count'] for p in fail_problems if p['name'] == x[0]), 0),
        reverse=True)
    
    # 최소 서버 수 보호: is_auto=1이 20개 이하로 내려가면 경고만
    if auto_count <= MIN_AUTO_SERVERS:
        names_all = ', '.join(n.replace('KOREA-', '') for n, _ in sorted_candidates)
        print(f'  ⚠ is_auto=1이 이미 {auto_count}대 (최소 {MIN_AUTO_SERVERS}). 비활성화 불가. 경고만 발송.')
        for name, reason in sorted_candidates:
            log_check(check_time, name, reason, '보호-건너뜀 (최소서버수)', '')
        msg = f'현재 is_auto 서버가 {auto_count}대로 최소 기준({MIN_AUTO_SERVERS})입니다. 문제서버: {names_all}. 확인해주세요.'
        send_pushplus(f'타이탄경고_{auto_count}개활성', msg)
        return
    
    # 비활성화 가능 수 = min(MAX_DISABLE, auto_count - MIN_AUTO_SERVERS)
    max_allowed = min(MAX_DISABLE, auto_count - MIN_AUTO_SERVERS)
    if max_allowed <= 0:
        names_all = ', '.join(n.replace('KOREA-', '') for n, _ in sorted_candidates)
        print(f'  ⚠ 비활성화 여유 없음. 경고만 발송.')
        for name, reason in sorted_candidates:
            log_check(check_time, name, reason, '보호-건너뜀 (최소서버수)', '')
        msg = f'현재 is_auto 서버가 {auto_count}대입니다. 문제서버: {names_all}. 확인해주세요.'
        send_pushplus(f'타이탄경고_{auto_count}개활성', msg)
        return
    
    # 상위 max_allowed개만 비활성화
    to_disable = sorted_candidates[:max_allowed]
    extra_servers = sorted_candidates[max_allowed:]
    
    disabled_names = []
    for name, reason in to_disable:
        success = disable_server(name, reason, '', check_time)
        if success:
            disabled_names.append(name)
            print(f'  🔴 {name} → is_auto=0  사유: {reason}')
        else:
            print(f'  ⏭ {name} 이미 is_auto=0')
    
    # 나머지는 로그만
    for name, reason in extra_servers:
        log_check(check_time, name, reason, '추가문제-로그만', '')
    
    # PushPlus 알림 전송
    if disabled_names:
        short_names = [n.replace('KOREA-', '') for n in disabled_names]
        body = f'{", ".join(short_names)}을 0처리했습니다.'
        
        if extra_servers:
            extra_names = [n.replace('KOREA-', '') for n in [x[0] for x in extra_servers]]
            extra_str = ', '.join(extra_names)
            body += f'\n더많은 서버들이 문제가있습니다. 확인해주세요.({extra_str})'
        
        remaining_auto = get_current_auto_count()
        send_pushplus(f'타이탄처리0_{remaining_auto}개활성', body)
    
    remaining_auto = get_current_auto_count()
    print(f'\n완료: {len(disabled_names)}대 비활성화, 남은 is_auto=1: {remaining_auto}대')


if __name__ == '__main__':
    main()
