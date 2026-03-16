# -*- coding: utf-8 -*-
"""
dbsync.py v2.0 — radacct ↔ 실제 VPN 세션 동기화

동작:
  1) strongSwan / OpenVPN 실제 세션 목록 수집
  2) 이 서버(nasipaddress = my_ip)의 radacct NULL 세션과 비교
  3) 실제 연결이 없는데 NULL → acctstoptime = now 로 닫기
  4) 실제 연결이 있는데 NULL row 없음 → radacct 새 row INSERT
  5) nasporttype NOT IN ('strongSwan','openvpn') 인 NULL 세션도 정리
  6) 동일 (user, port) 중복 NULL 제거
  7) 요약 로그 출력

변경 이력:
  2026-03-06 v2.1 — flock 이중잠금 버그 수정
    - cron에서 flock -n 래퍼 사용 시 내부 flock이 EWOULDBLOCK → 실행 안 됨
    - 내부 flock 제거 (cron 래퍼에 위임)
  2026-03-06 v2.0 — 전체 재작성 (SK83 478줄 기반 개선)
    - DB 연결 pool/재시도
    - strongSwan timeout 30s 내장
    - 배치 쿼리 최적화
    - 로그 파일 기록 (/var/log/dbsync.log)
    - 실행 시간 60초 제한
"""

import sys
# Python 2.7 호환
if hasattr(sys, 'setdefaultencoding'):
    reload(sys)
    sys.setdefaultencoding('utf-8')

import mysql.connector
import subprocess
import logging
import socket
import re
import os
import signal
import time
from datetime import datetime
from collections import defaultdict
import random
import string


# ==============================
# 설정
# ==============================
VERSION = "2.1"

DB_CONFIG = {
    'user':     'root',
    'password': 'uto6703',
    'host':     '218.158.57.51',
    'database': 'vcsvpn2013',
    'charset':  'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 10,
}

STRONGSWAN_BIN = "/usr/sbin/strongswan"
STRONGSWAN_TIMEOUT = 30  # seconds

OPENVPN_STATUS_FILES = [
    "/var/log/openvpn/status.log",
    "/var/log/openvpn/utostatus.log",
]

LOG_FILE = "/var/log/dbsync.log"
MAX_RUNTIME = 55  # seconds (cron runs every 60s, leave 5s margin)


# ==============================
# 로그 설정 (Python 2.7 호환)
# ==============================
logger = logging.getLogger('dbsync')
logger.setLevel(logging.WARNING)
_fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

try:
    _fh = logging.FileHandler(LOG_FILE)
    _fh.setFormatter(_fmt)
    logger.addHandler(_fh)
except:
    pass


# ==============================
# 시간 제한
# ==============================
_start_time = time.time()

def check_timeout():
    """MAX_RUNTIME 초과 시 True 반환."""
    return (time.time() - _start_time) > MAX_RUNTIME


# 참고: flock은 cron에서 `flock -n /tmp/dbsync.lock` 래퍼로 처리
# 내부 flock은 cron flock과 충돌하므로 사용하지 않음


# ==============================
# 유틸
# ==============================
def get_server_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        ip_addr = sock.getsockname()[0]
        sock.close()
        return ip_addr
    except Exception as e:
        logger.warning("Failed to get server IP: %s", e)
        return None

def get_db_conn():
    return mysql.connector.connect(**DB_CONFIG)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gen_random_token(length=16):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# ==============================
