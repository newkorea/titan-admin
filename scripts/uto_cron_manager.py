#!/usr/bin/env python3
"""
UTO NAS 중앙 Cron 관리자
========================
aws14에서 실행하여 모든 UTO NAS 서버의 유지보수 작업을 중앙에서 처리.

작업 종류:
  - log_cleanup      : /var/log 오래된 로그 삭제 + 대용량 로그 truncate
  - journal_vacuum   : systemd journal 크기 제한 (50MB)
  - deploy_qos_cleanup: QoS 정리 스크립트 배포 + crontab 등록
  - stale_radacct    : radacct에서 비정상 NULL 세션 정리
  - health_check     : 서버 상태 점검 (TC 누적, 메모리, 디스크)
  - cron_standardize : crontab 표준화

사용법:
  python3 uto_cron_manager.py                         # 기본 유지보수 (log+journal+radacct)
  python3 uto_cron_manager.py --task log_cleanup       # 로그 정리만
  python3 uto_cron_manager.py --task deploy_qos_cleanup # QoS 정리 스크립트 배포
  python3 uto_cron_manager.py --task health_check      # 전체 상태 점검
  python3 uto_cron_manager.py --task cron_standardize  # crontab 표준화
  python3 uto_cron_manager.py --server 125.132.9.170   # 특정 서버만
  python3 uto_cron_manager.py --dry-run                # 미리보기
"""

import os
import sys
import json
import time
import logging
import argparse
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Tuple

import paramiko
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ───────────── 설정 ─────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'titan-admin', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
SSH_TIMEOUT = 10
MAX_WORKERS = 8

# UTO DB 설정
UTO_DB_HOST = '218.158.57.51'
UTO_DB_USER = 'root'
UTO_DB_PASS = 'uto6703'
UTO_DB_NAME = 'vcsvpn2013'

# QoS 정리 스크립트 경로 (로컬)
QOS_CLEANUP_SCRIPT = os.path.join(SCRIPT_DIR, 'uto_cleanup_stale_qos.sh')

# UTO 표준 crontab 항목
STANDARD_CRON = [
    '* * * * * /usr/bin/flock -n /var/lock/checkuser.lock /usr/bin/timeout 55s /usr/bin/python /etc/strongswan/checkuser.py >/dev/null 2>&1',
    '* * * * * /usr/bin/flock -n /var/lock/dbsync.lock /usr/bin/timeout 55s /usr/bin/python /etc/strongswan/dbsync.py >/dev/null 2>&1',
    '*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh >> /var/log/cleanup_qos.log 2>&1',
    '0 6 * * 3 certbot renew >> /var/log/letsencrypt-renewal.log',
    '0 2 * * * /bin/journalctl --vacuum-size=50M >> /dev/null 2>&1',
]

# 로그
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'uto_cron_manager.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ───────────── DB 헬퍼 ─────────────
def get_db():
    import MySQLdb
    return MySQLdb.connect(
        host=UTO_DB_HOST, user=UTO_DB_USER, passwd=UTO_DB_PASS,
        db=UTO_DB_NAME, charset='utf8mb4'
    )


def get_active_servers() -> List[Dict]:
    """vpnlinek에서 활성 서버 목록 (중복 IP 제거)"""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT MIN(id) as id, ipname, address
        FROM vpnlinek
        WHERE su=1
          AND address REGEXP '^[0-9]+\\\\.'
        GROUP BY address
        ORDER BY ipname
    """)
    rows = cur.fetchall()
    cur.close()
    db.close()
    return [{'id': r[0], 'name': r[1], 'ip': r[2]} for r in rows]


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


def ssh_upload(ip: str, local_path: str, remote_path: str) -> Tuple[bool, str]:
    """SCP로 파일 업로드"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username='root', key_filename=SSH_KEY,
                    timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
        sftp = ssh.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.chmod(remote_path, 0o755)
        sftp.close()
        return (True, 'uploaded')
    except Exception as e:
        return (False, str(e)[:500])
    finally:
        ssh.close()


# ───────────── 작업별 함수 ─────────────

