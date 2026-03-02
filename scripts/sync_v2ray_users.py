#!/usr/bin/env python3
"""
V2RAY Per-User UUID Sync Script (Daily 8AM)
=============================================
Runs once daily at 8 AM KST via cron.

What it does:
1. Generates v2ray_uuid for users who don't have one
2. Regenerates shared UUID (tbl_agent3.v2_config) for all servers
   -> Old shared UUID becomes invalid, preventing unauthorized reuse
3. Deploys per-user UUIDs + new shared UUID to all xray servers
4. Marks deployed users (v2ray_deployed=1), resets undeployed (v2ray_deployed=0)
5. On failure: retries failed servers twice more (5 min apart), then emails report

Between syncs:
- New users / renewed users (v2ray_deployed=0) use the shared UUID via API
- Synced users (v2ray_deployed=1) use their personal UUID via API
- Expired users get blocked by API (result=300, no config download)

Usage:
    python3 sync_v2ray_users.py              # Normal sync
    python3 sync_v2ray_users.py --force      # Force restart all servers
    python3 sync_v2ray_users.py --dry-run    # Preview without changes
    python3 sync_v2ray_users.py --server IP  # Sync specific server only

Cron (8 AM KST daily):
    0 8 * * * cd /home/newkorea/project/titan && .venv310/bin/python3 /home/newkorea/project/scripts/sync_v2ray_users.py >> /home/newkorea/project/scripts/v2ray_sync.log 2>&1
"""

import os
import sys
import json
import hashlib
import subprocess
import argparse
import time
import logging
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed

# Django setup
sys.path.insert(0, '/home/newkorea/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()
from django.db import connections

LOG_FILE = '/home/newkorea/project/scripts/v2ray_sync.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

SSH_OPTS = '-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes'
SSH_TIMEOUT = 15  # seconds per SSH command
MAX_WORKERS = 10  # parallel SSH connections

# Safety limits to prevent OOM on VPN servers
MAX_USERS_LIMIT = 3000       # Abort if user count exceeds this (unexpected behavior)
MIN_USERS_LIMIT = 100        # Abort if user count below this (likely DB query error)
MAX_CONFIG_SIZE_KB = 1024    # Max config.json size in KB (1MB). 1609 users ~ 240KB

# Retry settings
MAX_RETRIES = 2              # Retry failed servers up to 2 more times
RETRY_INTERVAL = 300         # 5 minutes between retries

# Email settings
REPORT_EMAIL = 'softcan@naver.com'
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 465
SMTP_EMAIL = 'kakaovpn@naver.com'
SMTP_ID = 'kakaovpn'
SMTP_PW = '41XKPLFFXBN7'


def send_report_email(subject, body_html):
    """Send sync report email to admin."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = REPORT_EMAIL
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_ID, SMTP_PW)
            smtp.sendmail(SMTP_EMAIL, [REPORT_EMAIL], msg.as_string())
        log.info(f'Report email sent to {REPORT_EMAIL}')
    except Exception as e:
        log.error(f'Failed to send report email: {e}')


def build_report_html(user_count, server_count, results_history, final_failed, total_elapsed):
    """Build HTML report for sync results."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
    
    # Determine overall status
    if not final_failed:
        status = '✅ 전체 성공'
        status_color = '#27ae60'
    else:
        status = f'❌ {len(final_failed)}개 서버 실패'
        status_color = '#e74c3c'
    
    # Build attempt rows
    attempt_rows = ''
    for i, (attempt_results, attempt_failed) in enumerate(results_history):
        attempt_no = '초기' if i == 0 else f'재시도 {i}'
        attempt_rows += f'''
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{attempt_no}</td>
            <td style="padding:8px;border:1px solid #ddd;">{attempt_results["success"]} 성공</td>
            <td style="padding:8px;border:1px solid #ddd;">{attempt_results["skip"]} 스킵</td>
            <td style="padding:8px;border:1px solid #ddd;color:#e74c3c;">{attempt_results["fail"]} 실패</td>
            <td style="padding:8px;border:1px solid #ddd;">{", ".join(attempt_failed) if attempt_failed else "-"}</td>
        </tr>'''
    
    # Failed server details
    failed_detail = ''
    if final_failed:
        failed_items = ''.join(f'<li><b>{name}</b>: {msg}</li>' for name, msg in final_failed)
        failed_detail = f'''
        <h3 style="color:#e74c3c;">최종 실패 서버 ({len(final_failed)}개)</h3>
        <ul>{failed_items}</ul>'''
    
    html = f'''
    <html><body style="font-family:Arial,sans-serif;color:#333;">
        <h2 style="color:{status_color};">V2RAY Sync Report — {status}</h2>
        <p><b>시간:</b> {now}<br>
           <b>소요:</b> {total_elapsed:.0f}초<br>
           <b>유저 수:</b> {user_count}명<br>
           <b>서버 수:</b> {server_count}개</p>
        
        <h3>배포 시도 이력</h3>
        <table style="border-collapse:collapse;width:100%;">
            <tr style="background:#f5f5f5;">
                <th style="padding:8px;border:1px solid #ddd;">시도</th>
                <th style="padding:8px;border:1px solid #ddd;">성공</th>
                <th style="padding:8px;border:1px solid #ddd;">스킵</th>
                <th style="padding:8px;border:1px solid #ddd;">실패</th>
                <th style="padding:8px;border:1px solid #ddd;">실패 서버</th>
            </tr>
            {attempt_rows}
        </table>
        {failed_detail}
        <hr style="margin-top:20px;">
        <p style="font-size:11px;color:#aaa;">TITAN VPN V2RAY 자동 배포 시스템</p>
    </body></html>'''
    return html


def get_active_users():
    """Get users with valid (non-expired) subscriptions and v2ray_uuid."""
    import uuid as uuid_mod
    cursor = connections['default'].cursor()
    
    # Auto-generate UUID for active users without one
    cursor.execute('SELECT id FROM tbl_user WHERE v2ray_uuid IS NULL AND is_active = 1 AND delete_yn = %s', ['N'])
    missing = cursor.fetchall()
    if missing:
        for (uid,) in missing:
            cursor.execute('UPDATE tbl_user SET v2ray_uuid = %s WHERE id = %s', [str(uuid_mod.uuid4()), uid])
        log.info(f'Generated v2ray_uuid for {len(missing)} new users')
    
    # Only include users with valid (non-expired) subscriptions
    cursor.execute('''
        SELECT u.email, u.v2ray_uuid 
        FROM tbl_user u
        INNER JOIN radius.radcheck rc ON rc.username = u.email
        WHERE u.is_active = 1 
        AND u.delete_yn = 'N'
        AND u.v2ray_uuid IS NOT NULL
        AND rc.attribute = 'Expiration'
        AND rc.username NOT LIKE %s
        AND STR_TO_DATE(REPLACE(rc.value, ' KST', ''), %s) > NOW()
        ORDER BY u.id
    ''', ['Noactive__%', '%d %b %Y %H:%i:%s'])
    users = cursor.fetchall()
    return [(email, uuid) for email, uuid in users]


def rotate_shared_uuids(dry_run=False):
    """Regenerate shared UUID (v2_config) for ALL active V2RAY servers."""
    import uuid as uuid_mod
    cursor = connections['default'].cursor()
    
    cursor.execute('''
        SELECT hostip, name, v2_config
        FROM tbl_agent3 
        WHERE is_active = 1 AND v2_port = 9999 AND protocol LIKE '%%V2RAY%%'
        ORDER BY name
    ''')
    servers = cursor.fetchall()
    
    new_uuids = {}
    for hostip, name, old_uuid in servers:
        new_uuid = str(uuid_mod.uuid4())
        new_uuids[hostip] = new_uuid
        if not dry_run:
            cursor.execute('UPDATE tbl_agent3 SET v2_config = %s WHERE hostip = %s', [new_uuid, hostip])
        log.info(f'  Shared UUID rotated: {name} ({hostip}): {(old_uuid or "")[:8]}... -> {new_uuid[:8]}...')
    
    log.info(f'Rotated shared UUIDs for {len(new_uuids)} servers')
    return new_uuids


def mark_deployed_users(deployed_emails, dry_run=False):
    """Mark users as deployed/undeployed based on sync results."""
    if dry_run:
        log.info(f'DRY-RUN: Would mark {len(deployed_emails)} users as deployed')
        return
    
    cursor = connections['default'].cursor()
    
    # Reset ALL to 0 first
    cursor.execute('UPDATE tbl_user SET v2ray_deployed = 0 WHERE v2ray_deployed = 1')
    reset_count = cursor.rowcount
    
    # Then mark deployed users as 1
    if deployed_emails:
        for i in range(0, len(deployed_emails), 500):
            chunk = deployed_emails[i:i+500]
            placeholders = ','.join(['%s'] * len(chunk))
            cursor.execute(f'UPDATE tbl_user SET v2ray_deployed = 1 WHERE email IN ({placeholders})', chunk)
    
    log.info(f'Deployed flags: reset {reset_count}, set deployed={len(deployed_emails)}')


def get_active_servers(specific_ip=None):
    """Get all active V2RAY servers from DB, including shared UUID."""
    cursor = connections['default'].cursor()
    if specific_ip:
        cursor.execute('''
            SELECT hostip, hostdomain, v2_port, name, v2_config
            FROM tbl_agent3 
            WHERE is_active = 1 AND hostip = %s
        ''', [specific_ip])
    else:
        cursor.execute('''
            SELECT hostip, hostdomain, v2_port, name, v2_config
            FROM tbl_agent3 
            WHERE is_active = 1 
            AND v2_port = 9999
            AND protocol LIKE '%%V2RAY%%'
            ORDER BY name
        ''')
    servers = cursor.fetchall()
    return [{'ip': r[0], 'domain': r[1], 'port': r[2], 'name': r[3], 'legacy_uuid': r[4]} for r in servers]


def build_xray_config(server, users):
    """Build complete xray config.json for a server with all user UUIDs."""
    clients = []
    
    # Add shared UUID (for new/renewed users between daily syncs)
    shared_uuid = (server.get('legacy_uuid') or '').strip()
    if shared_uuid and len(shared_uuid) == 36 and '-' in shared_uuid:
        clients.append({
            "id": shared_uuid,
            "alterId": 7,
            "email": "_shared@titanvpn"
        })
    
    for email, uuid in users:
        clients.append({
            "id": uuid,
            "alterId": 7,
            "email": email
        })
    
    config = {
        "log": {
            "loglevel": "warning",
            "access": "/var/log/xray/access.log",
            "error": "/var/log/xray/error.log"
        },
        "api": {
            "tag": "api",
            "services": ["HandlerService", "StatsService"]
        },
        "stats": {},
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True
            }
        },
        "inbounds": [
            {
                "tag": "api",
                "listen": "127.0.0.1",
                "port": 62789,
                "protocol": "dokodemo-door",
                "settings": {
                    "address": "127.0.0.1"
                }
            },
            {
                "tag": "vmess-ws-tls",
                "listen": "0.0.0.0",
                "port": server['port'],
                "protocol": "vmess",
                "settings": {
                    "clients": clients
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "tls",
                    "tlsSettings": {
                        "serverName": server['domain'],
                        "certificates": [
                            {
                                "certificateFile": f"/etc/letsencrypt/live/{server['domain']}/fullchain.pem",
                                "keyFile": f"/etc/letsencrypt/live/{server['domain']}/privkey.pem"
                            }
                        ]
                    },
                    "wsSettings": {
                        "path": "/"
                    }
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"]
                }
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "blocked"}
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["api"],
                    "outboundTag": "api"
                },
                {
                    "type": "field",
                    "outboundTag": "blocked",
                    "ip": ["geoip:private"]
                },
                {
                    "type": "field",
                    "outboundTag": "blocked",
                    "protocol": ["bittorrent"]
                }
            ]
        }
    }
    
    # KT0/1/2 relay: google/gemini/youtube → LG3 (these KT IPs are blocked for Google)
    RELAY_SERVERS = {'14.51.2.130', '14.51.2.131', '14.51.2.132'}
    RELAY_UUID = '0da6e4d2-ee69-441d-a454-72f0406a84c8'
    LG3_IP = '1.221.16.187'
    RELAY_PORT = 10000
    RELAY_DOMAINS = [
        "domain:google.com",
        "domain:google.co.kr",
        "domain:google.co.jp",
        "domain:googleapis.com",
        "domain:gstatic.com",
        "domain:youtube.com",
        "domain:youtu.be",
        "domain:googlevideo.com",
        "domain:ytimg.com",
        "domain:ggpht.com",
        "domain:ip138.com",
        "domain:gemini.google.com"
    ]
    
    if server['ip'] in RELAY_SERVERS:
        # Add relay outbound to LG3
        config["outbounds"].append({
            "tag": "relay-lg3",
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": LG3_IP,
                    "port": RELAY_PORT,
                    "users": [{
                        "id": RELAY_UUID,
                        "alterId": 0,
                        "security": "auto"
                    }]
                }]
            }
        })
        # Insert domain routing rule after api rule
        config["routing"]["rules"].insert(1, {
            "type": "field",
            "outboundTag": "relay-lg3",
            "domain": RELAY_DOMAINS
        })
    
    # LG3 relay-in: accept relay traffic from KT servers
    if server['ip'] == LG3_IP:
        config["inbounds"].append({
            "tag": "relay-in",
            "protocol": "vmess",
            "port": RELAY_PORT,
            "listen": "0.0.0.0",
            "settings": {
                "clients": [{
                    "id": RELAY_UUID,
                    "alterId": 0,
                    "email": "relay@kt-servers"
                }]
            }
        })
    
    return config


