#!/usr/bin/env python3
"""
UTO VPN - Xray VLESS+Reality 사용자 동기화 스크립트

vpnuser 테이블에서 유효 사용자를 읽어 Xray config.json에 배포
- 인증: vuser+vpass → deterministic UUID (UUID5 namespace)
- 프로토콜: VLESS + XTLS-Reality (GFW 우회 최상)
- 대상 서버: DU3(115.71.13.137), UTOLGDHCP1(112.218.79.74), SK110(110.15.180.162), KT43(211.46.6.241), UTOLGDHCP2(1.221.16.188), KT118238(118.34.105.238)
"""

import json
import uuid
import sys
import os
import subprocess
import logging
import argparse
from datetime import datetime

# UTO namespace for deterministic UUID generation
UTO_UUID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

# ========== 서버 설정 ==========
SERVERS = {
    'DU3': {
        'ip': '115.71.13.137',
        'domain': 'du3.jobjapan.com',
        'port': 8443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'INIYRs6BkxSLSQCaMwbBWKVA6_HuWf5nl2BhK9x0IFU',
        'public_key': 'bHqNjsKhoZawCIz6HNxGU2_hEozhlIQweStFqs6EeD8',
        'short_ids': ['f1fa6fbf', '0a35b3cae00891e0'],
    },
    'UTOLGDHCP1': {
        'ip': '112.218.79.74',
        'domain': 'utolgdhcp1.jobjapan.net',
        'port': 443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'GII6Bugo5oZ57yBLL6va6IKMhV8W64uQdSXywCCvhHA',
        'public_key': 'aK_GOUZmyJ8nTVX5cgY7OXB1jpi1rT6f-L9RFp5GxBI',
        'short_ids': ['5779cac6', 'bb22341592110b9f'],
    },
    'SK110': {
        'ip': '110.15.180.162',
        'domain': 'sk110-15-180-162.jobjapan.com',
        'port': 443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'EM0IMp7lF5-9HgV0MJpQD0dHUo-W3XX-PxIIO62LTlk',
        'public_key': 'cpTRmtIhAZwnoBIy2yQ8D1ibqT9efOsYQokCqghkzFk',
        'short_ids': ['8b9a4bb2', '7197819a5f6383f2'],
    },
    'KT43': {
        'ip': '211.46.6.241',
        'domain': 'kt211466241.jobjapan.com',
        'port': 8443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'QBypUW6J5DGYtiJ8Xmj1xsxkBfN671WwGfdWdJ8UdWg',
        'public_key': '8HydMGXUtLNaAjgIJ0hG6sRtlBm4sh_dKU-Mdht8DCo',
        'short_ids': ['1aec903a', 'db5a2fad8a740633'],
    },
    'UTOLGDHCP2': {
        'ip': '1.221.16.188',
        'domain': 'utolgdhcp2.jobjapan.net',
        'port': 443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'YBM7vg0s9_o1NlOXHU349U7ko0ZsX5HlPdpjwUJU5VU',
        'public_key': '02DQLI5UNhEzVOvWlmI6_f55_9WshnVeDRY7ocJjRXI',
        'short_ids': ['1aaa6c09', 'a11c120361ba1b2d'],
    },
    'KT118238': {
        'ip': '118.34.105.238',
        'domain': 'kt118238.jobjapan.com',
        'port': 8443,
        'ssh_pass': 'uto6703',
        'xray_bin': '/usr/local/xray-reality/xray',
        'config_path': '/usr/local/xray-reality/config.json',
        'service_name': 'xray-reality',
        'private_key': 'GLWc5UOvY9VETDf6zehV6h0p8ie7C3UkvZiKB9TPDUc',
        'public_key': 'q3dKCr8C8kb32pHrRhls4p7GNPdjndFlRKJd4RjEy0w',
        'short_ids': ['64f629de', 'f2ebf856937881ab'],
    },
}

