#!/usr/bin/env python3
"""
NAS 중앙 Cron 관리자
====================
aws14(dev)에서 실행하여 모든 NAS 서버의 유지보수 작업을 중앙에서 처리.

작업 종류:
  - log_cleanup     : /var/log 오래된 로그 삭제 (7일 이상)
  - journal_vacuum  : systemd journal 크기 제한 (50MB)
  - packet_log_cleanup : SoftEther packet_log 삭제 (10일 이상)
  - cron_audit      : 각 NAS의 현재 crontab 수집
  - cron_standardize: NAS crontab을 표준 형태로 정리 (불필요 항목 제거)

사용법:
  python3 nas_cron_manager.py                    # 전체 유지보수 (cleanup + vacuum + packet_log)
  python3 nas_cron_manager.py --task log_cleanup  # 로그 정리만
  python3 nas_cron_manager.py --task cron_audit   # crontab 수집만
  python3 nas_cron_manager.py --task cron_standardize  # crontab 표준화
  python3 nas_cron_manager.py --json              # JSON 출력
"""

import os
import sys
import json
import time
import logging
import argparse
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import paramiko
import MySQLdb
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ───────────── 설정 ─────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
SSH_TIMEOUT = 10
MAX_WORKERS = 10

# DB 설정
DB_HOST = '218.158.57.48'
DB_USER = 'titan'
DB_PASS = 'xkdlxks12!@'
DB_NAME = 'titan'

# 이메일 설정 (settings_local.py 에서 로드)
EMAIL_TO = 'softcan@naver.com'
_SETTINGS_LOCAL = os.path.join(SCRIPT_DIR, '..', 'main', 'settings_local.py')
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 465
SMTP_EMAIL = ''
SMTP_USER = ''
SMTP_PASS = ''
try:
    _ns = {}
    with open(_SETTINGS_LOCAL) as _f:
        exec(_f.read(), _ns)
    SMTP_HOST = _ns.get('SMTP_HOST', SMTP_HOST)
    SMTP_PORT = _ns.get('SMTP_PORT', SMTP_PORT)
    SMTP_EMAIL = _ns.get('SMTP_EMAIL', '')
    SMTP_USER = _ns.get('SMTP_ID', '')
    SMTP_PASS = _ns.get('SMTP_PW', '')
except Exception as _e:
    pass  # 설정 파일 없으면 이메일 비활성

# DHCP 서버 (DDNS 필요)
DHCP_SERVERS = {'KT27', 'KT28', 'KT29', 'KT30', 'KT31', 'LG2', 'LG3'}

# 표준 crontab 항목 (모든 NAS 공통)
STANDARD_CRON_ENTRIES = [
    '* * * * * /usr/bin/python /etc/strongswan/checkuser.py',
    '* * * * * /usr/bin/flock -n /tmp/sync_qos.lock timeout 55 /usr/bin/python /root/sync_qos_all.py >> /root/sync_qos_all.cron.log 2>&1',
    '*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh',
]

# DHCP 전용 추가 항목
DDNS_CRON_ENTRY = '*/5 * * * * /root/cloudflare-ddns-updater/cloudflare-template.sh'

# 로그
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'nas_cron_manager.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ───────────── DB 헬퍼 ─────────────
def get_db():
    return MySQLdb.connect(
        host=DB_HOST, user=DB_USER, passwd=DB_PASS,
        db=DB_NAME, charset='utf8mb4'
    )


def get_active_servers() -> List[Dict]:
    """tbl_agent3에서 활성 서버 목록"""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, name, hostip
        FROM tbl_agent3 WHERE is_active=1
        ORDER BY name
    """)
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{'id': r[0], 'name': r[1], 'ip': r[2]} for r in rows]


def save_cron_log(task_type: str, total: int, success: int, fail: int, skip: int,
                  report: dict, elapsed: float):
    """실행 결과를 DB에 저장"""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tbl_nas_cron_log
            (run_time, task_type, total_servers, success_count, fail_count, skip_count,
             report_json, elapsed_sec)
        VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)
    """, [task_type, total, success, fail, skip, json.dumps(report, ensure_ascii=False), elapsed])
    db.commit()
    cur.close()
    db.close()


