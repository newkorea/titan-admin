#!/usr/bin/env python3
"""
cn_telecom_ping.py  –  NAS 서버 → 중국 3대 통신사 ping 측정 스크립트
====================================================================
각 한국 NAS 서버에서 중국 China Telecom / China Mobile / China Unicom
대표 IP에 대한 ICMP ping을 수행하고 결과를 DB에 저장한다.

사용:
    python3 cn_telecom_ping.py              # 모든 활성 KR 서버 측정
    python3 cn_telecom_ping.py --dry-run    # 측정만 하고 DB 저장 안 함
    python3 cn_telecom_ping.py --workers 15 # 동시 SSH 워커 수 조절

실행 주기: systemd timer로 매 2시간 실행 권장
"""

import os, sys, re, time, datetime, argparse, subprocess
import concurrent.futures

# ── DB 설정 ──
import MySQLdb

DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

def get_db():
    conn = MySQLdb.connect(**DB_CONFIG)
    conn.autocommit(True)
    return conn

# ── 측정 대상 IP ──
# 각 통신사별 2개씩 (1개 실패해도 다른 1개로 측정 가능)
CN_TARGETS = {
    'ct': {  # China Telecom
        'name': 'China Telecom',
        'ips': ['202.96.209.133', '202.96.134.133'],  # 상하이 DNS
    },
    'cm': {  # China Mobile
        'name': 'China Mobile',
        'ips': ['221.179.155.161', '211.136.112.50'],  # 베이징 DNS, 이동 DNS
    },
    'cu': {  # China Unicom
        'name': 'China Unicom',
        'ips': ['123.125.81.6', '119.6.6.6'],  # 베이징, 연통 DNS
    },
}

SSH_KEY = '/home/newkorea/.ssh/id_ed25519'
SSH_OPTS = '-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes'
PING_COUNT = 5  # 각 IP에 5회 ping
PING_TIMEOUT = 3  # 각 패킷 timeout(초)


