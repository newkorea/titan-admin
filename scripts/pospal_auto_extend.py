#!/usr/bin/env python3
"""
Pospal(银豹) POS 판매 → UTO VPN 자동 연장 스크립트

동작 흐름:
  1. Pospal API에서 최근 판매 단서(ticket)를 조회
  2. FRS(VPN) 상품만 필터링
  3. ticket remark에서 VPN 사용자명(vuser) 추출
  4. 바코드 → 요금제(session, months, type) 자동 매핑
  5. vpnuser.lastdate 자동 연장 (만료일 기준 누적)
  6. 처리 완료된 ticket은 DB에 기록 (중복 방지)

매장 직원 사용법:
  - Pospal POS에서 FRS 상품을 판매할 때
  - 비고(remark)에 VPN 사용자명을 입력 (예: "zhangsan" 또는 "13800138000")
  - 결제 완료 → 5분 내 자동 VPN 연장

크론 설정:
  */5 * * * * cd /home/newkorea/project && /home/newkorea/project/.venv/bin/python scripts/pospal_auto_extend.py >> scripts/pospal_auto_extend.log 2>&1
"""

import hashlib
import json
import time
import datetime
import calendar
import os
import sys
import logging
import urllib.request
import ssl
import gzip
import traceback
import pymysql

# ── 설정 ──────────────────────────────────────────────

POSPAL_APP_ID = "3C3F51AED8FFF46FE17AC8CDF07FB096"
POSPAL_APP_KEY = "685523063614039568"
POSPAL_HOST = "https://area4-win.pospal.cn:443"

UTO_DB_CONFIG = {
    'host': '218.158.57.51',
    'port': 3306,
    'user': 'root',
    'password': 'uto6703',
    'db': 'vcsvpn2013',
    'charset': 'utf8',
    'connect_timeout': 5,
}

# Pospal 바코드 → UTO 요금제 매핑
# session: 동시접속 수, months: 개월, customer_type: 고객유형, is_new: 신규계정 여부
BARCODE_PLAN_MAP = {
    # FRS 新ID (신규)
    '2003253000115': {'session': 1, 'months': 1,  'customer_type': 'account',  'is_new': True,  'name': 'FRS 新ID 1个月'},
    '2003253000139': {'session': 1, 'months': 6,  'customer_type': 'account',  'is_new': True,  'name': 'FRS 新ID 6个月'},
    '2003253000122': {'session': 1, 'months': 12, 'customer_type': 'account',  'is_new': True,  'name': 'FRS 新ID 1年'},
    '2003253000023': {'session': 2, 'months': 12, 'customer_type': 'account',  'is_new': True,  'name': 'FRS 2M 新ID 1年'},
    '2003253000030': {'session': 2, 'months': 6,  'customer_type': 'account',  'is_new': True,  'name': 'FRS 2M 新ID 6个月'},
    '2101182101405': {'session': 1, 'months': 12, 'customer_type': 'account',  'is_new': True,  'name': 'FRS 1M新ID 一年'},
    '2101182115099': {'session': 1, 'months': 6,  'customer_type': 'account',  'is_new': True,  'name': 'FRS1 new 6Mo'},

    # FRS 延长 (연장)
    '2003253000146': {'session': 1, 'months': 6,  'customer_type': 'account',  'is_new': False, 'name': 'FRS 延长 6个月'},
    '2001061105510': {'session': 1, 'months': 12, 'customer_type': 'account',  'is_new': False, 'name': 'FRS 1M延长 1年'},
    '2101182222407': {'session': 1, 'months': 6,  'customer_type': 'account',  'is_new': False, 'name': 'FRS1 6Mo'},

    # FRS K2 라우터
    '2003253000054': {'session': 2, 'months': 12, 'customer_type': 'router4',  'is_new': True,  'name': 'FRS K2 个人2M 路由器 1年'},
    '2003253000061': {'session': 2, 'months': 6,  'customer_type': 'router4',  'is_new': True,  'name': 'FRS K2 个人2M 路由器 6个月'},
    '2003253000078': {'session': 4, 'months': 12, 'customer_type': 'router4',  'is_new': True,  'name': 'FRS 4M企业路由器1年K2'},
    '2003253000085': {'session': 4, 'months': 6,  'customer_type': 'router4',  'is_new': True,  'name': 'FRS 4M企业路由器半年'},

    # FRS K2 연장 (라우터)
    '2003253000092': {'session': 2, 'months': 12, 'customer_type': 'router4',  'is_new': False, 'name': 'FRS K2延长 个人2M 路由器 1年'},
    '2003253000108': {'session': 2, 'months': 6,  'customer_type': 'router4',  'is_new': False, 'name': 'FRS K2延长 个人2M 路由器 6个月'},

    # FRS 고속 / 대량 세션
    '2003253000047': {'session': 5, 'months': 1,  'customer_type': 'account',  'is_new': True,  'name': 'FRS 5M速度 1个月'},
    '2975912904815': {'session': 10, 'months': 12, 'customer_type': 'account', 'is_new': True,  'name': 'FRS10 1Yr'},

    # FRS1 1Mo (1세션 1개월 — 연장용)
    '2554998127990': {'session': 1, 'months': 1,  'customer_type': 'account',  'is_new': False, 'name': 'FRS1 1Mo'},
}

LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger('pospal_sync')


# ── Pospal API ──────────────────────────────────────

def pospal_call(path, body_dict):
    """Pospal Open API 호출"""
    body_dict["appId"] = POSPAL_APP_ID
    json_body = json.dumps(body_dict, ensure_ascii=False)
    sign_source = POSPAL_APP_KEY + json_body
    signature = hashlib.md5(sign_source.encode("utf-8")).hexdigest().upper()
    timestamp = str(int(time.time() * 1000))
    headers = {
        "User-Agent": "openApi",
        "Content-Type": "application/json; charset=utf-8",
        "time-stamp": timestamp,
        "data-signature": signature,
        "accept-encoding": "gzip,deflate",
    }
    url = POSPAL_HOST + path
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=json_body.encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        raw = resp.read()
        enc = resp.headers.get("Content-Encoding", "")
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def fetch_tickets(start_time, end_time):
    """Pospal 판매 단서 조회 (1일 이내 범위)"""
    all_tickets = []
    pbp = {"parameterType": "String", "parameterValue": ""}
    for _ in range(50):  # 최대 50페이지
        r = pospal_call("/pospal-api2/openapi/v1/ticketOpenApi/queryTicketPages", {
            "startTime": start_time,
            "endTime": end_time,
            "postBackParameter": pbp,
        })
        if r.get("status") != "success":
            log.error(f"Pospal ticket API 오류: {r}")
            break
        batch = r["data"].get("result", [])
        all_tickets.extend(batch)
        if len(batch) < 100:
            break
        pbp = r["data"]["postBackParameter"]
    return all_tickets


# ── DB 연결 ──────────────────────────────────────

def get_db():
    return pymysql.connect(**UTO_DB_CONFIG)


def ensure_pospal_table(conn):
    """pospal_ticket_log 테이블 생성 (처리 이력 추적)"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pospal_ticket_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_sn VARCHAR(64) NOT NULL UNIQUE,
                ticket_datetime DATETIME,
                vuser VARCHAR(64),
                barcode VARCHAR(32),
                product_name VARCHAR(128),
                amount DECIMAL(10,2),
                session_val INT DEFAULT 1,
                months INT DEFAULT 1,
                customer_type VARCHAR(32) DEFAULT 'account',
                action VARCHAR(16) DEFAULT 'extend',
                old_lastdate DATETIME,
                new_lastdate DATETIME,
                status VARCHAR(16) DEFAULT 'pending',
                error_msg TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ticket_sn (ticket_sn),
                INDEX idx_vuser (vuser),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8
        """)
    conn.commit()