def task_log_cleanup(server: Dict, dry_run: bool = False) -> Dict:
    """오래된 로그 파일 삭제 + 대용량 로그 truncate"""
    name, ip = server['name'], server['ip']
    log.info(f"[log_cleanup] {name} ({ip})")

    ok_before, size_before = ssh_exec(ip, "du -sm /var/log 2>/dev/null | awk '{print $1}'")
    size_before = size_before.strip() if ok_before else '?'

    if dry_run:
        ok, output = ssh_exec(ip,
            "find /var/log -type f \\( -name '*.gz' -o -name '*.xz' -o -name '*.bz2' "
            "-o -name '*.[0-9]' -o -name '*-20*' -o -name '*.old' \\) -mtime +3 2>/dev/null | wc -l"
        )
        return {'name': name, 'ip': ip, 'status': 'dry-run', 'before_mb': size_before, 'deletable_files': output}

    cmd = (
        # 3일 이상 된 압축/로테이션 로그 삭제
        "find /var/log -type f \\( -name '*.gz' -o -name '*.xz' -o -name '*.bz2' "
        "-o -name '*.[0-9]' -o -name '*-20*' -o -name '*.old' \\) -mtime +3 -delete 2>/dev/null; "
        # btmp 로테이션 삭제 + 본체 truncate
        "find /var/log -name 'btmp-*' -delete 2>/dev/null; "
        "cat /dev/null > /var/log/btmp 2>/dev/null; "
        # 100MB 이상 로그파일 truncate (활성 로그 보호)
        "for f in /var/log/cron /var/log/messages /var/log/secure; do "
        "  [ -f \"$f\" ] && [ $(stat -c%s \"$f\" 2>/dev/null || echo 0) -gt 104857600 ] && "
        "  cat /dev/null > \"$f\" 2>/dev/null; done; "
        # root 디렉토리 로그 삭제
        "find /root -maxdepth 1 -name '*.log' -mtime +7 -delete 2>/dev/null; "
        "echo DONE"
    )
    ok, output = ssh_exec(ip, cmd)

    ok_after, size_after = ssh_exec(ip, "du -sm /var/log 2>/dev/null | awk '{print $1}'")
    size_after = size_after.strip() if ok_after else '?'

    freed = '?'
    try:
        freed = f"{int(size_before) - int(size_after)}MB"
    except:
        pass

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'before_mb': size_before,
        'after_mb': size_after,
        'freed': freed,
    }


def task_journal_vacuum(server: Dict, dry_run: bool = False) -> Dict:
    """systemd journal 크기 제한"""
    name, ip = server['name'], server['ip']
    log.info(f"[journal_vacuum] {name} ({ip})")

    ok_before, size_before = ssh_exec(ip,
        "journalctl --disk-usage 2>/dev/null | grep -oP '[\\d.]+[MGKB]+' | head -1")
    size_before = size_before.strip() if ok_before else '?'

    if dry_run:
        return {'name': name, 'ip': ip, 'status': 'dry-run', 'current_size': size_before}

    ok, output = ssh_exec(ip, "journalctl --vacuum-size=50M 2>&1")

    ok_after, size_after = ssh_exec(ip,
        "journalctl --disk-usage 2>/dev/null | grep -oP '[\\d.]+[MGKB]+' | head -1")
    size_after = size_after.strip() if ok_after else '?'

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'before': size_before,
        'after': size_after,
    }


def task_deploy_qos_cleanup(server: Dict, dry_run: bool = False) -> Dict:
    """QoS 정리 스크립트 배포 + crontab 등록"""
    name, ip = server['name'], server['ip']
    log.info(f"[deploy_qos] {name} ({ip})")

    if not os.path.exists(QOS_CLEANUP_SCRIPT):
        return {'name': name, 'ip': ip, 'status': 'fail', 'reason': 'Script not found'}

    # 현재 crontab 확인
    ok, current_cron = ssh_exec(ip, "crontab -l 2>/dev/null")
    has_cleanup = 'cleanup_stale_qos.sh' in current_cron if ok else False

    if dry_run:
        return {
            'name': name, 'ip': ip,
            'status': 'dry-run',
            'has_cleanup': has_cleanup,
            'action': 'skip' if has_cleanup else 'deploy',
        }

    # 스크립트 업로드
    ok_upload, msg = ssh_upload(ip, QOS_CLEANUP_SCRIPT, '/etc/strongswan/cleanup_stale_qos.sh')
    if not ok_upload:
        return {'name': name, 'ip': ip, 'status': 'fail', 'reason': f'Upload failed: {msg}'}

    # crontab에 없으면 추가
    if not has_cleanup:
        cron_line = '*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh >> /var/log/cleanup_qos.log 2>&1'
        new_cron = current_cron.rstrip() + '\n' + cron_line + '\n' if current_cron else cron_line + '\n'
        # 안전하게 새 crontab 적용
        safe_cron = new_cron.replace("'", "'\\''")
        ok_cron, output = ssh_exec(ip, f"echo '{safe_cron}' | crontab -")
        if not ok_cron:
            return {'name': name, 'ip': ip, 'status': 'fail', 'reason': f'Cron install failed: {output}'}

    # 즉시 1회 실행 (현재 누적 정리)
    ok_run, run_output = ssh_exec(ip, '/etc/strongswan/cleanup_stale_qos.sh 2>&1', timeout=30)

    # TC 클래스 수 확인
    ok_tc, tc_count = ssh_exec(ip, "tc class show dev eth0 2>/dev/null | grep -c 'parent 1:1 '")

    return {
        'name': name, 'ip': ip,
        'status': 'success',
        'uploaded': True,
        'cron_added': not has_cleanup,
        'first_run': run_output[:200] if run_output else 'clean',
        'tc_after': tc_count.strip() if ok_tc else '?',
    }


