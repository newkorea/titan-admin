#!/usr/bin/env python3
"""
TitanVPN NAS 서버 VPN 서비스 점검 스크립트
- DB에서 서버 정보 및 서비스 구성 읽기
- SSH로 프로세스 상태 확인 (charon, openvpn, vpnserver, xray)
- 네트워크 레벨 포트 연결 테스트 (IKEv2/500,4500, SSTP/443, OpenVPN, V2Ray)
- IKEv2 SA_INIT 핸드셰이크 테스트
- radius 인증 테스트 (check@titanx.top)

Usage:
    python3 scripts/nas_service_check.py              # 전체 점검
    python3 scripts/nas_service_check.py --json       # JSON 출력
    python3 scripts/nas_service_check.py --server IP  # 특정 서버만
"""

import sys
import os
import re
import json
import struct
import socket
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import ssl
import paramiko
import MySQLdb

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ─── 설정 ──────────────────────────────────────────
DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'charset': 'utf8',
}
SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_ed25519')
SSH_TIMEOUT = 8
PORT_TIMEOUT = 5
MAX_WORKERS = 15

# 서비스별 기본 포트
IKEV2_PORTS = [500, 4500]
SSTP_PORT = 443
# OpenVPN 포트는 config에서 파싱
# V2Ray 포트는 DB의 v2_port


def get_servers(target_ip=None):
    """DB에서 활성 서버 목록 + 서비스 구성 가져오기"""
    db = MySQLdb.connect(**DB_CONFIG, db='titan')
    c = db.cursor(MySQLdb.cursors.DictCursor)
    sql = '''SELECT id, name, hostip, natip, hostdomain, protocol, 
                    v2_port, config, v2_config, username, password, country
             FROM tbl_agent3 WHERE is_active=1'''
    if target_ip:
        sql += f" AND hostip='{target_ip}'"
    sql += ' ORDER BY hostip'
    c.execute(sql)
    servers = c.fetchall()
    db.close()

    # OpenVPN 포트 파싱
    for s in servers:
        s['services'] = [x.strip() for x in s['protocol'].split(',') if x.strip()]
        # OpenVPN remote 파싱
        conf = s.get('config') or ''
        m = re.search(r'remote\s+(\S+)\s+(\d+)', conf)
        if m:
            s['ovpn_domain'] = m.group(1)
            s['ovpn_port'] = int(m.group(2))
        else:
            s['ovpn_domain'] = None
            s['ovpn_port'] = None

        # OpenVPN proto (tcp/udp)
        pm = re.search(r'proto\s+(tcp|udp)', conf)
        s['ovpn_proto'] = pm.group(1) if pm else 'udp'

    return servers


def get_radius_account():
    """check@titanx.top 계정 정보 가져오기"""
    db = MySQLdb.connect(**DB_CONFIG, db='radius')
    c = db.cursor()
    c.execute("SELECT attribute, value FROM radcheck WHERE username='check@titanx.top'")
    info = {}
    for attr, val in c.fetchall():
        info[attr] = val
    db.close()
    return info


def resolve_host(hostname):
    """호스트네임 → IP 해석"""
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return None


def check_tcp_port(host, port, timeout=PORT_TIMEOUT):
    """TCP 포트 연결 확인"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_udp_port(host, port, timeout=PORT_TIMEOUT):
    """UDP 포트 응답 확인 (빈 패킷 전송 후 ICMP unreachable 확인용)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(b'\x00', (host, port))
        try:
            sock.recvfrom(1024)
            sock.close()
            return True  # 응답 있음
        except socket.timeout:
            sock.close()
            return True  # timeout = 포트 열림 (UDP는 응답 없을 수 있음)
        except ConnectionRefusedError:
            sock.close()
            return False  # ICMP unreachable = 닫힘
    except Exception:
        return False