def is_ticket_processed(conn, ticket_sn):
    """이미 처리된 ticket인지 확인"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM pospal_ticket_log WHERE ticket_sn = %s", (ticket_sn,))
        return cur.fetchone() is not None


def log_ticket(conn, ticket_sn, ticket_datetime, vuser, barcode, product_name,
               amount, session_val, months, customer_type, action,
               old_lastdate, new_lastdate, status, error_msg=None):
    """처리 결과 기록"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pospal_ticket_log
                (ticket_sn, ticket_datetime, vuser, barcode, product_name, amount,
                 session_val, months, customer_type, action, old_lastdate, new_lastdate,
                 status, error_msg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                error_msg = VALUES(error_msg),
                new_lastdate = VALUES(new_lastdate)
        """, (ticket_sn, ticket_datetime, vuser, barcode, product_name, amount,
              session_val, months, customer_type, action, old_lastdate, new_lastdate,
              status, error_msg))
    conn.commit()


# ── VPN 연장 로직 ──────────────────────────────────

def extend_vpn_user(conn, vuser, months, session_val=None):
    """
    vpnuser.lastdate 연장
    - 만료일이 미래면 만료일 기준 추가
    - 만료일이 과거면 현재 기준 추가
    반환: (old_lastdate, new_lastdate, status_msg)
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, vuser, lastdate, `session`, kz, `groups` FROM vpnuser WHERE vuser = %s",
            (vuser,)
        )
        row = cur.fetchone()
        if not row:
            return None, None, f"사용자를 찾을 수 없습니다: {vuser}"

        user_id, _, lastdate, cur_session, kz, groups_val = row

        now = datetime.datetime.now()
        if lastdate and lastdate > now:
            base_date = lastdate
        else:
            base_date = now

        # months 개월 추가
        new_month = base_date.month + months
        new_year = base_date.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1
        max_day = calendar.monthrange(new_year, new_month)[1]
        new_day = min(base_date.day, max_day)
        new_lastdate = base_date.replace(year=new_year, month=new_month, day=new_day)

        old_lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else None
        new_lastdate_str = new_lastdate.strftime('%Y-%m-%d %H:%M:%S')

        # UPDATE lastdate
        cur.execute("UPDATE vpnuser SET lastdate = %s WHERE id = %s", (new_lastdate_str, user_id))

        # groups NEW → BY
        if groups_val == 'NEW':
            cur.execute("UPDATE vpnuser SET `groups` = 'BY' WHERE id = %s", (user_id,))

        # session 변경 (요청한 경우)
        if session_val and int(session_val) != cur_session:
            cur.execute("UPDATE vpnuser SET `session` = %s WHERE id = %s", (int(session_val), user_id))

        # 변경 로그 기록
        try:
            desc = f'Pospal POS {months}개월 자동연장'
            cur.execute("""
                INSERT INTO uto_change_log (vuser, change_type, field_name, old_value, new_value, description, admin_user)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (vuser, 'extend', 'lastdate', old_lastdate_str, new_lastdate_str, desc, 'pospal_auto'))
        except Exception:
            pass  # 로그 실패해도 연장은 계속

    conn.commit()
    return old_lastdate_str, new_lastdate_str, None


def extract_vuser_from_ticket(ticket):
    """
    ticket에서 VPN 사용자명 추출
    우선순위: ticket remark → item remark → 회원번호 → None
    """
    # 1. ticket 전체 remark
    remark = (ticket.get('remark') or '').strip()
    if remark:
        return remark

    # 2. 각 item의 remark
    for item in ticket.get('items', []):
        item_remark = (item.get('remark') or '').strip()
        if item_remark:
            return item_remark

    # 3. Pospal 회원(customer) 이름/번호
    customer_name = (ticket.get('customerName') or '').strip()
    if customer_name:
        return customer_name

    return None


# ── 메인 동기화 로직 ──────────────────────────────

def sync_pospal_tickets(dry_run=False):
    """Pospal 판매 → VPN 자동 연장 메인 루프"""
    now = datetime.datetime.now()
    # 오늘 00:00 ~ 현재까지 조회
    start_time = now.strftime('%Y-%m-%d 00:00:00')
    end_time = now.strftime('%Y-%m-%d %H:%M:%S')

    log.info(f"=== Pospal 판매 동기화 시작 ({start_time} ~ {end_time}) ===")

    # Pospal 판매 조회
    try:
        tickets = fetch_tickets(start_time, end_time)
    except Exception as e:
        log.error(f"Pospal API 호출 실패: {e}")
        return

    if not tickets:
        log.info("새 판매 없음")
        return

    log.info(f"Pospal에서 {len(tickets)}건 조회")

    conn = get_db()
    try:
        ensure_pospal_table(conn)

        processed = 0
        skipped = 0
        errors = 0

        for ticket in tickets:
            ticket_sn = ticket.get('sn', '')
            ticket_dt = ticket.get('datetime', '')

            # 이미 처리된 ticket 스킵
            if is_ticket_processed(conn, ticket_sn):
                skipped += 1
                continue

            # 환불/무효 건 스킵
            if ticket.get('invalid', 0) != 0:
                log.info(f"  [{ticket_sn}] 무효 건 스킵 (invalid={ticket.get('invalid')})")
                continue
            if ticket.get('ticketType') != 'SELL':
                log.info(f"  [{ticket_sn}] 판매 아닌 건 스킵 (type={ticket.get('ticketType')})")
                continue

            # FRS 상품 필터링
            for item in ticket.get('items', []):
                barcode = item.get('productBarcode', '')
                plan = BARCODE_PLAN_MAP.get(barcode)

                if not plan:
                    continue  # FRS 상품 아님

                product_name = item.get('name', '')
                amount = item.get('totalAmount', 0)
                quantity = int(item.get('quantity', 1))

                # VPN 사용자명 추출
                vuser = extract_vuser_from_ticket(ticket)

                if not vuser:
                    # remark가 없으면 처리 보류 (대기 상태로 기록)
                    log.warning(f"  [{ticket_sn}] {product_name} — vuser 미입력! remark에 VPN 사용자명을 입력해주세요.")
                    log_ticket(conn, ticket_sn, ticket_dt, None, barcode, product_name,
                               amount, plan['session'], plan['months'], plan['customer_type'],
                               'new' if plan['is_new'] else 'extend',
                               None, None, 'pending', 'vuser 미입력 — ticket remark에 VPN 사용자명 필요')
                    errors += 1
                    continue

                # 수량만큼 반복 (보통 1회)
                total_months = plan['months'] * quantity

                if dry_run:
                    log.info(f"  [DRY-RUN] [{ticket_sn}] {product_name} → {vuser} {total_months}개월 연장 예정")
                    continue

                # VPN 연장 실행
                try:
                    old_ld, new_ld, err = extend_vpn_user(
                        conn, vuser, total_months, plan['session']
                    )
                    if err:
                        log.error(f"  [{ticket_sn}] {product_name} → {vuser} 연장 실패: {err}")
                        log_ticket(conn, ticket_sn, ticket_dt, vuser, barcode, product_name,
                                   amount, plan['session'], total_months, plan['customer_type'],
                                   'new' if plan['is_new'] else 'extend',
                                   None, None, 'error', err)
                        errors += 1
                    else:
                        log.info(f"  [{ticket_sn}] {product_name} → {vuser} {total_months}개월 연장 완료! ({old_ld} → {new_ld})")
                        log_ticket(conn, ticket_sn, ticket_dt, vuser, barcode, product_name,
                                   amount, plan['session'], total_months, plan['customer_type'],
                                   'new' if plan['is_new'] else 'extend',
                                   old_ld, new_ld, 'success')
                        processed += 1
                except Exception as e:
                    log.error(f"  [{ticket_sn}] {product_name} → {vuser} 예외: {e}")
                    traceback.print_exc()
                    log_ticket(conn, ticket_sn, ticket_dt, vuser, barcode, product_name,
                               amount, plan['session'], plan['months'], plan['customer_type'],
                               'extend', None, None, 'error', str(e))
                    errors += 1

        log.info(f"=== 동기화 완료: 처리 {processed}건, 스킵 {skipped}건, 오류 {errors}건 ===")

    finally:
        conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Pospal POS 판매 → UTO VPN 자동 연장')
    parser.add_argument('--dry-run', action='store_true', help='실제 연장 없이 미리보기')
    args = parser.parse_args()

    sync_pospal_tickets(dry_run=args.dry_run)
