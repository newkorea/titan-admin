#!/usr/bin/env python3
"""
자동결제 크론 스크립트
- 매일 9AM KST 실행 (cron: 0 9 * * *)
- tbl_autopay에서 active && next_pay_date <= NOW() 인 건을 찾아 빌키로 결제 실행
- 성공 시 서비스 시간 연장 + 다음 결제일 갱신
- 3회 연속 실패 시 자동 해지

사용법:
  cd /home/newkorea/project/titan && source .venv310/bin/activate
  DJANGO_SETTINGS_MODULE=main.settings python3 /home/newkorea/project/scripts/autopay_cron.py
  옵션: --dry-run (미리보기만), --force (next_pay_date 무시하고 전체 실행)
"""

import os
import sys
import json
import datetime
import uuid
import argparse
import logging

# Django 설정
sys.path.insert(0, '/home/newkorea/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

from django.db import connections
from django.conf import settings
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.views import giveServiceTime
from backend.models import TblUser, TblPriceHistory

# 로깅 설정
LOG_FILE = '/home/newkorea/project/scripts/autopay.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('autopay')

MAX_FAIL_COUNT = 3  # 연속 실패 허용 횟수


def get_pending_autopays(force=False):
    """결제 대상 자동결제 건 조회"""
    cursor = connections['default'].cursor()
    if force:
        cursor.execute('''
            SELECT a.id, a.user_id, a.billkey, a.pgcode, a.session, a.month_type,
                   a.product_name, a.amount, a.fail_count, a.next_pay_date,
                   u.email, u.username
            FROM tbl_autopay a
            JOIN tbl_user u ON a.user_id = u.id
            WHERE a.status = 'active'
            ORDER BY a.id
        ''')
    else:
        cursor.execute('''
            SELECT a.id, a.user_id, a.billkey, a.pgcode, a.session, a.month_type,
                   a.product_name, a.amount, a.fail_count, a.next_pay_date,
                   u.email, u.username
            FROM tbl_autopay a
            JOIN tbl_user u ON a.user_id = u.id
            WHERE a.status = 'active' AND a.next_pay_date <= NOW()
            ORDER BY a.id
        ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_order_number(user_id):
    """주문번호 생성"""
    now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return '%s_%s' % (user_id, now)


def create_custom_parameter(session, month_type):
    """커스텀 파라미터 생성 (autopay 표시 포함)"""
    return '%s_%s_autopay' % (session, month_type)


def execute_autopay(ap, dry_run=False):
    """단일 자동결제 실행"""
    autopay_id = ap['id']
    user_id = ap['user_id']
    billkey = ap['billkey']
    session = ap['session']
    month_type = ap['month_type']
    amount = ap['amount']
    email = ap['email']
    username = ap['username']
    product_name = ap['product_name'] or 'TITAN NETWORKS 자동결제'

    logger.info('처리 시작: autopay_id=%d, user_id=%d (%s), amount=%d, session=%d, month=%d',
                autopay_id, user_id, email, amount, session, month_type)

    if dry_run:
        logger.info('  [DRY-RUN] 건너뜀')
        return True

    order_no = create_order_number(user_id)
    custom_parameter = create_custom_parameter(session, month_type)

    cursor = connections['default'].cursor()

    try:
        # 페이레터 자동결제 API 호출
        p = Payletter(settings.PAYLETTER_MODE)
        status_code, response_text = p.autopay_payment(
            billkey=billkey,
            user_id=str(user_id),
            user_name=username,
            price=amount,
            product_name=product_name,
            order_no=order_no,
            custom_parameter=custom_parameter,
            email=email
        )

        response = json.loads(response_text)
        tid = response.get('tid', '')
        code = response.get('code', -1)

        if status_code == 200 and code == 0:
            # 결제 성공
            logger.info('  결제 성공: tid=%s', tid)

            # 콜백에서 이미 giveServiceTime을 처리할 수도 있지만,
            # autopay API는 callback_url을 호출하므로 콜백에서 처리됨.
            # 여기서는 tbl_autopay만 업데이트

            from dateutil.relativedelta import relativedelta
            next_pay = datetime.datetime.now() + relativedelta(months=int(month_type))

            cursor.execute('''
                UPDATE tbl_autopay
                SET last_paid_date = NOW(), next_pay_date = %s, fail_count = 0
                WHERE id = %s
            ''', [next_pay, autopay_id])

            # 성공 로그
            cursor.execute('''
                INSERT INTO tbl_autopay_log (autopay_id, user_id, tid, amount, status, created_date)
                VALUES (%s, %s, %s, %s, 'success', NOW())
            ''', [autopay_id, user_id, tid, amount])

            return True
        else:
            # 결제 실패
            error_msg = response.get('message', response_text[:200])
            logger.warning('  결제 실패: code=%s, message=%s', code, error_msg)

            new_fail_count = ap['fail_count'] + 1

            if new_fail_count >= MAX_FAIL_COUNT:
                # 3회 연속 실패 → 자동 해지
                cursor.execute('''
                    UPDATE tbl_autopay
                    SET status = 'failed', fail_count = %s, cancelled_date = NOW()
                    WHERE id = %s
                ''', [new_fail_count, autopay_id])
                logger.warning('  %d회 연속 실패 → 자동 해지: autopay_id=%d', new_fail_count, autopay_id)
            else:
                cursor.execute('''
                    UPDATE tbl_autopay SET fail_count = %s WHERE id = %s
                ''', [new_fail_count, autopay_id])

            # 실패 로그
            cursor.execute('''
                INSERT INTO tbl_autopay_log (autopay_id, user_id, tid, amount, status, error_message, created_date)
                VALUES (%s, %s, %s, %s, 'fail', %s, NOW())
            ''', [autopay_id, user_id, tid, amount, error_msg])

            return False

    except Exception as e:
        logger.error('  예외 발생: %s', str(e))
        cursor.execute('''
            INSERT INTO tbl_autopay_log (autopay_id, user_id, tid, amount, status, error_message, created_date)
            VALUES (%s, %s, '', %s, 'fail', %s, NOW())
        ''', [autopay_id, user_id, amount, str(e)])
        return False


def main():
    parser = argparse.ArgumentParser(description='자동결제 크론 스크립트')
    parser.add_argument('--dry-run', action='store_true', help='미리보기만 (실제 결제 안 함)')
    parser.add_argument('--force', action='store_true', help='next_pay_date 무시하고 active 전체 실행')
    args = parser.parse_args()

    logger.info('========== 자동결제 크론 시작 ==========')
    logger.info('모드: %s', 'DRY-RUN' if args.dry_run else ('FORCE' if args.force else 'NORMAL'))

    pending = get_pending_autopays(force=args.force)
    logger.info('결제 대상: %d건', len(pending))

    if not pending:
        logger.info('처리할 건이 없습니다.')
        return

    success_count = 0
    fail_count = 0

    for ap in pending:
        result = execute_autopay(ap, dry_run=args.dry_run)
        if result:
            success_count += 1
        else:
            fail_count += 1

    logger.info('========== 자동결제 완료: 성공 %d, 실패 %d ==========', success_count, fail_count)


if __name__ == '__main__':
    main()
