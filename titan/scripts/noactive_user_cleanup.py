#!/usr/bin/env python3
"""
비활성 회원 정리 스크립트
- 가입 후 3일 이상 경과, is_active=0 (비활성화) 상태인 회원을 Noactive_ 처리
- 이메일: Noactive__원래이메일#타임스탬프
- radcheck 테이블도 동일 처리
- 매일 1회 실행 (systemd timer 또는 cron)
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

import MySQLdb

# ───── 설정 ─────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

DB_HOST = '218.158.57.48'
DB_USER = 'titan'
DB_PASS = 'xkdlxks12!@'
DB_TITAN = 'titan'
DB_RADIUS = 'radius'

NOACTIVE_PREFIX = 'Noactive__'
DAYS_THRESHOLD = 3  # 가입 후 N일 경과

# 이메일 설정
EMAIL_TO = 'softcan@naver.com'
_SETTINGS_LOCAL = os.path.join(SCRIPT_DIR, '..', 'main', 'settings_local.py')
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 465
SMTP_EMAIL = ''
SMTP_USER = ''
SMTP_PASS = ''
try:
    _ns = {}
    with open(_SETTINGS_LOCAL) as _f:
        exec(_f.read(), _ns)
    SMTP_HOST = _ns.get('SMTP_HOST', SMTP_HOST)
    SMTP_PORT = _ns.get('SMTP_PORT', SMTP_PORT)
    SMTP_EMAIL = _ns.get('SMTP_EMAIL', '')
    SMTP_USER = _ns.get('SMTP_ID', '')
    SMTP_PASS = _ns.get('SMTP_PW', '')
except Exception:
    pass

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'noactive_user_cleanup.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def get_db(db_name):
    return MySQLdb.connect(
        host=DB_HOST, user=DB_USER, passwd=DB_PASS,
        db=db_name, charset='utf8mb4', use_unicode=True,
    )


def get_db_raw(db_name):
    """인코딩 깨진 데이터 읽기용 latin1 연결"""
    return MySQLdb.connect(
        host=DB_HOST, user=DB_USER, passwd=DB_PASS,
        db=db_name, charset='latin1', use_unicode=False,
    )


def find_noactive_users():
    """가입 후 3일 경과, 비활성(is_active=0), 삭제 아닌, 미처리 회원 조회"""
    db = get_db(DB_TITAN)
    cur = db.cursor()
    cutoff = (datetime.now() - timedelta(days=DAYS_THRESHOLD)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        SELECT id, email, username, regist_date
        FROM tbl_user
        WHERE is_active = 0
          AND delete_yn = 'N'
          AND email NOT LIKE 'Noactive\\_\\_%%'
          AND email NOT LIKE 'delete\\_\\_%%'
          AND regist_date <= %s
        ORDER BY id
    """, [cutoff])
    rows = []
    for r in cur.fetchall():
        try:
            email = str(r[1]) if r[1] else ''
            uname = str(r[2]) if r[2] else ''
            rows.append({'id': r[0], 'email': email, 'username': uname, 'regist_date': r[3]})
        except Exception:
            pass
    cur.close()
    db.close()
    return rows


def process_noactive_users(users, dry_run=False):
    """비활성 회원 이메일을 Noactive__원래이메일#타임스탬프로 변경"""
    if not users:
        log.info('처리 대상 비활성 회원 없음')
        return []

    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    processed = []

    db_titan = get_db(DB_TITAN)
    db_radius = get_db(DB_RADIUS)
    cur_titan = db_titan.cursor()
    cur_radius = db_radius.cursor()

    try:
        for user in users:
            uid = user['id']
            email = user['email']
            new_email = f"{NOACTIVE_PREFIX}{email}#{now_str}"

            if dry_run:
                log.info(f'[DRY-RUN] #{uid} {email} ({user["username"]}) → {new_email}')
                processed.append({'id': uid, 'email': email, 'username': user['username'], 'new_email': new_email})
                continue

            # tbl_user 업데이트
            cur_titan.execute("""
                UPDATE tbl_user SET email = %s WHERE id = %s
            """, [new_email, uid])

            # radcheck 업데이트 (username = 기존 이메일)
            cur_radius.execute("""
                UPDATE radcheck SET username = %s WHERE username = %s
            """, [new_email, email])

            log.info(f'처리: #{uid} {email} ({user["username"]}) → {new_email}')
            processed.append({'id': uid, 'email': email, 'username': user['username'], 'new_email': new_email})

        if not dry_run:
            db_titan.commit()
            db_radius.commit()
            log.info(f'총 {len(processed)}건 커밋 완료')

    except Exception as e:
        log.error(f'처리 중 오류: {e}')
        if not dry_run:
            db_titan.rollback()
            db_radius.rollback()
        raise
    finally:
        cur_titan.close()
        cur_radius.close()
        db_titan.close()
        db_radius.close()

    return processed