def check_ikev2_handshake(host, timeout=PORT_TIMEOUT):
    """IKE_SA_INIT 요청을 보내고 응답 확인 (실제 IKEv2 핸드셰이크 테스트)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # IKEv2 IKE_SA_INIT 패킷 구성 (최소)
        # IKE Header: 28 bytes
        spi_i = os.urandom(8)  # Initiator SPI
        spi_r = b'\x00' * 8    # Responder SPI (0 for SA_INIT)
        next_payload = 33       # SA payload
        version = 0x20          # IKEv2
        exchange_type = 34      # IKE_SA_INIT
        flags = 0x08            # Initiator flag
        msg_id = 0
        
        # SA Payload (simplified - just propose AES-CBC + SHA256 + DH14)
        # Proposal: ESP, AES-CBC-256, SHA2-256, DH group 14
        sa_payload = bytes([
            # SA payload header
            0x22,  # next payload = KE
            0x00,  # critical = 0
            0x00, 0x2c,  # length = 44
            # Proposal
            0x00,  # last proposal
            0x00,  # reserved
            0x00, 0x28,  # proposal length = 40
            0x01,  # proposal number
            0x01,  # protocol = IKE
            0x00,  # SPI size = 0
            0x04,  # num transforms = 4
            # Transform 1: ENCR_AES_CBC
            0x03, 0x00, 0x00, 0x0c,
            0x01, 0x00, 0x00, 0x0c,  # type=ENCR, id=AES_CBC
            0x80, 0x0e, 0x01, 0x00,  # key length 256
            # Transform 2: PRF_HMAC_SHA2_256
            0x03, 0x00, 0x00, 0x08,
            0x02, 0x00, 0x00, 0x05,  # type=PRF, id=SHA2_256
            # Transform 3: AUTH_HMAC_SHA2_256_128
            0x03, 0x00, 0x00, 0x08,
            0x03, 0x00, 0x00, 0x0c,  # type=INTEG, id=SHA2_256_128
            # Transform 4: DH Group 14
            0x00, 0x00, 0x00, 0x08,
            0x04, 0x00, 0x00, 0x0e,  # type=DH, id=14
        ])

        # KE payload (DH Group 14 - fake key data)
        ke_data = os.urandom(256)  # 256 bytes DH public value
        ke_payload = bytes([
            0x28,  # next payload = Nonce
            0x00,  # critical = 0
        ]) + struct.pack('!H', 4 + 4 + len(ke_data)) + struct.pack('!HH', 14, 0) + ke_data

        # Nonce payload
        nonce_data = os.urandom(32)
        nonce_payload = bytes([
            0x00,  # no next payload
            0x00,  # critical = 0
        ]) + struct.pack('!H', 4 + len(nonce_data)) + nonce_data

        payload = sa_payload + ke_payload + nonce_payload
        total_len = 28 + len(payload)

        # IKE Header
        header = spi_i + spi_r + bytes([
            next_payload, version, exchange_type, flags
        ]) + struct.pack('!I', msg_id) + struct.pack('!I', total_len)

        packet = header + payload

        sock.sendto(packet, (host, 500))
        data, addr = sock.recvfrom(4096)
        sock.close()

        # 응답이 28바이트 이상이면 IKE 응답
        if len(data) >= 28:
            resp_exchange = data[18]
            resp_version = data[17]
            if resp_version == 0x20 and resp_exchange == 34:
                return 'OK'
            elif len(data) > 28:
                return 'RESP'  # 응답은 있으나 형식 다름
            else:
                return 'PARTIAL'
        return 'NO_RESP'
    except socket.timeout:
        return 'TIMEOUT'
    except Exception as e:
        return f'ERR:{str(e)[:30]}'


def check_sstp_handshake(host, port=443, timeout=PORT_TIMEOUT):
    """SSTP/SoftEther TCP 443 연결 + TLS 핸드셰이크 확인"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        # TLS Client Hello 전송 (최소)
        # SoftEther는 443에서 TLS 핸들링
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        # TLS 연결 성공 = SSTP/SoftEther 동작
        cert = ssock.getpeercert(binary_form=True)
        ssock.close()
        return 'OK' if cert else 'OK_NOCERT'
    except ssl.SSLError as e:
        if 'WRONG_VERSION_NUMBER' in str(e):
            return 'NON_TLS'  # TLS는 아니지만 포트 열림
        return f'SSL_ERR'
    except ConnectionRefusedError:
        return 'REFUSED'
    except socket.timeout:
        return 'TIMEOUT'
    except Exception as e:
        return f'ERR:{str(e)[:30]}'


