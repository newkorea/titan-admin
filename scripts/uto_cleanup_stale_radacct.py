#!/usr/bin/env python3
"""
UTO vcsvpn2013.radacct 세션 관리 시스템
- [실시간] SSH로 strongSwan/openvpn 서버의 실제 세션과 radacct 비교 → 좀비 즉시 정리
- [실시간] ROS 서버: MikroTik API로 실제 활성 세션 조회 후 동기화
- [강제해제] 만료/세션초과 유저 강제 킥 (모든 프로토콜):
  - ROS (W/WS/O): MikroTik API /ppp/active/remove
  - strongSwan: SSH → strongswan stroke down-nb
  - openvpn/INDIA1: SSH → telnet 127.0.0.1:1199 → kill
  - v2ray: radacct만 종료 (xray 실시간 킥 불가)
- [정리] 시간 기준 stale 정리 (24h+ openvpn/v2ray, 48h+ strongSwan)
- 크론: 5분마다 실행 (*/5 * * * *)
- 로그: /home/newkorea/project/scripts/uto_stale_radacct.log

실행 순서:
  1. ROS 동기화 (MikroTik API → stale 종료 + 누락 복구)
  2. SSH 실시간 동기화 (strongSwan/openvpn → 좀비 즉시 종료)
  3. 만료/세션초과 유저 킥 (모든 프로토콜)
  4. 시간 기준 stale 정리 (SSH에서 못 잡은 나머지)

변경 이력:
  2026-03-03: 최초 생성. V2RAY nasipaddress 버그 대응 + 일반 stale 정리
  2026-03-03: ROS 세션을 MikroTik API로 실제 확인 후 동기화하도록 변경.
  2026-03-03: ROS 만료 유저 킥 + 세션 초과 킥 기능 추가.
  2026-03-03: 모든 프로토콜 만료/세션초과 킥 확장 (strongSwan SSH, openvpn telnet, v2ray radacct)
  2026-03-05: SSH 실시간 동기화 추가 — 병렬 SSH로 전 서버 실제 세션 비교, 좀비 즉시 정리
"""
import sys
import os
import logging
import argparse
import socket
import struct
import hashlib
import binascii
import uuid
import re
import time as _time_module
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Django 설정 로드
sys.path.insert(0, '/home/newkorea/project/titan-admin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()
from django.db import connections

# 로깅 설정
LOG_PATH = '/home/newkorea/project/scripts/uto_stale_radacct.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# 안전 제한: 한 번에 정리할 최대 건수
MAX_CLEANUP_PER_RUN = 50000

# SSH 접속 불가 서버 목록 (ROS 중국 서버, 내부IP, 거부 서버)
SSH_SKIP_IPS = {
    '27.115.70.46', '27.115.51.226', '58.246.240.2',  # ROS (MikroTik API로 처리)
    '10.99.0.14',                                       # 내부IP, timeout
    '218.158.57.66', '218.233.115.189', '218.233.115.190',  # SSH denied/reset
    '101.87.60.66', '180.173.120.9', '124.73.198.161',      # 중국 v2ray 서버
}

# ROS 서버 목록: (nasipaddress, nasporttype, API_IP, API_PORT, username, password)
ROS_SERVERS = [
    ('27.115.70.46',  'W ros',  '27.115.70.46',  8728, 'admin',   'vkfksgksmf'),
    ('27.115.51.226', 'WS ros', '27.115.51.226', 8728, 'admin',   'vkfksgksmf'),
    ('58.246.240.2',  'O ros',  '58.246.240.2',  8728, 'Oserver', 'vkfksgksmf'),
]


# ============================================================
# MikroTik RouterOS API 클라이언트 (최소 구현)
# ============================================================

class RouterOSError(Exception):
    pass


def _ros_encode_length(length):
    """RouterOS API 워드 길이 인코딩"""
    if length < 0x80:
        return struct.pack('!B', length)
    elif length < 0x4000:
        return struct.pack('!H', length | 0x8000)
    elif length < 0x200000:
        return struct.pack('!I', length | 0xC00000)[1:]  # 3 bytes
    elif length < 0x10000000:
        return struct.pack('!I', length | 0xE0000000)
    else:
        return b'\xF0' + struct.pack('!I', length)


def _ros_decode_length(sock):
    """RouterOS API 워드 길이 디코딩"""
    b = sock.recv(1)
    if not b:
        raise RouterOSError("Connection closed")
    b0 = b[0]
    if b0 < 0x80:
        return b0
    elif b0 < 0xC0:
        b1 = sock.recv(1)[0]
        return ((b0 & 0x3F) << 8) | b1
    elif b0 < 0xE0:
        rest = sock.recv(2)
        return ((b0 & 0x1F) << 16) | (rest[0] << 8) | rest[1]
    elif b0 < 0xF0:
        rest = sock.recv(3)
        return ((b0 & 0x0F) << 24) | (rest[0] << 16) | (rest[1] << 8) | rest[2]
    else:
        rest = sock.recv(4)
        return struct.unpack('!I', rest)[0]


def _ros_send_sentence(sock, words):
    """RouterOS API 문장 전송"""
    for w in words:
        encoded = w.encode('utf-8') if isinstance(w, str) else w
        sock.sendall(_ros_encode_length(len(encoded)) + encoded)
    sock.sendall(b'\x00')  # end of sentence


def _ros_read_sentence(sock):
    """RouterOS API 문장 수신"""
    words = []
    while True:
        length = _ros_decode_length(sock)
        if length == 0:
            break
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise RouterOSError("Connection closed during read")
            data += chunk
        words.append(data.decode('utf-8', errors='replace'))
    return words


def ros_connect(host, port, username, password, timeout=10):
    """MikroTik RouterOS API에 연결하고 로그인. 소켓 반환."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))

    # 새 스타일 로그인 시도 (RouterOS 6.43+)
    _ros_send_sentence(sock, ['/login', f'=name={username}', f'=password={password}'])
    resp = _ros_read_sentence(sock)

    if resp and resp[0] == '!done':
        # 챌린지가 있으면 구 스타일 로그인
        ret_dict = {}
        for w in resp[1:]:
            if w.startswith('='):
                k, v = w[1:].split('=', 1)
                ret_dict[k] = v

        if 'ret' in ret_dict:
            # 구 스타일: 챌린지 응답
            challenge = binascii.unhexlify(ret_dict['ret'])
            md = hashlib.md5()
            md.update(b'\x00')
            md.update(password.encode('utf-8'))
            md.update(challenge)
            response = '00' + md.hexdigest()

            _ros_send_sentence(sock, ['/login', f'=name={username}', f'=response={response}'])
            resp2 = _ros_read_sentence(sock)
            if not resp2 or resp2[0] != '!done':
                sock.close()
                raise RouterOSError(f"Login failed (old-style): {resp2}")
        return sock
    else:
        sock.close()
        raise RouterOSError(f"Login failed: {resp}")


def ros_get_ppp_active(sock):
    """활성 PPP 세션 목록 조회. [{name, caller-id, address, session-id, uptime}, ...]"""
    _ros_send_sentence(sock, ['/ppp/active/print'])

    sessions = []
    current = {}
    while True:
        resp = _ros_read_sentence(sock)
        if not resp:
            break
        if resp[0] == '!re':
            current = {}
            for w in resp[1:]:
                if w.startswith('='):
                    k, v = w[1:].split('=', 1)
                    current[k] = v
            sessions.append(current)
        elif resp[0] == '!done':
            break
        elif resp[0] == '!trap':
            log.warning(f"ROS trap: {resp}")
            break

    return sessions


def ros_remove_session(sock, session_id):
    """ROS에서 PPP 활성 세션을 강제 해제. session_id는 .id 값 (예: *8016C8FA)"""
    _ros_send_sentence(sock, ['/ppp/active/remove', f'=.id={session_id}'])
    resp = _ros_read_sentence(sock)
    if resp and resp[0] == '!done':
        return True
    else:
        log.warning(f"  ROS remove 실패 (.id={session_id}): {resp}")
        return False


def ros_close(sock):
    """ROS 연결 종료"""
    try:
        _ros_send_sentence(sock, ['/quit'])
        sock.close()
    except Exception:
        try:
            sock.close()
        except Exception:
            pass


# ============================================================
# ROS 세션 동기화
# ============================================================

def sync_ros_sessions(dry_run=False):
    """
    각 ROS 서버에 MikroTik API로 연결하여:
    1. radacct NULL에 있지만 ROS에 없는 세션 → 종료 (stale)
    2. ROS에 있지만 radacct NULL에 없는 세션 → INSERT (누락 복구)
    """
    cur = connections['uto'].cursor()
    total_closed = 0
    total_restored = 0

    for nas_ip, port_type, api_host, api_port, api_user, api_pass in ROS_SERVERS:
        log.info(f"--- {port_type} ({nas_ip}) 동기화 시작 ---")

        # 1. ROS API 연결
        try:
            sock = ros_connect(api_host, api_port, api_user, api_pass, timeout=10)
        except Exception as e:
            log.warning(f"  {port_type} API 연결 실패: {e} — 건너뜀")
            continue

        try:
            # 2. ROS 활성 PPP 세션 가져오기
            ros_sessions = ros_get_ppp_active(sock)
            ros_users = {}  # username -> session info
            for s in ros_sessions:
                name = s.get('name', '')
                if name:
                    # 같은 유저가 여러 세션 가질 수 있음 (최신만 유지)
                    ros_users[name] = s
            log.info(f"  ROS 활성 세션: {len(ros_sessions)} (유저: {len(ros_users)})")

        finally:
            ros_close(sock)

        # 3. radacct NULL 세션 가져오기
        cur.execute('''
            SELECT radacctid, username, acctstarttime, acctsessionid, framedipaddress
            FROM radacct
            WHERE acctstoptime IS NULL AND nasipaddress = %s
        ''', [nas_ip])
        radacct_rows = cur.fetchall()
        radacct_users = {}  # username -> (radacctid, starttime, sessionid, framedip)
        for row in radacct_rows:
            radacct_users[row[1]] = {
                'radacctid': row[0],
                'starttime': row[2],
                'sessionid': row[3],
                'framedip': row[4],
            }
        log.info(f"  radacct NULL 세션: {len(radacct_rows)}")

        ros_set = set(ros_users.keys())
        rad_set = set(radacct_users.keys())

        stale = rad_set - ros_set      # radacct에 있지만 ROS에 없음 → stale
        missing = ros_set - rad_set    # ROS에 있지만 radacct에 없음 → 복구
        matched = rad_set & ros_set    # 양쪽 다 있음 → 정상

        log.info(f"  정상={len(matched)}, stale={len(stale)}, 누락={len(missing)}")

        # 4. Stale 세션 종료
        if stale:
            stale_list = sorted(stale)
            log.info(f"  종료 대상: {', '.join(stale_list[:10])}{'...' if len(stale_list)>10 else ''}")

            if not dry_run:
                stale_ids = [radacct_users[u]['radacctid'] for u in stale_list]
                # 배치로 처리
                placeholders = ','.join(['%s'] * len(stale_ids))
                cur.execute(f'''
                    UPDATE radacct
                    SET acctstoptime = NOW(),
                        acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW())),
                        acctterminatecause = 'ROS-Sync-Close'
                    WHERE radacctid IN ({placeholders})
                ''', stale_ids)
                total_closed += cur.rowcount
                log.info(f"  → {cur.rowcount}건 종료 처리")
            else:
                log.info(f"  → DRY-RUN: {len(stale)}건 종료 예정")

        # 5. 누락 세션 복구 (INSERT)
        if missing:
            missing_list = sorted(missing)
            log.info(f"  복구 대상: {', '.join(missing_list[:10])}{'...' if len(missing_list)>10 else ''}")

            if not dry_run:
                restored_count = 0
                for uname in missing_list:
                    s = ros_users[uname]
                    session_id = s.get('session-id', '')
                    caller_id = s.get('caller-id', '')
                    address = s.get('address', '')
                    uptime_str = s.get('uptime', '0s')

                    # uptime 파싱 → acctstarttime 계산
                    start_time = _parse_ros_uptime_to_starttime(uptime_str)

                    # acctuniqueid: 고유값 생성
                    unique_id = uuid.uuid4().hex[:16]

                    try:
                        cur.execute('''
                            INSERT INTO radacct 
                            (acctsessionid, acctuniqueid, username, nasipaddress,
                             nasporttype, acctstarttime, calledstationid,
                             callingstationid, servicetype, framedprotocol,
                             framedipaddress, acctauthentic,
                             groupname, acctterminatecause)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 
                                    'Framed-User', 'PPP', %s, 'RADIUS', '', '')
                        ''', [session_id, unique_id, uname, nas_ip,
                              port_type, start_time, nas_ip,
                              caller_id, address])
                        restored_count += 1
                    except Exception as e:
                        log.error(f"  INSERT 실패 ({uname}): {e}")
                total_restored += restored_count
                log.info(f"  → {restored_count}건 복구 완료")
            else:
                log.info(f"  → DRY-RUN: {len(missing)}건 복구 예정")

    cur.close()
    return {'ros_closed': total_closed, 'ros_restored': total_restored}



def _parse_ros_uptime_to_starttime(uptime_str):
    """
    ROS uptime 문자열 (예: '12w3d5h30m10s') → acctstarttime (datetime) 계산.
    NOW() - uptime = 세션 시작 시각
    """
    import re
    total_seconds = 0
    parts = re.findall(r'(\d+)([wdhms])', uptime_str)
    for val, unit in parts:
        val = int(val)
        if unit == 'w':
            total_seconds += val * 7 * 86400
        elif unit == 'd':
            total_seconds += val * 86400
        elif unit == 'h':
            total_seconds += val * 3600
        elif unit == 'm':
            total_seconds += val * 60
        elif unit == 's':
            total_seconds += val

    from datetime import timedelta
    start = datetime.now() - timedelta(seconds=total_seconds)
    return start.strftime('%Y-%m-%d %H:%M:%S')


# ============================================================
# SSH를 사용한 실시간 세션 동기화 (strongSwan, openvpn)
# ============================================================

def _get_strongswan_users(ssh):
    """SSH로 strongSwan 실제 ESTABLISHED 유저 목록 추출.
    Returns: set of usernames currently connected.
    """
    try:
        _, stdout, _ = ssh.exec_command(
            'strongswan statusall 2>/dev/null | grep ESTABLISHED',
            timeout=10
        )
        output = stdout.read().decode('utf-8', 'replace')
        users = set()
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            # Format: ikev2-vpn[7]: ESTABLISHED ...server_ip[CN=VPN]...remote_ip[username]
            matches = re.findall(r'\[([^\[\]]+)\]', line)
            if len(matches) >= 2:
                username = matches[-1]  # Last bracket = remote identity = username
                if not username.startswith('CN=') and not username.startswith('C='):
                    users.add(username)
        return users
    except Exception as e:
        log.warning(f"  strongSwan 유저 조회 실패: {e}")
        return set()


def _get_openvpn_users(ssh):
    """SSH로 openvpn management interface에서 실제 연결 유저 목록 추출.
    Returns: set of usernames currently connected.
    """
    try:
        channel = ssh.invoke_shell()
        channel.settimeout(5)
        channel.send('telnet 127.0.0.1 1199\n')
        _time_module.sleep(0.5)
        channel.send('mykakao9898\n')
        _time_module.sleep(0.3)
        channel.send('status\n')
        _time_module.sleep(0.5)
        output = channel.recv(65535).decode('utf-8', 'replace')
        channel.send('exit\n')
        _time_module.sleep(0.2)
        channel.close()

        users = set()
        in_client_list = False
        for line in output.split('\n'):
            line = line.strip()
            if 'CLIENT LIST' in line or 'Common Name' in line:
                in_client_list = True
                continue
            if 'ROUTING TABLE' in line or line.startswith('Virtual'):
                in_client_list = False
                continue
            if in_client_list and ',' in line:
                username = line.split(',')[0].strip()
                if username and username != 'UNDEF' and username != 'Common Name':
                    users.add(username)
        return users
    except Exception as e:
        log.warning(f"  openvpn 유저 조회 실패: {e}")
        return set()


def _ssh_check_server(nas_ip):
    """단일 서버 SSH 접속 → strongSwan/openvpn 실제 유저 목록 반환.
    Returns: (nas_ip, swan_users: set|None, ovpn_users: set|None)
    """
    if nas_ip in SSH_SKIP_IPS:
        return nas_ip, None, None
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(nas_ip, username='root', timeout=5, banner_timeout=5,
                    auth_timeout=5, allow_agent=True, look_for_keys=True)
        swan_users = _get_strongswan_users(ssh)
        ovpn_users = _get_openvpn_users(ssh)
        ssh.close()
        return nas_ip, swan_users, ovpn_users
    except Exception as e:
        log.warning(f"  SSH 접속 실패 {nas_ip}: {e}")
        return nas_ip, None, None


def sync_ssh_sessions(dry_run=False):
    """
    strongSwan/openvpn/INDIA1 세션 중복 정리.

    모든 유저 공통: radacct 열린 세션 수가 허용(vpnuser.session)을 초과하면
    최신 세션만 sess_limit개 남기고 나머지(오래된 것)를 Preempted-Duplicate로 종료.
    초과하지 않으면 아무 조치도 하지 않음 (SSH stale 비교 안 함).

    * strongSwan은 클라이언트가 IP identity(192.168.x.x)로 연결하는 경우가 많아
      SSH username 비교가 불가능 → SSH stale 체크를 제거하고 초과분만 정리.
    """
    cur = connections['uto'].cursor()

    # radacct에서 열린 strongSwan/openvpn/INDIA1 세션 조회 (vpnuser.session 포함)
    cur.execute('''
        SELECT r.nasipaddress, r.nasporttype, r.radacctid, r.username, r.acctstarttime,
               COALESCE(v.session, 1) as sess_limit
        FROM radacct r
        LEFT JOIN vpnuser v ON r.username = v.vuser
        WHERE r.acctstoptime IS NULL
          AND r.nasporttype IN ('strongSwan', 'openvpn', 'INDIA1')
    ''')
    rows = cur.fetchall()

    # 유저별로 열린 세션 그룹핑
    user_open = {}  # username -> [(radacctid, nasip, ptype, starttime, sess_limit)]
    for ip, ptype, rid, uname, starttime, sess_limit in rows:
        if uname not in user_open:
            user_open[uname] = []
        user_open[uname].append((rid, ip, ptype, starttime, sess_limit))

    # 초과 세션 정리: 열린 수 > sess_limit 이면 최신 sess_limit개만 남기고 나머지 닫기
    dup_close_ids = []
    for uname, sessions in user_open.items():
        sess_limit = sessions[0][4]
        if len(sessions) > sess_limit:
            sessions.sort(key=lambda x: x[3] or datetime.min, reverse=True)  # newest first
            excess = sessions[sess_limit:]  # sess_limit개 초과분
            for rid, ip, ptype, st, _ in excess:
                dup_close_ids.append(rid)
                log.info(f"  초과정리: {uname} (limit={sess_limit}) @ {ip} [{ptype}] start={st} (radacctid={rid})")

    total_dup_closed = 0
    if dup_close_ids:
        if not dry_run:
            placeholders = ','.join(['%s'] * len(dup_close_ids))
            cur.execute(f'''
                UPDATE radacct
                SET acctstoptime = NOW(),
                    acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW())),
                    acctterminatecause = 'Preempted-Duplicate'
                WHERE radacctid IN ({placeholders}) AND acctstoptime IS NULL
            ''', dup_close_ids)
            total_dup_closed = cur.rowcount
            log.info(f"초과 세션 정리: {total_dup_closed}건 종료")
        else:
            log.info(f"DRY-RUN: 초과 세션 {len(dup_close_ids)}건 종료 예정")
    else:
        log.info("초과 세션 없음")

    cur.close()
    return {
        'dup_closed': total_dup_closed,
    }


# ============================================================
# SSH를 사용한 VPN 세션 킥 (strongSwan, openvpn)
# ============================================================

def _ssh_connect(host, timeout=5):
    """SSH 키 인증으로 연결. 실패 시 None 반환."""
    import paramiko
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username='root', timeout=timeout, banner_timeout=timeout,
                    auth_timeout=timeout, allow_agent=True, look_for_keys=True)
        return ssh
    except Exception as e:
        log.warning(f"  SSH 연결 실패 {host}: {e}")
        return None


def _ssh_kick_strongswan(ssh, host, username):
    """
    strongSwan SA 강제 해제.
    1) strongswan statusall | grep username → SA 이름 추출 (예: ikev2-vpn[7])
    2) strongswan stroke down-nb <SA>
    반환: True(성공) / False(실패/세션없음)
    """
    import time as _time
    try:
        cmd = f'strongswan statusall | grep "\\[{username}\\]"'
        _stdin, _stdout, _stderr = ssh.exec_command(cmd, timeout=5)
        lines = _stdout.read().decode('utf-8', 'replace').strip().split('\n')
        kicked = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 형식: "   ikev2-vpn[7]: ESTABLISHED ..."
            sa = line.split(':')[0].strip()
            if sa and '[' in sa:
                down_cmd = f'strongswan stroke down-nb {sa}'
                ssh.exec_command(down_cmd, timeout=5)
                _time.sleep(0.15)
                # 재시도 (안전)
                ssh.exec_command(down_cmd, timeout=5)
                kicked = True
                log.info(f"  ★ strongSwan 킥: {username} @ {host} (SA={sa})")
        return kicked
    except Exception as e:
        log.warning(f"  strongSwan 킥 실패 {username} @ {host}: {e}")
        return False


def _ssh_kick_openvpn(ssh, host, username):
    """
    openvpn 관리 인터페이스(telnet 127.0.0.1:1199)로 유저 킥.
    비밀번호: mykakao9898
    명령: kill <username>
    """
    import time as _time
    try:
        channel = ssh.invoke_shell()
        channel.settimeout(5)
        channel.send("telnet 127.0.0.1 1199\n")
        _time.sleep(0.5)
        channel.send("mykakao9898\n")
        _time.sleep(0.3)
        channel.send(f"kill {username}\n")
        _time.sleep(0.3)
        channel.send("exit\n")
        _time.sleep(0.2)
        channel.send("exit\n")
        _time.sleep(0.2)
        try:
            output = channel.recv(65535).decode('utf-8', 'replace')
        except Exception:
            output = ''
        channel.close()
        success = 'SUCCESS' in output or 'kill' in output.lower()
        log.info(f"  ★ openvpn 킥: {username} @ {host} (output={'OK' if success else 'sent'})")
        return True
    except Exception as e:
        log.warning(f"  openvpn 킥 실패 {username} @ {host}: {e}")
        return False


# ============================================================
# 모든 프로토콜 만료/세션초과 유저 강제 해제
# ============================================================

def enforce_all_sessions(dry_run=False):
    """
    모든 프로토콜에 대해 만료/세션초과 유저를 킥.
    - ROS (W/WS/O): MikroTik API
    - strongSwan: SSH → strongswan stroke down-nb
    - openvpn/INDIA1: SSH → telnet openvpn mgmt → kill
    - v2ray: radacct만 종료 (xray 실시간 킥 불가)
    """
    import paramiko
    cur = connections['uto'].cursor()
    total_expired_kicked = 0
    total_oversess_kicked = 0

    # 전체 활성 유저의 세션 제한/만료일 조회
    cur.execute('''
        SELECT r.username, v.session as sess_limit, v.lastdate,
               r.nasipaddress, r.nasporttype, r.radacctid, r.acctstarttime,
               r.acctsessionid
        FROM radacct r
        JOIN vpnuser v ON r.username = v.vuser
        WHERE r.acctstoptime IS NULL
        ORDER BY r.username, r.acctstarttime ASC
    ''')
    rows = cur.fetchall()

    # 유저별로 그룹핑
    user_sessions = {}
    for r in rows:
        uname = r[0]
        if uname not in user_sessions:
            user_sessions[uname] = []
        user_sessions[uname].append({
            'sess_limit': r[1],
            'lastdate': r[2],
            'nasip': r[3],
            'porttype': r[4],
            'radacctid': r[5],
            'starttime': r[6],
            'sessionid': r[7],
        })

    # 킥 대상 수집
    expired_kicks = []
    oversess_kicks = []
    now = datetime.now()

    for uname, sessions in user_sessions.items():
        lastdate = sessions[0]['lastdate']
        sess_limit = sessions[0]['sess_limit']

        # 1. 만료 체크
        if lastdate and lastdate < now:
            for s in sessions:
                expired_kicks.append((uname, s['nasip'], s['radacctid'], s['porttype'], 'Expired'))
            continue

        # 2. 세션 초과 체크 (전체 서버 합산)
        if len(sessions) > sess_limit:
            kick_count = len(sessions) - sess_limit
            for s in sessions[:kick_count]:
                oversess_kicks.append((uname, s['nasip'], s['radacctid'], s['porttype'], 'Over-Session'))

    if expired_kicks:
        log.info(f"만료 유저 킥 대상: {len(expired_kicks)}세션 ({len(set(k[0] for k in expired_kicks))}명)")
        for uname, nasip, rid, ptype, reason in expired_kicks:
            log.info(f"  킥: {uname} @ {nasip} [{ptype}] (radacctid={rid}, {reason})")

    if oversess_kicks:
        log.info(f"세션초과 킥 대상: {len(oversess_kicks)}세션 ({len(set(k[0] for k in oversess_kicks))}명)")
        for uname, nasip, rid, ptype, reason in oversess_kicks:
            log.info(f"  킥: {uname} @ {nasip} [{ptype}] (radacctid={rid}, {reason})")

    all_kicks = expired_kicks + oversess_kicks
    if not all_kicks:
        log.info("만료/세션초과 킥 대상 없음")
        cur.close()
        return {'expired_kicked': 0, 'oversess_kicked': 0}

    if dry_run:
        log.info(f"DRY-RUN: 만료 {len(expired_kicks)}건 + 세션초과 {len(oversess_kicks)}건 킥 예정")
        cur.close()
        return {'expired_kicked': 0, 'oversess_kicked': 0, 'dry_run': True}

    # ---- 실제 킥 실행 ----

    # ROS 서버 소켓 준비 (한번만)
    ros_socks = {}
    for nas_ip, port_type, api_host, api_port, api_user, api_pass in ROS_SERVERS:
        try:
            sock = ros_connect(api_host, api_port, api_user, api_pass, timeout=10)
            ros_active = ros_get_ppp_active(sock)
            ros_socks[nas_ip] = {
                'sock': sock,
                'sessions': ros_active,
                'name_to_ids': {},
            }
            for s in ros_active:
                name = s.get('name', '')
                if name:
                    if name not in ros_socks[nas_ip]['name_to_ids']:
                        ros_socks[nas_ip]['name_to_ids'][name] = []
                    ros_socks[nas_ip]['name_to_ids'][name].append(s.get('.id', ''))
        except Exception as e:
            log.warning(f"  ROS {port_type} 연결 실패: {e}")

    # SSH 연결 캐시 (NAS IP별 한번만 연결)
    ssh_conns = {}  # nasip -> paramiko.SSHClient or None

    ROS_IPS = set(s[0] for s in ROS_SERVERS)

    for uname, nasip, radacctid, porttype, reason in all_kicks:
        try:
            kicked_vpn = False

            if nasip in ROS_IPS:
                # --- ROS: MikroTik API ---
                if nasip in ros_socks:
                    name_ids = ros_socks[nasip]['name_to_ids'].get(uname, [])
                    if name_ids:
                        kick_id = name_ids.pop(0)
                        ok = ros_remove_session(ros_socks[nasip]['sock'], kick_id)
                        if ok:
                            log.info(f"  ★ ROS 킥: {uname} @ {nasip} (.id={kick_id}, {reason})")
                            kicked_vpn = True
                        else:
                            log.warning(f"  ROS 킥 실패: {uname} @ {nasip} (.id={kick_id})")
                    else:
                        log.info(f"  {uname} @ {nasip}: ROS에 세션 없음 (이미 해제)")
                else:
                    log.warning(f"  {uname} @ {nasip}: ROS 연결 없음")

            elif porttype == 'strongSwan':
                # --- strongSwan: SSH ---
                if nasip not in ssh_conns:
                    ssh_conns[nasip] = _ssh_connect(nasip, timeout=5)
                ssh = ssh_conns[nasip]
                if ssh:
                    kicked_vpn = _ssh_kick_strongswan(ssh, nasip, uname)
                else:
                    log.warning(f"  {uname} @ {nasip}: SSH 불가, radacct만 종료")

            elif porttype in ('openvpn', 'INDIA1'):
                # --- openvpn: SSH + telnet mgmt ---
                if nasip not in ssh_conns:
                    ssh_conns[nasip] = _ssh_connect(nasip, timeout=5)
                ssh = ssh_conns[nasip]
                if ssh:
                    kicked_vpn = _ssh_kick_openvpn(ssh, nasip, uname)
                else:
                    log.warning(f"  {uname} @ {nasip}: SSH 불가, radacct만 종료")

            elif porttype and 'v2ray' in porttype.lower():
                # --- v2ray: radacct만 종료 (실시간 킥 불가) ---
                log.info(f"  v2ray 세션 종료 (radacct only): {uname} @ {nasip} ({reason})")

            else:
                log.info(f"  알 수 없는 프로토콜 [{porttype}]: {uname} @ {nasip}, radacct만 종료")

            # radacct 종료 처리
            cur.execute('''
                UPDATE radacct
                SET acctstoptime = NOW(),
                    acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW())),
                    acctterminatecause = %s
                WHERE radacctid = %s AND acctstoptime IS NULL
            ''', [f'Admin-Kick-{reason}', radacctid])

            if reason == 'Expired':
                total_expired_kicked += 1
            else:
                total_oversess_kicked += 1

        except Exception as e:
            log.error(f"  킥 처리 실패: {uname} @ {nasip} [{porttype}] (radacctid={radacctid}): {e}")
            continue

    # 소켓/SSH 정리
    for nasip, info in ros_socks.items():
        try:
            ros_close(info['sock'])
        except Exception:
            pass
    for nasip, ssh in ssh_conns.items():
        try:
            if ssh:
                ssh.close()
        except Exception:
            pass

    log.info(f"킥 완료: 만료={total_expired_kicked}, 세션초과={total_oversess_kicked}")
    cur.close()
    return {'expired_kicked': total_expired_kicked, 'oversess_kicked': total_oversess_kicked}


# ============================================================
# 일반 stale 세션 정리 (V2RAY, openvpn, strongSwan 등)
# ============================================================

def cleanup_stale_sessions(dry_run=False, hours=24):
    """24시간 이상 경과한 NULL 세션 정리 (ROS 제외 — ROS는 sync_ros_sessions에서 처리)"""
    cur = connections['uto'].cursor()

    # 현황 파악
    cur.execute('SELECT COUNT(*) FROM radacct WHERE acctstoptime IS NULL')
    total_null = cur.fetchone()[0]

    # ROS를 제외한 stale 건수
    cur.execute('''
        SELECT COUNT(*) FROM radacct 
        WHERE acctstoptime IS NULL 
          AND acctstarttime < DATE_SUB(NOW(), INTERVAL %s HOUR)
          AND nasporttype NOT IN ('W ros', 'WS ros', 'O ros')
    ''', [hours])
    stale_count = cur.fetchone()[0]

    log.info(f"현황: 전체 NULL={total_null}, {hours}h+ stale(ROS제외)={stale_count}")

    if dry_run:
        # 프로토콜별 분포만 보여주기
        cur.execute('''
            SELECT nasporttype, COUNT(*) FROM radacct 
            WHERE acctstoptime IS NULL 
              AND acctstarttime < DATE_SUB(NOW(), INTERVAL %s HOUR)
            GROUP BY nasporttype ORDER BY COUNT(*) DESC
        ''', [hours])
        log.info("=== DRY-RUN: 정리 대상 프로토콜별 분포 ===")
        for r in cur.fetchall():
            log.info(f"  {r[0]:15s} {r[1]:6d}건")
        cur.close()
        return {'total_null': total_null, 'stale': stale_count, 'cleaned': 0, 'dry_run': True}

    # 실제 정리 실행
    # 1. V2RAY stale (가장 많음)
    cur.execute('''
        UPDATE radacct 
        SET acctstoptime = NOW(),
            acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW()))
        WHERE acctstoptime IS NULL 
          AND LOWER(nasporttype) = 'v2ray'
          AND acctstarttime < DATE_SUB(NOW(), INTERVAL %s HOUR)
        LIMIT %s
    ''', [hours, MAX_CLEANUP_PER_RUN])
    v2ray_cleaned = cur.rowcount
    log.info(f"V2RAY stale 정리: {v2ray_cleaned}건")

    # 2. openvpn / INDIA stale
    cur.execute('''
        UPDATE radacct 
        SET acctstoptime = NOW(),
            acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW()))
        WHERE acctstoptime IS NULL 
          AND nasporttype IN ('openvpn', 'INDIA1')
          AND acctstarttime < DATE_SUB(NOW(), INTERVAL %s HOUR)
        LIMIT %s
    ''', [hours, MAX_CLEANUP_PER_RUN])
    other_cleaned = cur.rowcount
    log.info(f"openvpn/INDIA stale 정리: {other_cleaned}건")

    # 3. strongSwan은 48시간 기준으로 (실제 활성 세션 보호)
    cur.execute('''
        UPDATE radacct 
        SET acctstoptime = NOW(),
            acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW()))
        WHERE acctstoptime IS NULL 
          AND nasporttype = 'strongSwan'
          AND acctstarttime < DATE_SUB(NOW(), INTERVAL 48 HOUR)
        LIMIT %s
    ''', [MAX_CLEANUP_PER_RUN])
    ss_cleaned = cur.rowcount
    log.info(f"strongSwan 48h+ stale 정리: {ss_cleaned}건")

    total_cleaned = v2ray_cleaned + other_cleaned + ss_cleaned

    # 정리 후 현황
    cur.execute('SELECT COUNT(*) FROM radacct WHERE acctstoptime IS NULL')
    after_null = cur.fetchone()[0]
    log.info(f"정리 완료: {total_cleaned}건 정리, 남은 NULL={after_null}")

    cur.close()
    return {
        'total_null': total_null,
        'stale': stale_count,
        'cleaned': total_cleaned,
        'after_null': after_null,
        'v2ray': v2ray_cleaned,
        'other': other_cleaned,
        'strongswan': ss_cleaned,
    }


def main():
    parser = argparse.ArgumentParser(description='UTO vcsvpn2013.radacct stale NULL 세션 정리')
    parser.add_argument('--dry-run', action='store_true', help='실제 정리하지 않고 현황만 보기')
    parser.add_argument('--hours', type=int, default=24, help='stale 기준 시간 (기본: 24)')
    parser.add_argument('--skip-ros', action='store_true', help='ROS 동기화 건너뛰기')
    parser.add_argument('--skip-ssh', action='store_true', help='SSH 실시간 동기화 건너뛰기')
    args = parser.parse_args()

    log.info(f"=== UTO radacct stale 정리 시작 (hours={args.hours}, dry_run={args.dry_run}) ===")

    try:
        # 1) ROS 세션 동기화 (MikroTik API로 실제 활성 확인)
        if not args.skip_ros:
            ros_result = sync_ros_sessions(dry_run=args.dry_run)
            log.info(f"ROS 동기화 결과: {ros_result}")
        else:
            log.info("ROS 동기화 건너뜀 (--skip-ros)")

        # 2) SSH 실시간 동기화 (strongSwan/openvpn 서버 실제 비교)
        if not args.skip_ssh:
            ssh_result = sync_ssh_sessions(dry_run=args.dry_run)
            log.info(f"SSH 동기화 결과: {ssh_result}")
        else:
            log.info("SSH 동기화 건너뜀 (--skip-ssh)")

        # 3) 만료/세션초과 유저 킥 (모든 프로토콜)
        kick_result = enforce_all_sessions(dry_run=args.dry_run)
        log.info(f"킥 결과: {kick_result}")

        # 4) 일반 stale 정리 — 시간 기준 (SSH sync에서 못 잡은 나머지)
        result = cleanup_stale_sessions(dry_run=args.dry_run, hours=args.hours)
        log.info(f"일반 정리 결과: {result}")
    except Exception as e:
        log.error(f"오류 발생: {e}", exc_info=True)
        sys.exit(1)

    log.info("=== 완료 ===")


if __name__ == '__main__':
    main()
