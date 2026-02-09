#!/usr/bin/env python3
"""
cert_auto_renew.py — Let's Encrypt 인증서 자동 갱신 (중앙 관리)
================================================================
aws13에서 매일 새벽 실행. 모든 활성 VPN 서버의 인증서를 점검하고
만료 20일 이내 서버의 인증서를 자동 갱신.

처리 순서 (서버별):
  1) SSH → StrongSwan 심링크로 실제 사용 인증서 & 만료일 확인
  2) 20일 이내 서버:
     a. x-ui(xray) 정지 + port 80 확인        ← standalone 인증 준비
     b. certbot certonly --standalone 갱신     ← 실제 갱신
     c. SoftEther 인증서 리로드 (certreload.sh)
     d. x-ui(xray) 재시작
     e. strongswan rereadall                  ← 기존 세션 유지!
     f. IKEv2 연결 검증 (서비스 + 인증서 + SA)

실패 추적:
  cert_renew_failures.json에 서버별 연속 실패 횟수 기록
  5회 이상 연속 실패 시 Email 알림

기존 서버 crontab의 certbot 자동갱신(주1회)을 대체함.
"""

import os, sys, subprocess, time, datetime, json, re, traceback, logging
import concurrent.futures
import MySQLdb
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────
DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

SSH_KEY = '/home/newkorea/.ssh/id_ed25519'
SSH_OPTS = [
    '-o', 'ConnectTimeout=15',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'BatchMode=yes',
    '-o', 'ServerAliveInterval=10',
    '-o', 'ServerAliveCountMax=3',
]

CERT_RENEW_DAYS = 20          # 이 일수 이하면 갱신 시도
MAX_CONSECUTIVE_FAILS = 5     # 연속 실패 → 알림
RENEW_WORKERS = 1             # 갱신은 순차 (안전)
CHECK_WORKERS = 8             # 인증서 확인은 병렬

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FAIL_TRACK_FILE = os.path.join(SCRIPT_DIR, 'cert_renew_failures.json')
LOG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'logs')

# (PushPlus 미사용 — Email만 사용)

# ── Email (SMTP) ──
EMAIL_TO = 'softcan@naver.com'
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 587
SMTP_USER = ''      # Naver ID (예: softcan)
SMTP_PASS = ''      # Naver 앱 비밀번호 (2단계 인증 후 생성)

# ── SoftEther ──
VPNCMD_PASSWORD = 'xkdlxksdpdlwjsxm12!@'

# ────────────────────────────────────────────────
# 로깅
# ────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)

log = logging.getLogger('cert_renew')
log.setLevel(logging.DEBUG)

_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter('%(message)s'))
log.addHandler(_console)

_today = datetime.datetime.now().strftime('%Y%m%d')
_file = logging.FileHandler(os.path.join(LOG_DIR, f'cert_renew_{_today}.log'), encoding='utf-8')
_file.setLevel(logging.DEBUG)
_file.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
log.addHandler(_file)

# ────────────────────────────────────────────────
# SSH 헬퍼
# ────────────────────────────────────────────────
def ssh_run(ip, cmd, timeout=30):
    """SSH 명령 실행 → (returncode, stdout, stderr)"""
    full = ['ssh', '-i', SSH_KEY] + SSH_OPTS + [f'root@{ip}', cmd]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, '', 'SSH_TIMEOUT'
    except Exception as e:
        return -1, '', str(e)


def ssh_run_retry(ip, cmd, timeout=30, retries=2, delay=3):
    """SSH 재시도 포함"""
    for i in range(retries):
        rc, out, err = ssh_run(ip, cmd, timeout)
        if rc == 0:
            return rc, out, err
        if i < retries - 1:
            time.sleep(delay)
    return rc, out, err

# ────────────────────────────────────────────────
# DB
# ────────────────────────────────────────────────
def get_db():
    conn = MySQLdb.connect(**DB_CONFIG)
    conn.autocommit(True)
    return conn


