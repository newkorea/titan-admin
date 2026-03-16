#!/usr/bin/env python3
"""
uto_update_server_scores.py — ISP별 서버 성공률 집계 + 유저별 실패 추적
=====================================================================
radacct 7일 데이터에서:
1) ISP별 서버별 성공률을 server_isp_score에 집계
2) 유저별 서버 연속 실패를 user_server_fail에 추적

성공 기준: callingstationid!='' AND acctsessiontime > 10
실패 기준: callingstationid!='' AND (acctsessiontime IS NULL OR acctsessiontime <= 10)
rekey 제외: callingstationid='' 세션은 IKE_SA rekey이므로 집계에서 제외

ISP 제외 기준: 성공률 30% 미만 AND 시도 10건 이상 → is_excluded=1
유저 제외 기준: 연속 실패 3회 이상 → excluded_until = 현재 + 24시간

사용:
    python3 uto_update_server_scores.py           # 전체 집계
    python3 uto_update_server_scores.py --dry-run  # 미리보기
    python3 uto_update_server_scores.py --verbose  # 상세 출력

크론: 매시 정각 (0 * * * *)
"""

import os
import sys
import argparse
import datetime

import MySQLdb

# ── DB 설정 ──
UTO_DB = {
    'host': '218.158.57.51',
    'user': 'root',
    'passwd': 'uto6703',
    'db': 'vcsvpn2013',
    'charset': 'utf8mb4',
}

# ── 설정 ──
LOOKBACK_DAYS = 3           # 집계 기간 (7→3일: 장애 반응 속도 개선)
MIN_ATTEMPTS = 10           # ISP 제외 최소 시도 수
EXCLUDE_THRESHOLD = 0.30    # 성공률 이 미만이면 제외
USER_FAIL_THRESHOLD = 3     # 유저 연속 실패 N회 이상이면 제외
USER_EXCLUDE_HOURS = 24     # 유저 제외 기간 (시간)

# ── 중국 통신사 IP 대역 (Python 버전) ──
import struct
import socket

def ip2long(ip):
    return struct.unpack("!I", socket.inet_aton(ip))[0]

# Simplified ranges matching cn_isp.php
CM_RANGES = [
    (ip2long('1.24.0.0'), ip2long('1.31.255.255')),
    (ip2long('36.128.0.0'), ip2long('36.255.255.255')),
    (ip2long('39.128.0.0'), ip2long('39.191.255.255')),
    (ip2long('100.64.0.0'), ip2long('100.127.255.255')),
    (ip2long('111.0.0.0'), ip2long('111.63.255.255')),
    (ip2long('111.128.0.0'), ip2long('111.159.255.255')),
    (ip2long('112.0.0.0'), ip2long('112.127.255.255')),
    (ip2long('117.128.0.0'), ip2long('117.191.255.255')),
    (ip2long('120.192.0.0'), ip2long('120.255.255.255')),
    (ip2long('183.192.0.0'), ip2long('183.255.255.255')),
    (ip2long('211.136.0.0'), ip2long('211.143.255.255')),
    (ip2long('218.200.0.0'), ip2long('218.207.255.255')),
    (ip2long('221.176.0.0'), ip2long('221.183.255.255')),
    (ip2long('223.64.0.0'), ip2long('223.159.255.255')),
]

