#!/usr/bin/env python3
"""
uto_server_health.py — UTO 서버 헬스체크 + ISP별 ping 측정 + 자동 배정 관리
===========================================================================
vcsvpn2013 DB의 vpnlinek/vpnlinek26 auto 서버에 대해:
1) SSH 헬스체크 (strongswan, IKEv2 포트, xfrm 세션 수)
2) 중국 3대 통신사 ping 측정 (SSH → 서버 → 중국 IP ping)
3) 스코어 계산 (Score = ping_avg * 0.7 + conn_count * 0.3)
4) server_health 테이블 업데이트
5) vpnlinek/vpnlinek26.check50 업데이트 (실제 접속자 수)
6) 비정상 서버 자동 감지 → is_healthy=0

사용:
    python3 uto_server_health.py               # 전체 체크
    python3 uto_server_health.py --dry-run      # 측정만 (DB 미저장)
    python3 uto_server_health.py --force-ping   # 무조건 ping 측정 포함
    python3 uto_server_health.py --verbose      # 상세 출력

크론: */5 * * * * /home/newkorea/project/.venv/bin/python3 /home/newkorea/project/scripts/uto_server_health.py >> /home/newkorea/project/scripts/uto_health.log 2>&1
"""

import os
import sys
import re
import time
import subprocess
import argparse
import datetime
import concurrent.futures

import MySQLdb

# ── DB 설정 ──
UTO_DB = {
    'host': '218.158.57.51',
    'user': 'root',
    'passwd': 'uto6703',
    'db': 'vcsvpn2013',
    'charset': 'utf8mb4',
}

TITAN_DB = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

# ── SSH 설정 ──
SSH_KEY = '/home/newkorea/.ssh/id_ed25519'
SSH_OPTS = '-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o BatchMode=yes'

# ── 중국 통신사 ping 대상 ──
CN_TARGETS = {
    'ct': {'name': 'China Telecom', 'ips': ['202.96.209.133', '202.96.134.133']},
    'cm': {'name': 'China Mobile', 'ips': ['221.179.155.161', '211.136.112.50']},
    'cu': {'name': 'China Unicom', 'ips': ['123.125.81.6', '119.6.6.6']},
}

PING_COUNT = 5
PING_TIMEOUT = 3
MAX_CONN = 50  # 서버당 최대 접속자 제한

# ── 점수 가중치 (2026-03-10: 스루풋 기반으로 전환) ──
# 스루풋이 있으면 스루풋 위주, 없으면 ping 폴백
SCORE_THROUGHPUT_WEIGHT = 60   # 스루풋 역수 × 이 값 (핵심)
SCORE_CONN_WEIGHT = 0.3        # 연결 수 × 이 값 (분산)
SCORE_PING_WEIGHT = 0.2        # ping × 이 값 (참고)
THROUGHPUT_WINDOW_HOURS = 48   # 스루풋 계산 윈도우 (시간)
THROUGHPUT_MIN_SESSION_SEC = 300  # 5분 이상 세션만 스루풋 계산
THROUGHPUT_MIN_SAMPLES = 3     # 최소 세션 수 (미만이면 ping 폴백)
PREFIX_MIN_SAMPLES = 5         # IP prefix별 최소 세션수 (이 이상이면 prefix-level 스코어 저장)

# ── 최소 헬스체크 주기 (초) ── ping은 무거우니 10분마다만
PING_INTERVAL_SEC = 600

# ── 실시간 접속 성공률 기반 헬스체크 설정 ──
SUCCESS_RATE_WINDOW_HOURS = 1    # 최근 N시간 radacct 기준
SUCCESS_RATE_DEAD_THRESHOLD = 0.10   # 10% 미만 + 10건 이상 → is_healthy=0
SUCCESS_RATE_DEAD_MIN_ATTEMPTS = 10
SUCCESS_RATE_DEGRADED_THRESHOLD = 0.30  # 30% 미만 + 5건 이상 → 스코어 페널티
SUCCESS_RATE_DEGRADED_MIN_ATTEMPTS = 5
SUCCESS_RATE_PENALTY_FACTOR = 200  # 페널티 = (1 - rate) * FACTOR → 스코어에 가산


def get_db(config):
    conn = MySQLdb.connect(**config)
    conn.autocommit(True)
    return conn