def get_all_servers():
    """활성 KR 서버 목록 (is_active=1)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, hostip
        FROM tbl_agent3
        WHERE is_active = 1 AND country = 'KR'
        ORDER BY name
    """)
    rows = [{'name': r[0], 'ip': r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows

# ────────────────────────────────────────────────
# 인증서 정보 확인
# ────────────────────────────────────────────────
def get_cert_info(server):
    """서버 인증서 정보 조회 → dict with domain, days_left, expiry, cert_path"""
    ip = server['ip']
    name = server['name']

    # readlink (no -f) → /etc/letsencrypt/live/DOMAIN/fullchain.pem
    # readlink -f     → /etc/letsencrypt/archive/DOMAIN/fullchainN.pem
    # Both are useful: 'live' for domain extraction, '-f' for actual file check
    cmd = (
        'link=$(readlink /etc/strongswan/ipsec.d/certs/certificate.pem 2>/dev/null); '
        'real=$(readlink -f /etc/strongswan/ipsec.d/certs/certificate.pem 2>/dev/null); '
        'if [ -n "$real" ] && [ -f "$real" ]; then '
        '  echo "CERT_LINK=$link"; '
        '  echo "CERT_REAL=$real"; '
        '  openssl x509 -enddate -noout -in "$real"; '
        'else '
        '  cert=$(find /etc/letsencrypt/live/ -name fullchain.pem '
        '         -not -path "*/README" 2>/dev/null | head -1); '
        '  if [ -n "$cert" ]; then '
        '    echo "CERT_LINK=$cert"; '
        '    echo "CERT_REAL=$cert"; '
        '    openssl x509 -enddate -noout -in "$cert"; '
        '  else echo "NO_CERT"; fi; '
        'fi'
    )

    rc, out, err = ssh_run_retry(ip, cmd, timeout=20)
    info = {
        'name': name, 'ip': ip,
        'domain': None, 'days_left': None, 'expiry': None,
        'cert_path': None, 'error': None,
    }

    if rc != 0:
        info['error'] = f'SSH 실패: {err[:200]}'
        return info

    for line in out.split('\n'):
        line = line.strip()
        if line == 'NO_CERT':
            info['error'] = '인증서 없음'
            return info
        if line.startswith('CERT_LINK='):
            # symlink path: /etc/letsencrypt/live/DOMAIN/fullchain.pem
            link_path = line.replace('CERT_LINK=', '')
            m = re.search(r'/etc/letsencrypt/(?:live|archive)/([^/]+)/', link_path)
            if m:
                info['domain'] = m.group(1)
        elif line.startswith('CERT_REAL='):
            path = line.replace('CERT_REAL=', '')
            info['cert_path'] = path
            # fallback domain from resolved path
            if not info['domain']:
                m = re.search(r'/etc/letsencrypt/(?:live|archive)/([^/]+)/', path)
                if m:
                    info['domain'] = m.group(1)
        elif line.startswith('notAfter='):
            date_str = line.replace('notAfter=', '').strip()
            try:
                expiry = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                info['days_left'] = (expiry - datetime.datetime.utcnow()).days
                info['expiry'] = expiry.strftime('%Y-%m-%d')
            except Exception:
                info['error'] = f'날짜 파싱 실패: {date_str}'

    return info


def check_all_certs(servers):
    """병렬로 모든 서버 인증서 확인"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
        results = list(pool.map(get_cert_info, servers))
    return results

# ────────────────────────────────────────────────
# 갱신 단계별 함수
# ────────────────────────────────────────────────
def stop_xui(ip):
    """x-ui 정지 + port 80 해제 확인 → (성공여부, 메시지)"""
    # x-ui 실행 여부 확인
    rc, out, _ = ssh_run(ip, 'pgrep -x x-ui >/dev/null 2>&1 && echo RUNNING || echo STOPPED')
    xui_was_running = 'RUNNING' in out

    if not xui_was_running:
        # port 80 도 비어있는지 확인
        rc, out, _ = ssh_run(ip, 'ss -tlnp 2>/dev/null | grep -q ":80 " && echo BUSY || echo FREE')
        if 'FREE' in out:
            return True, 'x-ui 미실행, 포트80 사용가능'
        # 다른 프로세스가 port 80 사용 중
        log.warning(f'  x-ui 미실행이지만 port 80 사용 중, 강제 해제 시도')
        ssh_run(ip, 'fuser -k 80/tcp 2>/dev/null')
        time.sleep(2)
        rc, out, _ = ssh_run(ip, 'ss -tlnp 2>/dev/null | grep -q ":80 " && echo BUSY || echo FREE')
        return 'FREE' in out, 'port 80 강제 해제' if 'FREE' in out else 'port 80 해제 실패'

    # x-ui 정지
    log.info(f'  x-ui 정지 중...')
    ssh_run(ip, 'service x-ui stop 2>/dev/null')
    time.sleep(2)

    # port 80 해제 대기 (최대 20초)
    for i in range(7):
        rc, out, _ = ssh_run(ip, 'ss -tlnp 2>/dev/null | grep -q ":80 " && echo BUSY || echo FREE')
        if 'FREE' in out:
            return True, 'x-ui 정지 완료, 포트80 해제'
        time.sleep(3)

    # 강제 해제
    log.warning(f'  port 80 미해제 → xray 강제 종료')
    ssh_run(ip, 'pkill -9 -f "xray" 2>/dev/null')
    time.sleep(3)
    rc, out, _ = ssh_run(ip, 'ss -tlnp 2>/dev/null | grep -q ":80 " && echo BUSY || echo FREE')
    if 'FREE' in out:
        return True, 'xray 강제종료 후 포트80 해제'
    return False, 'port 80 해제 실패 (20초 대기 + 강제종료 후에도 실패)'


def start_xui(ip):
    """x-ui 재시작"""
    ssh_run(ip, 'service x-ui start 2>/dev/null')
    time.sleep(3)
    rc, out, _ = ssh_run(ip, 'pgrep -x x-ui >/dev/null 2>&1 && echo RUNNING || echo STOPPED')
    return 'RUNNING' in out


def renew_cert_certbot(ip, domain):
    """certbot certonly로 인증서 갱신
    → (성공, 출력메시지)"""
    cmd = (
        f'certbot certonly --standalone '
        f'-d {domain} '
        f'--non-interactive --agree-tos '
        f'--preferred-challenges http '
        f'--force-renewal '
        f'2>&1'
    )
    rc, out, err = ssh_run(ip, cmd, timeout=120)
    full = out + '\n' + err

    success = (
        rc == 0 and
        ('Successfully received certificate' in full or
         'Congratulations' in full or
         'certificate obtained' in full.lower())
    )

    if not success and rc == 0:
        # certbot 은 성공했는데 메시지를 못 찾은 경우 → 인증서 파일 확인
        rc2, out2, _ = ssh_run(ip, f'ls -la /etc/letsencrypt/live/{domain}/fullchain.pem 2>&1')
        if rc2 == 0 and 'fullchain.pem' in out2:
            # 만료일이 80일 이상이면 갱신 성공으로 간주
            rc3, out3, _ = ssh_run(ip,
                f'openssl x509 -enddate -noout -in /etc/letsencrypt/live/{domain}/fullchain.pem 2>&1')
            if 'notAfter=' in out3:
                try:
                    date_str = out3.split('notAfter=')[1].strip()
                    expiry = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                    days = (expiry - datetime.datetime.utcnow()).days
                    if days >= 80:
                        success = True
                        full += f'\n[확인] 새 인증서 {days}일 남음'
                except Exception:
                    pass

    return success, full.strip()


def reload_softether(ip):
    """SoftEther certreload.sh 실행"""
    rc, out, err = ssh_run(ip,
        'if [ -f /usr/local/vpnserver/certreload.sh ]; then '
        '  bash /usr/local/vpnserver/certreload.sh 2>&1; echo RELOAD_OK; '
        'else echo NO_SCRIPT; fi',
        timeout=15)
    if 'RELOAD_OK' in out:
        return True, 'certreload.sh 실행 완료'
    elif 'NO_SCRIPT' in out:
        return True, 'certreload.sh 없음 (SoftEther 미설치?)'
    return False, f'certreload.sh 실패: {out[:200]}'


def reload_strongswan(ip):
    """StrongSwan 인증서 리로드 (세션 유지)"""
    # 상태 비교를 위해 현재 SA 수 기록
    rc, out, _ = ssh_run(ip,
        'strongswan statusall 2>/dev/null | grep -c "ESTABLISHED" || '
        'ipsec statusall 2>/dev/null | grep -c "ESTABLISHED"')
    sa_before = 0
    try:
        sa_before = int(out.strip())
    except ValueError:
        pass

    # rereadall
    rc, out, err = ssh_run(ip,
        'strongswan rereadall 2>&1 || ipsec rereadall 2>&1')

    time.sleep(2)

    # 갱신 후 SA 수 확인
    rc2, out2, _ = ssh_run(ip,
        'strongswan statusall 2>/dev/null | grep -c "ESTABLISHED" || '
        'ipsec statusall 2>/dev/null | grep -c "ESTABLISHED"')
    sa_after = 0
    try:
        sa_after = int(out2.strip())
    except ValueError:
        pass

    return rc == 0, sa_before, sa_after


def check_ikev2(ip, expected_min_days=80):
    """IKEv2 연결 검증: 서비스 + 인증서 + SA
    → (성공, 상세메시지)"""
    results = []

    # 1) StrongSwan 서비스 상태
    rc, out, _ = ssh_run(ip,
        '(systemctl is-active strongswan 2>/dev/null || '
        ' systemctl is-active ipsec 2>/dev/null)')
    svc_ok = rc == 0 and 'active' in out
    results.append(f'서비스: {"OK" if svc_ok else "FAIL"}')

    # 2) 로드된 인증서 만료일 확인
    cmd = (
        'cert=$(readlink -f /etc/strongswan/ipsec.d/certs/certificate.pem 2>/dev/null); '
        'if [ -n "$cert" ] && [ -f "$cert" ]; then '
        '  openssl x509 -enddate -noout -in "$cert"; '
        'fi'
    )
    rc, out, _ = ssh_run(ip, cmd)
    cert_days = None
    if 'notAfter=' in out:
        try:
            date_str = out.split('notAfter=')[1].strip()
            expiry = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
            cert_days = (expiry - datetime.datetime.utcnow()).days
        except Exception:
            pass

    cert_ok = cert_days is not None and cert_days >= expected_min_days
    results.append(f'인증서: {"OK" if cert_ok else "FAIL"} ({cert_days}일)')

    # 3) 활성 SA (IKEv2 세션)
    rc, out, _ = ssh_run(ip,
        'strongswan statusall 2>/dev/null | grep -c "ESTABLISHED" || '
        'ipsec statusall 2>/dev/null | grep -c "ESTABLISHED"')
    sa_count = 0
    try:
        sa_count = int(out.strip())
    except ValueError:
        pass
    results.append(f'활성SA: {sa_count}')

    overall = svc_ok and cert_ok
    return overall, ', '.join(results), cert_days

# ────────────────────────────────────────────────
# 갱신 전체 플로우 (서버 1대)
# ────────────────────────────────────────────────
def process_renewal(info):
    """한 서버 인증서 갱신 전체 과정
    → dict with name, ip, success, steps[], message"""
    name = info['name']
    ip = info['ip']
    domain = info['domain']
    short = name.replace('KOREA-', '')

    result = {
        'name': name, 'ip': ip, 'domain': domain,
        'success': False, 'steps': [], 'message': '',
    }

    log.info(f'\n{"="*60}')
    log.info(f'[갱신] {name} ({ip}) — {domain} — {info["days_left"]}일 남음')
    log.info(f'{"="*60}')

    # Step 1: x-ui 정지 + port 80 확보
    log.info(f'  [1/6] x-ui 정지 + port 80 확보')
    ok, msg = stop_xui(ip)
    result['steps'].append(f'x-ui정지: {msg}')
    log.info(f'    → {msg}')
    if not ok:
        result['message'] = f'port 80 확보 실패: {msg}'
        log.error(f'  ❌ {result["message"]}')
        # x-ui 복구 시도
        start_xui(ip)
        return result

    # Step 2: certbot 갱신
    log.info(f'  [2/6] certbot certonly --standalone -d {domain}')
    ok, output = renew_cert_certbot(ip, domain)
    result['steps'].append(f'certbot: {"성공" if ok else "실패"}')
    log.info(f'    → {"성공" if ok else "실패"}')
    log.debug(f'    certbot 출력:\n{output}')
    if not ok:
        result['message'] = f'certbot 갱신 실패: {output[:300]}'
        log.error(f'  ❌ certbot 실패')
        # x-ui 복구
        start_xui(ip)
        return result

    # Step 3: SoftEther certreload
    log.info(f'  [3/6] SoftEther 인증서 리로드')
    ok, msg = reload_softether(ip)
    result['steps'].append(f'SoftEther: {msg}')
    log.info(f'    → {msg}')

    # Step 4: x-ui 재시작
    log.info(f'  [4/6] x-ui 재시작')
    xui_ok = start_xui(ip)
    result['steps'].append(f'x-ui시작: {"OK" if xui_ok else "FAIL"}')
    log.info(f'    → {"OK" if xui_ok else "FAIL (비정상이지만 계속 진행)"}')

    # Step 5: StrongSwan rereadall (세션 유지)
    log.info(f'  [5/6] StrongSwan rereadall (세션 유지)')
    ok, sa_before, sa_after = reload_strongswan(ip)
    result['steps'].append(f'rereadall: {"OK" if ok else "FAIL"} SA({sa_before}→{sa_after})')
    log.info(f'    → rereadall {"OK" if ok else "FAIL"}, SA: {sa_before} → {sa_after}')
    if sa_before > 0 and sa_after < sa_before * 0.5:
        log.warning(f'    ⚠ SA 수가 절반 이하로 감소! ({sa_before}→{sa_after})')

    # Step 6: IKEv2 검증
    log.info(f'  [6/6] IKEv2 연결 검증')
    ok, detail, cert_days = check_ikev2(ip)
    result['steps'].append(f'IKEv2검증: {detail}')
    log.info(f'    → {detail}')

    if ok:
        result['success'] = True
        result['message'] = f'갱신 완료 ({cert_days}일)'
        log.info(f'  ✅ {name} 갱신 성공! 새 인증서 {cert_days}일')
    else:
        result['message'] = f'갱신은 됐으나 IKEv2 검증 실패: {detail}'
        log.warning(f'  ⚠ {name} IKEv2 검증 실패: {detail}')

    return result

# ────────────────────────────────────────────────
# 실패 추적
# ────────────────────────────────────────────────
def load_failures():
    """실패 추적 JSON 로드"""
    if os.path.exists(FAIL_TRACK_FILE):
        try:
            with open(FAIL_TRACK_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_failures(data):
    """실패 추적 JSON 저장"""
    with open(FAIL_TRACK_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_failure_track(name, success, message=''):
    """실패/성공 기록 업데이트 → 연속실패횟수 반환"""
    data = load_failures()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if name not in data:
        data[name] = {
            'consecutive_fails': 0,
            'last_fail_time': None,
            'last_fail_reason': None,
            'last_success_time': None,
            'alerted': False,
        }

    if success:
        data[name]['consecutive_fails'] = 0
        data[name]['last_success_time'] = now
        data[name]['alerted'] = False
    else:
        data[name]['consecutive_fails'] += 1
        data[name]['last_fail_time'] = now
        data[name]['last_fail_reason'] = message[:500]

    save_failures(data)
    return data[name]['consecutive_fails']

# ────────────────────────────────────────────────
# 알림: Email
# ────────────────────────────────────────────────
def send_email(subject, body):
    """SMTP로 이메일 전송"""
    if not SMTP_USER or not SMTP_PASS:
        log.warning('  Email: SMTP 미설정 — 전송 건너뜀 (로그에만 기록)')
        log.info(f'  [EMAIL 내용] 제목: {subject}')
        log.info(f'  {body[:500]}')
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = f'{SMTP_USER}@naver.com'
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        log.info(f'  Email 전송 완료 → {EMAIL_TO}')
    except Exception as e:
        log.error(f'  Email 전송 실패: {e}')
        log.info(f'  [EMAIL 내용] 제목: {subject}')
        log.info(f'  {body[:500]}')

# ────────────────────────────────────────────────
# 알림: 5회 이상 연속 실패 (Email)
# ────────────────────────────────────────────────
def alert_repeated_failures(failures_to_alert):
    """반복 실패 서버들에 대해 Email 알림"""
    if not failures_to_alert:
        return

    lines = []
    for f in failures_to_alert:
        short = f['name'].replace('KOREA-', '')
        lines.append(
            f"■ {short} ({f['ip']})\n"
            f"  도메인: {f.get('domain', '?')}\n"
            f"  연속실패: {f['fails']}회\n"
            f"  사유: {f['message']}"
        )

    body = (
        f"[타이탄 인증서 갱신 실패 경고]\n"
        f"시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"실패서버: {len(failures_to_alert)}대\n\n"
        + '\n\n'.join(lines)
        + '\n\n서버 접속하여 수동 갱신이 필요합니다.'
    )

    title = f'타이탄인증서갱신실패_{len(failures_to_alert)}대'

    # Email
    send_email(f'[TITAN] {title}', body)

    # 알림 플래그 설정
    data = load_failures()
    for f in failures_to_alert:
        if f['name'] in data:
            data[f['name']]['alerted'] = True
    save_failures(data)

# ────────────────────────────────────────────────
# 기존 crontab certbot 비활성화
# ────────────────────────────────────────────────
def disable_old_cron(ip):
    """서버의 기존 certbot cron 항목 주석처리"""
    cmd = (
        'crontab -l 2>/dev/null | '
        'sed \'s/^\\([^#].*certbot renew\\)/# disabled_by_titan \\1/\' | '
        'crontab - 2>&1 && echo CRON_UPDATED'
    )
    rc, out, _ = ssh_run(ip, cmd)
    return 'CRON_UPDATED' in out

# ────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────
def main():
    start_time = datetime.datetime.now()
    log.info(f'{"="*70}')
    log.info(f'인증서 자동 갱신 시작: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    log.info(f'{"="*70}')

    # 서버 목록
    servers = get_all_servers()
    log.info(f'활성 KR 서버: {len(servers)}대')

    # 전체 인증서 상태 확인 (병렬)
    log.info(f'\n[STEP 1] 인증서 만료일 확인 ({len(servers)}대, {CHECK_WORKERS} workers)...')
    cert_infos = check_all_certs(servers)

    # 분류
    need_renew = []     # 갱신 대상 (≤20일)
    ok_list = []        # 정상
    error_list = []     # 확인 실패
    no_cert = []        # 인증서 없음

    for info in cert_infos:
        if info.get('error'):
            error_list.append(info)
            log.warning(f'  ⚠ {info["name"]}: {info["error"]}')
        elif info['days_left'] is None:
            error_list.append(info)
            log.warning(f'  ⚠ {info["name"]}: 만료일 확인 불가')
        elif info['days_left'] <= CERT_RENEW_DAYS:
            need_renew.append(info)
            log.info(f'  🔶 {info["name"]}: {info["days_left"]}일 남음 → 갱신 대상')
        else:
            ok_list.append(info)

    log.info(f'\n  정상: {len(ok_list)}, 갱신필요: {len(need_renew)}, '
             f'에러: {len(error_list)}')

    if not need_renew:
        log.info(f'\n✅ 갱신 대상 서버 없음. 종료.')
        # 확인 에러가 있으면 실패 추적에만 기록
        for info in error_list:
            update_failure_track(info['name'], False, info.get('error', '확인실패'))
        _check_alerts()
        _print_summary(start_time, 0, 0, ok_list, error_list)
        return

    # 갱신 실행 (순차)
    log.info(f'\n[STEP 2] 인증서 갱신 ({len(need_renew)}대)...')
    success_count = 0
    fail_count = 0
    renew_results = []

    for info in need_renew:
        result = process_renewal(info)
        renew_results.append(result)

        if result['success']:
            success_count += 1
            update_failure_track(info['name'], True)
            # 기존 crontab 비활성화 (갱신 성공한 서버)
            if disable_old_cron(info['ip']):
                log.info(f'  📋 {info["name"]} 기존 certbot cron 비활성화 완료')
        else:
            fail_count += 1
            update_failure_track(info['name'], False, result['message'])

        # 서버 간 간격 (SSH 부하 분산)
        time.sleep(5)

    # 확인 에러 서버도 실패로 기록
    for info in error_list:
        update_failure_track(info['name'], False, info.get('error', '확인실패'))

    # 반복 실패 알림 체크
    _check_alerts()

    # 갱신 결과 알림
    if success_count > 0 or fail_count > 0:
        _send_renew_summary(renew_results, success_count, fail_count)

    _print_summary(start_time, success_count, fail_count, ok_list, error_list)


def _check_alerts():
    """연속 5회 실패 서버 알림"""
    data = load_failures()
    to_alert = []
    for name, info in data.items():
        if info['consecutive_fails'] >= MAX_CONSECUTIVE_FAILS and not info.get('alerted'):
            to_alert.append({
                'name': name,
                'ip': '',  # IP는 DB에서 조회
                'domain': '',
                'fails': info['consecutive_fails'],
                'message': info.get('last_fail_reason', ''),
            })

    if to_alert:
        # IP 정보 보충
        try:
            conn = get_db()
            cur = conn.cursor()
            for item in to_alert:
                cur.execute("SELECT hostip FROM tbl_agent3 WHERE name=%s", (item['name'],))
                row = cur.fetchone()
                if row:
                    item['ip'] = row[0]
            cur.close()
            conn.close()
        except Exception:
            pass

        alert_repeated_failures(to_alert)


def _send_renew_summary(results, success, fail):
    """갱신 결과 Email 전송"""
    lines = []
    for r in results:
        short = r['name'].replace('KOREA-', '')
        status = '✅' if r['success'] else '❌'
        lines.append(f'{status} {short}({r["ip"]}): {r["message"]}')

    body = '\n'.join(lines)
    title = f'타이탄인증서갱신_{success}성공_{fail}실패'
    send_email(f'[TITAN] {title}', body)


def _print_summary(start_time, success, fail, ok_list, error_list):
    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    log.info(f'\n{"="*70}')
    log.info(f'인증서 자동 갱신 완료 ({elapsed:.0f}초)')
    log.info(f'  정상: {len(ok_list)}, 갱신성공: {success}, '
             f'갱신실패: {fail}, 확인에러: {len(error_list)}')
    log.info(f'{"="*70}')


def renew_single_server(server_name):
    """단일 서버 인증서 수동 갱신 (--server 옵션용)
    JSON 결과를 stdout으로 출력"""
    log.info(f'=== 단일 서버 수동 갱신: {server_name} ===')

    # DB에서 서버 정보 조회
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, hostip FROM tbl_agent3 WHERE name=%s AND is_active=1", (server_name,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        result = {'success': False, 'message': f'서버를 찾을 수 없음: {server_name}'}
        print(json.dumps(result, ensure_ascii=False))
        return

    server = {'name': row[0], 'ip': row[1]}

    # 인증서 정보 확인
    info = get_cert_info(server)
    if info.get('error'):
        result = {'success': False, 'message': f'인증서 확인 실패: {info["error"]}',
                  'name': server_name, 'ip': server['ip']}
        print(json.dumps(result, ensure_ascii=False))
        return

    if not info.get('domain'):
        result = {'success': False, 'message': '도메인 정보를 찾을 수 없음',
                  'name': server_name, 'ip': server['ip']}
        print(json.dumps(result, ensure_ascii=False))
        return

    log.info(f'  도메인: {info["domain"]}, 남은일수: {info["days_left"]}')

    # 갱신 실행 (만료일 상관없이 강제 갱신)
    renewal = process_renewal(info)

    result = {
        'success': renewal['success'],
        'message': renewal['message'],
        'name': server_name,
        'ip': server['ip'],
        'domain': info['domain'],
        'days_before': info['days_left'],
        'steps': renewal['steps'],
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='인증서 자동 갱신')
    parser.add_argument('--server', type=str, help='단일 서버 갱신 (서버명, 예: KOREA-KT33)')
    args = parser.parse_args()

    if args.server:
        renew_single_server(args.server)
    else:
        main()