def check_openvpn_handshake(host, port, proto='udp', timeout=PORT_TIMEOUT):
    """OpenVPN 핸드셰이크 시도 (P_CONTROL_HARD_RESET_CLIENT_V2)"""
    try:
        if proto == 'udp':
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
        
        sock.settimeout(timeout)

        # OpenVPN P_CONTROL_HARD_RESET_CLIENT_V2 패킷
        # opcode = 7 (P_CONTROL_HARD_RESET_CLIENT_V2) << 3
        # key_id = 0
        session_id = os.urandom(8)
        # Minimal packet: opcode(1) + session_id(8) + hmac(0 for initial) + packet_id(4) + ack_len(1)
        opcode_keyid = (7 << 3) | 0  # 0x38
        packet_id = struct.pack('!I', 0)
        msg_packet_id = struct.pack('!I', 0)
        ack_len = b'\x00'

        # 실제 OpenVPN은 HMAC을 기대하지만, 서버 응답 여부만 확인
        payload = bytes([opcode_keyid]) + session_id + ack_len + msg_packet_id

        if proto == 'udp':
            sock.sendto(payload, (host, port))
        else:
            sock.send(payload)

        try:
            if proto == 'udp':
                data, addr = sock.recvfrom(4096)
            else:
                data = sock.recv(4096)
            sock.close()
            
            if data and len(data) > 2:
                resp_opcode = (data[0] >> 3) & 0x1f
                if resp_opcode == 8:  # P_CONTROL_HARD_RESET_SERVER_V2
                    return 'OK'
                return 'RESP'
            return 'EMPTY'
        except socket.timeout:
            sock.close()
            # UDP timeout은 방화벽일 수 있음
            return 'TIMEOUT'
    except ConnectionRefusedError:
        return 'REFUSED'
    except socket.timeout:
        return 'TIMEOUT'
    except Exception as e:
        return f'ERR:{str(e)[:30]}'


def check_v2ray_port(host, port, timeout=PORT_TIMEOUT):
    """V2Ray/Xray 포트 연결 확인 (HTTP 요청)"""
    if port <= 0:
        return 'N/A'
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        # HTTP GET 요청
        sock.send(b'GET / HTTP/1.1\r\nHost: ' + host.encode() + b'\r\n\r\n')
        try:
            data = sock.recv(1024)
            sock.close()
            if data:
                if b'HTTP' in data or b'Bad Request' in data or b'404' in data:
                    return 'OK'
                return 'RESP'
            return 'EMPTY'
        except socket.timeout:
            sock.close()
            return 'OK_SILENT'  # 연결 OK, 응답 없음 (websocket 대기 등)
    except ConnectionRefusedError:
        return 'REFUSED'
    except socket.timeout:
        return 'TIMEOUT'
    except Exception as e:
        return f'ERR:{str(e)[:30]}'