def get_uto_auto_servers():
    """vcsvpn2013에서 auto 서버 목록 조회 (vpnlinek + vpnlinek26 합집합)"""
    conn = get_db(UTO_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT address, ipname
        FROM (
            SELECT address, ipname FROM vpnlinek WHERE is_auto >= 1 AND su = 1
            UNION
            SELECT address, ipname FROM vpnlinek26 WHERE is_auto >= 1 AND su = 1
        ) combined
        ORDER BY address
    """)
    servers = [{'ip': r[0], 'name': r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return servers


def check_server_health(server):
    """SSH로 서버 헬스체크: strongswan + 포트 + 접속자 수"""
    ip = server['ip']
    name = server['name']
    result = {
        'server': server,
        'is_healthy': True,
        'health_msg': 'OK',
        'conn_count': 0,
        'checks': {},
    }

    cmd = (
        f"ssh -i {SSH_KEY} {SSH_OPTS} root@{ip} "
        f"'"
        f'echo SWAN_STATUS=$(systemctl is-active strongswan 2>/dev/null || systemctl is-active strongswan-starter 2>/dev/null || echo inactive); '
        f'echo PORT500=$(ss -ulnp 2>/dev/null | grep -c ":500 " || true); '
        f'echo PORT4500=$(ss -ulnp 2>/dev/null | grep -c ":4500 " || true); '
        f'echo XFRM_COUNT=$(ip xfrm state 2>/dev/null | grep -c "proto esp" || true); '
        f'echo UPTIME=$(cat /proc/uptime 2>/dev/null | cut -d " " -f1 || echo 0)'
        f"'"
    )

    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        output = proc.stdout.strip()

        if proc.returncode != 0 and not output:
            result['is_healthy'] = False
            result['health_msg'] = f'SSH failed (rc={proc.returncode})'
            return result

        # Parse output
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('SWAN_STATUS='):
                val = line.split('=', 1)[1].strip()
                result['checks']['strongswan'] = val
                if val != 'active':
                    result['is_healthy'] = False
                    result['health_msg'] = f'strongswan {val}'
            elif line.startswith('PORT500='):
                val = int(line.split('=', 1)[1].strip())
                result['checks']['port500'] = val
                if val == 0:
                    result['is_healthy'] = False
                    result['health_msg'] = 'IKEv2 port 500 not listening'
            elif line.startswith('PORT4500='):
                val = int(line.split('=', 1)[1].strip())
                result['checks']['port4500'] = val
                if val == 0:
                    result['is_healthy'] = False
                    result['health_msg'] = 'IKEv2 port 4500 not listening'
            elif line.startswith('XFRM_COUNT='):
                val = int(line.split('=', 1)[1].strip())
                result['conn_count'] = val
            elif line.startswith('UPTIME='):
                val = float(line.split('=', 1)[1].strip())
                result['checks']['uptime_sec'] = val

        # 추가 검증: strongswan active인데 xfrm 0이고 uptime > 1시간 → zombie 의심
        uptime = result['checks'].get('uptime_sec', 0)
        xfrm = result['conn_count']
        swan = result['checks'].get('strongswan', '')
        if swan == 'active' and xfrm == 0 and uptime > 3600:
            # strongswan 살아있지만 세션 0 → 1시간 넘으면 zombie 의심
            result['health_msg'] = 'zombie suspected (active but 0 sessions for >1h)'
            # 아직 healthy로 유지하되 경고만 (완전 장애는 아닐 수 있음)

    except subprocess.TimeoutExpired:
        result['is_healthy'] = False
        result['health_msg'] = 'SSH timeout'
    except Exception as e:
        result['is_healthy'] = False
        result['health_msg'] = f'Error: {str(e)[:100]}'

    return result


def measure_ping(server):
    """SSH로 서버에서 중국 통신사 IP에 ping 측정"""
    ip = server['ip']
    parts = []
    for tc_key, tc_info in CN_TARGETS.items():
        for target_ip in tc_info['ips']:
            parts.append(
                f'echo -n "{tc_key}:{target_ip}:" && '
                f'ping -c {PING_COUNT} -W {PING_TIMEOUT} {target_ip} 2>&1 | '
                f'grep -oP "rtt .+ = \\K[0-9./]+" || echo "FAIL"'
            )
    remote_cmd = ' && '.join(parts)
    cmd = f'ssh -i {SSH_KEY} {SSH_OPTS} root@{ip} \'{remote_cmd}\''

    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90)
        output = proc.stdout.strip()
        if not output:
            return None

        results = {}
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(\w+):([\d.]+):(.+)$', line)
            if not m:
                continue
            tc_key, target_ip, rtt_str = m.group(1), m.group(2), m.group(3)

            if tc_key not in results:
                results[tc_key] = {'measurements': []}

            if rtt_str == 'FAIL':
                continue

            rtt_parts = rtt_str.split('/')
            if len(rtt_parts) >= 3:
                try:
                    results[tc_key]['measurements'].append({
                        'min': float(rtt_parts[0]),
                        'avg': float(rtt_parts[1]),
                        'max': float(rtt_parts[2]),
                    })
                except ValueError:
                    pass

        # 통신사별 집계
        final = {}
        for tc_key in CN_TARGETS:
            if tc_key not in results or not results[tc_key]['measurements']:
                final[tc_key] = {'avg': None, 'min': None, 'max': None}
            else:
                ms = results[tc_key]['measurements']
                final[tc_key] = {
                    'avg': round(sum(m['avg'] for m in ms) / len(ms), 2),
                    'min': round(min(m['min'] for m in ms), 2),
                    'max': round(max(m['max'] for m in ms), 2),
                }
        return final

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def get_recent_success_rates(server_ips, hours=SUCCESS_RATE_WINDOW_HOURS):
    """radacct에서 최근 N시간 서버별 실제 접속 성공률 조회
    
    rekey 세션(callingstationid='') 제외, 실제 고객 접속만 집계.
    성공 기준: acctsessiontime > 10
    """
    if not server_ips:
        return {}
    try:
        conn = get_db(UTO_DB)
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(server_ips))
        cur.execute(f"""
            SELECT nasipaddress,
                   COUNT(*) as total,
                   SUM(CASE WHEN acctsessiontime > 10 THEN 1 ELSE 0 END) as success
            FROM radacct
            WHERE acctstarttime > NOW() - INTERVAL %s HOUR
              AND callingstationid != ''
              AND nasipaddress IN ({placeholders})
            GROUP BY nasipaddress
        """, [hours] + list(server_ips))
        rates = {}
        for nasip, total, success in cur.fetchall():
            total = int(total)
            success = int(success)
            rate = success / total if total > 0 else 1.0
            rates[nasip] = {'total': total, 'success': success, 'rate': rate}
        cur.close()
        conn.close()
        return rates
    except Exception as e:
        print(f'  WARNING: Failed to query recent success rates: {e}')
        return {}


def get_isp_throughput(server_ips, hours=THROUGHPUT_WINDOW_HOURS):
    """radacct에서 ISP별 × 서버별 실측 스루풋 계산
    
    같은 ISP의 모든 유저 세션을 집계하여 서버별 평균 스루풋을 구함.
    → 신규 유저도 같은 ISP 기존 유저 데이터로 최적 서버를 배정받음.
    
    Returns: {server_ip: {telecom: {'avg_mbps': float, 'samples': int}}}
    """
    if not server_ips:
        return {}
    try:
        conn = get_db(UTO_DB)
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(server_ips))
        # ISP 분류를 SQL CASE로 처리 (cn_isp_cache 또는 IP 대역 기반)
        # callingstationid 형식: "IP=5Bxxxx=5D" 또는 "IP"
        cur.execute(f"""
            SELECT 
                ra.nasipaddress,
                CASE
                    WHEN isp.cn_telecom IS NOT NULL AND isp.cn_telecom != 'unknown' 
                        THEN isp.cn_telecom
                    ELSE 'all'
                END as telecom,
                AVG(ra.acctoutputoctets * 8.0 / 1024 / 1024 / ra.acctsessiontime) as avg_ul_mbps,
                COUNT(*) as samples
            FROM radacct ra
            LEFT JOIN cn_isp_cache isp 
                ON isp.ip_prefix = CONCAT(
                    SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 1),
                    '.',
                    SUBSTRING_INDEX(SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 2), '.', -1)
                )
            WHERE ra.acctstarttime > NOW() - INTERVAL %s HOUR
              AND ra.acctsessiontime > %s
              AND ra.acctoutputoctets > 0
              AND ra.callingstationid != ''
              AND ra.nasipaddress IN ({placeholders})
            GROUP BY ra.nasipaddress, telecom
            HAVING samples >= 1
        """, [hours, THROUGHPUT_MIN_SESSION_SEC] + list(server_ips))
        
        result = {}
        for nasip, telecom, avg_mbps, samples in cur.fetchall():
            if nasip not in result:
                result[nasip] = {}
            result[nasip][telecom] = {
                'avg_mbps': float(avg_mbps) if avg_mbps else 0,
                'samples': int(samples),
            }
        
        # 'all' 집계도 추가 (ISP 무관 전체 평균)
        cur.execute(f"""
            SELECT 
                ra.nasipaddress,
                AVG(ra.acctoutputoctets * 8.0 / 1024 / 1024 / ra.acctsessiontime) as avg_ul_mbps,
                COUNT(*) as samples
            FROM radacct ra
            WHERE ra.acctstarttime > NOW() - INTERVAL %s HOUR
              AND ra.acctsessiontime > %s
              AND ra.acctoutputoctets > 0
              AND ra.callingstationid != ''
              AND ra.nasipaddress IN ({placeholders})
            GROUP BY ra.nasipaddress
        """, [hours, THROUGHPUT_MIN_SESSION_SEC] + list(server_ips))
        
        for nasip, avg_mbps, samples in cur.fetchall():
            if nasip not in result:
                result[nasip] = {}
            # ISP별 데이터가 없는 경우 'all'로 폴백
            if 'all' not in result[nasip]:
                result[nasip]['all'] = {
                    'avg_mbps': float(avg_mbps) if avg_mbps else 0,
                    'samples': int(samples),
                }
            # _total은 항상 저장
            result[nasip]['_total'] = {
                'avg_mbps': float(avg_mbps) if avg_mbps else 0,
                'samples': int(samples),
            }
        
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f'  WARNING: Failed to query ISP throughput: {e}')
        import traceback
        traceback.print_exc()
        return {}


def get_prefix_throughput(server_ips, hours=THROUGHPUT_WINDOW_HOURS):
    """IP prefix(지역)별 × 서버별 스루풋 계산
    
    같은 ISP 내에서도 IP prefix(대략 지역/성)에 따라
    최적 서버가 크게 다를 수 있으므로, prefix 단위 스코어를 계산.
    
    Returns: {server_ip: {'ct:114.86': {'avg_mbps':float, 'samples':int}, ...}}
    cn_telecom column에 'ct:114.86' 형식으로 저장 → PHP에서 prefix 매칭
    """
    if not server_ips:
        return {}
    try:
        conn = get_db(UTO_DB)
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(server_ips))
        cur.execute(f"""
            SELECT 
                ra.nasipaddress,
                CASE
                    WHEN isp.cn_telecom IS NOT NULL AND isp.cn_telecom != 'unknown' 
                        THEN isp.cn_telecom
                    ELSE NULL
                END as telecom,
                CONCAT(
                    SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 1),
                    '.',
                    SUBSTRING_INDEX(SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 2), '.', -1)
                ) as ip_prefix,
                AVG(ra.acctoutputoctets * 8.0 / 1024 / 1024 / ra.acctsessiontime) as avg_mbps,
                COUNT(*) as samples
            FROM radacct ra
            LEFT JOIN cn_isp_cache isp ON isp.ip_prefix = CONCAT(
                SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 1),
                '.',
                SUBSTRING_INDEX(SUBSTRING_INDEX(SUBSTRING_INDEX(ra.callingstationid, '=', 1), '.', 2), '.', -1)
            )
            WHERE ra.acctstarttime > NOW() - INTERVAL %s HOUR
              AND ra.acctsessiontime > %s
              AND ra.acctoutputoctets > 0
              AND ra.callingstationid != ''
              AND ra.nasipaddress IN ({placeholders})
            GROUP BY ra.nasipaddress, telecom, ip_prefix
            HAVING samples >= %s AND telecom IS NOT NULL
        """, [hours, THROUGHPUT_MIN_SESSION_SEC] + list(server_ips) + [PREFIX_MIN_SAMPLES])
        
        result = {}
        for nasip, telecom, prefix, avg_mbps, samples in cur.fetchall():
            if nasip not in result:
                result[nasip] = {}
            key = f'{telecom}:{prefix}'  # e.g. 'ct:114.86', 'cm:39.144'
            result[nasip][key] = {
                'avg_mbps': float(avg_mbps) if avg_mbps else 0,
                'samples': int(samples),
            }
        
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f'  WARNING: Failed to query prefix throughput: {e}')
        return {}


def calc_score(throughput_mbps, conn_count, ping_avg, throughput_samples):
    """새로운 점수 공식: 낮을수록 좋은 서버
    
    스루풋이 충분하면(>= THROUGHPUT_MIN_SAMPLES): 스루풋 역수 기반
    스루풋이 부족하면: ping 기반 (기존 방식 폴백)
    """
    if throughput_mbps and throughput_mbps > 0 and throughput_samples >= THROUGHPUT_MIN_SAMPLES:
        # 스루풋 기반: 1/mbps × weight (역수이므로 빠를수록 낮은 점수)
        tp_score = (1.0 / throughput_mbps) * SCORE_THROUGHPUT_WEIGHT
        conn_score = conn_count * SCORE_CONN_WEIGHT
        ping_score = (ping_avg or 80) * SCORE_PING_WEIGHT  # ping 참고만
        return round(tp_score + conn_score + ping_score, 1)
    elif ping_avg and ping_avg > 0:
        # ping 폴백 (기존 방식, 스루풋 데이터 없는 서버)
        return round(ping_avg * 0.7 + conn_count * 0.3, 1)
    else:
        return 99999.0


def get_existing_ping_data():
    """titan DB에서 기존 ping 데이터 조회 (24시간 이내)"""
    try:
        conn = get_db(TITAN_DB)
        cur = conn.cursor()
        cur.execute("""
            SELECT p.server_ip, p.cn_telecom, p.ping_avg, p.ping_min, p.ping_max, p.check_time
            FROM tbl_server_telecom_ping p
            INNER JOIN (
                SELECT server_ip, cn_telecom, MAX(id) AS max_id
                FROM tbl_server_telecom_ping
                WHERE check_time > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                GROUP BY server_ip, cn_telecom
            ) latest ON p.id = latest.max_id
        """)
        data = {}
        for r in cur.fetchall():
            key = (r[0], r[1])  # (server_ip, cn_telecom)
            data[key] = {
                'avg': float(r[2]) if r[2] else None,
                'min': float(r[3]) if r[3] else None,
                'max': float(r[4]) if r[4] else None,
                'time': r[5],
            }
        cur.close()
        conn.close()
        return data
    except Exception as e:
        print(f'  [WARN] titan DB ping 데이터 조회 실패: {e}')
        return {}


def should_run_ping():
    """마지막 ping 측정으로부터 PING_INTERVAL_SEC 이상 경과했는지 확인"""
    try:
        conn = get_db(UTO_DB)
        cur = conn.cursor()
        cur.execute("""
            SELECT MAX(last_check) FROM server_health
            WHERE cn_telecom != 'all' AND ping_avg IS NOT NULL
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or not row[0]:
            return True
        last = row[0]
        if isinstance(last, str):
            last = datetime.datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
        elapsed = (datetime.datetime.now() - last).total_seconds()
        return elapsed >= PING_INTERVAL_SEC
    except Exception:
        return True