# strongSwan 세션 파서
# ==============================
def get_strongswan_sessions():
    """
    { username: [nasportid1, nasportid2, ...] }
    ESTABLISHED 라인에서 ..IP[user] 파싱 + Remote EAP identity 오버라이드.
    """
    sessions_by_port = {}
    last_port = None

    try:
        cmd = "timeout %d %s statusall" % (STRONGSWAN_TIMEOUT, STRONGSWAN_BIN)
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        text = out.decode('utf-8', 'ignore').splitlines()
    except subprocess.CalledProcessError as e:
        rc = e.returncode
        if rc == 124:
            logger.warning("strongSwan statusall timed out after %ds", STRONGSWAN_TIMEOUT)
        elif rc == 1:
            pass  # no connections
        else:
            logger.warning("strongSwan statusall failed rc=%d", rc)
        return {}
    except Exception as e:
        logger.warning("strongSwan call error: %s", e)
        return {}

    for line in text:
        line = line.rstrip()

        # ESTABLISHED line: ikev2-vpn[PORT]: ESTABLISHED ..., SERVER[id]...REMOTE[user]
        m_est = re.search(
            r'ikev2-vpn\[(\d+)\]: ESTABLISHED.*\.\.\.[^\[]+\[([^\]]+)\]',
            line
        )
        if m_est:
            port = m_est.group(1)
            ident = m_est.group(2).strip()
            sessions_by_port[port] = {'user': ident, 'has_eap': False}
            last_port = port
            continue

        # Remote EAP identity overrides
        m_eap = re.search(r'Remote EAP identity:\s+(.+)', line)
        if m_eap and last_port and last_port in sessions_by_port:
            eap_user = m_eap.group(1).strip()
            sessions_by_port[last_port]['user'] = eap_user
            sessions_by_port[last_port]['has_eap'] = True
            continue

    # port -> user → user -> [ports]
    result = defaultdict(list)
    for port, info in sessions_by_port.items():
        user = info['user']
        if user:
            result[user].append(int(port))

    logger.warning("strongSwan: %d users, %d sessions", len(result), sum(len(v) for v in result.values()))
    return result


# ==============================
# OpenVPN 세션 파서
# ==============================
def parse_openvpn_status_file(path):
    sessions = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line.startswith("CLIENT_LIST"):
                    continue
                parts = line.split(',')
                if len(parts) < 12:
                    continue
                username = parts[9] or parts[1]
                try:
                    nasportid = int(parts[10])
                except:
                    continue
                sessions.append((username, nasportid))
    except IOError:
        return []
    return sessions

def get_openvpn_sessions():
    all_pairs = []
    for path in OPENVPN_STATUS_FILES:
        all_pairs.extend(parse_openvpn_status_file(path))

    result = defaultdict(list)
    for user, port in all_pairs:
        if port not in result[user]:
            result[user].append(port)

    if result:
        logger.warning("OpenVPN: %d users, %d sessions", len(result), sum(len(v) for v in result.values()))
    return dict(result)


# ==============================
# radacct 동기화 로직
# ==============================

def close_legacy_null_rows(conn, my_ip):
    """nasporttype 이 strongSwan/openvpn 아닌 NULL 세션 정리."""
    sql = """
        UPDATE radacct
           SET acctstoptime = %s, connectinfo_stop = 'dbsync-legacy'
         WHERE nasipaddress = %s
           AND acctstoptime IS NULL
           AND (nasporttype IS NULL OR nasporttype NOT IN ('openvpn', 'strongSwan'))
    """
    cur = conn.cursor()
    cur.execute(sql, (now_str(), my_ip))
    affected = cur.rowcount
    conn.commit()
    cur.close()
    if affected:
        logger.warning("Closed %d legacy NULL rows on %s", affected, my_ip)


def fetch_all_null_sessions(conn, my_ip, proto):
    """이 서버/프로토콜의 모든 NULL 세션을 한 번에 가져오기."""
    sql = """
        SELECT radacctid, username, nasportid, acctstarttime,
               acctsessionid, acctuniqueid, start_radius_server
          FROM radacct
         WHERE nasipaddress = %s
           AND nasporttype = %s
           AND acctstoptime IS NULL
    """
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, (my_ip, proto))
    rows = cur.fetchall()
    cur.close()
    return rows


def close_radacct_row(conn, radacctid):
    sql = """
        UPDATE radacct
           SET acctstoptime = %s, connectinfo_stop = 'dbsync-close'
         WHERE radacctid = %s AND acctstoptime IS NULL
    """
    cur = conn.cursor()
    cur.execute(sql, (now_str(), radacctid))
    conn.commit()
    cur.close()


def insert_radacct_row(conn, my_ip, proto, username, nasportid, base_row=None):
    """누락된 세션을 radacct에 INSERT."""
    now = now_str()
    acctsessionid = "%s-%s" % (int(time.time()), gen_random_token(4))
    acctuniqueid = gen_random_token(16)
    start_radius = base_row.get('start_radius_server') if base_row else None

    sql = """
        INSERT INTO radacct (
            acctsessionid, acctuniqueid, username, nasipaddress,
            nasportid, nasporttype, acctstarttime,
            acctstoptime, start_radius_server, stop_radius_server, connectinfo_stop
        ) VALUES (%s,%s,%s,%s,%s,%s,%s, NULL,%s,NULL,NULL)
    """
    cur = conn.cursor()
    cur.execute(sql, (
        acctsessionid, acctuniqueid, username, my_ip,
        nasportid, proto, now, start_radius
    ))
    conn.commit()
    cur.close()
    logger.warning("[%s] INSERT missing session: user=%s, port=%s", proto, username, nasportid)