# ───────────── 이메일 알림 ─────────────
def send_alert_email(task_type: str, report: dict):
    """WARNING/CRITICAL 이슈가 있으면 이메일 전송"""
    if not SMTP_EMAIL or not SMTP_PASS:
        log.warning('SMTP 설정 없음, 이메일 알림 건너뜀')
        return

    servers = report.get('servers', [])
    criticals = [s for s in servers if s.get('status') in ('critical', 'fail')]
    warnings_list = [s for s in servers if s.get('status') == 'warning']

    if not criticals and not warnings_list:
        log.info('이슈 없음, 이메일 알림 불필요')
        return

    # HTML 이메일 생성
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    task_labels = {
        'log_cleanup': '로그 정리', 'journal_vacuum': 'Journal Vacuum',
        'packet_log_cleanup': 'Packet Log 정리', 'cron_audit': 'Cron 감사',
        'cron_standardize': 'Cron 표준화',
    }
    task_label = task_labels.get(task_type, task_type)
    subject = f'[TitanVPN] NAS Cron {task_label}'
    if criticals:
        subject += f' - CRITICAL {len(criticals)}건'
    elif warnings_list:
        subject += f' - WARNING {len(warnings_list)}건'

    html = f'''
    <html><body style="font-family:Arial,sans-serif;font-size:14px;">
    <h2 style="color:#333;">NAS Cron {task_label} 결과</h2>
    <p>체크 시간: {now}</p>
    <p>전체: {report.get('total', 0)} | 
       성공: {report.get('success', 0)} | 
       실패: {report.get('fail', 0)} | 
       스킵: {report.get('skip', 0)}</p>
    '''

    if criticals:
        html += '<h3 style="color:#dc3545;">CRITICAL</h3>'
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">'
        html += '<tr style="background:#f8d7da;"><th>서버</th><th>IP</th><th>이슈</th></tr>'
        for s in criticals:
            issues = ', '.join(s.get('issues', [])) or s.get('output', s.get('reason', '-'))[:200]
            html += f'<tr><td><b>{s.get("name","-")}</b></td><td>{s.get("ip","-")}</td><td style="color:#dc3545;">{issues}</td></tr>'
        html += '</table>'

    if warnings_list:
        html += '<h3 style="color:#856404;">WARNING</h3>'
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">'
        html += '<tr style="background:#fff3cd;"><th>서버</th><th>IP</th><th>제거가능 항목</th></tr>'
        for s in warnings_list:
            removable = ', '.join(s.get('removable', [])) or s.get('output', '-')[:200]
            html += f'<tr><td><b>{s.get("name","-")}</b></td><td>{s.get("ip","-")}</td><td style="color:#856404;">{removable}</td></tr>'
        html += '</table>'

    html += '<br><p style="color:#888;font-size:12px;">관리자 페이지: <a href="https://tiadmintan14.titanvpn.kr/nas_cron">NAS Cron 관리</a></p>'
    html += '</body></html>'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = EMAIL_TO
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_EMAIL, [EMAIL_TO], msg.as_string())
        log.info(f'알림 이메일 전송 완료 → {EMAIL_TO}')
    except Exception as e:
        log.error(f'이메일 전송 실패: {e}')