def save_health_data(health_results, ping_results, now_str, throughput_data=None, prefix_data=None):
    """server_health 테이블에 저장 (스루풋 기반 스코어링)"""
    if throughput_data is None:
        throughput_data = {}
    if prefix_data is None:
        prefix_data = {}
    conn = get_db(UTO_DB)
    cur = conn.cursor()

    for hr in health_results:
        server = hr['server']
        ip = server['ip']
        conn_count = hr['conn_count']
        is_healthy = 1 if hr['is_healthy'] else 0
        health_msg = hr['health_msg']

        # ping 데이터 (서버별)
        ping_data = ping_results.get(ip, {})
        # 스루풋 데이터 (서버별)
        tp_data = throughput_data.get(ip, {})

        # 성공률 페널티 계산
        success_rate = hr.get('_success_rate', 1.0)
        success_penalty = 0
        if success_rate < SUCCESS_RATE_DEGRADED_THRESHOLD:
            success_penalty = round((1 - success_rate) * SUCCESS_RATE_PENALTY_FACTOR, 1)

        # 'all' 레코드: 전체 평균
        all_avgs = [ping_data[tc]['avg'] for tc in ('ct', 'cm', 'cu')
                    if tc in ping_data and ping_data[tc].get('avg') is not None]
        all_ping_avg = round(sum(all_avgs) / len(all_avgs), 2) if all_avgs else None
        all_ping_min = min(ping_data[tc]['min'] for tc in ('ct', 'cm', 'cu')
                          if tc in ping_data and ping_data[tc].get('min') is not None) if all_avgs else None
        all_ping_max = max(ping_data[tc]['max'] for tc in ('ct', 'cm', 'cu')
                          if tc in ping_data and ping_data[tc].get('max') is not None) if all_avgs else None

        # 'all' 스루풋
        all_tp = tp_data.get('_total', {})
        all_tp_avg = all_tp.get('avg_mbps')
        all_tp_samples = all_tp.get('samples', 0)

        base_score = calc_score(all_tp_avg, conn_count, all_ping_avg, all_tp_samples)
        score_all = round(base_score + success_penalty, 1)

        cur.execute("""
            INSERT INTO server_health (server_ip, cn_telecom, ping_avg, ping_min, ping_max,
                conn_count, score, throughput_avg, throughput_samples, is_healthy, health_msg, last_check)
            VALUES (%s, 'all', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                ping_avg=VALUES(ping_avg), ping_min=VALUES(ping_min), ping_max=VALUES(ping_max),
                conn_count=VALUES(conn_count), score=VALUES(score),
                throughput_avg=VALUES(throughput_avg), throughput_samples=VALUES(throughput_samples),
                is_healthy=VALUES(is_healthy), health_msg=VALUES(health_msg), last_check=VALUES(last_check)
        """, (ip, all_ping_avg, all_ping_min, all_ping_max, conn_count, score_all,
              all_tp_avg, all_tp_samples, is_healthy, health_msg, now_str))

        # per-telecom 레코드
        for tc in ('ct', 'cm', 'cu'):
            p = ping_data.get(tc, {})
            tc_ping_avg = p.get('avg')
            tc_tp = tp_data.get(tc, {})
            tc_tp_avg = tc_tp.get('avg_mbps')
            tc_tp_samples = tc_tp.get('samples', 0)

            # ISP별 스루풋이 없으면 'all' 스루풋으로 폴백
            if not tc_tp_avg and all_tp_avg:
                tc_tp_avg = all_tp_avg
                tc_tp_samples = all_tp_samples

            score_tc = calc_score(tc_tp_avg, conn_count, tc_ping_avg, tc_tp_samples)
            score_tc = round(score_tc + success_penalty, 1)

            cur.execute("""
                INSERT INTO server_health (server_ip, cn_telecom, ping_avg, ping_min, ping_max,
                    conn_count, score, throughput_avg, throughput_samples, is_healthy, health_msg, last_check)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ping_avg=VALUES(ping_avg), ping_min=VALUES(ping_min), ping_max=VALUES(ping_max),
                    conn_count=VALUES(conn_count), score=VALUES(score),
                    throughput_avg=VALUES(throughput_avg), throughput_samples=VALUES(throughput_samples),
                    is_healthy=VALUES(is_healthy), health_msg=VALUES(health_msg), last_check=VALUES(last_check)
            """, (ip, tc, tc_ping_avg, p.get('min'), p.get('max'), conn_count, score_tc,
                  tc_tp_avg, tc_tp_samples, is_healthy, health_msg, now_str))

        # per-prefix 레코드 (e.g. 'ct:114.86', 'cm:39.144')
        pfx_data = prefix_data.get(ip, {})
        for pfx_key, pfx_tp in pfx_data.items():
            # pfx_key 형식: 'ct:114.86'
            pfx_tp_avg = pfx_tp.get('avg_mbps', 0)
            pfx_tp_samples = pfx_tp.get('samples', 0)
            if pfx_tp_avg <= 0:
                continue
            # prefix에 해당하는 ISP의 ping 데이터 사용 (ct:114.86 → ct의 ping)
            pfx_isp = pfx_key.split(':')[0] if ':' in pfx_key else 'all'
            pfx_ping = ping_data.get(pfx_isp, {}).get('avg')
            pfx_score = calc_score(pfx_tp_avg, conn_count, pfx_ping, pfx_tp_samples)
            pfx_score = round(pfx_score + success_penalty, 1)
            cur.execute("""
                INSERT INTO server_health (server_ip, cn_telecom, conn_count, score,
                    throughput_avg, throughput_samples, is_healthy, health_msg, last_check)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    conn_count=VALUES(conn_count), score=VALUES(score),
                    throughput_avg=VALUES(throughput_avg), throughput_samples=VALUES(throughput_samples),
                    is_healthy=VALUES(is_healthy), health_msg=VALUES(health_msg), last_check=VALUES(last_check)
            """, (ip, pfx_key, conn_count, pfx_score,
                  pfx_tp_avg, pfx_tp_samples, is_healthy, health_msg, now_str))

    conn.commit()
    cur.close()
    conn.close()