def cleanup_app_login_logs(processed, dry_run=False):
    """Noactive 처리된 회원의 앱로그인로그(tbl_device_info) 삭제"""
    if not processed:
        return 0
    log.info('===== 앱로그인로그 정리 시작 =====')
    user_ids = [p['id'] for p in processed]
    db = get_db(DB_TITAN)
    cur = db.cursor()
    try:
        ph = ','.join(['%s'] * len(user_ids))
        if dry_run:
            cur.execute(f"SELECT COUNT(*) FROM tbl_device_info WHERE user_id IN ({ph})", user_ids)
            cnt = cur.fetchone()[0]
            log.info(f'[DRY-RUN] 앱로그인로그 삭제 대상: {cnt}건')
            return cnt
        cur.execute(f"DELETE FROM tbl_device_info WHERE user_id IN ({ph})", user_ids)
        deleted = cur.rowcount
        db.commit()
        log.info(f'앱로그인로그 {deleted}건 삭제 완료')
        return deleted
    except Exception as e:
        log.error(f'앱로그인로그 정리 오류: {e}')
        db.rollback()
        return 0
    finally:
        cur.close()
        db.close()


def cleanup_connection_logs(processed, dry_run=False):
    """Noactive 처리된 회원의 접속로그(radacct) 삭제"""
    if not processed:
        return 0
    log.info('===== 접속로그 정리 시작 =====')
    emails = [p['email'] for p in processed]
    db = get_db(DB_RADIUS)
    cur = db.cursor()
    try:
        ph = ','.join(['%s'] * len(emails))
        if dry_run:
            cur.execute(f"SELECT COUNT(*) FROM radacct WHERE username IN ({ph})", emails)
            cnt = cur.fetchone()[0]
            log.info(f'[DRY-RUN] 접속로그 삭제 대상: {cnt}건')
            return cnt
        cur.execute(f"DELETE FROM radacct WHERE username IN ({ph})", emails)
        deleted = cur.rowcount
        db.commit()
        log.info(f'접속로그 {deleted}건 삭제 완료')
        return deleted
    except Exception as e:
        log.error(f'접속로그 정리 오류: {e}')
        db.rollback()
        return 0
    finally:
        cur.close()
        db.close()


def cleanup_fail_logs(processed, dry_run=False):
    """Noactive 처리된 회원의 접속실패로그(tbl_agent_failed) 삭제"""
    if not processed:
        return 0
    log.info('===== 접속실패로그 정리 시작 =====')
    emails = [p['email'] for p in processed]
    db = get_db(DB_TITAN)
    cur = db.cursor()
    try:
        ph = ','.join(['%s'] * len(emails))
        if dry_run:
            cur.execute(f"SELECT COUNT(*) FROM tbl_agent_failed WHERE username IN ({ph})", emails)
            cnt = cur.fetchone()[0]
            log.info(f'[DRY-RUN] 접속실패로그 삭제 대상: {cnt}건')
            return cnt
        cur.execute(f"DELETE FROM tbl_agent_failed WHERE username IN ({ph})", emails)
        deleted = cur.rowcount
        db.commit()
        log.info(f'접속실패로그 {deleted}건 삭제 완료')
        return deleted
    except Exception as e:
        log.error(f'접속실패로그 정리 오류: {e}')
        db.rollback()
        return 0
    finally:
        cur.close()
        db.close()


