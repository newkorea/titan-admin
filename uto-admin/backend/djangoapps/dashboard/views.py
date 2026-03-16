# 대시보드 — 메인 대시보드 페이지, 요약 통계 데이터
import json
import re
from django.shortcuts import render
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

    with connections['default'].cursor() as cur:
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

    # ── NAS 서버 현황 요약 (tbl_nas_monitor_log 기반) ──
    # 기존 실시간 ping 제거: 매 페이지 로드마다 200대 ping → 느리고 불필요
    # 이제 nas_daily_check.py / nas_monitor.py 가 주기적으로 점검한 결과를 DB에서 읽음
    try:
        with connections['default'].cursor() as cur:
            # 최근 health 점검 결과
            cur.execute('''
                SELECT check_time, total_servers, ok_count, warning_count, critical_count, report_json
                FROM tbl_nas_monitor_log
                WHERE check_type = 'health'
                ORDER BY check_time DESC
                LIMIT 1
            ''')
            health_row = _dictfetchall(cur)

            # 최근 service 점검 결과
            cur.execute('''
                SELECT check_time, total_servers, ok_count, warning_count, critical_count, report_json
                FROM tbl_nas_monitor_log
                WHERE check_type = 'service'
                ORDER BY check_time DESC
                LIMIT 1
            ''')
            service_row = _dictfetchall(cur)

        # health 점검 결과에서 이슈 서버 추출
        issue_servers = []
        health_check_time = None
        health_summary = {'total': 0, 'ok': 0, 'warning': 0, 'critical': 0}

        if health_row:
            h = health_row[0]
            health_check_time = h['check_time']
            health_summary = {
                'total': h['total_servers'],
                'ok': h['ok_count'],
                'warning': h['warning_count'],
                'critical': h['critical_count'],
            }
            try:
                report = json.loads(h['report_json']) if isinstance(h['report_json'], str) else h['report_json']
                for srv in report.get('servers', []):
                    status = srv.get('status', 'ok')
                    if status in ('warning', 'critical'):
                        issues = srv.get('warnings', []) + srv.get('criticals', [])
                        issue_servers.append({
                            'name': srv.get('name', ''),
                            'ip': srv.get('ip', ''),
                            'status': status,
                            'disk': srv.get('disk_used', ''),
                            'mem': srv.get('mem_used', ''),
                            'cpu_load': srv.get('cpu_load', ''),
                            'ping': srv.get('ping_ms', ''),
                            'connections': srv.get('connections', 0),
                            'issues': ', '.join(issues[:3]),  # 최대 3개 이슈
                        })
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        # service 점검 결과에서 장애 서버 추출
        service_issues = []
        service_check_time = None
        service_summary = {'total': 0, 'ok': 0, 'warning': 0, 'critical': 0}

        if service_row:
            s = service_row[0]
            service_check_time = s['check_time']
            service_summary = {
                'total': s['total_servers'],
                'ok': s['ok_count'],
                'warning': s.get('warning_count', 0),
                'critical': s['critical_count'],
            }
            try:
                report = json.loads(s['report_json']) if isinstance(s['report_json'], str) else s['report_json']
                for srv in report.get('servers', []):
                    failed = srv.get('failed_services', [])
                    if failed:
                        service_issues.append({
                            'name': srv.get('name', ''),
                            'ip': srv.get('ip', ''),
                            'failed': ', '.join(failed),
                        })
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        context['health_summary'] = health_summary
        context['health_check_time'] = health_check_time
        context['issue_servers'] = issue_servers
        context['service_summary'] = service_summary
        context['service_check_time'] = service_check_time
        context['service_issues'] = service_issues
    except Exception:
        context['health_summary'] = {'total': 0, 'ok': 0, 'warning': 0, 'critical': 0}
        context['health_check_time'] = None
        context['issue_servers'] = []
        context['service_summary'] = {'total': 0, 'ok': 0, 'warning': 0, 'critical': 0}
        context['service_check_time'] = None
        context['service_issues'] = []

    # ── 현재 접속자 수 요약 ──
    try:
        with connections['default'].cursor() as cur:
            cur.execute('''
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN nasporttype='Virtual' THEN 1 ELSE 0 END) AS ikev2,
                    SUM(CASE WHEN nasporttype='ISDN' THEN 1 ELSE 0 END) AS openvpn,
                    SUM(CASE WHEN nasporttype='V2RAY' THEN 1 ELSE 0 END) AS v2ray,
                    SUM(CASE WHEN nasporttype='61' THEN 1 ELSE 0 END) AS softether
                FROM radius.radacct
                WHERE acctstoptime IS NULL
            ''')
            conn_row = _dictfetchall(cur)
            if conn_row:
                r = conn_row[0]
                context['conn_summary'] = {
                    'total': int(r.get('total') or 0),
                    'ikev2': int(r.get('ikev2') or 0),
                    'openvpn': int(r.get('openvpn') or 0),
                    'v2ray': int(r.get('v2ray') or 0),
                    'softether': int(r.get('softether') or 0),
                }
            else:
                context['conn_summary'] = {'total': 0, 'ikev2': 0, 'openvpn': 0, 'v2ray': 0, 'softether': 0}
    except Exception:
        context['conn_summary'] = {'total': 0, 'ikev2': 0, 'openvpn': 0, 'v2ray': 0, 'softether': 0}

    return render(request, 'admin/dashboard.html', context)