def update_check50(health_results):
    """vpnlinek/vpnlinek26의 check50 컬럼 업데이트 (실제 접속자 수)"""
    conn = get_db(UTO_DB)
    cur = conn.cursor()
    for hr in health_results:
        ip = hr['server']['ip']
        cnt = hr['conn_count']
        cur.execute("UPDATE vpnlinek SET check50 = %s WHERE address = %s AND is_auto >= 1", (cnt, ip))
        cur.execute("UPDATE vpnlinek26 SET check50 = %s WHERE address = %s AND is_auto >= 1", (cnt, ip))
    conn.commit()
    cur.close()
    conn.close()


def try_restart_unhealthy(hr):
    """비정상 서버 strongswan 자동 재시작 시도"""
    ip = hr['server']['ip']
    name = hr['server']['name']
    msg = hr['health_msg']

    # SSH 실패나 timeout이면 재시작 불가
    if 'SSH' in msg or 'timeout' in msg:
        return False

    # strongswan inactive → 재시작 시도
    if 'strongswan' in msg or 'port' in msg.lower():
        print(f'  [{name}] Attempting strongswan restart...')
        cmd = (
            f'ssh -i {SSH_KEY} {SSH_OPTS} root@{ip} '
            f'"systemctl restart strongswan 2>/dev/null; sleep 2; '
            f'systemctl is-active strongswan 2>/dev/null"'
        )
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            status = proc.stdout.strip().split('\n')[-1]
            if status == 'active':
                print(f'  [{name}] strongswan restarted successfully!')
                hr['is_healthy'] = True
                hr['health_msg'] = 'auto-restarted'
                return True
            else:
                print(f'  [{name}] restart failed: {status}')
                return False
        except Exception as e:
            print(f'  [{name}] restart error: {e}')
            return False
    return False