def task_stale_radacct(server: Dict, dry_run: bool = False) -> Dict:
    """이 서버의 radacct NULL 세션 중 실제 연결 없는 것 정리
       (dbsync.py가 이 역할을 하지만, 중앙에서도 보조적으로 체크)"""
    name, ip = server['name'], server['ip']
    log.info(f"[stale_radacct] {name} ({ip})")

    db = get_db()
    cur = db.cursor()

    # 이 서버의 NULL 세션 수
    cur.execute("""
        SELECT COUNT(*) FROM radacct
        WHERE nasipaddress=%s AND acctstoptime IS NULL
    """, [ip])
    null_count = cur.fetchone()[0]

    # 실제 활성 세션 수 (SSH)
    ok_ss, ss_count = ssh_exec(ip, "strongswan statusall 2>/dev/null | grep -c ESTABLISHED")
    ok_ovpn, ovpn_count = ssh_exec(ip,
        "for sf in /var/log/openvpn/status.log /var/log/openvpn/utostatus.log; do "
        "[ -f \"$sf\" ] && grep -c '^CLIENT_LIST' \"$sf\" 2>/dev/null; done | paste -sd+ | bc 2>/dev/null || echo 0")

    try:
        active = int(ss_count.strip()) + int(ovpn_count.strip())
    except:
        active = 0

    stale = max(0, null_count - active)

    if dry_run or stale <= 5:
        cur.close()
        db.close()
        return {
            'name': name, 'ip': ip,
            'status': 'dry-run' if dry_run else 'ok',
            'null_sessions': null_count,
            'active_sessions': active,
            'stale': stale,
        }

    # 24시간 이상 된 NULL 세션 중 이 서버 것만 정리
    cur.execute("""
        UPDATE radacct
        SET acctstoptime = NOW(),
            connectinfo_stop = 'cron-cleanup'
        WHERE nasipaddress=%s
          AND acctstoptime IS NULL
          AND acctstarttime < DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """, [ip])
    cleaned = cur.rowcount
    db.commit()
    cur.close()
    db.close()

    return {
        'name': name, 'ip': ip,
        'status': 'success',
        'null_sessions': null_count,
        'active_sessions': active,
        'cleaned': cleaned,
    }


def task_health_check(server: Dict, dry_run: bool = False) -> Dict:
    """서버 상태 종합 점검"""
    name, ip = server['name'], server['ip']
    log.info(f"[health] {name} ({ip})")

    cmd = (
        "UPDAYS=$(awk '{print int($1/86400)}' /proc/uptime);"
        "TC=$(tc class show dev eth0 2>/dev/null | grep -c 'parent 1:1 ');"
        "SS=$(strongswan statusall 2>/dev/null | grep -c ESTABLISHED);"
        "MEM_USED=$(free -m | awk '/Mem:/{print $3}');"
        "MEM_TOT=$(free -m | awk '/Mem:/{print $2}');"
        "DISK=$(df -h / | tail -1 | awk '{print $5}');"
        "LOAD=$(awk '{print $1}' /proc/loadavg);"
        "OOM=$(dmesg 2>/dev/null | grep -ci 'out of memory');"
        "echo \"$UPDAYS|$TC|$SS|$MEM_USED|$MEM_TOT|$DISK|$LOAD|$OOM\""
    )
    ok, output = ssh_exec(ip, cmd, timeout=15)
    if not ok:
        return {'name': name, 'ip': ip, 'status': 'unreachable', 'error': output}

    parts = output.strip().split('|')
    if len(parts) < 8:
        return {'name': name, 'ip': ip, 'status': 'parse_error', 'raw': output}

    updays, tc, ss, mem_used, mem_total, disk, load1, oom = parts[:8]

    issues = []
    try:
        if int(tc) > 500:
            issues.append(f'TC_HIGH({tc})')
        if int(disk.replace('%', '')) > 85:
            issues.append(f'DISK_HIGH({disk})')
        if int(mem_used) > int(mem_total) * 0.85:
            issues.append(f'MEM_HIGH({mem_used}/{mem_total}MB)')
        if int(oom) > 0:
            issues.append(f'OOM_DETECTED({oom})')
        if float(load1) > 4.0:
            issues.append(f'LOAD_HIGH({load1})')
    except:
        pass

    status = 'critical' if len(issues) >= 2 else 'warning' if issues else 'ok'

    return {
        'name': name, 'ip': ip,
        'status': status,
        'uptime_days': updays,
        'tc_classes': tc,
        'strongswan': ss,
        'mem_used_mb': mem_used,
        'mem_total_mb': mem_total,
        'disk': disk,
        'load1': load1,
        'oom_count': oom,
        'issues': issues,
    }