def cleanup_disconnect_logs(processed, dry_run=False):
    """Noactive 처리된 회원의 강제종료로그(tbl_disconnection) 삭제"""
    if not processed:
        return 0
    log.info('===== 강제종료로그 정리 시작 =====')
    emails = [p['email'] for p in processed]
    db = get_db(DB_TITAN)
    cur = db.cursor()
    try:
        ph = ','.join(['%s'] * len(emails))
        if dry_run:
            cur.execute(f"SELECT COUNT(*) FROM tbl_disconnection WHERE username IN ({ph})", emails)
            cnt = cur.fetchone()[0]
            log.info(f'[DRY-RUN] 강제종료로그 삭제 대상: {cnt}건')
            return cnt
        cur.execute(f"DELETE FROM tbl_disconnection WHERE username IN ({ph})", emails)
        deleted = cur.rowcount
        db.commit()
        log.info(f'강제종료로그 {deleted}건 삭제 완료')
        return deleted
    except Exception as e:
        log.error(f'강제종료로그 정리 오류: {e}')
        db.rollback()
        return 0
    finally:
        cur.close()
        db.close()


def send_report_email(processed, expired_closed=0, log_counts=None):
    """처리 결과 이메일 발송"""
    if log_counts is None:
        log_counts = {}
    total_activity = len(processed) + expired_closed + sum(log_counts.values())
    if not total_activity or not SMTP_EMAIL or not SMTP_PASS:
        return

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_total = sum(log_counts.values())
    subject = f'[TitanVPN] 회원 정리 - Noactive {len(processed)}건 / 만료세션 {expired_closed}건 / 로그삭제 {log_total}건'

    html = f'''
    <html><body style="font-family:Arial,sans-serif;font-size:14px;">
    <h2 style="color:#333;">자동 회원 정리 결과</h2>
    <p>실행 시간: {now}</p>
    '''

    if processed:
        html += f'''
    <h3>1. 비활성 회원 Noactive 처리: <b>{len(processed)}건</b></h3>
    <p>(가입 후 {DAYS_THRESHOLD}일 초과 비활성 회원)</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
    <tr style="background:#f0f0f0;"><th>#</th><th>ID</th><th>이름</th><th>기존 이메일</th><th>변경 이메일</th></tr>
    '''
        for i, p in enumerate(processed[:50], 1):
            html += f'<tr><td>{i}</td><td>{p["id"]}</td><td>{p.get("username","")}</td><td>{p["email"]}</td><td style="color:#856404;">{p["new_email"]}</td></tr>'
        if len(processed) > 50:
            html += f'<tr><td colspan="5" style="text-align:center;color:#888;">... 외 {len(processed)-50}건</td></tr>'
        html += '</table>'

    if expired_closed:
        html += f'''
    <h3>2. 만료 유저 radacct NULL 세션 정리: <b>{expired_closed}건</b></h3>
    <p>Expiration 만료된 유저의 미종료 세션(acctstoptime IS NULL)을 일괄 close 처리했습니다.</p>
    '''

    if log_counts:
        html += '''
    <h3>3. Noactive 회원 로그 삭제</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
    <tr style="background:#f0f0f0;"><th>로그 유형</th><th>삭제 건수</th></tr>
    '''
        log_labels = {
            'app_login': '앱로그인로그 (tbl_device_info)',
            'connection': '접속로그 (radacct)',
            'fail': '접속실패로그 (tbl_agent_failed)',
            'disconnect': '강제종료로그 (tbl_disconnection)',
        }
        for key, label in log_labels.items():
            cnt = log_counts.get(key, 0)
            if cnt:
                html += f'<tr><td>{label}</td><td style="text-align:right;">{cnt}</td></tr>'
        html += f'<tr style="background:#f0f0f0;"><td><b>합계</b></td><td style="text-align:right;"><b>{log_total}</b></td></tr>'
        html += '</table>'

    html += '<br><p style="color:#888;font-size:12px;">자동 발송 메일입니다.</p>'
    html += '</body></html>'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = EMAIL_TO
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_EMAIL, [EMAIL_TO], msg.as_string())
        log.info(f'리포트 이메일 전송 완료 → {EMAIL_TO}')
    except Exception as e:
        log.error(f'이메일 전송 실패: {e}')