def main():
    parser = argparse.ArgumentParser(description='UTO 서버 헬스체크 + ISP ping 측정')
    parser.add_argument('--dry-run', action='store_true', help='측정만, DB 미저장')
    parser.add_argument('--force-ping', action='store_true', help='ping 주기 무시, 무조건 측정')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세 출력')
    parser.add_argument('--no-restart', action='store_true', help='자동 재시작 비활성화')
    args = parser.parse_args()

    now = datetime.datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{now_str}] === UTO Server Health Check ===')

    # 1. 서버 목록 조회
    servers = get_uto_auto_servers()
    print(f'  Auto servers: {len(servers)}')
    if not servers:
        print('  No auto servers found. Exiting.')
        return

    # 2. 헬스체크 (병렬 SSH)
    print(f'  Running health checks...')
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        health_results = list(executor.map(check_server_health, servers))
    health_elapsed = time.time() - t0
    print(f'  Health checks done in {health_elapsed:.1f}s')

    # 비정상 서버 감지 + 자동 재시작
    unhealthy = [hr for hr in health_results if not hr['is_healthy']]
    if unhealthy and not args.no_restart:
        print(f'  Unhealthy servers: {len(unhealthy)}')
        for hr in unhealthy:
            try_restart_unhealthy(hr)

    # 2.5. radacct 기반 실시간 접속 성공률 체크
    server_ips = [hr['server']['ip'] for hr in health_results]
    recent_rates = get_recent_success_rates(server_ips)
    degraded_count = 0
    for hr in health_results:
        ip = hr['server']['ip']
        if ip not in recent_rates:
            continue
        r = recent_rates[ip]
        if r['total'] >= SUCCESS_RATE_DEAD_MIN_ATTEMPTS and r['rate'] < SUCCESS_RATE_DEAD_THRESHOLD:
            # 성공률 10% 미만 + 충분한 시도 → 즉시 배정 제외
            hr['is_healthy'] = False
            hr['health_msg'] = f"dead: {r['rate']*100:.0f}% success ({r['success']}/{r['total']} in {SUCCESS_RATE_WINDOW_HOURS}h)"
            degraded_count += 1
        elif r['total'] >= SUCCESS_RATE_DEGRADED_MIN_ATTEMPTS and r['rate'] < SUCCESS_RATE_DEGRADED_THRESHOLD:
            # 성공률 30% 미만 → 스코어 페널티 (health_msg에 기록, 스코어 계산시 반영)
            hr['health_msg'] = f"degraded: {r['rate']*100:.0f}% success ({r['success']}/{r['total']} in {SUCCESS_RATE_WINDOW_HOURS}h)"
            hr['_success_rate'] = r['rate']
            degraded_count += 1
        else:
            hr['_success_rate'] = r.get('rate', 1.0)
    if degraded_count > 0:
        print(f'  Degraded/dead by success rate: {degraded_count} servers')

    # 2.6. DB에서 실제 접속자 수 조회 (radacct: acctstoptime IS NULL = 현재 연결 중)
    try:
        db_conn = get_db(UTO_DB)
        db_cur = db_conn.cursor()
        server_ips = [hr['server']['ip'] for hr in health_results]
        if server_ips:
            placeholders = ','.join(['%s'] * len(server_ips))
            db_cur.execute(f"""
                SELECT nasipaddress, COUNT(*) as cnt
                FROM radacct
                WHERE acctstoptime IS NULL
                  AND nasipaddress IN ({placeholders})
                GROUP BY nasipaddress
            """, server_ips)
            db_conn_counts = {r[0]: r[1] for r in db_cur.fetchall()}
        else:
            db_conn_counts = {}
        db_cur.close()
        db_conn.close()

        # conn_count를 DB 기준으로 교체 (xfrm count는 xfrm_count로 별도 보존)
        for hr in health_results:
            ip = hr['server']['ip']
            hr['xfrm_count'] = hr['conn_count']  # 원래 xfrm count 보존
            hr['conn_count'] = db_conn_counts.get(ip, 0)  # DB 기준 접속자 수
    except Exception as e:
        print(f'  WARNING: Failed to query DB conn counts: {e}')

    # 2.7. ISP별 × 서버별 실측 스루풋 계산 (radacct 기반)
    print(f'  Calculating ISP throughput from radacct ({THROUGHPUT_WINDOW_HOURS}h window)...')
    throughput_data = get_isp_throughput(server_ips)
    tp_count = sum(1 for ip in throughput_data if throughput_data[ip].get('_total'))
    print(f'  Throughput data: {tp_count}/{len(server_ips)} servers with data')

    # 2.8. IP prefix(지역)별 × 서버별 스루풋 계산
    prefix_data = get_prefix_throughput(server_ips)
    pfx_total = sum(len(v) for v in prefix_data.values())
    print(f'  Prefix throughput: {pfx_total} prefix×server combinations (min {PREFIX_MIN_SAMPLES} sessions)')

    # 3. Ping 측정 (주기적으로만)
    ping_results = {}
    run_ping = args.force_ping or should_run_ping()

    if run_ping:
        print(f'  Running CN telecom ping measurements...')
        t1 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            ping_futures = {executor.submit(measure_ping, s): s for s in servers}
            for future in concurrent.futures.as_completed(ping_futures):
                s = ping_futures[future]
                try:
                    data = future.result()
                    if data:
                        ping_results[s['ip']] = data
                except Exception:
                    pass
        ping_elapsed = time.time() - t1
        print(f'  Ping measurements done in {ping_elapsed:.1f}s ({len(ping_results)}/{len(servers)} ok)')
    else:
        print(f'  Skipping ping (last measured within {PING_INTERVAL_SEC}s)')
        # 기존 server_health에서 ping 데이터 가져오기
        try:
            conn = get_db(UTO_DB)
            cur = conn.cursor()
            cur.execute("""
                SELECT server_ip, cn_telecom, ping_avg, ping_min, ping_max
                FROM server_health WHERE cn_telecom IN ('ct', 'cm', 'cu') AND ping_avg IS NOT NULL
            """)
            for r in cur.fetchall():
                ip, tc = r[0], r[1]
                if ip not in ping_results:
                    ping_results[ip] = {}
                ping_results[ip][tc] = {'avg': r[2], 'min': r[3], 'max': r[4]}
            cur.close()
            conn.close()
        except Exception:
            pass

    # 4. titan DB에서 추가 ping 데이터 가져오기 (UTO 서버와 동일 서브넷의 ping 데이터 활용)
    if not ping_results:
        titan_ping = get_existing_ping_data()
        for s in servers:
            ip = s['ip']
            for tc in ('ct', 'cm', 'cu'):
                if (ip, tc) in titan_ping:
                    if ip not in ping_results:
                        ping_results[ip] = {}
                    ping_results[ip][tc] = titan_ping[(ip, tc)]

    # 5. 결과 출력
    print()
    print(f'  {"Server":<15} {"IP":<20} {"Hlth":<6} {"Conn":<5} {"SRate":<8} {"TP(Mbps)":<10} {"TP#":<5} {"CT(ms)":<8} {"CM(ms)":<8} {"CU(ms)":<8} {"Score":<8} {"Basis":<6}')
    print('  ' + '=' * 123)

    for hr in sorted(health_results, key=lambda x: x['server']['ip']):
        s = hr['server']
        health_str = 'OK' if hr['is_healthy'] else 'FAIL'
        conn_str = str(hr['conn_count'])
        if hr['conn_count'] >= MAX_CONN:
            conn_str += '!'

        # success rate display
        ip = s['ip']
        if ip in recent_rates:
            r = recent_rates[ip]
            srate_str = f"{r['rate']*100:.0f}%({r['total']})"
        else:
            srate_str = 'N/A'

        # throughput display
        tp_data = throughput_data.get(ip, {})
        tp_total = tp_data.get('_total', {})
        tp_avg = tp_total.get('avg_mbps')
        tp_samples = tp_total.get('samples', 0)
        tp_s = f'{tp_avg:.3f}' if tp_avg else 'N/A'
        tp_n = str(tp_samples) if tp_samples else '-'

        ping_data = ping_results.get(s['ip'], {})
        ct_s = f"{ping_data['ct']['avg']:.0f}" if 'ct' in ping_data and ping_data['ct'].get('avg') else '-'
        cm_s = f"{ping_data['cm']['avg']:.0f}" if 'cm' in ping_data and ping_data['cm'].get('avg') else '-'
        cu_s = f"{ping_data['cu']['avg']:.0f}" if 'cu' in ping_data and ping_data['cu'].get('avg') else '-'

        # overall score using calc_score
        avgs = [ping_data[tc]['avg'] for tc in ('ct', 'cm', 'cu')
                if tc in ping_data and ping_data[tc].get('avg') is not None]
        avg_ping = sum(avgs) / len(avgs) if avgs else None
        score = calc_score(tp_avg, hr['conn_count'], avg_ping, tp_samples)
        # apply success rate penalty
        s_rate = hr.get('_success_rate', 1.0)
        if s_rate < SUCCESS_RATE_DEGRADED_THRESHOLD:
            score += (1 - s_rate) * SUCCESS_RATE_PENALTY_FACTOR
        score_s = f'{score:.1f}'
        basis = 'TP' if tp_avg and tp_samples >= THROUGHPUT_MIN_SAMPLES else 'PING'

        print(f'  {s["name"]:<15} {s["ip"]:<20} {health_str:<6} {conn_str:<5} {srate_str:<8} {tp_s:<10} {tp_n:<5} {ct_s:<8} {cm_s:<8} {cu_s:<8} {score_s:<8} {basis:<6}')

    # 6. DB 저장
    if not args.dry_run:
        save_health_data(health_results, ping_results, now_str, throughput_data, prefix_data)
        update_check50(health_results)
        pfx_rows = sum(len(v) for v in prefix_data.values())
        print(f'\n  Saved to DB ({len(health_results)} servers, {pfx_rows} prefix scores)')
    else:
        print(f'\n  [DRY RUN] DB 저장 건너뜀')

    # 요약
    ok_count = sum(1 for hr in health_results if hr['is_healthy'])
    fail_count = len(health_results) - ok_count
    over50 = sum(1 for hr in health_results if hr['conn_count'] >= MAX_CONN)
    print(f'\n  Summary: {ok_count} healthy, {fail_count} unhealthy, {over50} over {MAX_CONN} conn limit')
    print(f'  Done.\n')


if __name__ == '__main__':
    main()
