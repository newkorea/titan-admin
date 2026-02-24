#!/usr/bin/env python3
"""
TitanVPN NAS Server Monitor & Auto-Healer
==========================================
aws14 (dev) 에서 cron으로 실행하여 모든 활성 NAS 서버를 점검.

점검 항목:
  - Ping 응답
  - SSH 접속 가능
  - 디스크 사용률 (경고: 85%, 위험: 95%)
  - 메모리 사용률 (경고: 80%, 위험: 95%)
  - CPU 로드 (경고: cores*2, 위험: cores*4)
  - StrongSwan 데몬 상태
  - StrongSwan 활성 연결 수
  - OpenVPN 프로세스 상태
  - /var/log 용량

자동 복구:
  - 디스크 95% 이상: 압축 로그 삭제, 로그 truncate
  - StrongSwan 다운: 자동 재시작
  - 좀비 세션 감지 (DB에 활성이지만 서버에 없는 세션)

사용법:
  python3 nas_monitor.py              # 전체 점검
  python3 nas_monitor.py --fix        # 점검 + 자동 복구
  python3 nas_monitor.py --json       # JSON 형식 출력
  python3 nas_monitor.py --check-only # 점검만 (복구 없음, 기본값)
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import concurrent.futures
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

import paramiko
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ───────────── 설정 ─────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
SSH_TIMEOUT = 5
PING_TIMEOUT = 3
MAX_WORKERS = 15

# DB 설정
DB_HOST = '218.158.57.48'
DB_USER = 'titan'
DB_PASS = 'xkdlxks12!@'
DB_NAME = 'titan'

# 임계값
DISK_WARN = 85      # %
DISK_CRIT = 95      # %
MEM_WARN = 80       # %
MEM_CRIT = 95       # %
LOAD_WARN_MULT = 2  # CPU core 수 * 배수
LOAD_CRIT_MULT = 4
LOG_SIZE_WARN = 500  # MB
LOG_SIZE_CRIT = 1000 # MB

# 로그
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'nas_monitor.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('nas_monitor')


# ───────────── 데이터 구조 ─────────────
@dataclass
class ServerHealth:
    ip: str
    name: str = ""
    server_id: int = 0
    # 접속
    ping_ok: bool = False
    ssh_ok: bool = False
    ssh_error: str = ""
    # 리소스
    disk_pct: int = 0
    disk_total: str = ""
    disk_avail: str = ""
    mem_total_mb: int = 0
    mem_used_mb: int = 0
    mem_pct: int = 0
    cpu_cores: int = 0
    load_1m: float = 0.0
    load_5m: float = 0.0
    load_15m: float = 0.0
    # VPN 서비스
    strongswan_running: bool = False
    strongswan_uptime: str = ""
    strongswan_conns: int = 0
    openvpn_running: bool = False
    openvpn_procs: int = 0
    xray_running: bool = False
    softether_running: bool = False
    protocol: str = ""
    # 로그
    log_size_mb: int = 0
    # 프로세스 중복
    dup_procs: int = 0
    # 인증서
    cert_status: str = ""       # OK, EXPIRING, EXPIRED, NO_CERT, UNKNOWN
    cert_expiry: str = ""       # 만료일 (YYYY-MM-DD)
    cert_days_left: int = -999  # 남은 일수
    # 서버 uptime
    uptime_seconds: int = 0
    uptime_text: str = ""
    # 경고/위험
    warnings: List[str] = field(default_factory=list)
    criticals: List[str] = field(default_factory=list)
    # 자동 복구
    actions_taken: List[str] = field(default_factory=list)


# ───────────── DB 헬퍼 ─────────────
def get_active_servers():
    """tbl_agent3에서 is_active=1 서버 목록"""
    import MySQLdb
    db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB_NAME, charset='utf8')
    cur = db.cursor()
    cur.execute("""
        SELECT id, name, hostip, username, password, protocol
        FROM tbl_agent3 WHERE is_active=1
        ORDER BY hostip
    """)
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows


def get_active_sessions_by_nas():
    """radacct에서 NAS별 활성 세션 수"""
    import MySQLdb
    db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db='radius', charset='utf8')
    cur = db.cursor()
    cur.execute("""
        SELECT nasipaddress, COUNT(*) as cnt
        FROM radacct
        WHERE acctstoptime IS NULL
        GROUP BY nasipaddress
    """)
    result = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()
    db.close()
    return result


def get_stale_sessions(ip, hours=48):
    """48시간 이상 된 활성 세션 (좀비 가능성)"""
    import MySQLdb
    db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db='radius', charset='utf8')
    cur = db.cursor()
    cur.execute("""
        SELECT radacctid, username, acctstarttime
        FROM radacct
        WHERE nasipaddress=%s AND acctstoptime IS NULL
          AND acctstarttime < NOW() - INTERVAL %s HOUR
    """, (ip, hours))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows


# ───────────── SSH 메트릭 수집 ─────────────
METRIC_SCRIPT = r"""
echo "===DISK==="
df / | tail -1 | awk '{print $2,$3,$4,$5}'
echo "===MEM==="
free -m | grep Mem | awk '{print $2,$3}'
echo "===CPU==="
nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo
echo "===LOAD==="
cat /proc/loadavg | awk '{print $1,$2,$3}'
echo "===SWAN_STATUS==="
strongswan statusall 2>/dev/null | head -2 || ipsec statusall 2>/dev/null | head -2 || echo "NOT_RUNNING"
echo "===SWAN_CONNS==="
strongswan statusall 2>/dev/null | grep -c 'ESTABLISHED' || echo 0
echo "===OPENVPN==="
ps aux | grep -c '[o]penvpn' || echo 0
echo "===XRAY==="
ps aux | grep -c '[x]ray' || echo 0
echo "===VPNSERVER==="
ps aux | grep -c '[v]pnserver' || echo 0
echo "===LOGSIZE==="
du -sm /var/log/ 2>/dev/null | cut -f1 || echo 0
echo "===DUP_PROCS==="
ps -eo cmd | grep -E 'sync_qos_all|vpncmd.*SessionList' | grep -v grep | wc -l
echo "===UPTIME==="
cat /proc/uptime | awk '{print $1}'
echo "===CERT==="
cert=$(readlink -f /etc/strongswan/ipsec.d/certs/certificate.pem 2>/dev/null); if [ -n "$cert" ] && [ -f "$cert" ]; then openssl x509 -enddate -noout -in $cert; else cert=$(find /etc/letsencrypt/live/ -name fullchain.pem -not -path "*/README" 2>/dev/null | head -1); if [ -n "$cert" ]; then openssl x509 -enddate -noout -in $cert; else echo NO_CERT; fi; fi
echo "===END==="
"""


def ping_host(ip):
    """ping 체크"""
    try:
        r = subprocess.run(
            ['ping', '-c', '1', '-W', str(PING_TIMEOUT), ip],
            capture_output=True, timeout=PING_TIMEOUT + 2
        )
        return r.returncode == 0
    except:
        return False


def collect_metrics(health: ServerHealth, ssh_user: str, ssh_pass: str) -> ServerHealth:
    """SSH로 서버 메트릭 수집 (실패 시 1회 재시도)"""
    for attempt in range(2):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            timeout = SSH_TIMEOUT if attempt == 0 else SSH_TIMEOUT + 5

            # 키 인증 우선, 실패시 패스워드
            try:
                ssh.connect(health.ip, username=ssh_user, key_filename=SSH_KEY, timeout=timeout,
                            banner_timeout=timeout + 5)
            except:
                ssh.connect(health.ip, username=ssh_user, password=ssh_pass, timeout=timeout,
                            banner_timeout=timeout + 5)

            health.ssh_ok = True

            _, stdout, _ = ssh.exec_command(METRIC_SCRIPT)
            output = stdout.read().decode('utf-8', errors='replace')
            ssh.close()

            parse_metrics(health, output)
            evaluate_health(health)
            return health  # 성공 시 바로 반환

        except Exception as e:
            if attempt == 0:
                # 1차 실패 → 2초 대기 후 재시도
                log.debug(f"  {health.name} ({health.ip}) SSH 1차 실패, 재시도: {e}")
                time.sleep(2)
            else:
                health.ssh_ok = False
                health.ssh_error = str(e)[:100]
                health.criticals.append(f"SSH 접속 실패: {health.ssh_error}")

    return health


def parse_metrics(health: ServerHealth, output: str):
    """수집한 메트릭 파싱"""
    sections = {}
    current = None
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('===') and line.endswith('==='):
            current = line.strip('=')
            sections[current] = []
        elif current and line:
            sections.setdefault(current, []).append(line)

    # 디스크
    if 'DISK' in sections and sections['DISK']:
        parts = sections['DISK'][0].split()
        if len(parts) >= 4:
            try:
                total_kb = int(parts[0])
                used_kb = int(parts[1])
                avail_kb = int(parts[2])
                pct = parts[3].replace('%', '')
                health.disk_total = f"{total_kb // 1024 // 1024}G"
                health.disk_avail = f"{avail_kb // 1024}M"
                health.disk_pct = int(pct)
            except:
                pass

    # 메모리
    if 'MEM' in sections and sections['MEM']:
        parts = sections['MEM'][0].split()
        if len(parts) >= 2:
            try:
                health.mem_total_mb = int(parts[0])
                health.mem_used_mb = int(parts[1])
                if health.mem_total_mb > 0:
                    health.mem_pct = int(health.mem_used_mb * 100 / health.mem_total_mb)
            except:
                pass

    # CPU cores
    if 'CPU' in sections and sections['CPU']:
        try:
            health.cpu_cores = int(sections['CPU'][0])
        except:
            health.cpu_cores = 1

    # Load average
    if 'LOAD' in sections and sections['LOAD']:
        parts = sections['LOAD'][0].split()
        if len(parts) >= 3:
            try:
                health.load_1m = float(parts[0])
                health.load_5m = float(parts[1])
                health.load_15m = float(parts[2])
            except:
                pass

    # StrongSwan
    if 'SWAN_STATUS' in sections:
        swan_text = ' '.join(sections['SWAN_STATUS'])
        health.strongswan_running = 'NOT_RUNNING' not in swan_text and 'charon' in swan_text.lower()
        if 'uptime:' in swan_text:
            idx = swan_text.index('uptime:')
            health.strongswan_uptime = swan_text[idx + 7:idx + 40].strip().split(',')[0]

    if 'SWAN_CONNS' in sections and sections['SWAN_CONNS']:
        try:
            health.strongswan_conns = int(sections['SWAN_CONNS'][0])
        except:
            pass

    # OpenVPN
    if 'OPENVPN' in sections and sections['OPENVPN']:
        try:
            cnt = int(sections['OPENVPN'][0])
            health.openvpn_procs = cnt
            health.openvpn_running = cnt > 0
        except:
            pass

    # Xray (V2Ray)
    if 'XRAY' in sections and sections['XRAY']:
        try:
            health.xray_running = int(sections['XRAY'][0]) > 0
        except:
            pass

    # SoftEther (vpnserver)
    if 'VPNSERVER' in sections and sections['VPNSERVER']:
        try:
            health.softether_running = int(sections['VPNSERVER'][0]) > 0
        except:
            pass

    # Log size
    if 'LOGSIZE' in sections and sections['LOGSIZE']:
        try:
            health.log_size_mb = int(sections['LOGSIZE'][0])
        except:
            pass

    # 프로세스 중복
    if 'DUP_PROCS' in sections and sections['DUP_PROCS']:
        try:
            health.dup_procs = int(sections['DUP_PROCS'][0])
        except:
            pass

    # Uptime
    if 'UPTIME' in sections and sections['UPTIME']:
        try:
            secs = int(float(sections['UPTIME'][0]))
            health.uptime_seconds = secs
            days = secs // 86400
            hours = (secs % 86400) // 3600
            if days > 0:
                health.uptime_text = f"{days}d {hours}h"
            else:
                health.uptime_text = f"{hours}h {(secs % 3600) // 60}m"
        except:
            pass

    # 인증서
    if 'CERT' in sections and sections['CERT']:
        cert_line = sections['CERT'][0].strip()
        if cert_line == 'NO_CERT':
            health.cert_status = 'NO_CERT'
        elif cert_line.startswith('notAfter='):
            try:
                date_str = cert_line.replace('notAfter=', '').strip()
                expiry = datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                now = datetime.utcnow()
                days_left = (expiry - now).days
                health.cert_expiry = expiry.strftime('%Y-%m-%d')
                health.cert_days_left = days_left
                if days_left < 0:
                    health.cert_status = 'EXPIRED'
                elif days_left < 20:
                    health.cert_status = 'EXPIRING'
                else:
                    health.cert_status = 'OK'
            except:
                health.cert_status = 'PARSE_ERROR'
        else:
            health.cert_status = 'UNKNOWN'


def evaluate_health(health: ServerHealth):
    """임계값 기반 경고/위험 판단"""
    # 디스크
    if health.disk_pct >= DISK_CRIT:
        health.criticals.append(f"디스크 {health.disk_pct}% (남은공간: {health.disk_avail})")
    elif health.disk_pct >= DISK_WARN:
        health.warnings.append(f"디스크 {health.disk_pct}% (남은공간: {health.disk_avail})")

    # 메모리
    if health.mem_pct >= MEM_CRIT:
        health.criticals.append(f"메모리 {health.mem_pct}% ({health.mem_used_mb}/{health.mem_total_mb}MB)")
    elif health.mem_pct >= MEM_WARN:
        health.warnings.append(f"메모리 {health.mem_pct}% ({health.mem_used_mb}/{health.mem_total_mb}MB)")

    # CPU 로드
    if health.cpu_cores > 0:
        if health.load_1m >= health.cpu_cores * LOAD_CRIT_MULT:
            health.criticals.append(f"CPU 부하 {health.load_1m:.1f} (코어: {health.cpu_cores})")
        elif health.load_1m >= health.cpu_cores * LOAD_WARN_MULT:
            health.warnings.append(f"CPU 부하 {health.load_1m:.1f} (코어: {health.cpu_cores})")

    # StrongSwan
    if not health.strongswan_running:
        health.criticals.append("StrongSwan 데몬 다운!")

    # OpenVPN (프로토콜 포함 서버만 체크)
    if 'OPENVPN' in (health.protocol or '').upper() and not health.openvpn_running:
        health.criticals.append("OpenVPN 프로세스 다운!")

    # Xray/V2Ray
    if 'V2RAY' in (health.protocol or '').upper() and not health.xray_running:
        health.criticals.append("Xray(V2Ray) 프로세스 다운!")

    # SoftEther
    if 'SOFTETHER' in (health.protocol or '').upper() and not health.softether_running:
        health.criticals.append("SoftEther(vpnserver) 프로세스 다운!")

    # 로그 크기
    if health.log_size_mb >= LOG_SIZE_CRIT:
        health.criticals.append(f"/var/log {health.log_size_mb}MB")
    elif health.log_size_mb >= LOG_SIZE_WARN:
        health.warnings.append(f"/var/log {health.log_size_mb}MB")

    # 프로세스 중복
    if health.dup_procs >= 10:
        health.criticals.append(f"프로세스 중복 {health.dup_procs}개")
    elif health.dup_procs >= 5:
        health.warnings.append(f"프로세스 중복 {health.dup_procs}개")

    # 인증서
    if health.cert_status == 'EXPIRED':
        health.criticals.append(f"인증서 만료 ({health.cert_expiry})")
    elif health.cert_status == 'EXPIRING':
        health.warnings.append(f"인증서 {health.cert_days_left}일 남음 ({health.cert_expiry})")

# ───────────── 자동 복구 ─────────────
def auto_heal(health: ServerHealth, ssh_user: str, ssh_pass: str):
    """문제 발견 시 자동 복구 시도"""
    if not health.ssh_ok:
        return

    actions = []

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(health.ip, username=ssh_user, key_filename=SSH_KEY, timeout=SSH_TIMEOUT,
                        banner_timeout=SSH_TIMEOUT + 5)
        except:
            ssh.connect(health.ip, username=ssh_user, password=ssh_pass, timeout=SSH_TIMEOUT,
                        banner_timeout=SSH_TIMEOUT + 5)

        # 1) 로그 정리 (디스크 85% 이상 또는 /var/log 500MB 이상)
        need_log_clean = health.disk_pct >= DISK_WARN or health.log_size_mb >= LOG_SIZE_WARN
        if need_log_clean:
            reason = f"디스크 {health.disk_pct}%" if health.disk_pct >= DISK_WARN else f"/var/log {health.log_size_mb}MB"
            log.info(f"[{health.ip}] {reason} → 로그 정리 시작")
            cleanup_cmds = [
                # /root 내 큰 로그 (sync_qos_vpn_final.log 등)
                "find /root -maxdepth 1 -name '*.log' -size +10M -exec truncate -s 0 {} \\; 2>/dev/null",
                # logrotate 날짜접미사 파일 삭제 (messages-20260203 등)
                "find /var/log -maxdepth 1 -name '*-20[0-9][0-9]*' -delete 2>/dev/null",
                # /var/log 압축/로테이트 파일 삭제
                "find /var/log -name '*.gz' -delete 2>/dev/null",
                "find /var/log -name '*.[0-9]' -delete 2>/dev/null",
                "find /var/log -name '*.old' -delete 2>/dev/null",
                # OpenVPN 3일 이상 로그 삭제 + 현재 로그 truncate
                "find /var/log/openvpn -type f -mtime +3 -delete 2>/dev/null",
                "find /var/log/openvpn -type f -exec truncate -s 0 {} \\; 2>/dev/null",
                # 주요 로그 truncate (0바이트)
                "truncate -s 0 /var/log/messages 2>/dev/null",
                "truncate -s 0 /var/log/secure 2>/dev/null",
                "truncate -s 0 /var/log/maillog 2>/dev/null",
                "truncate -s 0 /var/log/cron 2>/dev/null",
                "truncate -s 0 /var/log/strongswan.log 2>/dev/null",
                "truncate -s 0 /var/log/charon.log 2>/dev/null",
                "truncate -s 0 /var/log/auth.log 2>/dev/null",
                "truncate -s 0 /var/log/btmp 2>/dev/null",
                "truncate -s 0 /var/log/wtmp 2>/dev/null",
                "truncate -s 0 /var/log/lastlog 2>/dev/null",
                # journal 정리
                "journalctl --vacuum-size=50M 2>/dev/null",
                # SoftEther 로그 정리
                "find /usr/local/vpnserver/packet_log -type f -mtime +3 -delete 2>/dev/null",
                "find /usr/local/vpnserver/security_log -type f -mtime +7 -delete 2>/dev/null",
                "find /usr/local/vpnserver/server_log -type f -mtime +7 -delete 2>/dev/null",
                # 패키지 캐시, 임시 파일
                "rm -rf /var/cache/yum/* 2>/dev/null",
                "rm -rf /tmp/cores/* 2>/dev/null",
            ]
            for cmd in cleanup_cmds:
                ssh.exec_command(cmd)
            time.sleep(1)

            # /var/log 사이즈 재확인
            _, out, _ = ssh.exec_command("du -sm /var/log/ 2>/dev/null | cut -f1")
            new_log = out.read().decode().strip()
            try:
                new_log_mb = int(new_log)
                actions.append(f"로그 정리: /var/log {health.log_size_mb}MB → {new_log_mb}MB")
                health.log_size_mb = new_log_mb
            except:
                pass

            # 디스크 확인
            _, out, _ = ssh.exec_command("df / | tail -1 | awk '{print $5}' | tr -d '%'")
            new_pct = out.read().decode().strip()
            try:
                new_pct = int(new_pct)
                freed = health.disk_pct - new_pct
                actions.append(f"디스크: {health.disk_pct}% → {new_pct}% ({freed}% 확보)")
                health.disk_pct = new_pct
            except:
                actions.append("로그 정리 실행 (결과 확인 실패)")

        # 2) StrongSwan 재시작
        if not health.strongswan_running:
            log.info(f"[{health.ip}] StrongSwan 다운 → 재시작")
            ssh.exec_command("strongswan restart 2>/dev/null || ipsec restart 2>/dev/null")
            time.sleep(3)
            _, out, _ = ssh.exec_command("strongswan statusall 2>/dev/null | head -1")
            result = out.read().decode().strip()
            if 'charon' in result.lower():
                actions.append("StrongSwan 재시작 성공")
                health.strongswan_running = True
            else:
                actions.append("StrongSwan 재시작 실패!")

        # 3) 메모리 부족 시 캐시 해제 + 좀비 프로세스 정리 (80% 이상)
        if health.mem_pct >= MEM_WARN:
            log.info(f"[{health.ip}] 메모리 {health.mem_pct}% → 캐시 해제 + 좀비 정리")
            # 캐시 해제
            ssh.exec_command("sync && echo 3 > /proc/sys/vm/drop_caches")
            # stale checkuser.py 프로세스 정리 (1일 이상된 것)
            ssh.exec_command("ps aux | grep 'checkuser.py' | grep -v grep | awk '{if ($10 ~ /^[0-9]+:/ && int($10) > 24*60) print $2}' | xargs -r kill 2>/dev/null")
            # 2025년 이전에 시작된 checkuser.py 정리
            ssh.exec_command("ps aux | grep 'checkuser.py' | grep -v grep | awk '{if ($9 ~ /2025/ || $9 ~ /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/) print $2}' | xargs -r kill 2>/dev/null")
            time.sleep(1)
            _, out, _ = ssh.exec_command("free -m | grep Mem | awk '{print $3}'")
            new_used = out.read().decode().strip()
            try:
                new_used = int(new_used)
                new_pct = int(new_used * 100 / health.mem_total_mb) if health.mem_total_mb > 0 else 0
                actions.append(f"메모리 정리: {health.mem_pct}% → {new_pct}%")
                health.mem_pct = new_pct
                health.mem_used_mb = new_used
            except:
                actions.append("캐시 해제 실행 (결과 확인 실패)")

        # 4) Ping 실패 시 ICMP 규칙 확인/추가
        if not health.ping_ok and health.ssh_ok:
            log.info(f"[{health.ip}] Ping 실패 → ICMP 규칙 확인")
            _, out, _ = ssh.exec_command("iptables -L INPUT -n | grep -c 'icmp-host-prohibited'")
            has_reject = int(out.read().decode().strip() or "0") > 0
            _, out, _ = ssh.exec_command("iptables -L INPUT -n | grep -c 'icmptype 8'")
            has_icmp = int(out.read().decode().strip() or "0") > 0
            if has_reject and not has_icmp:
                ssh.exec_command("iptables -I INPUT 5 -p icmp --icmp-type echo-request -j ACCEPT 2>/dev/null")
                ssh.exec_command("service iptables save 2>/dev/null || iptables-save > /etc/sysconfig/iptables 2>/dev/null")
                actions.append("ICMP 허용 규칙 추가")

        # 5) OpenVPN 프로세스 다운 → 재시작
        if 'OPENVPN' in (health.protocol or '').upper() and not health.openvpn_running:
            log.info(f"[{health.ip}] OpenVPN 다운 → 재시작")
            ssh.exec_command("systemctl restart openvpn 2>/dev/null || service openvpn restart 2>/dev/null")
            time.sleep(3)
            _, out, _ = ssh.exec_command("ps aux | grep -c '[o]penvpn'")
            cnt = int(out.read().decode().strip() or "0")
            if cnt > 0:
                actions.append("OpenVPN 재시작 성공")
                health.openvpn_running = True
            else:
                actions.append("OpenVPN 재시작 실패!")

        # 6) Xray(V2Ray) 프로세스 다운 → x-ui 재시작
        if 'V2RAY' in (health.protocol or '').upper() and not health.xray_running:
            log.info(f"[{health.ip}] Xray 다운 → x-ui 재시작")
            ssh.exec_command("x-ui restart 2>/dev/null || systemctl restart x-ui 2>/dev/null")
            time.sleep(5)
            _, out, _ = ssh.exec_command("ps aux | grep -c '[x]ray'")
            cnt = int(out.read().decode().strip() or "0")
            if cnt > 0:
                actions.append("Xray(V2Ray) 재시작 성공")
                health.xray_running = True
            else:
                actions.append("Xray(V2Ray) 재시작 실패!")

        # 7) 디스크 85% 이상 시 postfix 메일큐 정리
        if health.disk_pct >= DISK_WARN:
            ssh.exec_command("postsuper -d ALL 2>/dev/null; find /var/spool/postfix/deferred -type f -delete 2>/dev/null; find /var/spool/postfix/bounce -type f -delete 2>/dev/null; find /var/spool/postfix/corrupt -type f -delete 2>/dev/null")
            actions.append("postfix 메일큐 정리")

        ssh.close()

    except Exception as e:
        actions.append(f"자동 복구 실패: {str(e)[:60]}")

    health.actions_taken = actions


# ───────────── 메인 점검 ─────────────
def _do_single_check(srv, ping_results, db_sessions, do_fix=False):
    """단일 서버 점검 (재시도 로직 포함)"""
    sid, name, ip, ssh_user, ssh_pass, proto = srv
    h = ServerHealth(ip=ip, name=name, server_id=sid, protocol=proto or '')
    h.ping_ok = ping_results.get(ip, False)

    if not h.ping_ok:
        h.warnings.append("Ping 응답 없음 (ICMP 차단 가능)")

    # ping 실패해도 SSH 시도 (ICMP 차단/일시적 패킷로스 대응)
    collect_metrics(h, ssh_user, ssh_pass)

    if not h.ping_ok and not h.ssh_ok:
        h.warnings = [w for w in h.warnings if 'Ping' not in w]
        h.criticals.append("Ping + SSH 모두 실패 (서버 다운)")
    elif not h.ping_ok and h.ssh_ok:
        pass

    # DB 세션 vs StrongSwan 실제 연결 비교
    db_cnt = db_sessions.get(ip, 0)
    if db_cnt > 0 and not h.ping_ok and not h.ssh_ok:
        h.criticals.append(f"DB에 활성세션 {db_cnt}개인데 서버 응답 없음 (좀비 세션)")

    if do_fix and (h.criticals or h.warnings):
        auto_heal(h, ssh_user, ssh_pass)

    return h


def check_all_servers(do_fix=False, target_ip=None):
    """전체 또는 단일 서버 점검 (target_ip 지정 시 해당 서버만)"""
    log.info("=" * 60)
    log.info("NAS 서버 모니터링 시작")
    start = time.time()

    servers = get_active_servers()
    if target_ip:
        servers = [s for s in servers if s[2] == target_ip]
        if not servers:
            log.error(f"서버를 찾을 수 없음: {target_ip}")
            return [], time.time() - start
        log.info(f"단일 서버 점검: {servers[0][1]} ({target_ip})")
    else:
        log.info(f"활성 서버: {len(servers)}대")

    # DB 활성 세션
    db_sessions = get_active_sessions_by_nas()

    # Ping 체크 (병렬)
    ip_list = [s[2] for s in servers]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        ping_results = dict(zip(ip_list, ex.map(ping_host, ip_list)))

    # 서버별 메트릭 수집 (병렬)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        health_list = list(ex.map(
            lambda srv: _do_single_check(srv, ping_results, db_sessions, do_fix),
            servers
        ))

    # ── Critical 서버 재검증 (일시적 장애 방지) ──
    retry_targets = []
    for i, h in enumerate(health_list):
        if h.criticals:
            retry_targets.append((i, servers[i]))

    if retry_targets:
        log.info(f"Critical 서버 {len(retry_targets)}대 재검증 (5초 대기 후 재시도)")
        time.sleep(5)

        # 재시도 ping
        retry_ips = [s[1][2] for s in retry_targets]
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            retry_pings = dict(zip(retry_ips, ex.map(ping_host, retry_ips)))

        def retry_check(item):
            idx, srv = item
            return idx, _do_single_check(srv, retry_pings, db_sessions, do_fix)

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            retry_results = list(ex.map(retry_check, retry_targets))

        for idx, new_h in retry_results:
            old_h = health_list[idx]
            # 재시도에서 개선되었으면 새 결과로 교체
            if len(new_h.criticals) < len(old_h.criticals) or (not new_h.criticals and old_h.criticals):
                log.info(f"  ✓ {new_h.name} ({new_h.ip}) 재검증 결과 개선 → 업데이트")
                health_list[idx] = new_h
            else:
                log.info(f"  ✗ {old_h.name} ({old_h.ip}) 재검증에도 여전히 Critical")

    elapsed = time.time() - start
    return health_list, elapsed


# ───────────── 리포트 출력 ─────────────
def print_report(health_list: List[ServerHealth], elapsed: float):
    """점검 결과 리포트"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = len(health_list)
    crit_servers = [h for h in health_list if h.criticals]
    warn_servers = [h for h in health_list if h.warnings and not h.criticals]
    ok_servers = [h for h in health_list if not h.criticals and not h.warnings]

    print(f"\n{'='*70}")
    print(f"  TitanVPN NAS 서버 점검 리포트  |  {now}  |  {elapsed:.1f}초")
    print(f"{'='*70}")
    print(f"  전체: {total}대  |  정상: {len(ok_servers)}  |  경고: {len(warn_servers)}  |  위험: {len(crit_servers)}")
    print(f"{'='*70}")

    # 위험 서버
    if crit_servers:
        print(f"\n🔴 위험 ({len(crit_servers)}대)")
        print(f"  {'IP':<18} {'이름':<16} {'디스크':>5} {'메모리':>5} {'Load':>6} {'Swan':>4} {'문제'}")
        print(f"  {'-'*80}")
        for h in crit_servers:
            swan = f"{h.strongswan_conns}" if h.strongswan_running else "DOWN"
            issues = '; '.join(h.criticals)
            print(f"  {h.ip:<18} {h.name:<16} {h.disk_pct:>4}% {h.mem_pct:>4}% {h.load_1m:>6.1f} {swan:>4} {issues}")
            if h.actions_taken:
                for a in h.actions_taken:
                    print(f"    → {a}")

    # 경고 서버
    if warn_servers:
        print(f"\n🟡 경고 ({len(warn_servers)}대)")
        print(f"  {'IP':<18} {'이름':<16} {'디스크':>5} {'메모리':>5} {'Load':>6} {'Swan':>4} {'문제'}")
        print(f"  {'-'*80}")
        for h in warn_servers:
            swan = f"{h.strongswan_conns}" if h.strongswan_running else "DOWN"
            issues = '; '.join(h.warnings)
            print(f"  {h.ip:<18} {h.name:<16} {h.disk_pct:>4}% {h.mem_pct:>4}% {h.load_1m:>6.1f} {swan:>4} {issues}")
            if h.actions_taken:
                for a in h.actions_taken:
                    print(f"    → {a}")

    # 정상 서버 요약
    if ok_servers:
        print(f"\n🟢 정상 ({len(ok_servers)}대)")
        print(f"  {'IP':<18} {'이름':<16} {'디스크':>5} {'메모리':>5} {'Load':>6} {'Swan':>4} {'OVP':>3} {'Log':>5}")
        print(f"  {'-'*80}")
        for h in ok_servers:
            swan = f"{h.strongswan_conns}" if h.strongswan_running else "DOWN"
            print(f"  {h.ip:<18} {h.name:<16} {h.disk_pct:>4}% {h.mem_pct:>4}% {h.load_1m:>6.1f} {swan:>4} {h.openvpn_procs:>3} {h.log_size_mb:>4}M")

    print(f"\n{'='*70}\n")