CU_RANGES = [
    (ip2long('36.96.0.0'), ip2long('36.127.255.255')),
    (ip2long('42.80.0.0'), ip2long('42.99.255.255')),
    (ip2long('60.0.0.0'), ip2long('60.31.255.255')),
    (ip2long('110.6.0.0'), ip2long('110.99.255.255')),
    (ip2long('112.224.0.0'), ip2long('112.255.255.255')),
    (ip2long('113.0.0.0'), ip2long('113.15.255.255')),
    (ip2long('113.192.0.0'), ip2long('113.255.255.255')),
    (ip2long('116.112.0.0'), ip2long('116.127.255.255')),
    (ip2long('119.0.0.0'), ip2long('119.63.255.255')),
    (ip2long('120.64.0.0'), ip2long('120.95.255.255')),
    (ip2long('121.56.0.0'), ip2long('121.63.255.255')),
    (ip2long('122.0.0.0'), ip2long('122.15.255.255')),
    (ip2long('123.96.0.0'), ip2long('123.127.255.255')),
    (ip2long('124.64.0.0'), ip2long('124.95.255.255')),
    (ip2long('125.32.0.0'), ip2long('125.47.255.255')),
    (ip2long('140.224.0.0'), ip2long('140.255.255.255')),
    (ip2long('221.0.0.0'), ip2long('221.15.255.255')),
    (ip2long('221.192.0.0'), ip2long('221.223.255.255')),
]

CT_RANGES = [
    (ip2long('1.0.0.0'), ip2long('1.7.255.255')),
    (ip2long('14.0.0.0'), ip2long('14.31.255.255')),
    (ip2long('27.0.0.0'), ip2long('27.31.255.255')),
    (ip2long('36.0.0.0'), ip2long('36.63.255.255')),
    (ip2long('42.48.0.0'), ip2long('42.63.255.255')),
    (ip2long('49.64.0.0'), ip2long('49.95.255.255')),
    (ip2long('58.0.0.0'), ip2long('58.63.255.255')),
    (ip2long('59.32.0.0'), ip2long('59.63.255.255')),
    (ip2long('61.128.0.0'), ip2long('61.191.255.255')),
    (ip2long('101.0.0.0'), ip2long('101.127.255.255')),
    (ip2long('110.152.0.0'), ip2long('110.191.255.255')),
    (ip2long('111.64.0.0'), ip2long('111.127.255.255')),
    (ip2long('113.64.0.0'), ip2long('113.127.255.255')),
    (ip2long('114.64.0.0'), ip2long('114.127.255.255')),
    (ip2long('115.192.0.0'), ip2long('115.255.255.255')),
    (ip2long('116.0.0.0'), ip2long('116.63.255.255')),
    (ip2long('117.0.0.0'), ip2long('117.63.255.255')),
    (ip2long('118.64.0.0'), ip2long('118.127.255.255')),
    (ip2long('119.96.0.0'), ip2long('119.191.255.255')),
    (ip2long('120.0.0.0'), ip2long('120.63.255.255')),
    (ip2long('121.0.0.0'), ip2long('121.55.255.255')),
    (ip2long('122.192.0.0'), ip2long('122.255.255.255')),
    (ip2long('123.0.0.0'), ip2long('123.95.255.255')),
    (ip2long('124.0.0.0'), ip2long('124.63.255.255')),
    (ip2long('125.64.0.0'), ip2long('125.127.255.255')),
    (ip2long('175.0.0.0'), ip2long('175.31.255.255')),
    (ip2long('180.64.0.0'), ip2long('180.127.255.255')),
    (ip2long('182.96.0.0'), ip2long('182.127.255.255')),
    (ip2long('183.0.0.0'), ip2long('183.63.255.255')),
    (ip2long('202.96.0.0'), ip2long('202.111.255.255')),
    (ip2long('218.0.0.0'), ip2long('218.95.255.255')),
    (ip2long('220.160.0.0'), ip2long('220.191.255.255')),
    (ip2long('222.64.0.0'), ip2long('222.127.255.255')),
]


def classify_isp(ip_str):
    """IP 주소에서 callingstationid 형식(IP[port] 등)을 파싱하고 ISP 판별"""
    # callingstationid: '113.227.168.71[44149]' 또는 '113.227.168.71=5B44149=5D'
    if not ip_str:
        return 'unknown'
    # Extract IP part
    ip = ip_str.split('[')[0].split('=')[0].strip()
    if not ip:
        return 'unknown'
    try:
        ip_long = ip2long(ip)
    except (socket.error, struct.error):
        return 'unknown'

    for start, end in CM_RANGES:
        if start <= ip_long <= end:
            return 'cm'
    for start, end in CU_RANGES:
        if start <= ip_long <= end:
            return 'cu'
    for start, end in CT_RANGES:
        if start <= ip_long <= end:
            return 'ct'
    return 'unknown'