# Reality 공통 설정
REALITY_DEST = 'www.microsoft.com:443'  # 위장 대상 (Active Probing 시 이 사이트 응답)
REALITY_SERVER_NAMES = ['www.microsoft.com', 'microsoft.com']

# DB 설정
DB_CONFIG = {
    'host': '218.158.57.51',
    'port': 3306,
    'user': 'root',
    'password': 'uto6703',
    'database': 'vcsvpn2013',
}

# 안전장치
MAX_USERS_LIMIT = 3000
MIN_USERS_LIMIT = 10

LOG_FILE = '/home/newkorea/project/scripts/uto_reality_sync.log'


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )


def generate_uuid_for_user(vuser, vpass):
    """vuser+vpass 조합에서 deterministic UUID5 생성"""
    combined = f"{vuser}:{vpass}"
    return str(uuid.uuid5(UTO_UUID_NAMESPACE, combined))


def get_active_users():
    """UTO DB에서 유효 사용자 목록 가져오기"""
    import MySQLdb
    conn = MySQLdb.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        passwd=DB_CONFIG['password'],
        db=DB_CONFIG['database'],
        charset='utf8'
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vuser, vpass, session, lastdate
        FROM vpnuser
        WHERE lastdate > NOW()
        ORDER BY vuser
    """)
    users = []
    for row in cursor.fetchall():
        vuser, vpass, session, lastdate = row
        user_uuid = generate_uuid_for_user(vuser, vpass)
        users.append({
            'vuser': vuser,
            'uuid': user_uuid,
            'email': f"{vuser}@uto",
            'session': session or 1,
            'lastdate': str(lastdate),
        })
    cursor.close()
    conn.close()
    return users


def build_xray_config(server_conf, users):
    """Xray VLESS+Reality 설정 파일 생성"""
    clients = []
    for u in users:
        clients.append({
            'id': u['uuid'],
            'email': u['email'],
            'flow': 'xtls-rprx-vision',
        })

    config = {
        'log': {
            'loglevel': 'warning',
            'access': '/var/log/xray-reality/access.log',
            'error': '/var/log/xray-reality/error.log',
        },
        'api': {
            'tag': 'api',
            'services': ['HandlerService', 'StatsService'],
        },
        'stats': {},
        'policy': {
            'levels': {
                '0': {
                    'statsUserUplink': True,
                    'statsUserDownlink': True,
                }
            },
            'system': {
                'statsInboundUplink': True,
                'statsInboundDownlink': True,
            }
        },
        'inbounds': [
            {
                'tag': 'vless-reality',
                'listen': '0.0.0.0',
                'port': server_conf['port'],
                'protocol': 'vless',
                'settings': {
                    'clients': clients,
                    'decryption': 'none',
                },
                'streamSettings': {
                    'network': 'tcp',
                    'security': 'reality',
                    'realitySettings': {
                        'show': False,
                        'dest': REALITY_DEST,
                        'xver': 0,
                        'serverNames': REALITY_SERVER_NAMES,
                        'privateKey': server_conf['private_key'],
                        'shortIds': server_conf['short_ids'],
                    }
                },
                'sniffing': {
                    'enabled': True,
                    'destOverride': ['http', 'tls', 'quic'],
                }
            },
            {
                'tag': 'api-in',
                'listen': '127.0.0.1',
                'port': 62790,
                'protocol': 'dokodemo-door',
                'settings': {
                    'address': '127.0.0.1',
                },
            }
        ],
        'outbounds': [
            {
                'tag': 'direct',
                'protocol': 'freedom',
            },
            {
                'tag': 'block',
                'protocol': 'blackhole',
            }
        ],
        'routing': {
            'domainStrategy': 'AsIs',
            'rules': [
                {
                    'type': 'field',
                    'inboundTag': ['api-in'],
                    'outboundTag': 'api',
                },
            ]
        }
    }
    return config


def deploy_to_server(server_name, server_conf, config_json, dry_run=False):
    """서버에 config.json 배포 및 xray 재시작"""
    ip = server_conf['ip']
    config_path = server_conf['config_path']
    service_name = server_conf['service_name']
    ssh_pass = server_conf['ssh_pass']

    config_str = json.dumps(config_json, indent=2, ensure_ascii=False)
    config_size_kb = len(config_str.encode()) / 1024

    logging.info(f"[{server_name}] config size: {config_size_kb:.1f}KB, "
                 f"users: {len(config_json['inbounds'][0]['settings']['clients'])}")

    if config_size_kb > 1024:
        logging.error(f"[{server_name}] Config too large ({config_size_kb:.0f}KB > 1024KB), ABORT")
        return False

    if dry_run:
        logging.info(f"[{server_name}] DRY RUN - would deploy to {ip}")
        return True

    # SCP로 config 전송
    tmp_file = f'/tmp/xray_reality_config_{server_name}.json'
    with open(tmp_file, 'w') as f:
        f.write(config_str)

    try:
        # scp
        scp_cmd = [
            'sshpass', '-p', ssh_pass,
            'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
            tmp_file, f'root@{ip}:{config_path}'
        ]
        result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logging.error(f"[{server_name}] SCP failed: {result.stderr}")
            return False

        # 로그 디렉토리 생성 + 재시작
        restart_cmd = [
            'sshpass', '-p', ssh_pass,
            'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
            f'root@{ip}',
            f'mkdir -p /var/log/xray-reality && systemctl restart {service_name} && echo OK'
        ]
        result = subprocess.run(restart_cmd, capture_output=True, text=True, timeout=30)
        if 'OK' in result.stdout:
            logging.info(f"[{server_name}] Deploy + restart SUCCESS")
            return True
        else:
            logging.error(f"[{server_name}] Restart failed: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"[{server_name}] Deploy error: {e}")
        return False
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def main():
    parser = argparse.ArgumentParser(description='UTO VPN - Xray Reality User Sync')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--server', type=str, help='Deploy to specific server only')
    parser.add_argument('--verbose', action='store_true', help='Debug logging')
    parser.add_argument('--show-uuid', type=str, help='Show UUID for vuser:vpass (e.g., "user1:pass1")')
    args = parser.parse_args()

    setup_logging(args.verbose)

    # UUID 조회 모드
    if args.show_uuid:
        parts = args.show_uuid.split(':', 1)
        if len(parts) != 2:
            print("Format: vuser:vpass")
            sys.exit(1)
        uid = generate_uuid_for_user(parts[0], parts[1])
        print(f"vuser={parts[0]}, UUID={uid}")
        sys.exit(0)

    logging.info("=" * 60)
    logging.info("UTO Reality Sync START")

    # 1. DB에서 유효 사용자 가져오기
    try:
        users = get_active_users()
    except Exception as e:
        logging.error(f"DB connection failed: {e}")
        sys.exit(1)

    logging.info(f"Active users: {len(users)}")

    # 안전장치
    if len(users) > MAX_USERS_LIMIT:
        logging.error(f"Too many users ({len(users)} > {MAX_USERS_LIMIT}), ABORT")
        sys.exit(1)
    if len(users) < MIN_USERS_LIMIT:
        logging.error(f"Too few users ({len(users)} < {MIN_USERS_LIMIT}), ABORT - DB query issue?")
        sys.exit(1)

    # 2. 서버별 배포
    targets = SERVERS
    if args.server:
        if args.server in SERVERS:
            targets = {args.server: SERVERS[args.server]}
        else:
            logging.error(f"Unknown server: {args.server}")
            sys.exit(1)

    success_count = 0
    for name, conf in targets.items():
        config = build_xray_config(conf, users)
        ok = deploy_to_server(name, conf, config, dry_run=args.dry_run)
        if ok:
            success_count += 1

    logging.info(f"UTO Reality Sync DONE: {success_count}/{len(targets)} servers OK")


if __name__ == '__main__':
    main()