def ssh_check_processes(host, ssh_user='root', ssh_pass=None):
    """SSH로 접속하여 VPN 프로세스 상태 확인"""
    result = {
        'ssh': False,
        'charon': False,     # StrongSwan
        'openvpn': False,
        'vpnserver': False,  # SoftEther/SSTP
        'xray': False,       # V2Ray/Xray
        'x_ui': False,       # X-UI Panel
        'strongswan_clients': 0,
        'openvpn_clients': 0,
        'softether_clients': 0,
        'xray_clients': 0,
        'details': {}
    }
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key = None
        if os.path.exists(SSH_KEY_PATH):
            try:
                key = paramiko.Ed25519Key.from_private_key_file(SSH_KEY_PATH)
            except Exception:
                pass

        if key:
            try:
                ssh.connect(host, username=ssh_user, pkey=key, timeout=SSH_TIMEOUT)
            except Exception:
                if ssh_pass:
                    ssh.connect(host, username=ssh_user, password=ssh_pass, timeout=SSH_TIMEOUT)
                else:
                    raise
        else:
            ssh.connect(host, username=ssh_user, password=ssh_pass, timeout=SSH_TIMEOUT)

        result['ssh'] = True

        # 프로세스 체크
        cmd = """
        echo "CHARON:$(pgrep -c charon 2>/dev/null || echo 0)"
        echo "OPENVPN:$(pgrep -c openvpn 2>/dev/null || echo 0)"
        echo "VPNSERVER:$(pgrep -c vpnserver 2>/dev/null || echo 0)"
        echo "XRAY:$(pgrep -c 'xray' 2>/dev/null || echo 0)"
        echo "XUI:$(pgrep -c 'x-ui' 2>/dev/null || echo 0)"
        
        # StrongSwan 클라이언트 수 (CentOS 7: strongswan, others: ipsec)
        SWAN_OUT=$(strongswan statusall 2>/dev/null || ipsec statusall 2>/dev/null || true)
        SWAN_COUNT=$(echo "$SWAN_OUT" | grep -c 'ESTABLISHED' || echo 0)
        echo "SWAN_CLIENTS:${SWAN_COUNT}"
        
        # OpenVPN 클라이언트 수 (management interface via /dev/tcp, nc 없는 CentOS 7 호환)
        OVPN_CLIENTS=0
        for port in 1199 1198; do
            MGMT_PASS=$(cat /etc/openvpn/server/managepass.txt 2>/dev/null || echo "")
            if [ -n "$MGMT_PASS" ]; then
                RESULT=$({ sleep 0.2; echo "$MGMT_PASS"; sleep 0.2; echo "status"; sleep 0.5; echo "quit"; } | timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port; cat >&3; cat <&3" 2>/dev/null || true)
            else
                RESULT=$({ sleep 0.2; echo "status"; sleep 0.5; echo "quit"; } | timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port; cat >&3; cat <&3" 2>/dev/null || true)
            fi
            CNT=$(echo "$RESULT" | grep -c '^CLIENT_LIST' || true)
            OVPN_CLIENTS=$((OVPN_CLIENTS + CNT))
        done
        echo "OVPN_CLIENTS:${OVPN_CLIENTS}"
        
        # SoftEther 세션 수 (443 포트 ESTABLISHED 커넥션)
        SE_CLIENTS=$(ss -tnp sport = :443 2>/dev/null | grep -c ESTAB || echo 0)
        echo "SE_CLIENTS:${SE_CLIENTS}"

        # V2Ray/Xray 접속자 수 (established connections to xray ports)
        XRAY_CLIENTS=0
        for PORT in $(netstat -tlnp 2>/dev/null | grep 'xray-linux' | awk '{print $4}' | sed 's/.*://'); do
            CNT=$(ss -tnp 2>/dev/null | grep ":${PORT} " | grep -c ESTAB || true)
            XRAY_CLIENTS=$((XRAY_CLIENTS + CNT))
        done
        echo "XRAY_CLIENTS:${XRAY_CLIENTS}"

        # StrongSwan 버전
        echo "SWAN_VER:$(strongswan version 2>/dev/null | head -1 || ipsec version 2>/dev/null | head -1 || echo 'N/A')"
        
        # 443 포트 주인 확인
        echo "PORT443:$(ss -tlnp sport = :443 2>/dev/null | grep -oP 'users:\(\("\K[^"]+' | head -1 || echo 'N/A')"
        
        # V2Ray/Xray 설정 확인
        echo "XRAY_PORTS:$(netstat -tlnp 2>/dev/null | grep 'xray-linux' | awk '{print $4}' | sed 's/.*://' | tr '\n' ',' || echo 'N/A')"
        
        # OpenVPN 리스닝 포트 확인 (UDP + TCP) — CentOS 7 호환
        echo "OVPN_LISTEN:$(ss -ulnp 2>/dev/null | grep openvpn | awk '{print $4}' | sed 's/.*://' | tr '\n' ',')$(ss -tlnp 2>/dev/null | grep openvpn | awk '{print $4}' | sed 's/.*://' | tr '\n' ',')"
        """
        
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        output = stdout.read().decode()
        
        for line in output.strip().split('\n'):
            if ':' in line:
                key_name, val = line.split(':', 1)
                key_name = key_name.strip()
                val = val.strip()
                
                if key_name == 'CHARON':
                    result['charon'] = int(val) > 0 if val.isdigit() else False
                elif key_name == 'OPENVPN':
                    result['openvpn'] = int(val) > 0 if val.isdigit() else False
                elif key_name == 'VPNSERVER':
                    result['vpnserver'] = int(val) > 0 if val.isdigit() else False
                elif key_name == 'XRAY':
                    result['xray'] = int(val) > 0 if val.isdigit() else False
                elif key_name == 'XUI':
                    result['x_ui'] = int(val) > 0 if val.isdigit() else False
                elif key_name == 'SWAN_CLIENTS':
                    result['strongswan_clients'] = int(val) if val.isdigit() else 0
                elif key_name == 'OVPN_CLIENTS':
                    result['openvpn_clients'] = int(val) if val.isdigit() else 0
                elif key_name == 'SE_CLIENTS':
                    result['softether_clients'] = int(val) if val.isdigit() else 0
                elif key_name == 'XRAY_CLIENTS':
                    result['xray_clients'] = int(val) if val.isdigit() else 0
                elif key_name in ('SWAN_VER', 'PORT443', 'XRAY_PORTS', 'OVPN_LISTEN'):
                    result['details'][key_name] = val

        ssh.close()
    except Exception as e:
        result['ssh_error'] = str(e)[:50]

    return result