def task_cron_standardize(server: Dict, dry_run: bool = False) -> Dict:
    """crontab을 표준 형태로 정리"""
    name, ip = server['name'], server['ip']
    log.info(f"[cron_std] {name} ({ip})")

    ok, current = ssh_exec(ip, "crontab -l 2>/dev/null")
    if not ok:
        return {'name': name, 'ip': ip, 'status': 'fail', 'reason': 'Cannot read crontab'}

    current_lines = set()
    for line in current.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('PATH='):
            current_lines.add(line)

    # checkuser.py 경로 확인 (서버마다 다를 수 있음)
    ok_check, check_path = ssh_exec(ip,
        "[ -f /etc/strongswan/checkuser.py ] && echo /etc/strongswan/checkuser.py || "
        "[ -f /root/checkuser.py ] && echo /root/checkuser.py || echo NONE")
    check_path = check_path.strip()

    ok_dbsync, dbsync_path = ssh_exec(ip,
        "[ -f /etc/strongswan/dbsync.py ] && echo /etc/strongswan/dbsync.py || "
        "[ -f /root/dbsync.py ] && echo /root/dbsync.py || echo NONE")
    dbsync_path = dbsync_path.strip()

    # 서버 맞춤 표준 crontab 생성
    new_entries = []
    if check_path != 'NONE':
        new_entries.append(f'* * * * * /usr/bin/flock -n /var/lock/checkuser.lock /usr/bin/timeout 55s /usr/bin/python {check_path} >/dev/null 2>&1')
    if dbsync_path != 'NONE':
        new_entries.append(f'* * * * * /usr/bin/flock -n /var/lock/dbsync.lock /usr/bin/timeout 55s /usr/bin/python {dbsync_path} >/dev/null 2>&1')
    new_entries.append('*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh >> /var/log/cleanup_qos.log 2>&1')
    new_entries.append('0 6 * * 3 certbot renew >> /var/log/letsencrypt-renewal.log')
    new_entries.append('0 2 * * * /bin/journalctl --vacuum-size=50M >> /dev/null 2>&1')

    new_set = set(new_entries)

    removed = current_lines - new_set
    added = new_set - current_lines

    if not removed and not added:
        return {'name': name, 'ip': ip, 'status': 'ok', 'reason': 'Already standard'}

    if dry_run:
        return {
            'name': name, 'ip': ip,
            'status': 'dry-run',
            'current_entries': len(current_lines),
            'new_entries': len(new_entries),
            'to_remove': list(removed),
            'to_add': list(added),
        }

    new_crontab = '\n'.join(new_entries) + '\n'
    safe_cron = new_crontab.replace("'", "'\\''")
    ok, output = ssh_exec(ip, f"echo '{safe_cron}' | crontab -")

    return {
        'name': name, 'ip': ip,
        'status': 'success' if ok else 'fail',
        'entries': len(new_entries),
        'removed': list(removed),
        'added': list(added),
        'old_crontab': current,
    }