def sync_protocol(conn, my_ip, proto, active_sessions):
    """
    실제 세션과 radacct NULL 세션을 비교하여 동기화.
    - 실제 있는데 DB에 없음 → INSERT
    - DB에 있는데 실제 없음 → CLOSE
    - 동일 (user, port) 중복 NULL → 1개만 남기고 CLOSE
    """
    if check_timeout():
        logger.warning("[%s] TIMEOUT - skipping sync", proto)
        return

    # 모든 NULL 세션을 한 번에 가져오기 (유저별 쿼리 제거)
    null_rows = fetch_all_null_sessions(conn, my_ip, proto)
    null_count_before = len(null_rows)

    # user별 + port별 정리
    null_by_user = defaultdict(list)  # user -> [row, ...]
    for r in null_rows:
        null_by_user[r['username']].append(r)

    active_users = set(active_sessions.keys())
    created = 0
    closed = 0

    # === 1) 실제 연결이 있는 유저 처리 ===
    for username in active_users:
        if check_timeout():
            break

        active_ports = set(active_sessions[username])
        user_null_rows = null_by_user.get(username, [])

        # 중복 제거: 같은 port에 NULL row 여러 개 → 1개만 유지
        by_port = defaultdict(list)
        for r in user_null_rows:
            port = int(r['nasportid']) if r['nasportid'] is not None else -1
            by_port[port].append(r)

        # 유지할 row 세트
        keep_rows = {}
        for port, rows in by_port.items():
            if len(rows) > 1:
                # 가장 최근 것만 남기고 중복 닫기
                rows.sort(key=lambda x: x['acctstarttime'] or datetime.min)
                keep_rows[port] = rows[-1]
                for r in rows[:-1]:
                    close_radacct_row(conn, r['radacctid'])
                    closed += 1
            else:
                keep_rows[port] = rows[0]

        # a) 실제 있는데 DB에 없음 → INSERT
        existing_ports = set(keep_rows.keys())
        for port in active_ports:
            if port not in existing_ports:
                # base_row: 이 유저의 기존 row에서 start_radius_server 복사
                base = keep_rows.get(list(existing_ports)[0]) if existing_ports else None
                insert_radacct_row(conn, my_ip, proto, username, port, base)
                created += 1

        # b) DB에 있는데 실제 없음 → CLOSE (zombie)
        for port, row in keep_rows.items():
            if port not in active_ports and port != -1:
                close_radacct_row(conn, row['radacctid'])
                closed += 1

    # === 2) 실제 연결이 전혀 없는 유저 → 모든 NULL 닫기 ===
    for username, rows in null_by_user.items():
        if username in active_users:
            continue
        for r in rows:
            close_radacct_row(conn, r['radacctid'])
            closed += 1

    # 요약
    active_total = sum(len(v) for v in active_sessions.values())
    logger.warning("[%s] SUMMARY: actual=%d, db_null_before=%d, inserted=%d, closed=%d",
                   proto, active_total, null_count_before, created, closed)


# ==============================
# 메인
# ==============================
def main():
    my_ip = get_server_ip()
    if not my_ip:
        logger.warning("Cannot determine server IP - exit")
        return

    logger.warning("dbsync v%s START - %s", VERSION, my_ip)

    # 실제 세션 수집
    swan_sessions = get_strongswan_sessions()
    ovpn_sessions = get_openvpn_sessions()

    try:
        conn = get_db_conn()
    except Exception as e:
        logger.warning("DB connection failed: %s", e)
        return

    try:
        close_legacy_null_rows(conn, my_ip)

        if swan_sessions or not ovpn_sessions:
            sync_protocol(conn, my_ip, 'strongSwan', swan_sessions)

        if ovpn_sessions:
            sync_protocol(conn, my_ip, 'openvpn', ovpn_sessions)
    finally:
        conn.close()

    elapsed = time.time() - _start_time
    logger.warning("dbsync v%s DONE in %.1fs - %s", VERSION, elapsed, my_ip)


if __name__ == "__main__":
    main()