def check_single_server(server):
    """단일 서버의 모든 서비스 점검"""
    ip = server['hostip']
    name = server['name']
    services = server['services']
    
    report = {
        'ip': ip,
        'name': name,
        'hostdomain': server['hostdomain'],
        'country': server['country'],
        'services_config': services,
        'checks': {},
        'issues': [],
        'status': 'UNKNOWN'
    }

    # IP 해석 (도메인인 경우)
    actual_ip = ip
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        resolved = resolve_host(ip)
        if resolved:
            actual_ip = resolved
            report['resolved_ip'] = resolved
        else:
            report['issues'].append(f'DNS 해석 실패: {ip}')
            report['status'] = 'DNS_FAIL'
            return report

    # 1. SSH 프로세스 체크
    ssh_result = ssh_check_processes(actual_ip, 'root', server.get('password'))
    report['checks']['ssh'] = ssh_result

    if not ssh_result['ssh']:
        report['issues'].append(f"SSH 접속 실패: {ssh_result.get('ssh_error', 'unknown')}")

    # 2. IKEv2/StrongSwan 체크
    if 'IKEV2' in services:
        if ssh_result['charon']:
            # IKE_SA_INIT 핸드셰이크
            ike_result = check_ikev2_handshake(actual_ip)
            report['checks']['ikev2'] = {
                'process': True,
                'handshake': ike_result,
                'clients': ssh_result['strongswan_clients']
            }
            if ike_result not in ('OK', 'RESP', 'PARTIAL'):
                report['issues'].append(f'IKEv2 핸드셰이크 실패: {ike_result}')
        else:
            report['checks']['ikev2'] = {
                'process': False,
                'handshake': 'SKIP',
                'clients': 0
            }
            report['issues'].append('StrongSwan(charon) 프로세스 없음')

    # 3. SSTP/SoftEther 체크
    if 'SSTP' in services:
        if ssh_result['vpnserver']:
            sstp_result = check_sstp_handshake(actual_ip, SSTP_PORT)
            report['checks']['sstp'] = {
                'process': True,
                'port443': sstp_result,
                'port443_owner': ssh_result['details'].get('PORT443', 'N/A'),
                'clients': ssh_result['softether_clients']
            }
            if sstp_result not in ('OK', 'OK_NOCERT', 'NON_TLS'):
                report['issues'].append(f'SSTP/SoftEther 443 연결 실패: {sstp_result}')
        else:
            report['checks']['sstp'] = {
                'process': False,
                'port443': 'SKIP',
                'clients': 0
            }
            report['issues'].append('SoftEther(vpnserver) 프로세스 없음')

    # 4. OpenVPN 체크
    if 'OPENVPN' in services:
        if ssh_result['openvpn']:
            ovpn_port = server.get('ovpn_port')
            ovpn_proto = server.get('ovpn_proto', 'udp')
            ovpn_domain = server.get('ovpn_domain')
            
            if ovpn_port:
                # 도메인 해석 확인
                domain_ok = True
                if ovpn_domain:
                    resolved = resolve_host(ovpn_domain)
                    if not resolved:
                        report['issues'].append(f'OpenVPN 도메인 해석 실패: {ovpn_domain}')
                        domain_ok = False
                
                ovpn_result = check_openvpn_handshake(actual_ip, ovpn_port, ovpn_proto)
                
                # UDP TIMEOUT은 tls-auth/tls-crypt 때문에 정상일 수 있음
                # SSH에서 포트 리스닝 확인으로 보완
                ovpn_listen_ports = ssh_result['details'].get('OVPN_LISTEN', '')
                port_listening = str(ovpn_port) in ovpn_listen_ports.split(',') if ovpn_listen_ports else False
                
                # UDP TIMEOUT + 포트 리스닝 확인됨 = 정상 (tls-auth)
                if ovpn_result == 'TIMEOUT' and ovpn_proto == 'udp' and port_listening:
                    effective_status = 'OK_TLSAUTH'
                elif ovpn_result == 'TIMEOUT' and port_listening:
                    effective_status = 'OK_LISTEN'
                else:
                    effective_status = ovpn_result
                
                report['checks']['openvpn'] = {
                    'process': True,
                    'port': ovpn_port,
                    'proto': ovpn_proto,
                    'domain': ovpn_domain,
                    'domain_resolves': domain_ok,
                    'handshake': ovpn_result,
                    'port_listening': port_listening,
                    'effective_status': effective_status,
                    'clients': ssh_result['openvpn_clients']
                }
                if effective_status not in ('OK', 'RESP', 'OK_TLSAUTH', 'OK_LISTEN'):
                    if ovpn_result == 'REFUSED':
                        report['issues'].append(f'OpenVPN 포트 거부: {ovpn_port}/{ovpn_proto}')
                    elif ovpn_result == 'TIMEOUT' and not port_listening:
                        report['issues'].append(f'OpenVPN 응답없음 (포트 리스닝 미확인): {ovpn_port}/{ovpn_proto}')
            else:
                report['checks']['openvpn'] = {
                    'process': True,
                    'port': None,
                    'handshake': 'NO_CONFIG'
                }
                report['issues'].append('OpenVPN config에 포트 정보 없음')
        else:
            report['checks']['openvpn'] = {
                'process': False,
                'handshake': 'SKIP'
            }
            report['issues'].append('OpenVPN 프로세스 없음')

    # 5. V2Ray/Xray 체크
    if 'V2RAY' in services:
        v2_port = server.get('v2_port', 0)
        if ssh_result['xray']:
            if v2_port > 0:
                v2_result = check_v2ray_port(actual_ip, v2_port)
                report['checks']['v2ray'] = {
                    'process': True,
                    'port': v2_port,
                    'connection': v2_result,
                    'xray_ports': ssh_result['details'].get('XRAY_PORTS', ''),
                    'clients': ssh_result['xray_clients']
                }
                if v2_result in ('REFUSED', 'TIMEOUT'):
                    report['issues'].append(f'V2Ray 포트 {v2_port} 연결 실패: {v2_result}')
            else:
                report['checks']['v2ray'] = {
                    'process': True,
                    'port': 0,
                    'connection': 'NO_PORT_CONFIG',
                    'clients': 0
                }
        else:
            report['checks']['v2ray'] = {
                'process': False,
                'port': v2_port,
                'connection': 'SKIP'
            }
            report['issues'].append('V2Ray/Xray 프로세스 없음')

    # 종합 상태 판정
    critical_issues = [i for i in report['issues'] if '프로세스 없음' in i or 'SSH 접속 실패' in i or 'DNS 해석 실패' in i]
    warning_issues = [i for i in report['issues'] if i not in critical_issues]
    
    if not ssh_result['ssh']:
        report['status'] = 'CRITICAL'
    elif critical_issues:
        report['status'] = 'CRITICAL'
    elif warning_issues:
        report['status'] = 'WARNING'
    else:
        report['status'] = 'OK'

    return report