# ───────────── 메인 실행 ─────────────
def run_task(task_name: str, servers: List[Dict], dry_run: bool = False) -> Dict:
    """지정된 작업을 모든 서버에 병렬 실행"""
    task_funcs = {
        'log_cleanup': task_log_cleanup,
        'journal_vacuum': task_journal_vacuum,
        'deploy_qos_cleanup': task_deploy_qos_cleanup,
        'stale_radacct': task_stale_radacct,
        'health_check': task_health_check,
        'cron_standardize': task_cron_standardize,
    }

    func = task_funcs.get(task_name)
    if not func:
        log.error(f"Unknown task: {task_name}")
        return {'error': f'Unknown task: {task_name}'}

    results = []
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(func, s, dry_run): s for s in servers}
        for future in concurrent.futures.as_completed(futures):
            server = futures[future]
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as e:
                results.append({
                    'name': server['name'],
                    'ip': server['ip'],
                    'status': 'error',
                    'error': str(e)[:200],
                })

    elapsed = time.time() - start

    # 집계
    success = sum(1 for r in results if r.get('status') in ('success', 'ok'))
    fail = sum(1 for r in results if r.get('status') in ('fail', 'error', 'unreachable'))
    warning = sum(1 for r in results if r.get('status') == 'warning')
    critical = sum(1 for r in results if r.get('status') == 'critical')

    report = {
        'task': task_name,
        'total': len(results),
        'success': success,
        'fail': fail,
        'warning': warning,
        'critical': critical,
        'elapsed': round(elapsed, 1),
        'servers': results,
    }

    log.info(f"[{task_name}] 완료: total={len(results)} success={success} fail={fail} "
             f"warning={warning} critical={critical} elapsed={elapsed:.1f}s")

    return report


def main():
    parser = argparse.ArgumentParser(description='UTO NAS 중앙 Cron 관리자')
    parser.add_argument('--task', default=None,
                        choices=['log_cleanup', 'journal_vacuum', 'deploy_qos_cleanup',
                                 'stale_radacct', 'health_check', 'cron_standardize'],
                        help='실행할 작업 (미지정 시 기본 유지보수)')
    parser.add_argument('--server', default=None, help='특정 서버 IP만 실행')
    parser.add_argument('--dry-run', action='store_true', help='미리보기 (실제 변경 없음)')
    parser.add_argument('--json', action='store_true', help='JSON 출력')
    args = parser.parse_args()

    # 서버 목록
    servers = get_active_servers()
    log.info(f"활성 UTO 서버: {len(servers)}개")

    # 도메인/해외 서버 제외 (SSH 키 접근 가능한 것만)
    exclude_ips = set()
    for s in servers:
        ip = s['ip']
        if not ip[0].isdigit():
            exclude_ips.add(ip)  # 도메인 주소
    # 해외/전용선 제외
    for ip_prefix in ['58.246', '220.248', '27.115', '45.63', '139.84', '118.27']:
        for s in servers:
            if s['ip'].startswith(ip_prefix):
                exclude_ips.add(s['ip'])

    servers = [s for s in servers if s['ip'] not in exclude_ips]
    log.info(f"SSH 대상 서버: {len(servers)}개 (해외/도메인 제외)")

    if args.server:
        servers = [s for s in servers if s['ip'] == args.server]
        if not servers:
            log.error(f"서버를 찾을 수 없습니다: {args.server}")
            sys.exit(1)

    # 작업 실행
    if args.task:
        tasks = [args.task]
    else:
        # 기본 유지보수: 로그 정리 + journal + radacct 정리
        tasks = ['log_cleanup', 'journal_vacuum', 'stale_radacct']

    all_reports = {}
    for task in tasks:
        report = run_task(task, servers, dry_run=args.dry_run)
        all_reports[task] = report

        if not args.json:
            print(f"\n{'='*60}")
            print(f" {task} — {report.get('total', 0)}서버, "
                  f"성공:{report.get('success', 0)} 실패:{report.get('fail', 0)} "
                  f"경고:{report.get('warning', 0)} ({report.get('elapsed', 0)}s)")
            print(f"{'='*60}")
            for r in report.get('servers', []):
                status_icon = {'success': '✓', 'ok': '✓', 'warning': '⚠', 'critical': '✗',
                               'fail': '✗', 'error': '✗', 'unreachable': '?', 'dry-run': '~',
                               'skip': '-'}.get(r.get('status', '?'), '?')
                extra = ''
                if task == 'health_check' and r.get('issues'):
                    extra = f" [{', '.join(r['issues'])}]"
                elif task == 'log_cleanup' and r.get('freed'):
                    extra = f" freed={r['freed']}"
                elif task == 'deploy_qos_cleanup':
                    extra = f" cron_added={r.get('cron_added', '?')} tc={r.get('tc_after', '?')}"
                elif task == 'stale_radacct':
                    extra = f" null={r.get('null_sessions', '?')} active={r.get('active_sessions', '?')} cleaned={r.get('cleaned', 0)}"
                print(f"  {status_icon} {r.get('name', '?'):20s} {r.get('ip', '?'):20s} {r.get('status', '?')}{extra}")

    if args.json:
        print(json.dumps(all_reports, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
