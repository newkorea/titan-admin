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

    # NOTE: 결제 요약 섹션은 요구사항과 맞지 않아 제거했습니다.

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

    # PING < 0 (unreachable) NAS 목록
    try:
        with connections['default'].cursor() as cur:
            cur.execute("SHOW COLUMNS FROM titan.tbl_agent3")
            cols = {r[0] for r in cur.fetchall()}
        if 'ping' in cols:
            with connections['default'].cursor() as cur:
                cur.execute(
                    '''
                    SELECT id, name, hostdomain, hostip, telecom, ping
                    FROM titan.tbl_agent3
                    WHERE ping < 0
                    ORDER BY ping ASC, id DESC
                    LIMIT 50
                    '''
                )
                context['bad_ping_agents'] = _dictfetchall(cur)
        else:
            context['bad_ping_agents'] = []
    except Exception:
        context['bad_ping_agents'] = []

    return render(request, 'admin/dashboard.html', context)