def get_active_servers():
    """DB에서 활성 서버 목록 조회 (해외 서버 포함, 도메인 hostip 제외)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, hostip, telecom
        FROM tbl_agent3
        WHERE is_active = 1
          AND hostip REGEXP '^[0-9]'
        ORDER BY name
    """)
    rows = [{'name': r[0], 'ip': r[1], 'telecom': r[2]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def get_server_by_name(name):
    """DB에서 특정 서버 1개 조회"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, hostip, telecom
        FROM tbl_agent3
        WHERE name = %s AND is_active = 1
    """, (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {'name': row[0], 'ip': row[1], 'telecom': row[2]}
    return None


def build_ssh_ping_command(server_ip):
    """하나의 SSH 명령으로 모든 통신사 ping을 수행하는 명령 생성"""
    parts = []
    for tc_key, tc_info in CN_TARGETS.items():
        for ip in tc_info['ips']:
            # ping 결과에서 rtt 라인 추출, 형식: min/avg/max/mdev
            parts.append(
                f'echo -n "{tc_key}:{ip}:" && '
                f'ping -c {PING_COUNT} -W {PING_TIMEOUT} {ip} 2>&1 | '
                f'grep -oP "rtt .+ = \\K[0-9./]+" || echo "FAIL"'
            )
    remote_cmd = ' && '.join(parts)
    return (
        f'ssh -i {SSH_KEY} {SSH_OPTS} root@{server_ip} '
        f"'{remote_cmd}'"
    )


def parse_ping_output(output):
    """SSH 출력에서 통신사별 ping 결과 파싱
    
    반환: {
        'ct': {'avg': 56.3, 'min': 52.1, 'max': 60.5, 'ips': '202.96.209.133,202.96.134.133'},
        'cm': {...},
        'cu': {...},
    }
    """
    results = {}
    for line in output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # 형식: ct:202.96.209.133:min/avg/max/mdev  또는  ct:202.96.209.133:FAIL
        m = re.match(r'^(\w+):([\d.]+):(.+)$', line)
        if not m:
            continue
        tc_key, target_ip, rtt_str = m.group(1), m.group(2), m.group(3)
        
        if tc_key not in results:
            results[tc_key] = {'measurements': [], 'ips': []}
        
        results[tc_key]['ips'].append(target_ip)
        
        if rtt_str == 'FAIL':
            continue
        
        # rtt_str = "min/avg/max/mdev"
        parts = rtt_str.split('/')
        if len(parts) >= 3:
            try:
                min_ms = float(parts[0])
                avg_ms = float(parts[1])
                max_ms = float(parts[2])
                results[tc_key]['measurements'].append({
                    'min': min_ms, 'avg': avg_ms, 'max': max_ms
                })
            except ValueError:
                pass
    
    # 통신사별 평균 집계
    final = {}
    for tc_key in CN_TARGETS:
        if tc_key not in results or not results[tc_key]['measurements']:
            final[tc_key] = {
                'avg': None, 'min': None, 'max': None,
                'ips': ','.join(results.get(tc_key, {}).get('ips', []))
            }
        else:
            ms = results[tc_key]['measurements']
            final[tc_key] = {
                'avg': round(sum(m['avg'] for m in ms) / len(ms), 2),
                'min': round(min(m['min'] for m in ms), 2),
                'max': round(max(m['max'] for m in ms), 2),
                'ips': ','.join(results[tc_key]['ips']),
            }
    return final


def measure_server(server):
    """단일 서버에 대한 ping 측정 실행"""
    name = server['name']
    ip = server['ip']
    cmd = build_ssh_ping_command(ip)
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=90
        )
        output = result.stdout
        if result.returncode != 0 and not output.strip():
            return {'server': server, 'error': f'SSH failed (rc={result.returncode})', 'data': None}
        
        data = parse_ping_output(output)
        return {'server': server, 'error': None, 'data': data}
    except subprocess.TimeoutExpired:
        return {'server': server, 'error': 'SSH timeout', 'data': None}
    except Exception as e:
        return {'server': server, 'error': str(e), 'data': None}


def save_results(results, check_time):
    """측정 결과를 DB에 저장"""
    insert_sql = """
        INSERT INTO tbl_server_telecom_ping
            (server_ip, server_name, cn_telecom, ping_avg, ping_min, ping_max, target_ips, check_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows_to_insert = []
    for r in results:
        if r['error'] or not r['data']:
            # 에러 서버도 NULL로 기록 (측정 실패 추적)
            for tc_key in CN_TARGETS:
                rows_to_insert.append((
                    r['server']['ip'], r['server']['name'], tc_key,
                    None, None, None, '', check_time
                ))
            continue
        
        for tc_key, ping_data in r['data'].items():
            rows_to_insert.append((
                r['server']['ip'], r['server']['name'], tc_key,
                ping_data['avg'], ping_data['min'], ping_data['max'],
                ping_data['ips'], check_time
            ))
    
    conn = get_db()
    cur = conn.cursor()
    cur.executemany(insert_sql, rows_to_insert)
    conn.commit()
    cur.close()
    conn.close()
    
    return len(rows_to_insert)


def cleanup_old_data(days=7):
    """7일 이상 된 측정 데이터 삭제"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM tbl_server_telecom_ping
        WHERE check_time < DATE_SUB(NOW(), INTERVAL %s DAY)
    """, (days,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if deleted > 0:
        print(f'  Cleaned up {deleted} old records (>{days} days)')


def main():
    parser = argparse.ArgumentParser(description='NAS → 중국 통신사 ping 측정')
    parser.add_argument('--dry-run', action='store_true', help='측정만 하고 DB 저장 안함')
    parser.add_argument('--workers', type=int, default=10, help='동시 SSH 워커 수 (기본 10)')
    parser.add_argument('--server', type=str, default='', help='특정 서버만 측정 (서버명)')
    args = parser.parse_args()
    
    check_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'=== CN Telecom Ping Measurement: {check_time} ===')
    
    if args.server:
        sv = get_server_by_name(args.server)
        if not sv:
            print(f'Server not found or inactive: {args.server}')
            sys.exit(1)
        servers = [sv]
        print(f'Single server mode: {args.server}')
    else:
        servers = get_active_servers()
    print(f'Target servers: {len(servers)}')
    
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(measure_server, servers))
    elapsed = time.time() - t0
    
    # 결과 출력
    ok_count = sum(1 for r in results if not r['error'])
    fail_count = sum(1 for r in results if r['error'])
    print(f'\nCompleted in {elapsed:.1f}s — OK: {ok_count}, Fail: {fail_count}\n')
    
    print(f'{"Server":<20} {"회선":<6} {"CT(ms)":<10} {"CM(ms)":<10} {"CU(ms)":<10} {"Best"}')
    print('=' * 65)
    
    for r in sorted(results, key=lambda x: x['server']['name']):
        s = r['server']
        if r['error']:
            print(f'{s["name"]:<20} {s["telecom"]:<6} ERROR: {r["error"]}')
            continue
        d = r['data']
        ct_s = f'{d["ct"]["avg"]:.1f}' if d['ct']['avg'] else 'FAIL'
        cm_s = f'{d["cm"]["avg"]:.1f}' if d['cm']['avg'] else 'FAIL'
        cu_s = f'{d["cu"]["avg"]:.1f}' if d['cu']['avg'] else 'FAIL'
        
        vals = {}
        if d['ct']['avg']: vals['CT'] = d['ct']['avg']
        if d['cm']['avg']: vals['CM'] = d['cm']['avg']
        if d['cu']['avg']: vals['CU'] = d['cu']['avg']
        best = min(vals, key=vals.get) if vals else '?'
        
        print(f'{s["name"]:<20} {s["telecom"]:<6} {ct_s:<10} {cm_s:<10} {cu_s:<10} {best}')
    
    # DB 저장
    if not args.dry_run:
        saved = save_results(results, check_time)
        print(f'\nSaved {saved} records to DB')
        cleanup_old_data(7)
    else:
        print('\n[DRY RUN] DB 저장 건너뜀')
    
    print('Done.')


if __name__ == '__main__':
    main()