def get_remote_config_hash(server_ip):
    """Get MD5 hash of remote config.json."""
    try:
        cmd = f"ssh {SSH_OPTS} root@{server_ip} 'md5sum /usr/local/xray/config.json 2>/dev/null || echo NONE'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=SSH_TIMEOUT)
        output = result.stdout.strip()
        if output and output != 'NONE' and not output.startswith('NONE'):
            return output.split()[0]
    except Exception:
        pass
    return None


def sync_server(server, config_json, config_hash, force=False, dry_run=False):
    """Sync config to a single server. Returns (server_name, success, message)."""
    server_ip = server['ip']
    server_name = server['name']
    
    try:
        # Check if remote config matches
        if not force:
            remote_hash = get_remote_config_hash(server_ip)
            if remote_hash == config_hash:
                return (server_name, True, 'SKIP (unchanged)')
        
        if dry_run:
            return (server_name, True, f'DRY-RUN (would update, hash={config_hash[:8]})')
        
        # Write config to temp file
        tmp_file = f'/tmp/xray_config_{server_ip}.json'
        with open(tmp_file, 'w') as f:
            f.write(config_json)
        
        # SCP geo files if missing on remote
        geo_check = f"ssh {SSH_OPTS} root@{server_ip} 'ls /usr/local/xray/geoip.dat 2>/dev/null && echo EXISTS || echo MISSING'"
        geo_result = subprocess.run(geo_check, shell=True, capture_output=True, text=True, timeout=SSH_TIMEOUT)
        if 'MISSING' in geo_result.stdout:
            geo_files = '/tmp/geoip.dat /tmp/geosite.dat'
            # Copy geo files from local cache
            for gf in ['geoip.dat', 'geosite.dat']:
                src = f'/home/newkorea/project/scripts/{gf}'
                if not os.path.exists(src):
                    src = f'/tmp/{gf}'
                if os.path.exists(src):
                    geo_cmd = f"scp {SSH_OPTS} {src} root@{server_ip}:/usr/local/xray/{gf}"
                    subprocess.run(geo_cmd, shell=True, capture_output=True, text=True, timeout=60)

        # SCP config to server
        cmd = f"scp {SSH_OPTS} {tmp_file} root@{server_ip}:/usr/local/xray/config.json"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return (server_name, False, f'SCP FAIL: {result.stderr.strip()}')
        
        # Restart xray
        cmd = f"ssh {SSH_OPTS} root@{server_ip} 'systemctl restart xray && sleep 1 && systemctl is-active xray'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=SSH_TIMEOUT)
        if 'active' in result.stdout:
            return (server_name, True, f'UPDATED ({config_hash[:8]})')
        else:
            return (server_name, False, f'RESTART FAIL: {result.stdout.strip()} {result.stderr.strip()}')
        
    except subprocess.TimeoutExpired:
        return (server_name, False, 'TIMEOUT')
    except Exception as e:
        return (server_name, False, f'ERROR: {str(e)}')
    finally:
        tmp_file = f'/tmp/xray_config_{server_ip}.json'
        try:
            os.unlink(tmp_file)
        except:
            pass