def print_report(results):
    """점검 결과 리포트 출력"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elapsed = time.time() - start_time

    critical = [r for r in results if r['status'] == 'CRITICAL']
    warning = [r for r in results if r['status'] == 'WARNING']
    ok = [r for r in results if r['status'] == 'OK']
    other = [r for r in results if r['status'] not in ('CRITICAL', 'WARNING', 'OK')]

    print()
    print('=' * 100)
    print(f'  TitanVPN NAS VPN 서비스 점검 리포트  |  {now}  |  {elapsed:.1f}초')
    print('=' * 100)
    print(f'  전체: {len(results)}대  |  정상: {len(ok)}  |  경고: {len(warning)}  |  위험: {len(critical)}')
    print('=' * 100)

    def print_server(r):
        ip = r['ip']
        name = r['name']
        svcs = r['services_config']
        checks = r['checks']
        
        # 서비스별 상태 요약
        svc_status = []
        
        # IKEv2
        if 'ikev2' in checks:
            ck = checks['ikev2']
            proc = '●' if ck['process'] else '✗'
            hs = ck.get('handshake', '?')
            clients = ck.get('clients', 0)
            if ck['process'] and hs in ('OK', 'RESP', 'PARTIAL'):
                svc_status.append(f'IKE:{proc}✓({clients})')
            elif ck['process']:
                svc_status.append(f'IKE:{proc}✗{hs}')
            else:
                svc_status.append(f'IKE:✗DEAD')
        
        # SSTP
        if 'sstp' in checks:
            ck = checks['sstp']
            proc = '●' if ck['process'] else '✗'
            port = ck.get('port443', '?')
            if ck['process'] and port in ('OK', 'OK_NOCERT', 'NON_TLS'):
                svc_status.append(f'SSTP:{proc}✓')
            elif ck['process']:
                svc_status.append(f'SSTP:{proc}✗{port}')
            else:
                svc_status.append(f'SSTP:✗DEAD')
        
        # OpenVPN
        if 'openvpn' in checks:
            ck = checks['openvpn']
            proc = '●' if ck['process'] else '✗'
            hs = ck.get('handshake', '?')
            port = ck.get('port', '?')
            clients = ck.get('clients', 0)
            if ck['process'] and hs in ('OK', 'RESP', 'TIMEOUT'):
                svc_status.append(f'OVPN:{proc}✓p{port}({clients})')
            elif ck['process']:
                svc_status.append(f'OVPN:{proc}✗{hs}')
            else:
                svc_status.append(f'OVPN:✗DEAD')
        
        # V2Ray
        if 'v2ray' in checks:
            ck = checks['v2ray']
            proc = '●' if ck['process'] else '✗'
            conn = ck.get('connection', '?')
            port = ck.get('port', 0)
            if ck['process'] and conn in ('OK', 'RESP', 'OK_SILENT', 'EMPTY'):
                svc_status.append(f'V2R:{proc}✓p{port}')
            elif ck['process'] and conn == 'NO_PORT_CONFIG':
                svc_status.append(f'V2R:{proc}?noCfg')
            elif ck['process']:
                svc_status.append(f'V2R:{proc}✗{conn}')
            else:
                svc_status.append(f'V2R:✗DEAD')

        ssh_ok = '✓' if checks.get('ssh', {}).get('ssh', False) else '✗'
        
        status_str = ' | '.join(svc_status)
        print(f'  {ip:18s} {name:20s} SSH:{ssh_ok}  {status_str}')
        
        if r['issues']:
            for issue in r['issues']:
                print(f'    ⚠ {issue}')

    if critical:
        print(f'\n🔴 위험 ({len(critical)}대)')
        print('  ' + '-' * 96)
        for r in sorted(critical, key=lambda x: x['ip']):
            print_server(r)
    
    if warning:
        print(f'\n🟡 경고 ({len(warning)}대)')
        print('  ' + '-' * 96)
        for r in sorted(warning, key=lambda x: x['ip']):
            print_server(r)
    
    if ok:
        print(f'\n🟢 정상 ({len(ok)}대)')
        print('  ' + '-' * 96)
        for r in sorted(ok, key=lambda x: x['ip']):
            print_server(r)
    
    if other:
        print(f'\n⚪ 기타 ({len(other)}대)')
        print('  ' + '-' * 96)
        for r in sorted(other, key=lambda x: x['ip']):
            print_server(r)

    print()
    print('=' * 100)

    # 서비스별 통계
    svc_stats = {}
    for svc in ['ikev2', 'sstp', 'openvpn', 'v2ray']:
        total = 0
        proc_ok = 0
        conn_ok = 0
        for r in results:
            if svc in r['checks']:
                total += 1
                ck = r['checks'][svc]
                if ck.get('process', False):
                    proc_ok += 1
                    if svc == 'ikev2' and ck.get('handshake') in ('OK', 'RESP', 'PARTIAL'):
                        conn_ok += 1
                    elif svc == 'sstp' and ck.get('port443') in ('OK', 'OK_NOCERT', 'NON_TLS'):
                        conn_ok += 1
                    elif svc == 'openvpn' and ck.get('handshake') in ('OK', 'RESP', 'TIMEOUT'):
                        conn_ok += 1
                    elif svc == 'v2ray' and ck.get('connection') in ('OK', 'RESP', 'OK_SILENT', 'EMPTY', 'NO_PORT_CONFIG'):
                        conn_ok += 1
        if total > 0:
            svc_stats[svc] = {'total': total, 'process_ok': proc_ok, 'connect_ok': conn_ok}

    print('  서비스별 통계:')
    for svc, stats in svc_stats.items():
        label = {'ikev2': 'IKEv2/StrongSwan', 'sstp': 'SSTP/SoftEther', 'openvpn': 'OpenVPN', 'v2ray': 'V2Ray/Xray'}[svc]
        print(f'    {label:20s}: 서버 {stats["total"]}대 | 프로세스 OK {stats["process_ok"]}/{stats["total"]} | 연결 OK {stats["connect_ok"]}/{stats["total"]}')
    
    print('=' * 100)


def main():
    global start_time
    start_time = time.time()

    # 인자 파싱
    args = sys.argv[1:]
    output_json = '--json' in args
    target_ip = None
    if '--server' in args:
        idx = args.index('--server')
        if idx + 1 < len(args):
            target_ip = args[idx + 1]

    # 서버 목록 조회
    servers = get_servers(target_ip)
    if not servers:
        print('활성 서버가 없습니다.')
        sys.exit(1)

    if not output_json:
        print(f'[INFO] VPN 서비스 점검 시작 - {len(servers)}대 서버')

    # 병렬 점검
    results = []
    server_map = {s['hostip']: s for s in servers}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_single_server, s): s for s in servers}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                server = futures[future]
                results.append({
                    'ip': server['hostip'],
                    'name': server['name'],
                    'status': 'ERROR',
                    'issues': [str(e)],
                    'checks': {},
                    'services_config': server['services']
                })

    # ===== 실패 서버 자동 1회 재점검 (전체 점검 시에만) =====
    if not target_ip:
        failed = [r for r in results if r.get('status') in ('CRITICAL', 'ERROR')]
        if failed:
            if not output_json:
                print(f'[RETRY] {len(failed)}대 실패 서버 재점검 (5초 대기 후)')
            time.sleep(5)
            retry_results = {}
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                retry_futures = {}
                for r in failed:
                    s = server_map.get(r['ip'])
                    if s:
                        retry_futures[executor.submit(check_single_server, s)] = r['ip']
                for future in as_completed(retry_futures):
                    ip = retry_futures[future]
                    try:
                        retry_results[ip] = future.result()
                    except Exception as e:
                        pass  # 재시도도 실패 → 원래 결과 유지
            # 재시도 결과가 개선되었으면 교체
            improved = 0
            for i, r in enumerate(results):
                if r['ip'] in retry_results:
                    new_r = retry_results[r['ip']]
                    if new_r.get('status') not in ('CRITICAL', 'ERROR') or \
                       len(new_r.get('issues', [])) < len(r.get('issues', [])):
                        results[i] = new_r
                        improved += 1
            if not output_json:
                print(f'[RETRY] 재점검 완료: {improved}/{len(failed)}대 복구')

    if output_json:
        # JSON 출력
        output = {
            'timestamp': datetime.now().isoformat(),
            'elapsed': round(time.time() - start_time, 1),
            'total': len(results),
            'critical': len([r for r in results if r['status'] == 'CRITICAL']),
            'warning': len([r for r in results if r['status'] == 'WARNING']),
            'ok': len([r for r in results if r['status'] == 'OK']),
            'servers': results
        }
        print(json.dumps(output, indent=2, default=str, ensure_ascii=False))
    else:
        print_report(results)

    # 결과 저장
    os.makedirs('logs', exist_ok=True)
    save_data = {
        'timestamp': datetime.now().isoformat(),
        'elapsed': round(time.time() - start_time, 1),
        'total': len(results),
        'critical': len([r for r in results if r['status'] == 'CRITICAL']),
        'warning': len([r for r in results if r['status'] == 'WARNING']),
        'ok': len([r for r in results if r['status'] == 'OK']),
        'servers': results
    }
    with open('logs/nas_service_check_latest.json', 'w') as f:
        json.dump(save_data, f, indent=2, default=str, ensure_ascii=False)

    # 종료 코드: critical이 있으면 2, warning이면 1
    critical_count = len([r for r in results if r['status'] == 'CRITICAL'])
    if critical_count > 0:
        sys.exit(2)
    warning_count = len([r for r in results if r['status'] == 'WARNING'])
    if warning_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