def cleanup_expired_user_sessions(dry_run=False):
    """만료(Expiration 지남) 유저의 radacct NULL 세션을 일괄 close 처리"""
    log.info('===== 만료 유저 NULL 세션 정리 시작 =====')

    db = get_db_raw(DB_RADIUS)
    cur = db.cursor()

    try:
        # 1. radcheck Expiration 전체 조회 → Python에서 만료 필터
        cur.execute("SELECT username, value FROM radcheck WHERE attribute = 'Expiration'")
        now = datetime.now()
        expired_users = set()
        for row in cur.fetchall():
            try:
                username = row[0].decode('utf-8', errors='replace') if isinstance(row[0], bytes) else str(row[0])
                exp_str = row[1].decode('utf-8', errors='replace') if isinstance(row[1], bytes) else str(row[1])
                exp_date = datetime.strptime(exp_str.replace(' KST', ''), '%d %b %Y %H:%M:%S')
                if exp_date < now:
                    expired_users.add(username)
            except Exception:
                pass

        if not expired_users:
            log.info('만료 유저 없음')
            return 0

        # 2. NULL 세션 전체 조회 → 만료 유저 필터
        cur.execute("SELECT radacctid, username, nasporttype FROM radacct WHERE acctstoptime IS NULL")
        to_close = []
        for row in cur.fetchall():
            try:
                rid = row[0]
                uname = row[1].decode('utf-8', errors='replace') if isinstance(row[1], bytes) else str(row[1])
                pt = row[2].decode('utf-8', errors='replace') if isinstance(row[2], bytes) else str(row[2])
                if uname in expired_users:
                    to_close.append((rid, uname, pt))
            except Exception:
                pass

        if not to_close:
            log.info('만료 유저의 NULL 세션 없음')
            return 0

        log.info(f'만료 유저 NULL 세션: {len(to_close)}건 발견')

        if dry_run:
            from collections import Counter
            pt_count = Counter(t[2] for t in to_close)
            for pt, cnt in pt_count.most_common():
                log.info(f'  [DRY-RUN] {pt}: {cnt}건')
            return len(to_close)

        # 3. 배치 UPDATE
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        ids = [t[0] for t in to_close]
        batch_size = 100
        total_updated = 0
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            ph = ','.join(['%s'] * len(batch))
            cur.execute(
                f"UPDATE radacct SET acctstoptime = %s WHERE radacctid IN ({ph})",
                [now_str] + batch
            )
            total_updated += cur.rowcount
        db.commit()

        from collections import Counter
        pt_count = Counter(t[2] for t in to_close)
        for pt, cnt in pt_count.most_common():
            log.info(f'  {pt}: {cnt}건 close')

        log.info(f'만료 유저 NULL 세션 {total_updated}건 정리 완료')
        return total_updated

    except Exception as e:
        log.error(f'만료 유저 세션 정리 오류: {e}')
        db.rollback()
        return 0
    finally:
        cur.close()
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='비활성 회원 정리 (Noactive_ 처리)')
    parser.add_argument('--dry-run', action='store_true', help='실제 변경 없이 대상만 확인')
    parser.add_argument('--no-email', action='store_true', help='이메일 발송 안함')
    args = parser.parse_args()

    # 1) 비활성 회원 Noactive_ 처리
    log.info(f'===== 비활성 회원 정리 시작 (dry_run={args.dry_run}) =====')

    users = find_noactive_users()
    log.info(f'대상 회원: {len(users)}건')

    processed = []
    if users:
        processed = process_noactive_users(users, dry_run=args.dry_run)

    # 2) Noactive 처리된 회원 로그 삭제
    log_counts = {}
    if processed:
        log_counts['app_login'] = cleanup_app_login_logs(processed, dry_run=args.dry_run)
        log_counts['connection'] = cleanup_connection_logs(processed, dry_run=args.dry_run)
        log_counts['fail'] = cleanup_fail_logs(processed, dry_run=args.dry_run)
        log_counts['disconnect'] = cleanup_disconnect_logs(processed, dry_run=args.dry_run)

    # 3) 만료 유저 radacct NULL 세션 정리
    expired_closed = cleanup_expired_user_sessions(dry_run=args.dry_run)

    # 4) 이메일 리포트
    log_total = sum(log_counts.values())
    if (processed or expired_closed or log_total) and not args.dry_run and not args.no_email:
        send_report_email(processed, expired_closed, log_counts)

    log.info(f'===== 완료: Noactive {len(processed)}건, 로그삭제 {log_total}건, 만료세션 {expired_closed}건 =====')


if __name__ == '__main__':
    main()