def print_json(health_list: List[ServerHealth], elapsed: float):
    """JSON 출력"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_sec": round(elapsed, 1),
        "total": len(health_list),
        "critical": len([h for h in health_list if h.criticals]),
        "warning": len([h for h in health_list if h.warnings and not h.criticals]),
        "ok": len([h for h in health_list if not h.criticals and not h.warnings]),
        "servers": [asdict(h) for h in health_list],
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


def save_report(health_list: List[ServerHealth]):
    """최근 리포트를 JSON 파일로 저장 (히스토리용)"""
    report_file = os.path.join(LOG_DIR, 'nas_monitor_latest.json')
    data = {
        "timestamp": datetime.now().isoformat(),
        "servers": [asdict(h) for h in health_list],
    }
    with open(report_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ───────────── CLI ─────────────
def main():
    parser = argparse.ArgumentParser(description='TitanVPN NAS 서버 모니터링')
    parser.add_argument('--fix', action='store_true', help='문제 발견 시 자동 복구')
    parser.add_argument('--json', action='store_true', help='JSON 형식 출력')
    parser.add_argument('--check-only', action='store_true', default=True, help='점검만 (기본값)')
    parser.add_argument('--server', type=str, default=None, help='특정 서버 IP만 점검')
    args = parser.parse_args()

    do_fix = args.fix

    health_list, elapsed = check_all_servers(do_fix=do_fix, target_ip=args.server)

    if args.json:
        print_json(health_list, elapsed)
    else:
        print_report(health_list, elapsed)

    if not args.server:
        save_report(health_list)

    # 종료 코드: 위험 있으면 2, 경고 있으면 1, 정상 0
    if any(h.criticals for h in health_list):
        sys.exit(2)
    elif any(h.warnings for h in health_list):
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
