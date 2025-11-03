import json
from django.shortcuts import render  # ✅ djangomako 제거
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from datetime import datetime, timedelta


def _dictfetchall(cur):
    """Return all rows from a cursor as a list of dicts."""
    cols = [col[0] for col in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

# 대쉬보드 렌더링 (2020-03-16)
# @allow_admin
def dashboard(request):
    context = {}

    # 최근 무통장 결제 내역 3개 리스트 (요청/승인/취소·환불)
    with connections['default'].cursor() as cur:
        # 요청 대기 (R)
        cur.execute(
            '''
            SELECT  x.id,
                    y.username,
                    y.email,
                    x.product_name,
                    x.krw,
                    DATE_FORMAT(x.regist_date, "%Y-%m-%d %H:%i") AS dt,
                    UPPER(TRIM(x.status)) AS status
            FROM tbl_send_history x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE UPPER(TRIM(x.status)) = 'R'
            ORDER BY x.regist_date DESC
            LIMIT 10;
            '''
        )
        context['list_pending'] = _dictfetchall(cur)

        # 승인 완료 (A,S)
        cur.execute(
            '''
            SELECT  x.id,
                    y.username,
                    y.email,
                    x.product_name,
                    x.krw,
                    DATE_FORMAT(COALESCE(x.accept_date, x.api_date, x.regist_date), "%Y-%m-%d %H:%i") AS dt,
                    UPPER(TRIM(x.status)) AS status
            FROM tbl_send_history x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE UPPER(TRIM(x.status)) IN ('A','S')
            ORDER BY COALESCE(x.accept_date, x.api_date, x.regist_date) DESC
            LIMIT 10;
            '''
        )
        context['list_approved'] = _dictfetchall(cur)

        # 취소 / 환불 (C,Z)
        cur.execute(
            '''
            SELECT  x.id,
                    y.username,
                    y.email,
                    x.product_name,
                    x.krw,
                    DATE_FORMAT(COALESCE(x.cancel_date, x.refund_date, x.regist_date), "%Y-%m-%d %H:%i") AS dt,
                    UPPER(TRIM(x.status)) AS status
            FROM tbl_send_history x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE UPPER(TRIM(x.status)) IN ('C','Z')
            ORDER BY COALESCE(x.cancel_date, x.refund_date, x.regist_date) DESC
            LIMIT 10;
            '''
        )
        context['list_canceled'] = _dictfetchall(cur)

    # Top 10 (last 24h) — 로그인 시도, 접속 실패, 강제 종료
    with connections['default'].cursor() as cur:
        # 최근 24시간 기준 시각 (DB 비교를 위해 NOW() 사용 가능하나, 파라미터 바인딩으로 전달)
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(hours=24)

        # 1) 앱 로그인 시도 상위 10 — tbl_device_info
        cur.execute(
            '''
            SELECT COALESCE(y.email, y.username) AS email,
                   COUNT(*) AS cnt
            FROM tbl_device_info x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE x.login_time >= %s
            GROUP BY COALESCE(y.email, y.username)
            ORDER BY cnt DESC
            LIMIT 10;
            ''', [since]
        )
        context['top_login_24h'] = _dictfetchall(cur)

        # 2) 서버 접속 실패 상위 10 — tbl_agent_failed
        cur.execute(
            '''
            SELECT username AS email,
                   COUNT(*) AS cnt
            FROM tbl_agent_failed
            WHERE failed_time >= %s
              AND IFNULL(username, '') <> ''
            GROUP BY username
            ORDER BY cnt DESC
            LIMIT 10;
            ''', [since]
        )
        context['top_failed_24h'] = _dictfetchall(cur)

        # 3) 강제 종료 상위 10 — tbl_disconnection
        cur.execute(
            '''
            SELECT username AS email,
                   COUNT(*) AS cnt
            FROM tbl_disconnection
            WHERE disconnected_time >= %s
              AND IFNULL(username, '') <> ''
            GROUP BY username
            ORDER BY cnt DESC
            LIMIT 10;
            ''', [since]
        )
        context['top_force_24h'] = _dictfetchall(cur)

    return render(request, 'admin/dashboard.html', context)