# ───────────── SSH 헬퍼 ─────────────
def ssh_exec(ip: str, command: str, timeout: int = 30) -> Tuple[bool, str]:
    """SSH로 명령 실행 후 (성공여부, 출력) 반환"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username='root', key_filename=SSH_KEY,
                    timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        exit_code = stdout.channel.recv_exit_status()
        output = out if out else err
        return (exit_code == 0, output[:2000])
    except Exception as e:
        return (False, str(e)[:500])
    finally:
        ssh.close()


# ───────────── 작업별 함수 ─────────────
def task_log_cleanup(server: Dict) -> Dict:
    """오래된 로그 파일 삭제"""
    name, ip = server['name'], server['ip']
    log.info(f"[log_cleanup] {name} ({ip})")

    # 삭제 전 /var/log 크기
    ok_before, size_before = ssh_exec(ip, "du -sm /var/log 2>/dev/null | awk '{print $1}'")
    size_before = size_before.strip() if ok_before else '?'

    # 7일 이상 된 로그 삭제 (gzip, bz2, xz, numbered logs)
    cmd = (
        "find /var/log -type f \\( -name '*.gz' -o -name '*.bz2' -o -name '*.xz' "
        "-o -name '*.[0-9]' -o -name '*.[0-9][0-9]' \\) -mtime +7 -delete 2>/dev/null; "
        "find /var/log -type f -name '*.log' -size +100M -exec truncate -s 0 {} \\; 2>/dev/null; "
        "echo DONE"
    )
    ok, output = ssh_exec(ip, cmd)

    # 삭제 후 크기
    ok_after, size_after = ssh_exec(ip, "du -sm /var/log 2>/dev/null | awk '{print $1}'")
    size_after = size_after.strip() if ok_after else '?'

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'before_mb': size_before,
        'after_mb': size_after,
        'output': output[:500],
    }


def task_journal_vacuum(server: Dict) -> Dict:
    """systemd journal 크기 제한"""
    name, ip = server['name'], server['ip']
    log.info(f"[journal_vacuum] {name} ({ip})")

    # 현재 크기
    ok_before, size_before = ssh_exec(ip, "journalctl --disk-usage 2>/dev/null | grep -oP '[\\d.]+[MGKB]+' | head -1")
    size_before = size_before.strip() if ok_before else '?'

    ok, output = ssh_exec(ip, "journalctl --vacuum-size=50M 2>&1")

    # 정리 후 크기
    ok_after, size_after = ssh_exec(ip, "journalctl --disk-usage 2>/dev/null | grep -oP '[\\d.]+[MGKB]+' | head -1")
    size_after = size_after.strip() if ok_after else '?'

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'before': size_before,
        'after': size_after,
        'output': output[:500],
    }


def task_packet_log_cleanup(server: Dict) -> Dict:
    """SoftEther packet_log 정리 (10일 이상)"""
    name, ip = server['name'], server['ip']
    log.info(f"[packet_log] {name} ({ip})")

    # SoftEther가 있는지 확인
    ok_check, _ = ssh_exec(ip, "test -d /usr/local/vpnserver/packet_log && echo YES")
    if not ok_check:
        return {'name': name, 'ip': ip, 'status': 'skip', 'reason': 'no packet_log dir'}

    # 삭제 전 크기
    ok_before, size_before = ssh_exec(ip, "du -sm /usr/local/vpnserver/packet_log 2>/dev/null | awk '{print $1}'")
    size_before = size_before.strip() if ok_before else '?'

    ok, output = ssh_exec(ip, "find /usr/local/vpnserver/packet_log -type f -mtime +10 -delete 2>/dev/null; echo DONE")

    ok_after, size_after = ssh_exec(ip, "du -sm /usr/local/vpnserver/packet_log 2>/dev/null | awk '{print $1}'")
    size_after = size_after.strip() if ok_after else '?'

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'before_mb': size_before,
        'after_mb': size_after,
        'output': output[:500],
    }


def task_cron_audit(server: Dict) -> Dict:
    """현재 crontab 내용 수집"""
    name, ip = server['name'], server['ip']
    log.info(f"[cron_audit] {name} ({ip})")

    ok, crontab = ssh_exec(ip, "crontab -l 2>/dev/null")
    if not ok:
        return {'name': name, 'ip': ip, 'status': 'fail', 'crontab': '', 'output': crontab}

    # cron.d 파일도 수집
    ok_d, crond = ssh_exec(ip, "ls /etc/cron.d/ 2>/dev/null && echo '---' && cat /etc/cron.d/qos_sync 2>/dev/null || echo 'N/A'")

    # 활성 라인 분석
    lines = [l.strip() for l in crontab.split('\n') if l.strip() and not l.strip().startswith('#')]

    # 분류
    has_checkuser = any('checkuser' in l for l in lines)
    has_sync_qos = any('sync_qos' in l for l in lines)
    has_rdate = any('rdate' in l for l in lines)
    has_log_cleanup = any('find /var/log' in l for l in lines)
    has_journal = any('journalctl' in l for l in lines)
    has_packet_log = any('packet_log' in l for l in lines)
    has_certbot = any('certbot' in l and not l.startswith('#') for l in lines)
    has_strongswanalert = any('strongswanuseralert' in l for l in lines)
    has_ddns = any('cloudflare' in l or 'ddns' in l.lower() for l in lines)

    # 표준 대비 상태 판단
    issues = []
    if not has_checkuser:
        issues.append('MISSING: checkuser.py')
    if not has_sync_qos:
        issues.append('MISSING: sync_qos_all.py')
    removable = []
    if has_rdate:
        removable.append('rdate (chronyd 대체)')
    if has_log_cleanup:
        removable.append('log cleanup (중앙화)')
    if has_journal:
        removable.append('journal vacuum (중앙화)')
    if has_packet_log:
        removable.append('packet_log cleanup (중앙화)')
    if has_certbot:
        removable.append('certbot (cert_auto_renew.py 대체)')
    if has_strongswanalert:
        removable.append('strongswanuseralert (nas_monitor.py 대체)')

    status = 'ok'
    if issues:
        status = 'critical'
    elif removable:
        status = 'warning'

    return {
        'name': name, 'ip': ip,
        'status': status,
        'crontab': crontab,
        'crond': crond if ok_d else '',
        'active_entries': len(lines),
        'has_checkuser': has_checkuser,
        'has_sync_qos': has_sync_qos,
        'has_rdate': has_rdate,
        'has_ddns': has_ddns,
        'issues': issues,
        'removable': removable,
    }


def task_cron_standardize(server: Dict) -> Dict:
    """NAS crontab을 표준 형태로 정리 (불필요 항목 제거)"""
    name, ip = server['name'], server['ip']
    log.info(f"[cron_standardize] {name} ({ip})")

    # 현재 crontab 가져오기
    ok, current = ssh_exec(ip, "crontab -l 2>/dev/null")
    if not ok:
        return {'name': name, 'ip': ip, 'status': 'fail', 'output': 'Cannot read crontab'}

    # 표준 crontab 생성
    new_entries = list(STANDARD_CRON_ENTRIES)

    # DHCP 서버면 DDNS 추가
    if name in DHCP_SERVERS:
        new_entries.append(DDNS_CRON_ENTRY)

    new_crontab = '\n'.join(new_entries) + '\n'

    # 현재와 비교해서 이미 표준이면 skip
    current_active = set()
    for line in current.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            current_active.add(line)

    new_active = set(new_entries)
    if current_active == new_active:
        return {
            'name': name, 'ip': ip,
            'status': 'skip',
            'reason': 'Already standard',
            'entries': len(new_entries),
        }

    removed = current_active - new_active
    added = new_active - current_active

    # crontab 교체
    ok, output = ssh_exec(ip, f"echo '{new_crontab}' | crontab -")
    if not ok:
        return {
            'name': name, 'ip': ip,
            'status': 'fail',
            'output': output,
        }

    # chronyd 확인 & 활성화 (rdate 대체)
    ssh_exec(ip, "systemctl is-active chronyd >/dev/null 2>&1 || (systemctl enable chronyd && systemctl start chronyd && timedatectl set-ntp true)")

    return {
        'name': name, 'ip': ip,
        'status': 'success',
        'entries': len(new_entries),
        'removed': list(removed),
        'added': list(added),
        'old_crontab': current,
    }


# ───────────── 메인 실행 ─────────────
def run_task(task_name: str, servers: List[Dict]) -> Dict:
    """지정된 작업을 모든 서버에 병렬 실행"""
    task_funcs = {
        'log_cleanup': task_log_cleanup,
        'journal_vacuum': task_journal_vacuum,
        'packet_log_cleanup': task_packet_log_cleanup,
        'cron_audit': task_cron_audit,
        'cron_standardize': task_cron_standardize,
    }
    func = task_funcs.get(task_name)
    if not func:
        log.error(f"Unknown task: {task_name}")
        return {}

    start_time = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(func, s): s for s in servers}
        for future in concurrent.futures.as_completed(future_map):
            server = future_map[future]
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as e:
                results.append({
                    'name': server['name'], 'ip': server['ip'],
                    'status': 'fail', 'output': str(e)[:500],
                })

    # ── FAIL 서버 자동 재시도 (SSH 일시 오류 대응) ──
    failed_results = [r for r in results if r.get('status') == 'fail']
    if failed_results:
        failed_ips = {r['ip'] for r in failed_results}
        failed_servers = [s for s in servers if s['ip'] in failed_ips]
        log.info(f"[{task_name}] {len(failed_servers)}대 FAIL → 5초 대기 후 재시도: {', '.join(s['name'] for s in failed_servers)}")
        time.sleep(5)

        retry_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map2 = {executor.submit(func, s): s for s in failed_servers}
            for future in concurrent.futures.as_completed(future_map2):
                server = future_map2[future]
                try:
                    result = future.result(timeout=120)
                    retry_results[server['ip']] = result
                except Exception as e:
                    retry_results[server['ip']] = {
                        'name': server['name'], 'ip': server['ip'],
                        'status': 'fail', 'output': str(e)[:500],
                    }

        # 재시도 성공한 서버 결과 교체
        improved = 0
        for i, r in enumerate(results):
            if r['ip'] in retry_results and r.get('status') == 'fail':
                new_r = retry_results[r['ip']]
                if new_r.get('status') != 'fail':
                    results[i] = new_r
                    improved += 1
                    log.info(f"  ✓ {new_r['name']} ({new_r['ip']}) 재시도 성공")
                else:
                    # 재시도도 실패면 최신 결과로 교체 (에러 메시지 갱신)
                    results[i] = new_r
                    log.info(f"  ✗ {new_r['name']} ({new_r['ip']}) 재시도도 실패")
        log.info(f"[{task_name}] 재시도 결과: {improved}/{len(failed_servers)}대 복구")

    elapsed = round(time.time() - start_time, 1)

    # 결과 정렬 (이름순)
    results.sort(key=lambda x: x.get('name', ''))

    success = sum(1 for r in results if r.get('status') == 'success')
    fail = sum(1 for r in results if r.get('status') == 'fail')
    skip = sum(1 for r in results if r.get('status') == 'skip')
    # cron_audit의 경우 critical/warning도 success로 카운트
    if task_name == 'cron_audit':
        success = sum(1 for r in results if r.get('status') in ('ok', 'warning', 'critical'))
        fail = sum(1 for r in results if r.get('status') == 'fail')

    report = {
        'task': task_name,
        'total': len(servers),
        'success': success,
        'fail': fail,
        'skip': skip,
        'elapsed': elapsed,
        'servers': results,
    }

    # DB 저장
    save_cron_log(task_name, len(servers), success, fail, skip, report, elapsed)

    return report


def main():
    parser = argparse.ArgumentParser(description='NAS 중앙 Cron 관리자')
    parser.add_argument('--task', choices=[
        'log_cleanup', 'journal_vacuum', 'packet_log_cleanup',
        'cron_audit', 'cron_standardize', 'all_maintenance'
    ], default='all_maintenance', help='실행할 작업')
    parser.add_argument('--json', action='store_true', help='JSON 형식 출력')
    parser.add_argument('--server', help='특정 서버만 (이름으로 지정)')
    args = parser.parse_args()

    servers = get_active_servers()
    if args.server:
        servers = [s for s in servers if s['name'] == args.server]
        if not servers:
            log.error(f"Server not found: {args.server}")
            sys.exit(1)

    log.info(f"=== NAS Cron Manager: {args.task} ({len(servers)} servers) ===")

    if args.task == 'all_maintenance':
        # 3가지 유지보수 작업 순차 실행
        all_reports = {}
        for task_name in ['log_cleanup', 'journal_vacuum', 'packet_log_cleanup']:
            report = run_task(task_name, servers)
            all_reports[task_name] = report
            if not args.json:
                s = report.get('success', 0)
                f = report.get('fail', 0)
                sk = report.get('skip', 0)
                log.info(f"  [{task_name}] OK={s} FAIL={f} SKIP={sk} ({report.get('elapsed', 0)}s)")

        if args.json:
            print(json.dumps(all_reports, indent=2, ensure_ascii=False))
        else:
            log.info("=== 전체 유지보수 완료 ===")
    else:
        report = run_task(args.task, servers)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            log.info(f"=== {args.task} 완료: OK={report.get('success',0)} FAIL={report.get('fail',0)} SKIP={report.get('skip',0)} ({report.get('elapsed',0)}s) ===")
        # cron_audit, cron_standardize 또는 실패 있는 작업 → 이메일 알림
        if report.get('fail', 0) > 0 or args.task in ('cron_audit', 'cron_standardize'):
            send_alert_email(args.task, report)


if __name__ == '__main__':
    main()