def deploy_to_servers(servers, users, force=False, dry_run=False):
    """Deploy configs to servers. Returns (results_dict, failed_list).
    
    failed_list: list of (server_name, error_message) for failed servers.
    """
    results = {'success': 0, 'skip': 0, 'fail': 0}
    failed = []  # [(server_name, message)]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        
        for server in servers:
            config = build_xray_config(server, users)
            config_json = json.dumps(config, indent=2, ensure_ascii=False)
            config_hash = hashlib.md5(config_json.encode()).hexdigest()
            
            future = executor.submit(
                sync_server, server, config_json, config_hash,
                force=force, dry_run=dry_run
            )
            futures[future] = server
        
        for future in as_completed(futures):
            server_name, success, message = future.result()
            if success:
                if 'SKIP' in message:
                    results['skip'] += 1
                    log.debug(f'  {server_name:15s} -> {message}')
                else:
                    results['success'] += 1
                    log.info(f'  {server_name:15s} -> {message}')
            else:
                results['fail'] += 1
                failed.append((server_name, message))
                log.error(f'  {server_name:15s} -> {message}')
    
    return results, failed


def main():
    parser = argparse.ArgumentParser(description='Sync V2RAY per-user UUIDs to all servers (daily 8AM)')
    parser.add_argument('--force', action='store_true', help='Force restart all servers')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    parser.add_argument('--server', type=str, help='Sync specific server IP only')
    args = parser.parse_args()
    
    start_time = time.time()
    log.info('='*60)
    log.info('V2RAY Daily Sync Started')
    
    # 1. Get active users (also auto-generates UUIDs for users without one)
    users = get_active_users()
    log.info(f'Active users with UUID: {len(users)}')
    
    if not users:
        log.error('No users found! Aborting.')
        sys.exit(1)
    
    # Safety check
    if len(users) > MAX_USERS_LIMIT:
        log.error(f'SAFETY ABORT: User count {len(users)} exceeds limit {MAX_USERS_LIMIT}.')
        sys.exit(2)
    
    if len(users) < MIN_USERS_LIMIT:
        log.error(f'SAFETY ABORT: User count {len(users)} below minimum {MIN_USERS_LIMIT}.')
        sys.exit(2)
    
    # 2. Rotate shared UUIDs for all servers
    log.info('Rotating shared UUIDs...')
    rotate_shared_uuids(dry_run=args.dry_run)
    
    # 3. Get active servers (with newly rotated shared UUIDs)
    servers = get_active_servers(args.server)
    log.info(f'Active V2RAY servers (port 9999): {len(servers)}')
    
    if not servers:
        log.error('No servers found! Aborting.')
        sys.exit(1)
    
    # 4. Validate config size
    sample_config = build_xray_config(servers[0], users)
    sample_json = json.dumps(sample_config, indent=2, ensure_ascii=False)
    config_size_kb = len(sample_json.encode()) / 1024
    log.info(f'Config size: {config_size_kb:.0f}KB ({len(users)} users + shared UUID)')
    
    if config_size_kb > MAX_CONFIG_SIZE_KB:
        log.error(f'SAFETY ABORT: Config size {config_size_kb:.0f}KB exceeds limit {MAX_CONFIG_SIZE_KB}KB.')
        sys.exit(2)
    
    # 5. Deploy with retry logic
    results_history = []  # [(results_dict, failed_names)]
    all_failed_detail = []  # final [(name, msg)]
    
    # Initial deployment
    log.info('--- Initial deployment ---')
    results, failed = deploy_to_servers(servers, users, force=args.force, dry_run=args.dry_run)
    failed_names = [name for name, msg in failed]
    results_history.append((dict(results), list(failed_names)))
    log.info(f'Initial: {results["success"]} updated, {results["skip"]} unchanged, {results["fail"]} failed')
    
    # Retry failed servers up to MAX_RETRIES times
    retry_failed = failed  # [(name, msg)]
    for retry_num in range(1, MAX_RETRIES + 1):
        if not retry_failed:
            break
        
        failed_ips = set()
        for name, msg in retry_failed:
            # Find server by name
            for s in servers:
                if s['name'] == name:
                    failed_ips.add(s['ip'])
                    break
        
        retry_servers = [s for s in servers if s['ip'] in failed_ips]
        
        log.info(f'--- Retry {retry_num}/{MAX_RETRIES}: waiting {RETRY_INTERVAL}s, then retrying {len(retry_servers)} servers ---')
        time.sleep(RETRY_INTERVAL)
        
        retry_results, retry_failed = deploy_to_servers(
            retry_servers, users, force=True, dry_run=args.dry_run
        )
        retry_failed_names = [name for name, msg in retry_failed]
        results_history.append((dict(retry_results), list(retry_failed_names)))
        log.info(f'Retry {retry_num}: {retry_results["success"]} updated, {retry_results["skip"]} unchanged, {retry_results["fail"]} failed')
    
    all_failed_detail = retry_failed  # Whatever is still failing after all retries
    
    # 6. Mark deployed users in DB
    deployed_emails = [email for email, uuid in users]
    mark_deployed_users(deployed_emails, dry_run=args.dry_run)
    
    total_elapsed = time.time() - start_time
    log.info(f'Sync complete in {total_elapsed:.1f}s')
    
    # 7. Send email report (always — so admin knows it ran)
    if not args.dry_run:
        if all_failed_detail:
            subject = f'[V2RAY Sync] ❌ {len(all_failed_detail)}개 서버 실패 — {datetime.datetime.now().strftime("%m/%d %H:%M")}'
        else:
            subject = f'[V2RAY Sync] ✅ 전체 성공 ({len(servers)}서버, {len(users)}유저) — {datetime.datetime.now().strftime("%m/%d %H:%M")}'
        
        report_html = build_report_html(
            user_count=len(users),
            server_count=len(servers),
            results_history=results_history,
            final_failed=all_failed_detail,
            total_elapsed=total_elapsed
        )
        send_report_email(subject, report_html)
    
    log.info('='*60)
    
    if all_failed_detail:
        sys.exit(1)


if __name__ == '__main__':
    main()