def get_db():
    conn = MySQLdb.connect(**UTO_DB)
    conn.autocommit(True)
    return conn


def aggregate_isp_server_scores(conn, dry_run=False, verbose=False):
    """radacct 7일 데이터에서 ISP별 서버별 성공률 집계"""
    cur = conn.cursor()
    now = datetime.datetime.now()

    print("[%s] === ISP-서버 성공률 집계 시작 ===" % now.strftime('%Y-%m-%d %H:%M:%S'))

    # radacct에서 실제 연결 시도만 가져옴 (rekey=callingstationid='' 제외)
    cur.execute("""
        SELECT nasipaddress, callingstationid,
               CASE WHEN acctsessiontime > 10 THEN 1 ELSE 0 END as is_success
        FROM radacct
        WHERE acctstarttime > NOW() - INTERVAL %s DAY
          AND callingstationid != ''
          AND nasporttype IN ('Virtual', 'strongSwan')
    """, (LOOKBACK_DAYS,))

    # 서버별 ISP별 집계
    scores = {}  # (server_ip, isp) -> {'total': N, 'success': N}
    row_count = 0
    for nasip, calling_sid, is_success in cur:
        row_count += 1
        isp = classify_isp(calling_sid)

        # ISP별 집계
        for key_isp in [isp, 'all']:
            k = (nasip, key_isp)
            if k not in scores:
                scores[k] = {'total': 0, 'success': 0}
            scores[k]['total'] += 1
            scores[k]['success'] += is_success

    print("  radacct rows processed: %d" % row_count)
    print("  unique (server, isp) combinations: %d" % len(scores))

    # DB에 저장
    excluded_count = 0
    if not dry_run:
        # 기존 데이터 초기화
        cur.execute("DELETE FROM server_isp_score")

    for (server_ip, isp), data in sorted(scores.items()):
        total = data['total']
        success = data['success']
        fail = total - success
        rate = success / total if total > 0 else 0.0
        is_excluded = 1 if (total >= MIN_ATTEMPTS and rate < EXCLUDE_THRESHOLD) else 0

        if is_excluded:
            excluded_count += 1

        if verbose or is_excluded:
            mark = " *** EXCLUDED ***" if is_excluded else ""
            print("  %s [%s]: %d/%d = %.1f%%%s" % (
                server_ip, isp, success, total, rate * 100, mark))

        if not dry_run:
            cur.execute("""
                INSERT INTO server_isp_score
                    (server_ip, cn_telecom, total_attempts, success_count, fail_count,
                     success_rate, is_excluded, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (server_ip, isp, total, success, fail, rate, is_excluded))

    print("  총 제외 서버-ISP 조합: %d" % excluded_count)
    cur.close()
    return excluded_count


def update_user_server_fails(conn, dry_run=False, verbose=False):
    """유저별 서버 연속 실패를 추적하고 제외 설정"""
    cur = conn.cursor()
    now = datetime.datetime.now()

    print("\n[%s] === 유저별 서버 실패 추적 ===" % now.strftime('%Y-%m-%d %H:%M:%S'))

    # 최근 24시간의 실제 연결 시도를 시간순으로 가져옴
    cur.execute("""
        SELECT username, nasipaddress,
               CASE WHEN acctsessiontime > 10 THEN 1 ELSE 0 END as is_success,
               acctstarttime
        FROM radacct
        WHERE acctstarttime > NOW() - INTERVAL 24 HOUR
          AND callingstationid != ''
          AND nasporttype IN ('Virtual', 'strongSwan')
        ORDER BY username, nasipaddress, acctstarttime
    """)

    # 유저별 서버별 최근 연속 실패 수 계산
    user_server = {}  # (username, server_ip) -> {'consecutive_fails': N, 'last_attempt': datetime}
    for username, nasip, is_success, start_time in cur:
        k = (username, nasip)
        if k not in user_server:
            user_server[k] = {'consecutive_fails': 0, 'last_attempt': start_time}

        user_server[k]['last_attempt'] = start_time

        if is_success:
            # 성공하면 연속 실패 카운터 리셋
            user_server[k]['consecutive_fails'] = 0
        else:
            user_server[k]['consecutive_fails'] += 1

    # 연속 실패가 있는 유저-서버 쌍 업데이트
    excluded_count = 0
    total_tracked = 0

    for (username, server_ip), data in user_server.items():
        if data['consecutive_fails'] == 0:
            continue

        total_tracked += 1
        excluded_until = None

        if data['consecutive_fails'] >= USER_FAIL_THRESHOLD:
            excluded_until = now + datetime.timedelta(hours=USER_EXCLUDE_HOURS)
            excluded_count += 1

            if verbose:
                print("  %s -> %s: %d consecutive fails → excluded until %s" % (
                    username, server_ip, data['consecutive_fails'],
                    excluded_until.strftime('%Y-%m-%d %H:%M')))

        if not dry_run:
            cur.execute("""
                INSERT INTO user_server_fail
                    (username, server_ip, consecutive_fails, last_attempt, excluded_until)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    consecutive_fails = VALUES(consecutive_fails),
                    last_attempt = VALUES(last_attempt),
                    excluded_until = CASE
                        WHEN VALUES(consecutive_fails) >= %s THEN VALUES(excluded_until)
                        ELSE NULL
                    END
            """, (username, server_ip, data['consecutive_fails'],
                  data['last_attempt'], excluded_until, USER_FAIL_THRESHOLD))

    # 성공한 유저-서버 쌍은 제외 해제
    success_pairs = [(u, s) for (u, s), d in user_server.items() if d['consecutive_fails'] == 0]
    cleared_count = 0
    if not dry_run and success_pairs:
        for username, server_ip in success_pairs:
            cur.execute("""
                UPDATE user_server_fail
                SET consecutive_fails = 0, excluded_until = NULL
                WHERE username = %s AND server_ip = %s AND consecutive_fails > 0
            """, (username, server_ip))
            cleared_count += cur.rowcount

    # 만료된 제외 정리 (24시간 지난 것)
    if not dry_run:
        cur.execute("""
            DELETE FROM user_server_fail
            WHERE excluded_until IS NOT NULL AND excluded_until < NOW()
        """)
        expired = cur.rowcount
    else:
        expired = 0

    print("  유저-서버 실패 추적: %d pairs" % total_tracked)
    print("  유저-서버 제외 설정: %d (연속 %d회+ 실패)" % (excluded_count, USER_FAIL_THRESHOLD))
    print("  유저-서버 제외 해제: %d (성공으로 리셋)" % cleared_count)
    print("  만료 제외 삭제: %d" % expired)

    cur.close()
    return excluded_count


def main():
    parser = argparse.ArgumentParser(description='ISP별 서버 성공률 집계 + 유저별 실패 추적')
    parser.add_argument('--dry-run', action='store_true', help='미리보기 (DB 미저장)')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세 출력')
    args = parser.parse_args()

    conn = get_db()

    try:
        isp_excluded = aggregate_isp_server_scores(conn, args.dry_run, args.verbose)
        user_excluded = update_user_server_fails(conn, args.dry_run, args.verbose)

        mode = "[DRY-RUN] " if args.dry_run else ""
        print("\n%s완료: ISP 제외=%d, 유저 제외=%d" % (mode, isp_excluded, user_excluded))

    finally:
        conn.close()


if __name__ == '__main__':
    main()
