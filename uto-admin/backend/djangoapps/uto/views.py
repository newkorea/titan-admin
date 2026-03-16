# UTO VPN 관리 — 별도 DB(vcsvpn2013)를 사용하는 독립 모듈
# titan-admin 기존 코드에 영향 없음
import base64
import calendar
import hashlib as hashlib_mod
import hmac as hmac_mod
import json
import os
import tempfile
import traceback
import subprocess
import threading
import time
import uuid as uuid_mod
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import connections
from backend.djangoapps.common.views import allow_admin, dictfetchall


# ============================================================
# UTO DB 헬퍼 — 'uto' / 'uto_radius' 커넥션만 사용
# ============================================================
def _uto_cursor():
    """vcsvpn2013 DB 커서"""
    return connections['uto'].cursor()

def _next_uto_port(cur):
    """다음 사용 가능한 port 번호 반환 (중복 방지)"""
    cur.execute("SELECT COALESCE(MAX(port), 40000) + 1 FROM vpnuser WHERE port IS NOT NULL AND port > 0")
    next_port = cur.fetchone()[0]
    # 혹시 이미 존재하면 빈 번호 탐색
    cur.execute("SELECT port FROM vpnuser WHERE port = %s", [next_port])
    if cur.fetchone():
        cur.execute("""SELECT t.port + 1 AS next_port
                       FROM vpnuser t LEFT JOIN vpnuser t2 ON t.port + 1 = t2.port
                       WHERE t.port >= 40000 AND t2.port IS NULL
                       ORDER BY t.port LIMIT 1""")
        row = cur.fetchone()
        next_port = row[0] if row else next_port + 1
    return next_port

def _uto_radius_cursor():
    """UTO radius DB 커서"""
    return connections['uto_radius'].cursor()


# ============================================================
# [render] UTO 회원 관리 페이지
# ============================================================
@allow_admin
def uto_user(request):
    # groups 코드 목록 (필터용)
    groups_list = [
        {'code': '', 'name': '전체'},
        {'code': 'BY', 'name': 'BY (월정액)'},
        {'code': 'LL', 'name': 'LL (트래픽)'},
        {'code': 'NEW', 'name': 'NEW (신규)'},
    ]
    # 상태 코드
    kz_list = [
        {'code': '', 'name': '전체'},
        {'code': '1', 'name': '정상'},
        {'code': '2', 'name': '차단'},
    ]
    # game 코드 (서비스 유형)
    game_list = [
        {'code': '', 'name': '전체'},
        {'code': 'KOREA', 'name': 'KOREA'},
        {'code': 'SS', 'name': 'SS'},
    ]
    context = {
        'groups_list': groups_list,
        'kz_list': kz_list,
        'game_list': game_list,
    }
    return render(request, 'admin/uto_user.html', context)


# ============================================================
# [api] UTO 회원 통계
# ============================================================
@allow_admin
def api_read_uto_user_count(request):
    try:
        tbl = 'vpnuser202603' if request.POST.get('use_backup') == '1' else 'vpnuser'

        # 관리자/대리점 권한 필터
        role = request.session.get('role', 1)
        dealer_name = request.session.get('dealer_name', '')
        dealer_filter = ''
        dealer_params = []
        if role != 1 and dealer_name:
            dealer_filter = ' AND member = %s AND lastdate BETWEEN DATE_SUB(NOW(), INTERVAL 7 DAY) AND DATE_ADD(NOW(), INTERVAL 7 DAY)'
            dealer_params = [dealer_name]

        with _uto_cursor() as cur:
            # 전체
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE 1=1{dealer_filter}", dealer_params)
            total = cur.fetchone()[0]

            # 정상 (kz=1)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE kz = 1{dealer_filter}", dealer_params)
            active = cur.fetchone()[0]

            # 차단 (kz=2)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE kz = 2{dealer_filter}", dealer_params)
            blocked = cur.fetchone()[0]

            # 접속중
            if role != 1 and dealer_name:
                cur.execute("""SELECT COUNT(DISTINCT r.username) FROM radacct r
                    INNER JOIN vpnuser v ON r.username = v.vuser
                    WHERE r.acctstoptime IS NULL AND v.member = %s
                    AND v.lastdate BETWEEN DATE_SUB(NOW(), INTERVAL 7 DAY) AND DATE_ADD(NOW(), INTERVAL 7 DAY)""", [dealer_name])
            else:
                cur.execute("SELECT COUNT(DISTINCT username) FROM radacct WHERE acctstoptime IS NULL")
            online = cur.fetchone()[0]

            # 세션 초과
            if role != 1 and dealer_name:
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT r.username, COUNT(*) as cnt, COALESCE(v.`session`, 1) as allowed
                        FROM radacct r
                        LEFT JOIN vpnuser v ON r.username = v.vuser
                        WHERE r.acctstoptime IS NULL AND v.member = %s
                        AND v.lastdate BETWEEN DATE_SUB(NOW(), INTERVAL 7 DAY) AND DATE_ADD(NOW(), INTERVAL 7 DAY)
                        GROUP BY r.username
                        HAVING cnt > allowed
                    ) t
                """, [dealer_name])
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT r.username, COUNT(*) as cnt, COALESCE(v.`session`, 1) as allowed
                        FROM radacct r
                        LEFT JOIN vpnuser v ON r.username = v.vuser
                        WHERE r.acctstoptime IS NULL
                        GROUP BY r.username
                        HAVING cnt > allowed
                    ) t
                """)
            over_session = cur.fetchone()[0]

            # 만료 (lastdate < NOW())
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE lastdate IS NOT NULL AND lastdate < NOW() AND kz = 1{dealer_filter}", dealer_params)
            expired = cur.fetchone()[0]

            # BY(월정액) / LL(트래픽)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE `groups` = 'BY'{dealer_filter}", dealer_params)
            by_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE `groups` = 'LL'{dealer_filter}", dealer_params)
            ll_count = cur.fetchone()[0]

        return JsonResponse({
            'result': 200,
            'total': total,
            'active': active,
            'blocked': blocked,
            'online': online,
            'over_session': over_session,
            'expired': expired,
            'by_count': by_count,
            'll_count': ll_count,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 회원 DataTables
# ============================================================
@allow_admin
def api_read_uto_user_datatables(request):
    try:
        start = int(request.POST.get('start', 0))
        length = int(request.POST.get('length', 10))
        draw = int(request.POST.get('draw', 1))
        orderby_col = int(request.POST.get('order[0][column]', 0))
        orderby_opt = request.POST.get('order[0][dir]', 'desc')

        if orderby_opt not in ('asc', 'desc'):
            orderby_opt = 'desc'

        # 검색 필터
        vuser = request.POST.get('vuser', '')
        groups = request.POST.get('groups', '')
        kz = request.POST.get('kz', '')
        game = request.POST.get('game', '')
        member = request.POST.get('member', '')
        hqq = request.POST.get('hqq', '')
        port = request.POST.get('port', '')

        # WHERE 조건 (v. prefix for JOIN query)
        wc = " WHERE 1=1"
        wc_bare = " WHERE 1=1"  # COUNT 쿼리용 (alias 없음)
        params = []
        if vuser:
            wc += " AND v.vuser LIKE %s"
            wc_bare += " AND vuser LIKE %s"
            params.append(f"%{vuser}%")
        if groups:
            wc += " AND v.`groups` = %s"
            wc_bare += " AND `groups` = %s"
            params.append(groups)
        if kz:
            wc += " AND v.kz = %s"
            wc_bare += " AND kz = %s"
            params.append(kz)
        if game:
            wc += " AND v.game = %s"
            wc_bare += " AND game = %s"
            params.append(game)
        if member:
            wc += " AND v.member LIKE %s"
            wc_bare += " AND member LIKE %s"
            params.append(f"%{member}%")
        if hqq:
            wc += " AND v.hqq LIKE %s"
            wc_bare += " AND hqq LIKE %s"
            params.append(f"%{hqq}%")
        if port:
            wc += " AND v.port = %s"
            wc_bare += " AND port = %s"
            params.append(port)

        # 관리자/대리점 권한 필터 (role != 1: 본인 대리점 회원만 + ±1주 만료 범위)
        role = request.session.get('role', 1)
        dealer_name = request.session.get('dealer_name', '')
        if role != 1 and dealer_name:
            # 검색 필드 사용 시 제한 해제 (아이디/전화번호/포트 검색)
            if vuser or hqq or port:
                pass  # 검색 시 모든 회원 대상 (대리점/만료 필터 미적용)
            else:
                # 대리점 필터: 본인 회원만
                wc += " AND v.member = %s"
                wc_bare += " AND member = %s"
                params.append(dealer_name)
                # 만료 범위: 1주일 전 ~ 1주일 후
                wc += " AND v.lastdate BETWEEN DATE_SUB(NOW(), INTERVAL 7 DAY) AND DATE_ADD(NOW(), INTERVAL 7 DAY)"
                wc_bare += " AND lastdate BETWEEN DATE_SUB(NOW(), INTERVAL 7 DAY) AND DATE_ADD(NOW(), INTERVAL 7 DAY)"

        # 카드 필터
        card_filter = request.POST.get('card_filter', 'all')
        if card_filter == 'active':
            wc += " AND v.kz = 1"
            wc_bare += " AND kz = 1"
        elif card_filter == 'blocked':
            wc += " AND v.kz = 2"
            wc_bare += " AND kz = 2"
        elif card_filter == 'online':
            wc += " AND v.vuser IN (SELECT DISTINCT username FROM radacct WHERE acctstoptime IS NULL)"
            wc_bare += " AND vuser IN (SELECT DISTINCT username FROM radacct WHERE acctstoptime IS NULL)"
        elif card_filter == 'expired':
            wc += " AND v.lastdate < NOW()"
            wc_bare += " AND lastdate < NOW()"
        elif card_filter == 'by':
            wc += " AND v.`groups` = 'BY'"
            wc_bare += " AND `groups` = 'BY'"
        elif card_filter == 'll':
            wc += " AND v.`groups` = 'LL'"
            wc_bare += " AND `groups` = 'LL'"

        tbl = 'vpnuser202603' if request.POST.get('use_backup') == '1' else 'vpnuser'

        # 세션 초과 필터
        if card_filter == 'over_session':
            sub = """ AND v.vuser IN (
                SELECT r.username FROM radacct r
                LEFT JOIN vpnuser v2 ON r.username = v2.vuser
                WHERE r.acctstoptime IS NULL
                GROUP BY r.username, v2.`session`
                HAVING COUNT(*) > COALESCE(v2.`session`, 1)
            )"""
            wc += sub
            wc_bare += sub.replace('v.vuser', 'vuser')

        column_names = ['id', 'vuser', 'groups', 'kz', 'cash', 'lastdate', 'creatdate', 'game', 'member', 'session', 'active_sessions']
        if orderby_col >= len(column_names):
            orderby_col = 0
        order_col = column_names[orderby_col]
        # active_sessions는 서브쿼리 alias, 나머지는 v. prefix
        if order_col == 'active_sessions':
            order_expr = 'ra.active_sessions'
        else:
            order_expr = f'v.`{order_col}`' if order_col in ('groups', 'session') else f'v.{order_col}'

        # Count
        with _uto_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {tbl} {wc_bare}", params)
            total = cur.fetchone()[0]

        # Data
        with _uto_cursor() as cur:
            query = f"""
                SELECT v.id, v.vuser, v.vpass, v.`groups`,
                       v.onlines, v.sess, v.cash,
                       DATE_FORMAT(v.lastdate, '%%Y-%%m-%%d %%H:%%i:%%s') as lastdate,
                       DATE_FORMAT(v.creatdate, '%%Y-%%m-%%d %%H:%%i:%%s') as creatdate,
                       v.game, v.member, v.hyid, v.`session`, v.forcedip, v.kz,
                       v.hmail, v.hqq, v.hmemo,
                       CASE WHEN v.lastdate IS NOT NULL AND v.lastdate < NOW() THEN 1 ELSE 0 END as is_expired,
                       COALESCE(ra.active_sessions, 0) as active_sessions
                FROM {tbl} v
                LEFT JOIN (
                    SELECT username, COUNT(*) as active_sessions
                    FROM radacct WHERE acctstoptime IS NULL
                    GROUP BY username
                ) ra ON v.vuser = ra.username
                {wc}
                ORDER BY {order_expr} {orderby_opt}
                LIMIT %s, %s
            """
            cur.execute(query, params + [start, length])
            rows = dictfetchall(cur)

        return JsonResponse({
            "recordsTotal": total,
            "recordsFiltered": total,
            "draw": draw,
            "data": rows
        })
    except Exception as e:
        traceback.print_exc()
        draw = int(request.POST.get('draw', 1))
        return JsonResponse({
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "draw": draw,
            "data": [],
            "error": str(e)
        })


# ============================================================
# [api] UTO 회원 상세 정보
# ============================================================
@allow_admin
def api_read_uto_user_detail(request):
    try:
        user_id = request.POST.get('user_id')
        vuser = (request.POST.get('vuser') or '').strip()
        with _uto_cursor() as cur:
            if vuser:
                cur.execute("""
                    SELECT v.id, v.vuser, v.vpass, v.`groups`, v.onlines, v.onlines2, v.sess, v.cash, v.`session`,
                           DATE_FORMAT(v.lastdate, '%%Y-%%m-%%d %%H:%%i:%%s') as lastdate,
                           DATE_FORMAT(v.creatdate, '%%Y-%%m-%%d %%H:%%i:%%s') as creatdate,
                           DATE_FORMAT(v.lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                           v.userip, v.nasip, v.vpnip, v.forcedip, v.kz, v.game, v.member, v.hyid,
                           v.hmail, v.hqq, v.hmemo, v.flow, v.vpntype,
                           v.port, v.updk, v.downdk, v.ddh, v.haddr,
                           h.hyname
                    FROM vpnuser v LEFT JOIN hyid h ON v.hyid = h.id
                    WHERE v.vuser = %s
                """, [vuser])
            else:
                cur.execute("""
                    SELECT v.id, v.vuser, v.vpass, v.`groups`, v.onlines, v.onlines2, v.sess, v.cash, v.`session`,
                           DATE_FORMAT(v.lastdate, '%%Y-%%m-%%d %%H:%%i:%%s') as lastdate,
                           DATE_FORMAT(v.creatdate, '%%Y-%%m-%%d %%H:%%i:%%s') as creatdate,
                           DATE_FORMAT(v.lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                           v.userip, v.nasip, v.vpnip, v.forcedip, v.kz, v.game, v.member, v.hyid,
                           v.hmail, v.hqq, v.hmemo, v.flow, v.vpntype,
                           v.port, v.updk, v.downdk, v.ddh, v.haddr,
                           h.hyname
                    FROM vpnuser v LEFT JOIN hyid h ON v.hyid = h.id
                    WHERE v.id = %s
                """, [user_id])
            rows = dictfetchall(cur)

        if not rows:
            return JsonResponse({'result': 404, 'msg': '사용자를 찾을 수 없습니다'})

        return JsonResponse({'result': 200, 'user': rows[0], 'data': rows[0]})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 회원 수정 (비밀번호, 만료일, 상태, 동시접속, 메모 등)
# ============================================================
@allow_admin
def api_update_uto_user(request):
    try:
        user_id = request.POST.get('user_id')
        field = request.POST.get('field')
        value = request.POST.get('value')

        allowed_fields = {
            'vpass': 'vpass',
            'lastdate': 'lastdate',
            'kz': 'kz',
            'hyid': 'hyid',
            'session': 'session',
            'onlines': 'onlines',
            'groups': '`groups`',
            'cash': 'cash',
            'hmemo': 'hmemo',
            'hmail': 'hmail',
            'hqq': 'hqq',
            'haddr': 'haddr',
            'game': 'game',
            'forcedip': 'forcedip',
            # 'port': 가입 시 자동 할당, 수동 변경 금지
            'updk': 'updk',
            'downdk': 'downdk',
        }

        if field not in allowed_fields:
            return JsonResponse({'result': 400, 'msg': f'허용되지 않는 필드: {field}'})

        col = allowed_fields[field]
        admin_user = request.session.get('username', 'unknown')

        with _uto_cursor() as cur:
            # 변경 전 값 조회
            cur.execute(f"SELECT vuser, {col} FROM vpnuser WHERE id = %s", [user_id])
            old_row = cur.fetchone()
            old_vuser = old_row[0] if old_row else 'unknown'
            old_val = old_row[1] if old_row else None

            cur.execute(f"UPDATE vpnuser SET {col} = %s WHERE id = %s", [value, user_id])

            # 변경 로그 기록
            _log_uto_change(old_vuser, 'edit', field, old_val, value, f'{field} 수정', admin_user)

        return JsonResponse({'result': 200, 'msg': '수정 완료'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 회원 차단/해제
# ============================================================
@allow_admin
def api_update_uto_user_block(request):
    try:
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')  # 'block' or 'unblock'

        kz_value = 2 if action == 'block' else 1
        admin_user = request.session.get('username', 'unknown')

        with _uto_cursor() as cur:
            cur.execute("SELECT vuser, kz FROM vpnuser WHERE id = %s", [user_id])
            old_row = cur.fetchone()
            old_vuser = old_row[0] if old_row else 'unknown'
            old_kz = old_row[1] if old_row else None

            cur.execute("UPDATE vpnuser SET kz = %s WHERE id = %s", [kz_value, user_id])

            change_type = 'block' if action == 'block' else 'unblock'
            _log_uto_change(old_vuser, change_type, 'kz', old_kz, kz_value, '차단' if action == 'block' else '해제', admin_user)

        return JsonResponse({'result': 200, 'msg': '차단' if action == 'block' else '해제'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 접속중인 사용자 세션 강제 종료
# ============================================================
@allow_admin
def api_update_uto_user_kick(request):
    try:
        user_id = request.POST.get('user_id')
        admin_user = request.session.get('username', 'unknown')

        with _uto_cursor() as cur:
            cur.execute("SELECT vuser FROM vpnuser WHERE id = %s", [user_id])
            row = cur.fetchone()
            vuser = row[0] if row else 'unknown'

            cur.execute("UPDATE vpnuser SET sess = 0 WHERE id = %s", [user_id])

            _log_uto_change(vuser, 'kick', 'sess', None, 0, '세션 강제 종료', admin_user)

        return JsonResponse({'result': 200, 'msg': '세션 종료 완료'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [render] UTO 서버 관리 페이지
# ============================================================
@allow_admin
def uto_server(request):
    if request.session.get('role', 1) != 1:
        return redirect('/uto_user')
    context = {}
    return render(request, 'admin/uto_server.html', context)


# ============================================================
# [api] UTO 서버 DataTables
# ============================================================
@allow_admin
def api_read_uto_server_datatables(request):
    try:
        start = int(request.POST.get('start', 0))
        length = int(request.POST.get('length', 50))
        draw = int(request.POST.get('draw', 1))
        orderby_col = int(request.POST.get('order[0][column]', 0))
        orderby_opt = request.POST.get('order[0][dir]', 'asc')

        if orderby_opt not in ('asc', 'desc'):
            orderby_opt = 'asc'

        # 필터
        ipname = request.POST.get('ipname', '')
        ip = request.POST.get('ip', '')
        su = request.POST.get('su', '')
        country = request.POST.get('country', '')
        protocol = request.POST.get('protocol', '')

        wc = " WHERE 1=1"
        params = []
        if ipname:
            wc += " AND ipname LIKE %s"
            params.append(f"%{ipname}%")
        if ip:
            wc += " AND ip LIKE %s"
            params.append(f"%{ip}%")
        if su != '':
            wc += " AND su = %s"
            params.append(su)
        if country:
            wc += " AND country = %s"
            params.append(country)
        if protocol:
            wc += " AND protocol = %s"
            params.append(protocol)

        column_names = ['id', 'ipname', 'ip', 'address', 'su', 'country', 'protocol', 'maxnum', 'is_auto']
        if orderby_col >= len(column_names):
            orderby_col = 0
        order_col = column_names[orderby_col]

        with _uto_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM vpnlinek {wc}", params)
            total = cur.fetchone()[0]

        with _uto_cursor() as cur:
            query = f"""
                SELECT id, ipname, ip, address, su, is_auto, game,
                       country, protocol, config, tcp, maxnum, speed, login,
                       ovpnport, port
                FROM vpnlinek
                {wc}
                ORDER BY {order_col} {orderby_opt}
                LIMIT %s, %s
            """
            cur.execute(query, params + [start, length])
            rows = dictfetchall(cur)

        return JsonResponse({
            "recordsTotal": total,
            "recordsFiltered": total,
            "draw": draw,
            "data": rows
        })
    except Exception as e:
        traceback.print_exc()
        draw = int(request.POST.get('draw', 1))
        return JsonResponse({
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "draw": draw,
            "data": [],
            "error": str(e)
        })


# ============================================================
# [api] UTO 서버 수정 (활성/비활성, is_auto, maxnum 등)
# ============================================================
@allow_admin
def api_update_uto_server(request):
    try:
        server_id = request.POST.get('server_id')
        field = request.POST.get('field')
        value = request.POST.get('value')

        allowed_fields = {
            'su': 'su',
            'is_auto': 'is_auto',
            'maxnum': 'maxnum',
            'protocol': 'protocol',
            'country': 'country',
            'ipname': 'ipname',
            'address': 'address',
            'speed': 'speed',
        }

        if field not in allowed_fields:
            return JsonResponse({'result': 400, 'msg': f'허용되지 않는 필드: {field}'})

        col = allowed_fields[field]
        with _uto_cursor() as cur:
            cur.execute(f"UPDATE vpnlinek SET {col} = %s WHERE id = %s", [value, server_id])

        return JsonResponse({'result': 200, 'msg': '수정 완료'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 서버 통계
# ============================================================
@allow_admin
def api_read_uto_server_count(request):
    try:
        with _uto_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM vpnlinek")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM vpnlinek WHERE su = 1")
            active = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM vpnlinek WHERE su != 1")
            inactive = cur.fetchone()[0]

            # 프로토콜별
            cur.execute("""
                SELECT protocol, COUNT(*) as cnt
                FROM vpnlinek
                WHERE su = 1
                GROUP BY protocol
                ORDER BY cnt DESC
            """)
            protocols = dictfetchall(cur)

            # 국가별
            cur.execute("""
                SELECT country, COUNT(*) as cnt
                FROM vpnlinek
                WHERE su = 1
                GROUP BY country
                ORDER BY cnt DESC
            """)
            countries = dictfetchall(cur)

        return JsonResponse({
            'result': 200,
            'total': total,
            'active': active,
            'inactive': inactive,
            'protocols': protocols,
            'countries': countries,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 대리점(member) 목록
# ============================================================
@allow_admin
def api_read_uto_dealers(request):
    try:
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT m.id, m.huser, m.hcash, m.zk,
                       DATE_FORMAT(m.lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                       m.lastip,
                       (SELECT COUNT(*) FROM vpnuser WHERE member = m.huser) as user_count
                FROM member m
                ORDER BY m.id
            """)
            rows = dictfetchall(cur)

        return JsonResponse({'result': 200, 'data': rows})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 실시간 접속자
# ============================================================
@allow_admin
def api_read_uto_online_users(request):
    try:
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT u.id, u.vuser, u.nasip, u.vpnip, u.userip, u.vpntype,
                       DATE_FORMAT(u.lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                       u.game, u.member,
                       s.ipname as server_name
                FROM vpnuser u
                LEFT JOIN vpnlinek s ON u.nasip = s.ip
                WHERE u.sess > 0
                ORDER BY u.lasttime DESC
            """)
            rows = dictfetchall(cur)

        return JsonResponse({'result': 200, 'data': rows, 'count': len(rows)})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# UTO NAS 서버 현황 (uto_nas_status)
# ============================================================

# SSH 키 인증 사용 (deploy_uto_ssh.py로 배포 완료)
# RouterOS(admin login) 서버는 제외

# ---- 파일 기반 점검 상태 (worker 간 공유 + 재시작 보존) ----
_UTO_CHECK_DIR = os.path.join(tempfile.gettempdir(), 'uto_nas_check')
os.makedirs(_UTO_CHECK_DIR, exist_ok=True)
_uto_check_lock = threading.Lock()


def _uto_check_results_file():
    return os.path.join(_UTO_CHECK_DIR, 'results.json')


def _uto_check_running_file():
    return os.path.join(_UTO_CHECK_DIR, 'running.json')


def _read_uto_check_results():
    """파일에서 점검 결과 읽기 (worker 간 공유)"""
    fpath = _uto_check_results_file()
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _write_uto_check_results(data):
    """점검 결과를 파일에 저장 (atomic write)"""
    fpath = _uto_check_results_file()
    tmp = fpath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, fpath)


def _is_uto_check_running():
    """점검이 진행 중인지 확인 (PID 기반 stale lock 감지)"""
    fpath = _uto_check_running_file()
    if not os.path.exists(fpath):
        return False, 0
    try:
        with open(fpath, 'r') as f:
            info = json.load(f)
        pid = info.get('pid', 0)
        start_time = info.get('start_time', 0)
        # PID가 살아있는지 확인
        if pid:
            try:
                os.kill(pid, 0)  # 신호 0 = 존재확인만
            except OSError:
                # PID 죽음 → stale lock 제거
                os.remove(fpath)
                return False, 0
        elapsed = time.time() - start_time if start_time else 0
        # 5분 이상이면 stale로 간주
        if elapsed > 300:
            os.remove(fpath)
            return False, 0
        return True, round(elapsed, 1)
    except Exception:
        return False, 0


def _set_uto_check_running(running):
    """점검 진행 상태 설정"""
    fpath = _uto_check_running_file()
    if running:
        with open(fpath, 'w') as f:
            json.dump({'pid': os.getpid(), 'start_time': time.time()}, f)
    else:
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass


def _ssh_exec(ip, cmd, port=22, timeout=12):
    """SSH로 원격 명령 실행 (키 인증)"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
             '-o', 'StrictHostKeyChecking=no', '-p', str(port),
             f'root@{ip}', cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode == 0
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', False
    except Exception as e:
        return str(e), False


def _check_single_uto_server(server_info):
    """단일 UTO 서버 health 체크 (SSH)"""
    ip = server_info['address']
    name = server_info['ipname']
    protocol = server_info.get('protocol', '')
    port = 22  # SSH는 항상 22번 (V2RAY/SSTP의 port는 VPN 포트)

    result = {
        'name': name,
        'ip': ip,
        'protocol': protocol,
        'ssh_ok': False,
        'ping_ok': False,
        'uptime_text': '-',
        'uptime_seconds': 0,
        'disk_pct': 0,
        'mem_pct': 0,
        'load_1m': '-',
        'online_users': 0,
        'cert_status': '',
        'cert_expiry': '',
        'cert_days_left': None,
        'cert_issuer': '',
        'criticals': [],
        'warnings': [],
    }

    # 한 번의 SSH로 모든 정보 수집 (인증서 정보 포함)
    cmd = """
echo "===UPTIME==="
uptime 2>/dev/null
echo "===DISK==="
df -h / 2>/dev/null | tail -1
echo "===MEM==="
free -m 2>/dev/null | grep Mem
echo "===LOAD==="
cat /proc/loadavg 2>/dev/null
echo "===CERT==="
CERT_FILE=""
for f in /etc/strongswan/ipsec.d/certs/certificate.pem /etc/letsencrypt/live/*/fullchain.pem /etc/letsencrypt/live/*/cert.pem; do
  if [ -f "$f" ]; then CERT_FILE="$f"; break; fi
done
if [ -n "$CERT_FILE" ]; then
  openssl x509 -in "$CERT_FILE" -noout -enddate -issuer 2>/dev/null
else
  echo "NO_CERT"
fi
echo "===DONE==="
"""
    output, ok = _ssh_exec(ip, cmd, port=port, timeout=15)

    if not ok:
        result['criticals'].append('SSH 접속 실패')
        # Ping 체크
        try:
            ping_result = subprocess.run(
                ['ping', '-c', '1', '-W', '3', ip],
                capture_output=True, timeout=5
            )
            result['ping_ok'] = ping_result.returncode == 0
        except:
            pass
        if not result['ping_ok']:
            result['criticals'].append('Ping 실패')
        return result

    result['ssh_ok'] = True
    result['ping_ok'] = True

    # Parse output
    sections = {}
    current_section = None
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('===') and line.endswith('==='):
            current_section = line.strip('=')
        elif current_section:
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append(line)

    # Uptime
    uptime_lines = sections.get('UPTIME', [])
    if uptime_lines:
        up_str = uptime_lines[0]
        result['uptime_text'] = up_str
        # Parse uptime seconds
        import re
        m = re.search(r'up\s+(\d+)\s+day', up_str)
        if m:
            result['uptime_seconds'] = int(m.group(1)) * 86400
        else:
            m2 = re.search(r'up\s+(\d+):(\d+)', up_str)
            if m2:
                result['uptime_seconds'] = int(m2.group(1)) * 3600 + int(m2.group(2)) * 60
            m3 = re.search(r'up\s+(\d+)\s+min', up_str)
            if m3:
                result['uptime_seconds'] = int(m3.group(1)) * 60
        days = result['uptime_seconds'] // 86400
        if days >= 90:
            result['warnings'].append(f'Uptime {days}일 (재부팅 권장)')

    # Disk
    disk_lines = sections.get('DISK', [])
    if disk_lines:
        parts = disk_lines[0].split()
        if len(parts) >= 5:
            pct_str = parts[4].replace('%', '')
            try:
                result['disk_pct'] = int(pct_str)
                if result['disk_pct'] >= 90:
                    result['criticals'].append(f'디스크 {result["disk_pct"]}%')
                elif result['disk_pct'] >= 80:
                    result['warnings'].append(f'디스크 {result["disk_pct"]}%')
            except:
                pass

    # Memory
    mem_lines = sections.get('MEM', [])
    if mem_lines:
        parts = mem_lines[0].split()
        if len(parts) >= 3:
            try:
                total = int(parts[1])
                used = int(parts[2])
                if total > 0:
                    result['mem_pct'] = round(used / total * 100)
                    if result['mem_pct'] >= 95:
                        result['criticals'].append(f'메모리 {result["mem_pct"]}%')
                    elif result['mem_pct'] >= 85:
                        result['warnings'].append(f'메모리 {result["mem_pct"]}%')
            except:
                pass

    # Load
    load_lines = sections.get('LOAD', [])
    if load_lines:
        parts = load_lines[0].split()
        if parts:
            result['load_1m'] = parts[0]

    # Certificate
    cert_lines = sections.get('CERT', [])
    if cert_lines:
        cert_text = '\n'.join(cert_lines).strip()
        if 'NO_CERT' in cert_text:
            result['cert_status'] = 'NO_CERT'
        else:
            import re as _re
            # Parse expiry: notAfter=May 14 00:00:00 2026 GMT
            m_exp = _re.search(r'notAfter=(.+)', cert_text)
            if m_exp:
                from datetime import datetime as _dt
                try:
                    exp_str = m_exp.group(1).strip()
                    exp_date = _dt.strptime(exp_str, '%b %d %H:%M:%S %Y %Z')
                    result['cert_expiry'] = exp_date.strftime('%Y-%m-%d')
                    days_left = (exp_date - _dt.now()).days
                    result['cert_days_left'] = days_left
                    if days_left <= 0:
                        result['cert_status'] = 'EXPIRED'
                        result['criticals'].append(f'인증서 만료 ({result["cert_expiry"]})')
                    elif days_left <= 14:
                        result['cert_status'] = 'EXPIRING'
                        result['warnings'].append(f'인증서 {days_left}일 남음')
                    else:
                        result['cert_status'] = 'OK'
                except Exception:
                    result['cert_status'] = 'UNKNOWN'
            # Parse issuer: issuer= /C=US/O=Let's Encrypt/CN=R12 or issuer=C = US, O = Let's Encrypt, CN = R12
            m_iss = _re.search(r'issuer.*?CN\s*=\s*(\S+)', cert_text)
            if m_iss:
                result['cert_issuer'] = m_iss.group(1).strip().rstrip('/')

    # Online users from DB — radacct 기준 (vpnuser.sess는 부정확)
    try:
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM radacct
                WHERE acctstoptime IS NULL AND nasipaddress = %s
            """, [ip])
            result['online_users'] = cur.fetchone()[0]
    except:
        pass

    return result


def _check_infra_server(server_info):
    """인프라 서버 health 체크 (API/DB — SSH 또는 서비스 체크)"""
    ip = server_info['address']
    name = server_info['ipname']
    role = server_info.get('role', 'INFRA')  # API, DB, RADIUS
    ssh_port = server_info.get('ssh_port', 22)
    http_url = server_info.get('http_url', '')
    is_db = server_info.get('is_db', False)

    result = {
        'name': name,
        'ip': ip,
        'protocol': role,
        'is_infra': True,
        'ssh_ok': False,
        'ping_ok': False,
        'uptime_text': '-',
        'uptime_seconds': 0,
        'disk_pct': 0,
        'mem_pct': 0,
        'load_1m': '-',
        'online_users': 0,
        'cert_status': '',
        'cert_expiry': '',
        'cert_days_left': None,
        'cert_issuer': '',
        'criticals': [],
        'warnings': [],
        'services': {},  # 서비스별 상태
    }

    # 1) Ping 체크
    try:
        ping_result = subprocess.run(
            ['ping', '-c', '1', '-W', '3', ip],
            capture_output=True, timeout=5
        )
        result['ping_ok'] = ping_result.returncode == 0
    except:
        pass

    if not result['ping_ok']:
        result['criticals'].append('Ping 실패')
        return result

    # 2) SSH 체크
    is_api = (role == 'API')
    ssh_cmd = """
echo "===UPTIME==="
uptime 2>/dev/null
echo "===DISK==="
df -h / 2>/dev/null | tail -1
echo "===MEM==="
free -m 2>/dev/null | grep Mem
echo "===LOAD==="
cat /proc/loadavg 2>/dev/null
"""
    if is_api:
        ssh_cmd += """echo "===HTTPD==="
HTTPD_COUNT=$(ps aux 2>/dev/null | grep -c '[h]ttpd' || echo 0)
HTTPD_STATUS=$(systemctl is-active httpd 2>/dev/null || echo unknown)
echo "HTTPD_COUNT=$HTTPD_COUNT"
echo "HTTPD_STATUS=$HTTPD_STATUS"
echo "===PHP_ERRORS==="
PHP_ERRORS_1H=$(awk -v d="$(date -d '1 hour ago' '+%d-%b-%Y %H:%M' 2>/dev/null)" 'BEGIN{c=0} $0>=d{c++} END{print c}' /var/log/httpd/error_log 2>/dev/null || echo 0)
echo "PHP_ERRORS_1H=$PHP_ERRORS_1H"
echo "===ACCESS==="
ACCESS_1H=$(awk -v d="$(date -d '1 hour ago' '+%d/%b/%Y:%H:%M' 2>/dev/null)" '$4>=("["d){c++} END{print c+0}' /var/log/httpd/access_log 2>/dev/null || echo 0)
echo "ACCESS_1H=$ACCESS_1H"
echo "===CONN==="
ss -s 2>/dev/null | head -3
"""
    ssh_cmd += 'echo "===DONE==="\n'
    output, ok = _ssh_exec(ip, ssh_cmd, port=ssh_port, timeout=15)

    if ok:
        result['ssh_ok'] = True
        # Parse sections
        sections = {}
        current_section = None
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('===') and line.endswith('==='):
                current_section = line.strip('=')
            elif current_section:
                if current_section not in sections:
                    sections[current_section] = []
                sections[current_section].append(line)

        # Uptime
        uptime_lines = sections.get('UPTIME', [])
        if uptime_lines:
            up_str = uptime_lines[0]
            result['uptime_text'] = up_str
            import re
            m = re.search(r'up\s+(\d+)\s+day', up_str)
            if m:
                result['uptime_seconds'] = int(m.group(1)) * 86400
            else:
                m2 = re.search(r'up\s+(\d+):(\d+)', up_str)
                if m2:
                    result['uptime_seconds'] = int(m2.group(1)) * 3600 + int(m2.group(2)) * 60
                m3 = re.search(r'up\s+(\d+)\s+min', up_str)
                if m3:
                    result['uptime_seconds'] = int(m3.group(1)) * 60

        # Disk
        disk_lines = sections.get('DISK', [])
        if disk_lines:
            parts = disk_lines[0].split()
            if len(parts) >= 5:
                pct_str = parts[4].replace('%', '')
                try:
                    result['disk_pct'] = int(pct_str)
                    if result['disk_pct'] >= 90:
                        result['criticals'].append(f'디스크 {result["disk_pct"]}%')
                    elif result['disk_pct'] >= 80:
                        result['warnings'].append(f'디스크 {result["disk_pct"]}%')
                except:
                    pass

        # Memory
        mem_lines = sections.get('MEM', [])
        if mem_lines:
            parts = mem_lines[0].split()
            if len(parts) >= 3:
                try:
                    total = int(parts[1])
                    used = int(parts[2])
                    if total > 0:
                        result['mem_pct'] = round(used / total * 100)
                        if result['mem_pct'] >= 95:
                            result['criticals'].append(f'메모리 {result["mem_pct"]}%')
                        elif result['mem_pct'] >= 85:
                            result['warnings'].append(f'메모리 {result["mem_pct"]}%')
                except:
                    pass

        # Load
        load_lines = sections.get('LOAD', [])
        if load_lines:
            parts = load_lines[0].split()
            if parts:
                result['load_1m'] = parts[0]

        # API server extra info
        if is_api:
            # HTTPD
            httpd_lines = sections.get('HTTPD', [])
            for hl in httpd_lines:
                if hl.startswith('HTTPD_COUNT='):
                    try:
                        result['httpd_count'] = int(hl.split('=', 1)[1])
                    except:
                        pass
                elif hl.startswith('HTTPD_STATUS='):
                    status_val = hl.split('=', 1)[1].strip()
                    result['services']['Apache'] = (status_val == 'active')
                    if status_val != 'active':
                        result['criticals'].append('Apache 비정상')

            # PHP errors
            php_lines = sections.get('PHP_ERRORS', [])
            for pl in php_lines:
                if pl.startswith('PHP_ERRORS_1H='):
                    try:
                        php_err = int(pl.split('=', 1)[1])
                        result['php_errors_1h'] = php_err
                        if php_err >= 100:
                            result['criticals'].append(f'PHP 에러 {php_err}건/h')
                        elif php_err >= 20:
                            result['warnings'].append(f'PHP 에러 {php_err}건/h')
                    except:
                        pass

            # Access count
            access_lines = sections.get('ACCESS', [])
            for al in access_lines:
                if al.startswith('ACCESS_1H='):
                    try:
                        result['access_1h'] = int(al.split('=', 1)[1])
                    except:
                        pass

            # TCP connections
            conn_lines = sections.get('CONN', [])
            for cl in conn_lines:
                m = re.search(r'estab\s+(\d+)', cl)
                if m:
                    result['tcp_estab'] = int(m.group(1))

    # 3) HTTP 서비스 체크 (API 서버)
    if http_url:
        try:
            http_result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}|%{time_total}',
                 '--connect-timeout', '5', '--max-time', '10', http_url],
                capture_output=True, text=True, timeout=15
            )
            parts = http_result.stdout.strip().split('|')
            http_code = parts[0]
            result['services']['HTTP'] = http_code == '200'
            if len(parts) > 1:
                try:
                    result['http_response_time'] = float(parts[1])
                except:
                    pass
            if http_code != '200':
                result['criticals'].append(f'HTTP {http_code}')
        except:
            result['services']['HTTP'] = False
            result['criticals'].append('HTTP 타임아웃')

    # 4) MySQL 서비스 체크 (DB 서버)
    if is_db:
        try:
            with _uto_cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            result['services']['MySQL'] = True
        except:
            result['services']['MySQL'] = False
            result['criticals'].append('MySQL 연결 실패')

        # DB 통계: 활성 세션 수
        try:
            with _uto_cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM radacct WHERE acctstoptime IS NULL")
                total_sessions = cur.fetchone()[0]
                result['online_users'] = total_sessions
        except:
            pass

    return result


# ---- 인프라 서버 목록 (API + DB) ----
_INFRA_SERVERS = [
    {
        'address': '218.158.57.55',
        'ipname': 'UTO-API-1',
        'role': 'API',
        'ssh_port': 2202,
        'http_url': 'http://218.158.57.55/users/client/api26/checkuser.php',
        'is_db': False,
    },
    {
        'address': '125.132.9.240',
        'ipname': 'UTO-API-2',
        'role': 'API',
        'ssh_port': 22,
        'http_url': 'http://125.132.9.240/users/client/api26/checkuser.php',
        'is_db': False,
    },
    {
        'address': '218.158.57.51',
        'ipname': 'UTO-DB/RADIUS',
        'role': 'DB',
        'ssh_port': 22,
        'http_url': '',
        'is_db': True,
    },
]


def _run_uto_check_all():
    """전체 UTO 서버 health 체크 (백그라운드 스레드)"""
    global _uto_check_state
    start_time = time.time()

    try:
        # Get VPN server list
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT DISTINCT address, ipname, ip, protocol, port, login
                FROM vpnlinek
                WHERE su = 1 AND address != '' AND login = 'root'
                ORDER BY ipname
            """)
            servers = dictfetchall(cur)

        # Deduplicate by address
        seen = {}
        for s in servers:
            addr = s['address']
            if addr not in seen:
                seen[addr] = s

        server_list = list(seen.values())

        # Parallel checks (max 10 threads)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        vpn_results = []
        infra_results = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            # VPN 서버 체크
            vpn_futures = {executor.submit(_check_single_uto_server, s): s for s in server_list}
            # 인프라 서버 체크
            infra_futures = {executor.submit(_check_infra_server, s): s for s in _INFRA_SERVERS}

            for future in as_completed(vpn_futures):
                try:
                    vpn_results.append(future.result())
                except Exception as e:
                    s = vpn_futures[future]
                    vpn_results.append({
                        'name': s['ipname'], 'ip': s['address'],
                        'protocol': s.get('protocol', ''),
                        'ssh_ok': False, 'ping_ok': False,
                        'criticals': [str(e)], 'warnings': [],
                        'uptime_text': '-', 'uptime_seconds': 0,
                        'disk_pct': 0, 'mem_pct': 0, 'load_1m': '-',
                        'online_users': 0,
                    })

            for future in as_completed(infra_futures):
                try:
                    infra_results.append(future.result())
                except Exception as e:
                    s = infra_futures[future]
                    infra_results.append({
                        'name': s['ipname'], 'ip': s['address'],
                        'protocol': s.get('role', 'INFRA'),
                        'is_infra': True,
                        'ssh_ok': False, 'ping_ok': False,
                        'criticals': [str(e)], 'warnings': [],
                        'uptime_text': '-', 'uptime_seconds': 0,
                        'disk_pct': 0, 'mem_pct': 0, 'load_1m': '-',
                        'online_users': 0, 'services': {},
                    })

        # 모든 결과 합산
        results = vpn_results + infra_results
        elapsed = round(time.time() - start_time, 1)

        # Compute summary (인프라 서버 포함)
        ok = sum(1 for r in results if not r.get('criticals') and not r.get('warnings'))
        warning = sum(1 for r in results if r.get('warnings') and not r.get('criticals'))
        critical = sum(1 for r in results if r.get('criticals'))

        _write_uto_check_results({
            'servers': vpn_results,
            'infra_servers': infra_results,
            'total': len(results),
            'vpn_count': len(vpn_results),
            'infra_count': len(infra_results),
            'ok': ok,
            'warning': warning,
            'critical': critical,
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'elapsed': elapsed,
        })
        _set_uto_check_running(False)

    except Exception as e:
        traceback.print_exc()
        _write_uto_check_results({'error': str(e)})
        _set_uto_check_running(False)


@allow_admin
def uto_nas_status(request):
    """UTO NAS 서버 현황 페이지"""
    if request.session.get('role', 1) != 1:
        return redirect('/uto_user')
    return render(request, 'admin/uto_nas_status.html', {})


@allow_admin
def api_read_uto_nas_status(request):
    """최신 UTO NAS 점검 결과 반환"""
    results = _read_uto_check_results()
    if results:
        return JsonResponse({'result': 200, **results})
    return JsonResponse({'result': 200, 'servers': [], 'infra_servers': [], 'total': 0, 'ok': 0, 'warning': 0, 'critical': 0})


@allow_admin
def api_update_uto_nas_check(request):
    """UTO NAS 전체 점검 시작"""
    with _uto_check_lock:
        running, elapsed = _is_uto_check_running()
        if running:
            return JsonResponse({'result': 409, 'msg': f'점검 진행 중 ({round(elapsed)}초)'})
        _set_uto_check_running(True)

    thread = threading.Thread(target=_run_uto_check_all, daemon=True)
    thread.start()
    return JsonResponse({'result': 200, 'msg': '점검 시작'})


@allow_admin
def api_read_uto_nas_check_status(request):
    """UTO NAS 점검 진행 상태"""
    running, elapsed = _is_uto_check_running()
    data = _read_uto_check_results()
    if not running and data:
        elapsed = data.get('elapsed', 0)

    return JsonResponse({
        'result': 200,
        'running': running,
        'elapsed': elapsed,
        'data': data,
    })


@allow_admin
def api_read_uto_ssh_info(request):
    """UTO 서버 SSH 접속 정보"""
    ip = request.GET.get('ip', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    try:
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT DISTINCT address, ipname, login, port, uspw
                FROM vpnlinek
                WHERE address = %s AND su = 1
                LIMIT 1
            """, [ip])
            rows = dictfetchall(cur)

        if not rows:
            return JsonResponse({'result': 404, 'msg': '서버를 찾을 수 없습니다'})

        s = rows[0]
        return JsonResponse({
            'result': 200,
            'data': {
                'name': s['ipname'],
                'ip': s['address'],
                'username': s['login'],
                'password': s['uspw'] or '',
                'port': s['port'] or 22,
            }
        })
    except Exception as e:
        return JsonResponse({'result': 400, 'msg': str(e)})


@allow_admin
def api_update_uto_reboot(request):
    """UTO 서버 재부팅"""
    ip = request.POST.get('ip', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    # reboot 명령은 서버가 즉시 종료되므로:
    # - SSH returncode=255 (connection closed) → 정상
    # - TIMEOUT → 정상 (서버 종료 중 SSH 끊김)
    # - stderr에 "closed by remote host" → 정상
    try:
        proc = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
             '-o', 'StrictHostKeyChecking=no', f'root@{ip}', 'reboot'],
            capture_output=True, text=True, timeout=10
        )
        combined = (proc.stdout + ' ' + proc.stderr).lower()
        # reboot 성공 시: rc=0 또는 rc=255(연결끊김) 모두 정상
        if proc.returncode == 0 or proc.returncode == 255 or 'closed' in combined:
            return JsonResponse({'result': 200, 'msg': f'{ip} 재부팅 명령 전송 완료'})
        return JsonResponse({'result': 400, 'msg': f'재부팅 실패 (rc={proc.returncode}): {proc.stderr[:200]}'})
    except subprocess.TimeoutExpired:
        # reboot 후 SSH 연결이 끊기며 타임아웃 → 재부팅 성공
        return JsonResponse({'result': 200, 'msg': f'{ip} 재부팅 명령 전송 완료 (서버 종료 중)'})
    except Exception as e:
        return JsonResponse({'result': 400, 'msg': f'재부팅 실패: {str(e)}'})


@allow_admin
def api_update_uto_single_check(request):
    """단일 UTO 서버 점검"""
    ip = request.POST.get('ip', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    try:
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT DISTINCT address, ipname, ip, protocol, port, login
                FROM vpnlinek
                WHERE address = %s AND su = 1 AND login = 'root'
                LIMIT 1
            """, [ip])
            rows = dictfetchall(cur)

        if not rows:
            return JsonResponse({'result': 404, 'msg': '서버를 찾을 수 없습니다'})

        result = _check_single_uto_server(rows[0])

        # Update cached results (파일 기반)
        cached = _read_uto_check_results()
        if cached and 'servers' in cached:
            servers = cached['servers']
            idx = next((i for i, s in enumerate(servers) if s['ip'] == ip), None)
            if idx is not None:
                servers[idx] = result
            else:
                servers.append(result)
            # Recompute summary
            cached['ok'] = sum(1 for r in servers if not r['criticals'] and not r['warnings'])
            cached['warning'] = sum(1 for r in servers if r['warnings'] and not r['criticals'])
            cached['critical'] = sum(1 for r in servers if r['criticals'])
            cached['total'] = len(servers)
            _write_uto_check_results(cached)

        return JsonResponse({'result': 200, 'data': result})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ===== 인증서 갱신 진행 상태 (파일 기반 — uWSGI 워커 간 공유) =====
_UTO_CERT_RENEW_DIR = os.path.join(tempfile.gettempdir(), 'uto_cert_renew')
os.makedirs(_UTO_CERT_RENEW_DIR, exist_ok=True)


def _cert_renew_file(ip):
    """IP별 갱신 상태 파일 경로"""
    safe_ip = ip.replace('.', '_')
    return os.path.join(_UTO_CERT_RENEW_DIR, f'{safe_ip}.json')


def _read_cert_renew_status(ip):
    """파일에서 갱신 상태 읽기"""
    fpath = _cert_renew_file(ip)
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
            # PID 살아있는지 확인 (stale 감지)
            if data.get('running') and data.get('pid'):
                try:
                    os.kill(data['pid'], 0)
                except OSError:
                    # PID 죽음 → stale
                    data['running'] = False
                    data['result'] = {'success': False, 'message': '프로세스 비정상 종료'}
                    _write_cert_renew_status(ip, data)
            # 3분 이상 running이면 stale로 간주
            if data.get('running') and data.get('start_time'):
                elapsed = time.time() - data['start_time']
                if elapsed > 180:
                    data['running'] = False
                    data['result'] = {'success': False, 'message': '타임아웃 (180초)'}
                    _write_cert_renew_status(ip, data)
            return data
        except Exception:
            pass
    return None


def _write_cert_renew_status(ip, data):
    """갱신 상태를 파일에 저장 (atomic write)"""
    fpath = _cert_renew_file(ip)
    tmp = fpath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, fpath)


@allow_admin
def api_update_uto_cert_renew(request):
    """UTO 서버 인증서 갱신 (certbot renew + strongswan rereadall)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    ip = request.POST.get('ip', '')
    name = request.POST.get('name', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    # 이미 갱신 중인지 확인
    status = _read_cert_renew_status(ip)
    if status and status.get('running'):
        return JsonResponse({'result': 409, 'msg': f'{name or ip} 갱신이 이미 진행 중입니다.'})

    _write_cert_renew_status(ip, {
        'running': True, 'result': None,
        'pid': os.getpid(), 'start_time': time.time(),
    })

    def run_renewal():
        try:
            # 0) certbot hook 사전 정리 (certreload.sh/vpnserver 등 깨진 hook 제거)
            fix_hooks_cmd = (
                'python -c "'
                'import re\\n'
                'for p in [\"/etc/letsencrypt/cli.ini\"]:\\n'
                '    try:\\n'
                '        c=open(p).read()\\n'
                '        c=re.sub(r\"pre-hook = .*\",\"# pre-hook = (disabled)\",c)\\n'
                '        c=re.sub(r\"renew-hook = .*\",\"# renew-hook = (disabled)\",c)\\n'
                '        c=re.sub(r\"post-hook = .*\",\"# post-hook = (disabled)\",c)\\n'
                '        open(p,\"w\").write(c)\\n'
                '    except: pass\\n'
                'import glob\\n'
                'for p in glob.glob(\"/etc/letsencrypt/renewal/*.conf\"):\\n'
                '    try:\\n'
                '        c=open(p).read()\\n'
                '        c=re.sub(r\"post_hook = .*certreload.*\",\"post_hook = strongswan rereadall\",c)\\n'
                '        c=re.sub(r\"post_hook = .*vpnserver.*\",\"post_hook = strongswan rereadall\",c)\\n'
                '        c=re.sub(r\"renew_hook = .*vpnserver.*\",\"renew_hook = strongswan rereadall\",c)\\n'
                '        c=re.sub(r\"renew_hook = .*strongswan restart.*\",\"renew_hook = strongswan rereadall\",c)\\n'
                '        c=re.sub(r\"pre_hook = service x-ui.*\",\"pre_hook = echo pre\",c)\\n'
                '        open(p,\"w\").write(c)\\n'
                '    except: pass\\n'
                '" 2>/dev/null; '
                'rm -f /etc/letsencrypt/renewal-hooks/deploy/*trojan* 2>/dev/null; '
                'echo "HOOKS_CLEANED"'
            )
            _ssh_exec(ip, fix_hooks_cmd, timeout=15)

            # 1) certbot renew (만료/임박 인증서 갱신)
            renew_cmd = 'certbot renew --quiet 2>&1; echo "CERTBOT_RC=$?"'
            renew_out, renew_ok = _ssh_exec(ip, renew_cmd, timeout=120)

            # 2) strongswan 인증서 리로드 (rereadall = 인증서 파일만 재읽기, 세션 유지)
            reload_cmd = (
                'if command -v strongswan >/dev/null 2>&1; then '
                'strongswan rereadall 2>&1; echo "SWAN_REREAD"; '
                'elif command -v ipsec >/dev/null 2>&1; then '
                'ipsec rereadall 2>&1; echo "IPSEC_REREAD"; '
                'else echo "NO_STRONGSWAN"; fi'
            )
            reload_out, reload_ok = _ssh_exec(ip, reload_cmd, timeout=15)

            # 3) 갱신 후 인증서 상태 확인
            check_cmd = (
                'CERT_FILE=""; '
                'for f in /etc/strongswan/ipsec.d/certs/certificate.pem '
                '/etc/letsencrypt/live/*/fullchain.pem '
                '/etc/letsencrypt/live/*/cert.pem; do '
                'if [ -f "$f" ]; then CERT_FILE="$f"; break; fi; done; '
                'if [ -n "$CERT_FILE" ]; then '
                'openssl x509 -in "$CERT_FILE" -noout -enddate -issuer 2>/dev/null; '
                'else echo "NO_CERT"; fi'
            )
            check_out, check_ok = _ssh_exec(ip, check_cmd, timeout=15)

            result_data = {
                'success': True,
                'renew_output': renew_out[-500:] if renew_out else '',
                'reload_output': reload_out[-200:] if reload_out else '',
                'cert_check': check_out[-300:] if check_out else '',
            }

            # Parse new cert info
            import re as _re
            from datetime import datetime as _dt
            m_exp = _re.search(r'notAfter=(.+)', check_out or '')
            if m_exp:
                try:
                    exp_date = _dt.strptime(m_exp.group(1).strip(), '%b %d %H:%M:%S %Y %Z')
                    result_data['new_expiry'] = exp_date.strftime('%Y-%m-%d')
                    result_data['new_days_left'] = (exp_date - _dt.now()).days
                except Exception:
                    pass

            _write_cert_renew_status(ip, {'running': False, 'result': result_data})

        except Exception as e:
            _write_cert_renew_status(ip, {
                'running': False,
                'result': {'success': False, 'message': str(e)}
            })

    t = threading.Thread(target=run_renewal, daemon=True)
    t.start()

    return JsonResponse({
        'result': 200,
        'msg': f'{name or ip} 인증서 갱신을 시작했습니다.',
        'ip': ip,
    })


@allow_admin
def api_read_uto_cert_renew_status(request):
    """UTO 인증서 갱신 진행 상태 조회"""
    ip = request.GET.get('ip', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    status = _read_cert_renew_status(ip)
    if not status:
        return JsonResponse({'result': 404, 'msg': '갱신 기록 없음', 'ip': ip})

    return JsonResponse({
        'result': 200,
        'ip': ip,
        'running': status.get('running', False),
        'data': status.get('result'),
    })


# ============================================================
# UTO 목표사이트 점검
# ============================================================

UTO_SITES_TO_CHECK = [
    ('gemini',    'Google Gemini',   'https://gemini.google.com'),
    ('youtube',   'YouTube',         'https://www.youtube.com'),
    ('facebook',  'Facebook',        'https://www.facebook.com'),
    ('instagram', 'Instagram',       'https://www.instagram.com'),
    ('tiktok',    'TikTok',          'https://www.tiktok.com'),
    ('netflix',   'Netflix',         'https://www.netflix.com'),
]

UTO_SITE_CHECK_DIR = os.path.join(tempfile.gettempdir(), 'uto_site_check')
os.makedirs(UTO_SITE_CHECK_DIR, exist_ok=True)


def _uto_site_check_file():
    return os.path.join(UTO_SITE_CHECK_DIR, 'results.json')


def _read_uto_site_check():
    fpath = _uto_site_check_file()
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_uto_site_check(data):
    fpath = _uto_site_check_file()
    tmp = fpath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, fpath)


def _check_single_uto_site(ip, server_name):
    """SSH로 UTO 서버에 접속하여 목표 사이트 접속 체크 + 출구IP 확인"""
    urls = ' '.join(f'"{s[2]}"' for s in UTO_SITES_TO_CHECK)
    script = f'''UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0"
RETRY_URLS=""
for url in {urls}; do
  code=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 10 -o /dev/null -w "%{{http_code}}" "$url" 2>/dev/null)
  echo "SITE|$url|$code"
  case "$code" in
    2*|3*) ;;
    *) RETRY_URLS="$RETRY_URLS $url" ;;
  esac
done
if [ -n "$RETRY_URLS" ]; then
  sleep 3
  for url in $RETRY_URLS; do
    code=$(curl -4 -s -A "$UA" --connect-timeout 7 --max-time 12 -o /dev/null -w "%{{http_code}}" "$url" 2>/dev/null)
    echo "RETRY|$url|$code"
  done
fi
gemini_geo=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 15 "https://gemini.google.com" 2>/dev/null | grep -oP '"[a-z]{{2}}"' | head -1 | tr -d '"')
[ -z "$gemini_geo" ] && gemini_geo="UNKNOWN"
echo "GEMINI_GEO|$gemini_geo"
exitip=$(curl -4 -s --connect-timeout 4 --max-time 8 "https://ifconfig.me" 2>/dev/null | head -1)
[ -z "$exitip" ] && exitip=$(curl -4 -s --connect-timeout 4 --max-time 8 "https://api.ipify.org" 2>/dev/null | head -1)
echo "EXITIP|$exitip"
'''
    try:
        output, ok = _ssh_exec(ip, f"bash << 'SITECHECKEOF'\n{script}\nSITECHECKEOF", timeout=120)
        if not ok:
            return {
                'ip': ip, 'name': server_name, 'sites': {},
                'exit_ip': '', 'exit_ip_diff': False, 'ssh_ok': False,
            }

        sites = {}
        exit_ip = ''
        GEMINI_BLOCKED_GEOS = {'cn', 'hk', 'ru'}

        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('SITE|') or line.startswith('RETRY|'):
                parts = line.split('|')
                if len(parts) >= 3:
                    url = parts[1]
                    code = parts[2]
                    is_retry = line.startswith('RETRY|')
                    for key, _name, check_url in UTO_SITES_TO_CHECK:
                        if check_url == url:
                            new_ok = bool(code and code[0] in ('2', '3'))
                            if is_retry:
                                prev = sites.get(key, {})
                                sites[key] = {'code': code, 'ok': new_ok, 'retried': True}
                                if prev.get('first_code'):
                                    sites[key]['first_code'] = prev['first_code']
                                else:
                                    sites[key]['first_code'] = prev.get('code', '')
                            else:
                                sites[key] = {'code': code, 'ok': new_ok}
                            break
            elif line.startswith('GEMINI_GEO|'):
                geo = line.split('|')[1].strip()
                if 'gemini' in sites and geo in GEMINI_BLOCKED_GEOS:
                    sites['gemini']['ok'] = False
                    sites['gemini']['blocked'] = True
                    sites['gemini']['geo'] = geo
                elif 'gemini' in sites:
                    sites['gemini']['geo'] = geo
            elif line.startswith('EXITIP|'):
                val = line[7:].strip()
                if val:
                    exit_ip = val

        # Cloudflare 봇 차단 처리
        BOT_BLOCKED_SITES = {'tiktok'}
        for site_key in BOT_BLOCKED_SITES:
            if site_key in sites and sites[site_key].get('code') == '403':
                sites[site_key]['bot_blocked'] = True
                sites[site_key]['ok'] = True

        return {
            'ip': ip, 'name': server_name, 'sites': sites,
            'exit_ip': exit_ip, 'exit_ip_diff': bool(exit_ip and exit_ip != ip),
            'ssh_ok': True,
        }
    except subprocess.TimeoutExpired:
        return {'ip': ip, 'name': server_name, 'sites': {}, 'exit_ip': '', 'exit_ip_diff': False, 'ssh_ok': False}
    except Exception as e:
        return {'ip': ip, 'name': server_name, 'sites': {}, 'exit_ip': '', 'exit_ip_diff': False, 'ssh_ok': False}


@allow_admin
def api_update_uto_site_check(request):
    """UTO 목표사이트 점검 시작 (전체 또는 단일)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    status = _read_uto_site_check()
    if status.get('running'):
        if time.time() - status.get('started', 0) < 300:
            return JsonResponse({'result': 409, 'msg': '점검이 이미 진행 중입니다.'})

    target_ip = request.POST.get('ip', '').strip()

    with _uto_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT address, ipname
            FROM vpnlinek
            WHERE su = 1 AND address != '' AND login = 'root'
            ORDER BY ipname
        """)
        rows = dictfetchall(cur)

    # Deduplicate by address
    seen = {}
    for r in rows:
        if r['address'] not in seen:
            seen[r['address']] = r
    servers = [{'ip': v['address'], 'name': v['ipname']} for v in seen.values()]

    if target_ip:
        servers = [s for s in servers if s['ip'] == target_ip]
        if not servers:
            return JsonResponse({'result': 404, 'msg': 'Server not found'})

    started = time.time()
    _write_uto_site_check({
        'running': True, 'started': started,
        'total': len(servers), 'completed': 0,
        'results': status.get('results', []),
    })

    def run_check():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        prev_results = {}
        if target_ip and status.get('results'):
            for r in status['results']:
                prev_results[r['ip']] = r

        new_results = {}
        completed = 0

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_check_single_uto_site, s['ip'], s['name']): s
                for s in servers
            }
            for future in as_completed(futures):
                s = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = {'ip': s['ip'], 'name': s['name'], 'sites': {}, 'exit_ip': '', 'exit_ip_diff': False, 'ssh_ok': False}
                new_results[r['ip']] = r
                completed += 1

                merged = dict(prev_results)
                merged.update(new_results)
                merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))
                _write_uto_site_check({
                    'running': True, 'started': started,
                    'total': len(servers), 'completed': completed,
                    'results': merged_list,
                })

        merged = dict(prev_results)
        merged.update(new_results)
        merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))

        # 실패 서버 자동 1회 재점검 (전체 점검 시에만)
        if not target_ip:
            def _is_failed(r):
                if not r.get('ssh_ok'):
                    return True
                for k, chk in (r.get('sites') or {}).items():
                    if chk and not chk.get('ok') and not chk.get('blocked'):
                        return True
                return False

            failed_servers = [r for r in merged_list if _is_failed(r)]
            if failed_servers:
                _write_uto_site_check({
                    'running': True, 'started': started,
                    'total': len(servers), 'completed': len(servers),
                    'results': merged_list,
                    'retry': True, 'retry_count': len(failed_servers),
                })
                with ThreadPoolExecutor(max_workers=4) as executor:
                    retry_futures = {
                        executor.submit(_check_single_uto_site, r['ip'], r['name']): r
                        for r in failed_servers
                    }
                    for future in as_completed(retry_futures):
                        r_orig = retry_futures[future]
                        try:
                            r_new = future.result()
                        except Exception:
                            continue
                        orig = merged.get(r_orig['ip'], r_orig)
                        orig_ok = sum(1 for c in (orig.get('sites') or {}).values() if c and c.get('ok'))
                        new_ok = sum(1 for c in (r_new.get('sites') or {}).values() if c and c.get('ok'))
                        if r_new.get('ssh_ok') and (new_ok > orig_ok or not orig.get('ssh_ok')):
                            merged[r_new['ip']] = r_new
                merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))

        _write_uto_site_check({
            'running': False, 'started': started, 'finished': time.time(),
            'total': len(servers), 'completed': len(servers),
            'results': merged_list,
            'elapsed': round(time.time() - started, 1),
        })

    t = threading.Thread(target=run_check, daemon=True)
    t.start()
    return JsonResponse({'result': 200, 'msg': f'{len(servers)}개 서버 점검을 시작했습니다.'})


@allow_admin
def api_read_uto_site_check_status(request):
    """UTO 목표사이트 점검 상태/결과 조회"""
    data = _read_uto_site_check()
    running = data.get('running', False)
    started = data.get('started')
    elapsed = round(time.time() - started, 1) if started and running else data.get('elapsed')

    return JsonResponse({
        'result': 200,
        'running': running,
        'total': data.get('total', 0),
        'completed': data.get('completed', 0),
        'elapsed': elapsed,
        'retry': data.get('retry', False),
        'retry_count': data.get('retry_count', 0),
        'results': data.get('results', []),
        'sites': [{'key': s[0], 'name': s[1]} for s in UTO_SITES_TO_CHECK],
    })


# ============================================================
# 디스크 용량 분석 & 정리
# ============================================================

@allow_admin
def api_read_uto_disk_analysis(request):
    """서버 디스크 용량 분석 — 삭제 가능 항목 표시"""
    ip = request.GET.get('ip', '')
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})

    cmd = r"""
echo '===DF==='
df -h / 2>/dev/null | tail -1
echo '===JOURNAL==='
journalctl --disk-usage 2>/dev/null
echo '===ROTATED_LOGS==='
find /var/log \( -name '*.gz' -o -name '*-20*' -o -name '*.old' -o -name '*.xz' \) 2>/dev/null | xargs du -shc 2>/dev/null | tail -1
echo '===ROTATED_LIST==='
find /var/log \( -name '*.gz' -o -name '*-20*' -o -name '*.old' -o -name '*.xz' \) 2>/dev/null | head -20
echo '===BTMP==='
du -sh /var/log/btmp* 2>/dev/null
echo '===LARGE_LOGS==='
find /var/log -type f -size +10M -exec du -sh {} \; 2>/dev/null | sort -rh | head -10
echo '===ROOT_LOGS==='
find /root -maxdepth 1 -name '*.log' -exec du -sh {} \; 2>/dev/null | sort -rh
echo '===ROOT_MISC==='
find /root -maxdepth 1 -name '*.txt' -o -name '*.py' -o -name '*.sh' 2>/dev/null | xargs du -shc 2>/dev/null | tail -1
echo '===TROJAN==='
du -sh /root/trojan-web /root/trojan /root/hy 2>/dev/null
echo '===OLD_KERNELS==='
rpm -q kernel 2>/dev/null
echo '===YUM_CACHE==='
du -sh /var/cache/yum 2>/dev/null
echo '===PKT_LOG==='
du -shc /usr/local/vpnserver/packet_log/*/pkt_*.log 2>/dev/null | tail -1
echo '===PKT_COUNT==='
find /usr/local/vpnserver/packet_log -name 'pkt_*.log' 2>/dev/null | wc -l
echo '===SOFTETHER_LOG==='
du -shc /usr/local/vpnserver/server_log/*.log /usr/local/vpnserver/security_log/*/*.log 2>/dev/null | tail -1
echo '===NODE==='
du -sh /usr/local/n 2>/dev/null
echo '===XUI==='
du -sh /usr/local/x-ui 2>/dev/null
echo '===CLEANUP_LOG==='
du -sh /var/log/cleanup_qos.log 2>/dev/null
echo '===TMP==='
du -shc /tmp/* 2>/dev/null | tail -1
echo '===DONE==='
"""
    output, ok = _ssh_exec(ip, cmd, timeout=25)
    if not ok:
        return JsonResponse({'result': 400, 'msg': f'SSH 접속 실패: {output[:200]}'})

    # Parse
    sections = {}
    current = None
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('===') and line.endswith('==='):
            current = line.strip('=')
            sections[current] = []
        elif current and line:
            sections[current].append(line)

    items = []  # {name, size_text, size_bytes_approx, category, deletable}

    def parse_size(s):
        """Rough parse: '224.0M' -> bytes"""
        s = s.strip()
        try:
            if s.endswith('G'): return float(s[:-1]) * 1024**3
            if s.endswith('M'): return float(s[:-1]) * 1024**2
            if s.endswith('K'): return float(s[:-1]) * 1024
            return float(s)
        except:
            return 0

    # DF
    df_info = {}
    df_lines = sections.get('DF', [])
    if df_lines:
        parts = df_lines[0].split()
        if len(parts) >= 5:
            df_info = {'size': parts[1], 'used': parts[2], 'avail': parts[3], 'pct': parts[4]}

    # Journal
    for line in sections.get('JOURNAL', []):
        import re
        m = re.search(r'take up ([\d.]+[KMGT]?)', line)
        if m:
            sz = m.group(1)
            sz_bytes = parse_size(sz)
            if sz_bytes > 50 * 1024 * 1024:  # >50M만 표시
                items.append({'name': 'systemd journal 로그', 'size_text': sz, 'size_bytes': sz_bytes, 'category': 'journal', 'deletable': True})

    # Rotated logs
    rot_lines = sections.get('ROTATED_LOGS', [])
    if rot_lines:
        parts = rot_lines[0].split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 1024 * 1024:
                items.append({'name': '로테이션된 로그 (gz, old, -20*)', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'rotated_logs', 'deletable': True})

    # btmp
    btmp_total = 0
    for line in sections.get('BTMP', []):
        parts = line.split()
        if parts and not parts[1].endswith('/btmp'):
            btmp_total += parse_size(parts[0])
    if btmp_total > 10 * 1024 * 1024:
        items.append({'name': 'btmp 로그 (SSH 실패 기록)', 'size_text': f'{btmp_total/1024/1024:.0f}M', 'size_bytes': btmp_total, 'category': 'btmp', 'deletable': True})

    # Root logs
    for line in sections.get('ROOT_LOGS', []):
        parts = line.split()
        if len(parts) >= 2:
            sz_bytes = parse_size(parts[0])
            fname = parts[1]
            if sz_bytes > 5 * 1024 * 1024:
                items.append({'name': f'root 로그: {os.path.basename(fname)}', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'root_logs', 'deletable': True})

    # Trojan install files
    trojan_total = 0
    trojan_names = []
    for line in sections.get('TROJAN', []):
        parts = line.split()
        if len(parts) >= 2:
            sz = parse_size(parts[0])
            trojan_total += sz
            trojan_names.append(os.path.basename(parts[1]))
    if trojan_total > 10 * 1024 * 1024:
        trojan_joined = ", ".join(trojan_names)
        trojan_size_text = f"{trojan_total/1024/1024:.0f}M"
        items.append({'name': f'설치파일 ({trojan_joined})', 'size_text': trojan_size_text, 'size_bytes': trojan_total, 'category': 'trojan', 'deletable': True})

    # Old kernels
    kernels = sections.get('OLD_KERNELS', [])
    if len(kernels) > 1:
        old_count = len(kernels) - 1
        items.append({'name': f'오래된 커널 ({old_count}개)', 'size_text': f'~{old_count*50}M', 'size_bytes': old_count * 50 * 1024 * 1024, 'category': 'old_kernels', 'deletable': True})

    # Yum cache
    for line in sections.get('YUM_CACHE', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 50 * 1024 * 1024:
                items.append({'name': 'yum 패키지 캐시', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'yum_cache', 'deletable': True})

    # VPN packet_log (SoftEther)
    for line in sections.get('PKT_LOG', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 5 * 1024 * 1024:
                pkt_count = '?'
                pkt_cnt_lines = sections.get('PKT_COUNT', [])
                if pkt_cnt_lines:
                    pkt_count = pkt_cnt_lines[0].strip()
                items.append({'name': f'VPN 패킷로그 ({pkt_count}개 파일)', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'pkt_log', 'deletable': True})

    # SoftEther server_log / security_log
    for line in sections.get('SOFTETHER_LOG', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 5 * 1024 * 1024:
                items.append({'name': 'SoftEther 서버/보안 로그', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'softether_log', 'deletable': True})

    # Node.js (unused)
    for line in sections.get('NODE', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 10 * 1024 * 1024:
                items.append({'name': 'Node.js 설치 (미사용)', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'nodejs', 'deletable': True})

    # x-ui (old xray panel)
    for line in sections.get('XUI', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 5 * 1024 * 1024:
                items.append({'name': '구 x-ui 패널 (마이그레이션 완료)', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'xui', 'deletable': True})

    # cleanup_qos.log (cron이 append로 쌓는 로그)
    for line in sections.get('CLEANUP_LOG', []):
        parts = line.split()
        if parts:
            sz_bytes = parse_size(parts[0])
            if sz_bytes > 5 * 1024 * 1024:
                items.append({'name': 'QoS 정리 크론 로그', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'cleanup_log', 'deletable': True})

    # Large log files (>10M)
    active_log_names = {'messages', 'secure', 'cron', 'btmp', 'wtmp'}
    for line in sections.get('LARGE_LOGS', []):
        parts = line.split()
        if len(parts) >= 2:
            sz_bytes = parse_size(parts[0])
            fname = parts[1]
            base = os.path.basename(fname)
            if base in active_log_names:
                # 활성 로그는 truncate 가능 항목으로 별도 표시
                items.append({'name': f'활성 로그: {base} (비우기)', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'large_logs', 'deletable': True})
            else:
                items.append({'name': f'대용량 로그: {base}', 'size_text': parts[0], 'size_bytes': sz_bytes, 'category': 'large_logs', 'deletable': True})

    # 정렬: 큰 것부터
    items.sort(key=lambda x: x.get('size_bytes', 0), reverse=True)

    # 프론트엔드가 기대하는 형식으로 변환: size_mb, detail 추가
    for it in items:
        it['size_mb'] = round(it.get('size_bytes', 0) / 1024 / 1024)
        it['detail'] = it.get('name', '')

    total_cleanable = sum(it.get('size_bytes', 0) for it in items if it.get('deletable'))

    return JsonResponse({
        'result': 200,
        'df': df_info,
        'disk_used': df_info.get('used', '-'),
        'disk_total': df_info.get('size', '-'),
        'disk_pct': df_info.get('pct', '-').replace('%', ''),
        'items': items,
        'total_cleanable': f'{total_cleanable/1024/1024:.0f}M',
        'total_cleanable_bytes': total_cleanable,
    })


@allow_admin
def api_update_uto_disk_cleanup(request):
    """서버 디스크 정리 실행"""
    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = {}
    ip = body.get('ip', '') or request.POST.get('ip', '')
    categories = body.get('categories', [])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(',') if c.strip()]
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP 필요'})
    if not categories:
        return JsonResponse({'result': 400, 'msg': '정리 항목을 선택하세요'})

    cmds = []

    if 'journal' in categories:
        cmds.append('journalctl --vacuum-size=50M 2>&1')

    if 'rotated_logs' in categories:
        cmds.append('find /var/log -name "*.gz" -delete 2>/dev/null; find /var/log -name "*-20*" -delete 2>/dev/null; find /var/log -name "*.old" -delete 2>/dev/null; find /var/log -name "*.xz" -delete 2>/dev/null; echo "rotated logs deleted"')

    if 'btmp' in categories:
        cmds.append('find /var/log -name "btmp-*" -delete 2>/dev/null; cat /dev/null > /var/log/btmp 2>/dev/null; echo "btmp cleaned"')

    if 'root_logs' in categories:
        cmds.append('find /root -maxdepth 1 -name "*.log" -delete 2>/dev/null; echo "root logs deleted"')

    if 'trojan' in categories:
        cmds.append('rm -rf /root/trojan-web /root/trojan /root/hy 2>/dev/null; echo "install files removed"')

    if 'old_kernels' in categories:
        cmds.append('package-cleanup --oldkernels --count=1 -y 2>/dev/null || yum remove -y $(rpm -q kernel | head -n -1) 2>/dev/null; echo "old kernels removed"')

    if 'yum_cache' in categories:
        cmds.append('yum clean all 2>/dev/null; rm -rf /var/cache/yum/* 2>/dev/null; echo "yum cache cleaned"')

    if 'pkt_log' in categories:
        cmds.append('find /usr/local/vpnserver/packet_log -name "pkt_*.log" -mtime +1 -delete 2>/dev/null; echo "packet logs deleted"')

    if 'softether_log' in categories:
        cmds.append('find /usr/local/vpnserver/server_log -name "*.log" -mtime +7 -delete 2>/dev/null; find /usr/local/vpnserver/security_log -name "*.log" -mtime +7 -delete 2>/dev/null; echo "softether logs deleted"')

    if 'nodejs' in categories:
        cmds.append('rm -rf /usr/local/n 2>/dev/null; rm -f /usr/local/bin/node /usr/local/bin/npm /usr/local/bin/npx 2>/dev/null; echo "nodejs removed"')

    if 'xui' in categories:
        cmds.append('systemctl stop x-ui 2>/dev/null; systemctl disable x-ui 2>/dev/null; rm -rf /usr/local/x-ui 2>/dev/null; rm -f /etc/systemd/system/x-ui.service 2>/dev/null; echo "x-ui removed"')

    if 'cleanup_log' in categories:
        cmds.append('cat /dev/null > /var/log/cleanup_qos.log 2>/dev/null; echo "cleanup log truncated"')

    if 'large_logs' in categories:
        # Truncate active logs (cron, messages, secure, btmp) and delete non-essential big logs
        cmds.append('for f in /var/log/cron /var/log/messages /var/log/secure /var/log/btmp /var/log/openvpn/*.log; do [ -f "$f" ] && cat /dev/null > "$f" 2>/dev/null; done; find /var/log -type f -name "*.log" -size +50M -exec truncate -s 0 {} \\; 2>/dev/null; echo "large logs truncated"')

    if not cmds:
        return JsonResponse({'result': 400, 'msg': '유효한 정리 항목 없음'})

    # 정리 전 디스크
    before_cmd = "df -h / | tail -1 | awk '{print $5}'"
    before_out, _ = _ssh_exec(ip, before_cmd, timeout=10)
    before_pct_str = before_out.strip().replace('%', '')

    # 실행
    full_cmd = '; '.join(cmds) + "; echo '===AFTER==='; df -h / | tail -1"
    output, ok = _ssh_exec(ip, full_cmd, timeout=60)

    # 정리 후 디스크
    after_pct = '?'
    after_line = ''
    after_section = False
    for line in output.split('\n'):
        if '===AFTER===' in line:
            after_section = True
            continue
        if after_section:
            parts = line.split()
            if len(parts) >= 5 and '%' in parts[4]:
                after_pct = parts[4].replace('%', '')
                after_line = line.strip()
                break

    # freed 계산
    freed = ''
    try:
        b = int(before_pct_str)
        a = int(after_pct)
        freed = f'{b - a}%p'
    except:
        freed = '?'

    details = []
    for cat in categories:
        details.append({'category': cat, 'ok': True, 'msg': '완료'})

    return JsonResponse({
        'result': 200,
        'msg': f'정리 완료 ({before_pct_str}% → {after_pct}%)',
        'before_pct': before_pct_str,
        'after_pct': after_pct,
        'freed': freed,
        'details': details,
        'output': output[:1000],
    })


# ============================================================
# [render] UTO 서버 배정 현황 페이지
# ============================================================
@allow_admin
def uto_assignment(request):
    """UTO 서버 배정 현황 (통신사별 ping 순위 + 접속자 기반)"""
    if request.session.get('role', 1) != 1:
        return redirect('/uto_user')
    return render(request, 'admin/uto_assignment.html', {})


# ============================================================
# [api] UTO 서버 배정 현황 데이터
# ============================================================
@allow_admin
def api_read_uto_assignment(request):
    """UTO 중국 3대 통신사별 ping 순위 + 접속자수 기반 서버 배정 현황

    - server_health 테이블에서 ping/score/health 데이터
    - vpnuser.onlines=1 기준 접속자 수
    - vpnlinek 테이블에서 is_auto/서버정보
    - MAX_CONN=50 초과 시 배정 제외
    - is_healthy=0 이면 배정 제외
    """
    MAX_CONN = 50
    telecoms_meta = [
        ('ct', 'China Telecom', '#e74c3c'),
        ('cm', 'China Mobile', '#3498db'),
        ('cu', 'China Unicom', '#2ecc71'),
    ]

    try:
        cur = connections['uto'].cursor()

        # 1. 서버 목록 (vpnlinek에서 su=1, V2RAY 제외)
        cur.execute("""
            SELECT DISTINCT vl.address, vl.ipname, vl.ip, vl.su, vl.is_auto,
                   vl.protocol, vl.maxnum, vl.country
            FROM vpnlinek vl
            WHERE vl.su = 1 AND (vl.protocol IS NULL OR vl.protocol != 'V2RAY')
            ORDER BY vl.address
        """)
        servers_raw = dictfetchall(cur)

        # 2. 실제 접속자 수 (radacct: acctstoptime IS NULL = 현재 연결 중)
        cur.execute("""
            SELECT nasipaddress, COUNT(*) AS cnt
            FROM radacct
            WHERE acctstoptime IS NULL
            GROUP BY nasipaddress
        """)
        conn_map = {r['nasipaddress']: r['cnt'] for r in dictfetchall(cur)}

        # 3. server_health 데이터 (통신사별 ping, score, healthy)
        cur.execute("""
            SELECT server_ip, cn_telecom, ping_avg, ping_min, ping_max, score,
                   is_healthy, health_msg, last_check
            FROM server_health
        """)
        health_rows = dictfetchall(cur)
        # {server_ip: {cn_telecom: {...}}}
        health_map = {}
        for h in health_rows:
            ip = h['server_ip']
            tc = h['cn_telecom']
            if ip not in health_map:
                health_map[ip] = {}
            health_map[ip][tc] = h

        result = {}
        for tc_code, tc_name, tc_color in telecoms_meta:
            servers = []
            rank = 0

            # 서버별 데이터 조합
            server_list = []
            for s in servers_raw:
                ip = s['address']
                conn_count = conn_map.get(ip, 0)
                health_tc = health_map.get(ip, {}).get(tc_code, {})
                health_all = health_map.get(ip, {}).get('all', {})
                is_healthy = health_all.get('is_healthy', 1) if health_all else 1
                health_msg = health_all.get('health_msg', '') if health_all else ''
                ping_avg = float(health_tc['ping_avg']) if health_tc.get('ping_avg') is not None else None
                ping_min = float(health_tc['ping_min']) if health_tc.get('ping_min') is not None else None
                ping_max = float(health_tc['ping_max']) if health_tc.get('ping_max') is not None else None

                # Score = ping_avg * 0.7 + conn_count * 0.3
                if ping_avg is not None:
                    score = round(ping_avg * 0.7 + conn_count * 0.3, 1)
                else:
                    score = None

                check_time = health_tc.get('last_check') or health_all.get('last_check')
                if check_time and hasattr(check_time, 'strftime'):
                    check_time = check_time.strftime('%Y-%m-%d %H:%M:%S')

                # ISP from IP prefix
                kr_isp = 'SK' if ip.startswith('218.49.') or ip.startswith('221.143.') or ip.startswith('218.233.') else 'KT' if ip.startswith('218.158.') or ip.startswith('125.132.') or ip.startswith('14.51.') else 'LG' if ip.startswith('112.218.') else 'ETC'

                # is_auto: 1=auto, 2=EM
                is_auto = s['is_auto']

                server_list.append({
                    'name': s['ipname'],
                    'ip': ip,
                    'domain': s['ip'],
                    'protocol': s['protocol'] or 'IKEV2',
                    'kr_isp': kr_isp,
                    'is_auto': is_auto,
                    'ping_avg': ping_avg,
                    'ping_min': ping_min,
                    'ping_max': ping_max,
                    'conn_count': conn_count,
                    'score': score,
                    'is_healthy': is_healthy,
                    'health_msg': health_msg,
                    'check_time': check_time,
                    'maxnum': s['maxnum'] or 100,
                })

            # Score 순 정렬 (is_auto DESC → score ASC → conn_count ASC)
            server_list.sort(key=lambda x: (
                -(x['is_auto'] or 0),
                x['score'] if x['score'] is not None else 99999,
                x['conn_count'],
            ))

            for s in server_list:
                is_assignable = (
                    s['is_auto'] >= 1
                    and s['ping_avg'] is not None
                    and s['conn_count'] < MAX_CONN
                    and s['is_healthy']
                    and s['protocol'] != 'V2RAY'
                )
                if is_assignable:
                    rank += 1
                    s['rank'] = rank
                else:
                    s['rank'] = None
                s['is_assignable'] = is_assignable

            top = next((s for s in server_list if s['rank'] == 1), None)

            result[tc_code] = {
                'name': tc_name,
                'color': tc_color,
                'servers': server_list,
                'top_server': top,
                'assignable_count': sum(1 for s in server_list if s['is_assignable']),
                'total_count': len(server_list),
            }

        # 마지막 측정 시간
        cur.execute("SELECT MAX(last_check) AS last_check FROM server_health")
        lc = dictfetchall(cur)
        last_check = lc[0]['last_check']
        if last_check and hasattr(last_check, 'strftime'):
            last_check = last_check.strftime('%Y-%m-%d %H:%M:%S')

        return JsonResponse({
            'result': 200,
            'telecoms': result,
            'last_check': last_check,
            'max_conn': MAX_CONN,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO is_auto 토글
# ============================================================
@allow_admin
def api_toggle_uto_is_auto(request):
    """vpnlinek/vpnlinek26 is_auto 토글"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})
    server_name = request.POST.get('name', '')
    if not server_name:
        return JsonResponse({'result': 400, 'msg': 'name required'})
    try:
        cur = connections['uto'].cursor()
        # 현재 값 확인 (동일 ipname이 여러 프로토콜로 존재할 수 있음)
        cur.execute("SELECT MAX(is_auto) FROM vpnlinek WHERE ipname = %s", [server_name])
        row = cur.fetchone()
        if not row or row[0] is None:
            return JsonResponse({'result': 404, 'msg': 'server not found'})
        # MAX(is_auto) >= 1이면 → 전부 0으로, 아니면 → 전부 1로
        new_val = 0 if row[0] >= 1 else 1
        # vpnlinek — 동일 ipname의 모든 행을 같은 값으로
        cur.execute(
            "UPDATE vpnlinek SET is_auto = %s WHERE ipname = %s",
            [new_val, server_name]
        )
        # vpnlinek26도 동일하게
        cur.execute(
            "UPDATE vpnlinek26 SET is_auto = %s WHERE ipname = %s",
            [new_val, server_name]
        )
        return JsonResponse({'result': 200, 'name': server_name, 'is_auto': new_val})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 사용자 종합 진단 (계정/세션/이력 분석)
# ============================================================
@allow_admin
def api_read_uto_user_diagnosis(request):
    """UTO 고객 문의 시 한눈에 파악할 수 있는 종합 진단 데이터"""
    user_id = request.POST.get('user_id')
    try:
        with _uto_cursor() as cur:
            # ── 1. 계정 기본 정보 ──
            cur.execute("""
                SELECT id, vuser, vpass, `groups`, kz, game, member, hyid, session,
                       cash, onlines,
                       DATE_FORMAT(lastdate, '%%Y-%%m-%%d %%H:%%i:%%s') as lastdate,
                       DATE_FORMAT(creatdate, '%%Y-%%m-%%d %%H:%%i:%%s') as creatdate,
                       DATE_FORMAT(lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                       userip, nasip, vpnip, vpntype, forcedip, port,
                       hmail, hqq, haddr, hmemo, flow
                FROM vpnuser WHERE id = %s
            """, [user_id])
            rows = dictfetchall(cur)
            if not rows:
                return JsonResponse({'result': 404, 'msg': '사용자를 찾을 수 없습니다'})
            user = rows[0]
            vuser = user['vuser']

            # 만료 여부
            expired = False
            days_left = None
            if user['lastdate']:
                try:
                    from datetime import datetime as dt
                    exp_dt = dt.strptime(user['lastdate'], '%Y-%m-%d %H:%M:%S')
                    expired = exp_dt < dt.now()
                    days_left = (exp_dt - dt.now()).days
                except:
                    pass

            kz_labels = {1: '정상', 2: '차단'}
            hyid_labels = {1: '무료', 2: '일반', 3: '고급', 4: '기업', 5: '전용선', 7: '대기업', 8: '내부'}
            groups_labels = {'BY': 'BY (월정액)', 'LL': 'LL (트래픽)', 'NEW': 'NEW (신규)'}

            account = {
                'id': user['id'],
                'vuser': vuser,
                'groups': user['groups'] or 'NEW',
                'groups_label': groups_labels.get(user['groups'], user['groups'] or 'NEW'),
                'kz': user['kz'],
                'kz_label': kz_labels.get(user['kz'], str(user['kz'])),
                'game': user['game'] or '',
                'member': user['member'] or '-',
                'hyid': user['hyid'],
                'hyid_label': hyid_labels.get(user['hyid'], str(user['hyid'])),
                'session': user['session'] or 1,
                'cash': user['cash'] or 0,
                'lastdate': user['lastdate'] or '',
                'creatdate': user['creatdate'] or '',
                'lasttime': user['lasttime'] or '',
                'expired': expired,
                'days_left': days_left,
                'port': user['port'] or '',
                'forcedip': user['forcedip'] or '',
                'hmail': user['hmail'] or '',
                'hqq': user['hqq'] or '',
                'hmemo': user['hmemo'] or '',
                'flow': user['flow'] or 0,
                'onlines': user['onlines'],
            }

            # ── 2. 현재 활성 세션 ──
            cur.execute("""
                SELECT radacctid, nasipaddress, nasporttype, acctstarttime,
                       acctsessiontime, callingstationid, framedipaddress,
                       acctinputoctets, acctoutputoctets
                FROM radacct
                WHERE username = %s AND acctstoptime IS NULL
                ORDER BY acctstarttime DESC
            """, [vuser])
            active_sessions = []
            nas_ips = set()
            for r in dictfetchall(cur):
                nas_ips.add(r['nasipaddress'])
                active_sessions.append({
                    'radacctid': r['radacctid'],
                    'nas_ip': r['nasipaddress'] or '',
                    'protocol': r['nasporttype'] or '',
                    'start_time': str(r['acctstarttime']) if r['acctstarttime'] else '',
                    'session_sec': r['acctsessiontime'] or 0,
                    'client_ip': r['callingstationid'] or '',
                    'private_ip': r['framedipaddress'] or '',
                    'input_bytes': r['acctinputoctets'] or 0,
                    'output_bytes': r['acctoutputoctets'] or 0,
                })

            # ── 3. 최근 세션 이력 (20건) ──
            cur.execute("""
                SELECT radacctid, nasipaddress, nasporttype, acctstarttime, acctstoptime,
                       acctsessiontime, callingstationid, acctterminatecause,
                       acctinputoctets, acctoutputoctets, framedipaddress
                FROM radacct
                WHERE username = %s
                ORDER BY radacctid DESC
                LIMIT 20
            """, [vuser])
            recent_sessions = []
            for r in dictfetchall(cur):
                nas_ips.add(r['nasipaddress'])
                sess = r['acctsessiontime'] or 0
                if sess > 10:
                    status = 'success'
                elif r['acctstoptime'] is None:
                    status = 'active'
                else:
                    status = 'failed'
                recent_sessions.append({
                    'radacctid': r['radacctid'],
                    'nas_ip': r['nasipaddress'] or '',
                    'protocol': r['nasporttype'] or '',
                    'start_time': str(r['acctstarttime']) if r['acctstarttime'] else '',
                    'stop_time': str(r['acctstoptime']) if r['acctstoptime'] else '',
                    'session_sec': sess,
                    'client_ip': r['callingstationid'] or '',
                    'private_ip': r['framedipaddress'] or '',
                    'terminate_cause': r['acctterminatecause'] or '',
                    'status': status,
                    'input_bytes': r['acctinputoctets'] or 0,
                    'output_bytes': r['acctoutputoctets'] or 0,
                })

            # ── 4. 프로토콜별 성공/실패 요약 (최근 7일) ──
            cur.execute("""
                SELECT nasporttype,
                       COUNT(*) as total,
                       SUM(CASE WHEN acctsessiontime > 10 THEN 1 ELSE 0 END) as success_cnt,
                       SUM(CASE WHEN acctsessiontime <= 10 AND acctstoptime IS NOT NULL THEN 1 ELSE 0 END) as fail_cnt
                FROM radacct
                WHERE username = %s AND acctstarttime >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY nasporttype
            """, [vuser])
            proto_summary = []
            for r in dictfetchall(cur):
                total = r['total'] or 0
                succ = int(r['success_cnt'] or 0)
                fail = int(r['fail_cnt'] or 0)
                rate = round(succ * 100 / total, 1) if total > 0 else 0
                proto_summary.append({
                    'protocol': r['nasporttype'] or '',
                    'total': total,
                    'success': succ,
                    'failed': fail,
                    'rate': rate,
                })

            # ── 5. NAS IP → 서버 이름 매핑 (vpnlinek) ──
            server_map = {}
            nas_ips.discard(None)
            if nas_ips:
                placeholders = ','.join(['%s'] * len(nas_ips))
                cur.execute("""
                    SELECT DISTINCT address, ip FROM vpnlinek WHERE address IN ({})
                """.format(placeholders), list(nas_ips))
                for r in dictfetchall(cur):
                    server_map[r['address']] = r['ip']

            # ── 6. 앱 접속 실패 로그 (sv_failed_server) ──
            # user_id 인덱스가 없어 37M행 풀스캔 → 별도 API로 분리
            recent_failures = []

            # ── 7. 앱 API 로그 (applogin_log) ──
            app_logs = []
            cur.execute("""
                SELECT login_time, client_ip, host, request_uri, app_version, os
                FROM applogin_log
                WHERE username = %s
                ORDER BY id DESC
                LIMIT 20
            """, [vuser])
            for r in dictfetchall(cur):
                app_logs.append({
                    'time': str(r['login_time']) if r['login_time'] else '',
                    'client_ip': r['client_ip'] or '',
                    'host': r['host'] or '',
                    'uri': r['request_uri'] or '',
                    'app_version': r['app_version'] or '',
                    'os': r['os'] or '',
                })

        return JsonResponse({'result': 200, 'data': {
            'account': account,
            'active_sessions': active_sessions,
            'recent_sessions': recent_sessions,
            'proto_summary': proto_summary,
            'server_map': server_map,
            'recent_failures': recent_failures,
            'app_logs': app_logs,
        }})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 사용자 접속 실패 로그 (별도 비동기 로드)
# ============================================================
@allow_admin
def api_read_uto_user_failures(request):
    """sv_failed_server에서 접속 실패 로그 조회 (user_id 인덱스 없어 느릴 수 있음)"""
    user_id = request.POST.get('user_id', '').strip()
    if not user_id or not user_id.isdigit():
        return JsonResponse({'result': 400, 'msg': 'invalid user_id'})
    try:
        with _uto_cursor() as cur:
            cur.execute("SET SESSION max_execution_time = 15000")  # 15초 제한
            cur.execute("""
                SELECT name, domain, protocol, platform, app_version, device_version,
                       DATE_FORMAT(failed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as failed_at
                FROM sv_failed_server
                WHERE user_id = %s AND failed_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                ORDER BY failed_at DESC
                LIMIT 20
            """, [int(user_id)])
            rows = []
            for r in dictfetchall(cur):
                rows.append({
                    'server_name': r['name'] or '',
                    'server_domain': r['domain'] or '',
                    'protocol': r['protocol'] or '',
                    'platform': r['platform'] or '',
                    'device': r['device_version'] or '',
                    'time': r['failed_at'] or '',
                    'app_version': r['app_version'] or '',
                })
        return JsonResponse({'result': 200, 'data': rows})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# 변경내역 로그 헬퍼
# ============================================================
def _log_uto_change(vuser, change_type, field_name, old_value, new_value, description, admin_user, source='uto-admin'):
    """uto_change_log 테이블에 변경 내역 기록"""
    try:
        with _uto_cursor() as cur:
            cur.execute("""
                INSERT INTO uto_change_log (vuser, change_type, field_name, old_value, new_value, description, admin_user, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [vuser, change_type, field_name, str(old_value) if old_value is not None else None,
                  str(new_value) if new_value is not None else None, description, admin_user, source])
    except Exception:
        traceback.print_exc()


# ============================================================
# [render] UTO 신규가입 페이지
# ============================================================
@allow_admin
def uto_register(request):
    return render(request, 'admin/uto_register.html')


# ============================================================
# [api] UTO 신규가입 — vuser 중복 확인
# ============================================================
@allow_admin
def api_read_uto_check_vuser(request):
    try:
        vuser = (request.GET.get('vuser') or '').strip()
        if not vuser:
            return JsonResponse({'result': 400, 'msg': '사용자명을 입력하세요.'})

        with _uto_cursor() as cur:
            cur.execute("SELECT id, vuser FROM vpnuser WHERE vuser = %s", [vuser])
            row = cur.fetchone()
            if row:
                return JsonResponse({'result': 409, 'msg': f'이미 존재하는 사용자명입니다: {vuser}'})

        return JsonResponse({'result': 200, 'msg': '사용 가능한 사용자명입니다.'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 신규가입 처리
# ============================================================
@allow_admin
def api_create_uto_register(request):
    try:
        vuser = (request.POST.get('vuser') or '').strip()
        vpass = (request.POST.get('vpass') or '').strip()
        hyid = int(request.POST.get('hyid', 2))
        phone = (request.POST.get('phone') or '').strip()
        memo = (request.POST.get('memo') or '').strip()

        if not vuser:
            return JsonResponse({'result': 400, 'msg': '사용자명(vuser)을 입력하세요.'})
        if not vpass:
            return JsonResponse({'result': 400, 'msg': '비밀번호를 입력하세요.'})
        if len(vuser) < 2 or len(vuser) > 50:
            return JsonResponse({'result': 400, 'msg': '사용자명은 2~50자여야 합니다.'})
        if len(vpass) < 2 or len(vpass) > 20:
            return JsonResponse({'result': 400, 'msg': '비밀번호는 2~20자여야 합니다.'})
        if hyid not in (1, 2, 3, 4, 5, 7, 8):
            return JsonResponse({'result': 400, 'msg': '회원등급이 올바르지 않습니다.'})

        # hyid별 자동 설정값
        HYID_CONF = {
            1: {'label': '무료회원',       'speed': 0,      'game': 'KOREA'},
            2: {'label': '일반회원',       'speed': 2048,   'game': 'KOREA'},
            3: {'label': '고급회원(4M)',   'speed': 4096,   'game': 'SS'},
            4: {'label': '기업회원(10M)',  'speed': 10240,  'game': 'SS'},
            5: {'label': '전용선회원(20M)','speed': 20480,  'game': 'SS'},
            7: {'label': '대기업회원(50M)','speed': 51200,  'game': 'SS'},
            8: {'label': '내부사용',       'speed': 102400, 'game': 'SS'},
        }
        conf = HYID_CONF[hyid]
        hyid_label = conf['label']
        game = conf['game']
        speed = conf['speed']
        session_val = 1  # 기본 1세션, 나중에 결제 시 변경
        admin_user = request.session.get('username', 'unknown')

        with _uto_cursor() as cur:
            # 중복 확인
            cur.execute("SELECT id FROM vpnuser WHERE vuser = %s", [vuser])
            if cur.fetchone():
                return JsonResponse({'result': 409, 'msg': f'이미 존재하는 사용자명입니다: {vuser}'})

            # 만료일 = 현재 시간 (즉시 만료, POS 연동 필요)
            now = datetime.now()
            lastdate = now
            lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S')

            # port 자동 부여 (중복 방지)
            next_port = _next_uto_port(cur)

            # transfer_enable: 기존 유저와 동일 값 (~4.7PB, 사실상 무제한)
            transfer_enable = 5272832192811000

            # vpnuser에 계정 생성 (session=1, updk/downdk=speed 자동설정)
            cur.execute("""
                INSERT INTO vpnuser (vuser, vpass, `session`, `groups`, lastdate, creatdate, kz, hyid, game, ddh,
                                     updk, downdk, attribute, op, forcedip, member, port, transfer_enable)
                VALUES (%s, %s, %s, 'BY', %s, NOW(), 1, %s, %s, %s,
                        %s, %s, 'Cleartext-Password', ':=', 'S62', %s, %s, %s)
            """, [vuser, vpass, session_val, lastdate_str, hyid, game, phone, speed, speed, admin_user, next_port, transfer_enable])

            new_id = cur.lastrowid

        # 변경 로그 기록
        speed_label = f'{speed // 1024}M' if speed >= 1024 else f'{speed}K'
        desc = f'신규가입 [{hyid_label}] 속도:{speed_label} 서버:{game} (즉시만료, POS연동필요)'
        if memo:
            desc += f' (메모: {memo})'
        _log_uto_change(vuser, 'create', 'lastdate', 'NULL', lastdate_str, desc, admin_user)

        return JsonResponse({
            'result': 200,
            'msg': f'가입 완료: {vuser} (ID: {new_id}, {hyid_label}, 속도:{speed_label}, 만료일: {lastdate_str} - POS연동 필요)',
            'user_id': new_id,
            'lastdate': lastdate_str,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [render] UTO 무통장 연장 페이지
# ============================================================
@allow_admin
def uto_extend(request):
    return render(request, 'admin/uto_extend.html')


# ============================================================
# [api] UTO 무통장 연장 처리
# ============================================================
@allow_admin
def api_create_uto_extend(request):
    try:
        vuser = (request.POST.get('vuser') or '').strip()
        months = int(request.POST.get('months', 0))
        session_val = request.POST.get('session', '')
        memo = (request.POST.get('memo') or '').strip()
        customer_type = (request.POST.get('customer_type') or 'account').strip()
        price = request.POST.get('price', '')

        if not vuser:
            return JsonResponse({'result': 400, 'msg': '사용자명(vuser)을 입력하세요.'})
        if months <= 0 or months > 24:
            return JsonResponse({'result': 400, 'msg': '개월 수는 1~24 사이여야 합니다.'})
        if not memo:
            return JsonResponse({'result': 400, 'msg': '연장 사유를 입력하세요.'})

        ctype_labels = {
            'account': '계정고객',
            'router4': '라우터4M',
            'router10': '라우터10M',
            'router20': '라우터20M',
        }
        ctype_label = ctype_labels.get(customer_type, customer_type)

        admin_user = request.session.get('username', 'unknown')

        # 고객 유형별 설정 (회원등급, 서버그룹)
        # account=일반(2), router4=고급4M(3), router10=기업10M(4), router20=전용선20M(5)
        CTYPE_EXTEND_CONF = {
            'account':  {'hyid': 2, 'game': 'KOREA'},
            'router4':  {'hyid': 3, 'game': 'SS'},
            'router10': {'hyid': 4, 'game': 'SS'},
            'router20': {'hyid': 5, 'game': 'SS'},
        }
        PAID_TRANSFER = 5497558138880  # 5TB

        with _uto_cursor() as cur:
            # 유저 조회
            cur.execute("""SELECT id, vuser, lastdate, `session`, kz, `groups`, hyid,
                                  game, transfer_enable, updk, downdk
                           FROM vpnuser WHERE vuser = %s""", [vuser])
            row = cur.fetchone()
            if not row:
                return JsonResponse({'result': 400, 'msg': f'사용자를 찾을 수 없습니다: {vuser}'})

            user_id, vuser_db, lastdate, cur_session, kz, groups_val, hyid, \
                cur_game, cur_transfer, cur_updk, cur_downdk = row

            # 연장 계산: 만료일이 과거면 현재부터, 미래면 기존 만료일부터
            import datetime
            now = datetime.datetime.now()
            if lastdate and lastdate > now:
                base_date = lastdate
            else:
                base_date = now

            # months 개월 추가
            new_month = base_date.month + months
            new_year = base_date.year + (new_month - 1) // 12
            new_month = ((new_month - 1) % 12) + 1
            import calendar
            max_day = calendar.monthrange(new_year, new_month)[1]
            new_day = min(base_date.day, max_day)
            new_lastdate = base_date.replace(year=new_year, month=new_month, day=new_day)

            old_lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else 'NULL'
            new_lastdate_str = new_lastdate.strftime('%Y-%m-%d %H:%M:%S')

            # UPDATE lastdate
            cur.execute("UPDATE vpnuser SET lastdate = %s WHERE id = %s", [new_lastdate_str, user_id])

            # groups 변경 (NEW → BY)
            if groups_val == 'NEW':
                cur.execute("UPDATE vpnuser SET `groups` = 'BY' WHERE id = %s", [user_id])
                _log_uto_change(vuser, 'extend', 'groups', 'NEW', 'BY', '무통장 연장 시 자동변경', admin_user)

            # 고객 유형별 자동 설정 (회원등급, 서버그룹, 트래픽, 속도)
            conf = CTYPE_EXTEND_CONF.get(customer_type, {'hyid': 2, 'game': 'KOREA'})

            # hyid (회원등급) 변경: 고객유형에 맞는 등급으로 설정
            target_hyid = conf['hyid']
            if hyid != target_hyid:
                cur.execute("UPDATE vpnuser SET hyid = %s WHERE id = %s", [target_hyid, user_id])
                _log_uto_change(vuser, 'extend', 'hyid', hyid, target_hyid, '연장 시 회원등급 자동변경', admin_user)

            # game (서버그룹) 변경: NULL/미설정 → KOREA
            target_game = conf['game']
            if cur_game != target_game:
                cur.execute("UPDATE vpnuser SET game = %s WHERE id = %s", [target_game, user_id])
                _log_uto_change(vuser, 'extend', 'game', cur_game or 'NULL', target_game, '연장 시 서버그룹 자동변경', admin_user)

            # transfer_enable (트래픽) 설정: 100MB 이하 → 5TB
            if cur_transfer is None or cur_transfer <= 104857600:
                cur.execute("UPDATE vpnuser SET transfer_enable = %s WHERE id = %s", [PAID_TRANSFER, user_id])
                old_te = f'{cur_transfer // (1024*1024)}MB' if cur_transfer else 'NULL'
                _log_uto_change(vuser, 'extend', 'transfer_enable', old_te, '5TB', '연장 시 트래픽 자동설정', admin_user)

            # session 변경 (요청한 경우)
            actual_session = cur_session
            if session_val and session_val.isdigit():
                new_sess = int(session_val)
                if new_sess != cur_session:
                    cur.execute("UPDATE vpnuser SET `session` = %s WHERE id = %s", [new_sess, user_id])
                    _log_uto_change(vuser, 'extend', 'session', cur_session, new_sess, f'무통장 연장 시 세션 변경', admin_user)
                    actual_session = new_sess

            # updk/downdk (속도) 자동 설정
            target_speed = _calc_uto_speed(target_hyid, actual_session)
            if cur_updk != target_speed or cur_downdk != target_speed:
                cur.execute("UPDATE vpnuser SET updk = %s, downdk = %s WHERE id = %s", [target_speed, target_speed, user_id])
                speed_label = f'{target_speed // 1024}M' if target_speed >= 1024 else f'{target_speed}K'
                _log_uto_change(vuser, 'extend', 'updk', cur_updk, target_speed, f'연장 시 속도 자동설정 → {speed_label}', admin_user)

            # member (대리점) → 연장한 관리자 ID로 기록
            cur.execute("UPDATE vpnuser SET member = %s WHERE id = %s", [admin_user, user_id])

            # 변경 로그 기록
            desc = f'무통장 {months}개월 연장 [{ctype_label}]'
            if price:
                desc += f' ¥{price}元'
            if memo:
                desc += f' (메모: {memo})'
            _log_uto_change(vuser, 'extend', 'lastdate', old_lastdate_str, new_lastdate_str, desc, admin_user)

        return JsonResponse({
            'result': 200,
            'msg': f'{vuser} — {ctype_label} {months}개월 연장 완료 (새 만료일: {new_lastdate_str})',
            'new_lastdate': new_lastdate_str,
            'old_lastdate': old_lastdate_str,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 패키지 변경 (잔여일수 비례환산)
# ============================================================
PKG_MONTHLY = {
    'account_1': 100, 'account_2': 180, 'account_3': 260,
    'account_5': 420, 'account_10': 820,
    'router4': 200, 'router10': 400, 'router20': 800,
}
PKG_LABELS = {
    'account_1': '계정 1세션', 'account_2': '계정 2세션', 'account_3': '계정 3세션',
    'account_5': '계정 5세션', 'account_10': '계정 10세션',
    'router4': '라우터 4M', 'router10': '라우터 10M', 'router20': '라우터 20M',
}

def _pkg_session(pkg):
    """account_N 형태에서 세션 수 추출. 라우터는 None."""
    if pkg and pkg.startswith('account_'):
        try:
            return int(pkg.split('_')[1])
        except Exception:
            pass
    return None


@allow_admin
def api_update_uto_package_change(request):
    """패키지 변경 시 잔여일수를 월단가 비율로 환산하여 만료일 변경.
    계정→계정: 세션 수도 변경. 라우터→라우터: 세션 변경 없음.
    """
    try:
        vuser = (request.POST.get('vuser') or '').strip()
        old_pkg = (request.POST.get('old_pkg') or '').strip()
        new_pkg = (request.POST.get('new_pkg') or '').strip()
        memo = (request.POST.get('memo') or '').strip()

        if not vuser:
            return JsonResponse({'result': 400, 'msg': '사용자명을 입력하세요.'})
        if not old_pkg or not new_pkg:
            return JsonResponse({'result': 400, 'msg': '현재/변경 패키지를 선택하세요.'})
        if old_pkg == new_pkg:
            return JsonResponse({'result': 400, 'msg': '현재 패키지와 변경 패키지가 같습니다.'})
        if not memo:
            return JsonResponse({'result': 400, 'msg': '패키지 변경 사유를 입력하세요.'})
        if old_pkg not in PKG_MONTHLY or new_pkg not in PKG_MONTHLY:
            return JsonResponse({'result': 400, 'msg': f'잘못된 패키지: {old_pkg} / {new_pkg}'})

        old_monthly = PKG_MONTHLY[old_pkg]
        new_monthly = PKG_MONTHLY[new_pkg]
        admin_user = request.session.get('username', 'unknown')

        import datetime
        now = datetime.datetime.now()

        with _uto_cursor() as cur:
            cur.execute("SELECT id, vuser, lastdate, `session`, kz, hyid FROM vpnuser WHERE vuser = %s", [vuser])
            row = cur.fetchone()
            if not row:
                return JsonResponse({'result': 400, 'msg': f'사용자를 찾을 수 없습니다: {vuser}'})

            user_id, vuser_db, lastdate, cur_session, kz, hyid = row

            # 잔여일수 계산
            remain_days = 0
            if lastdate and lastdate > now:
                remain_days = (lastdate - now).days

            # 비례환산
            new_days = int(remain_days * old_monthly / new_monthly)
            new_lastdate = now + datetime.timedelta(days=new_days)

            old_lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else 'NULL'
            new_lastdate_str = new_lastdate.strftime('%Y-%m-%d %H:%M:%S')

            # UPDATE lastdate
            cur.execute("UPDATE vpnuser SET lastdate = %s WHERE id = %s", [new_lastdate_str, user_id])

            old_label = PKG_LABELS.get(old_pkg, old_pkg)
            new_label = PKG_LABELS.get(new_pkg, new_pkg)
            desc = f'패키지 변경: {old_label} → {new_label} (¥{old_monthly}→¥{new_monthly}/월, {remain_days}일→{new_days}일)'
            if memo:
                desc += f' (메모: {memo})'
            _log_uto_change(vuser, 'edit', 'lastdate', old_lastdate_str, new_lastdate_str, desc, admin_user)

            # 세션 변경 (계정→계정 간 전환 시) + 속도 자동 연동
            new_sess = _pkg_session(new_pkg)
            if new_sess and new_sess != cur_session:
                cur.execute("UPDATE vpnuser SET `session` = %s WHERE id = %s", [new_sess, user_id])
                _log_uto_change(vuser, 'edit', 'session', cur_session, new_sess,
                                f'패키지 변경 시 세션 변경 ({old_label} → {new_label})', admin_user)
                # 속도 자동 조정 (일반회원: 세션×2048K)
                new_speed = _calc_uto_speed(hyid, new_sess)
                old_speed = _calc_uto_speed(hyid, cur_session)
                if new_speed != old_speed:
                    cur.execute("UPDATE vpnuser SET updk = %s, downdk = %s WHERE id = %s", [new_speed, new_speed, user_id])
                    speed_label = f'{new_speed // 1024}M' if new_speed >= 1024 else f'{new_speed}K'
                    _log_uto_change(vuser, 'edit', 'updk', old_speed, new_speed,
                                    f'패키지 변경 속도 자동조정 → {speed_label}', admin_user)

        msg = (f'{vuser} — 패키지 변경 완료\n'
               f'{old_label} → {new_label}\n'
               f'잔여일: {remain_days}일 → {new_days}일\n'
               f'새 만료일: {new_lastdate_str}')
        return JsonResponse({'result': 200, 'msg': msg})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [render] UTO 변경내역 페이지
# ============================================================
@allow_admin
def uto_change_history(request):
    # 최고관리자만 접근 가능
    if request.session.get('role', 1) != 1:
        return redirect('/uto_user')
    return render(request, 'admin/uto_change_history.html')


# ============================================================
# [api] UTO 변경내역 DataTables
# ============================================================
@allow_admin
def api_read_uto_change_history(request):
    # 최고관리자만 접근 가능
    if request.session.get('role', 1) != 1:
        return JsonResponse({'result': 403, 'msg': '권한 없음'})
    try:
        start = int(request.POST.get('start', 0))
        length = int(request.POST.get('length', 50))
        draw = int(request.POST.get('draw', 1))

        # 필터
        search_vuser = (request.POST.get('vuser') or '').strip()
        search_type = (request.POST.get('change_type') or '').strip()
        search_source = (request.POST.get('source') or '').strip()
        date_from = (request.POST.get('date_from') or '').strip()
        date_to = (request.POST.get('date_to') or '').strip()

        # prddbh ddtype → change_type/source 매핑
        # adm→extend/admin-php, add→create/sales-php, android/apple/PC→extend/api-app, xf→extend/sales-php
        prddbh_sql = """
            SELECT
                CONCAT('p', id) as id,
                vpnus as vuser,
                CASE
                    WHEN ddtype IN ('adm') THEN 'extend'
                    WHEN ddtype IN ('add') THEN 'create'
                    WHEN ddtype IN ('android','apple','PC') THEN 'extend'
                    WHEN ddtype IN ('xf') THEN 'extend'
                    ELSE 'edit'
                END as change_type,
                CASE
                    WHEN ddtype = 'add' THEN 'vpnuser'
                    ELSE 'lastdate'
                END as field_name,
                CASE
                    WHEN ddtype = 'add' THEN ''
                    ELSE IFNULL(DATE_FORMAT(oldlastdate, '%%Y-%%m-%%d %%H:%%i:%%s'), '')
                END as old_value,
                CASE
                    WHEN ddtype = 'add' THEN vpnus
                    ELSE IFNULL(DATE_FORMAT(newlastdate, '%%Y-%%m-%%d %%H:%%i:%%s'), '')
                END as new_value,
                CONCAT(IFNULL(spname,''), ' [', IFNULL(ddtype,''), '] ', IFNULL(CAST(sjg AS CHAR),''), '원') as description,
                IFNULL(memus, '') as admin_user,
                CASE
                    WHEN ddtype = 'adm' THEN 'admin-php'
                    WHEN ddtype = 'add' THEN 'sales-php'
                    WHEN ddtype IN ('android','apple','PC') THEN 'api-app'
                    WHEN ddtype = 'xf' THEN 'sales-php'
                    ELSE 'admin-php'
                END as source,
                DATE_FORMAT(ddtime, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
            FROM prddbh
        """

        changelog_sql = """
            SELECT
                CONCAT('c', id) as id,
                vuser, change_type, field_name,
                IFNULL(old_value, '') as old_value,
                IFNULL(new_value, '') as new_value,
                IFNULL(description, '') as description,
                IFNULL(admin_user, '') as admin_user,
                IFNULL(source, 'uto-admin') as source,
                DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
            FROM uto_change_log
        """

        union_sql = f"SELECT * FROM ({changelog_sql} UNION ALL {prddbh_sql}) AS combined"

        wc = " WHERE 1=1 "
        params = []
        if search_vuser:
            wc += " AND vuser LIKE %s "
            params.append(f'%{search_vuser}%')
        if search_type:
            wc += " AND change_type = %s "
            params.append(search_type)
        if search_source:
            wc += " AND source = %s "
            params.append(search_source)
        if date_from:
            wc += " AND created_at >= %s "
            params.append(date_from)
        if date_to:
            wc += " AND created_at <= %s "
            params.append(date_to + ' 23:59:59')

        with _uto_cursor() as cur:
            # 카운트
            cur.execute(f"SELECT COUNT(*) FROM ({union_sql} {wc}) AS cnt_q", params)
            total = cur.fetchone()[0]

            # 데이터
            cur.execute(f"""
                {union_sql} {wc}
                ORDER BY created_at DESC
                LIMIT %s, %s
            """, params + [start, length])

            columns = [col[0] for col in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        return JsonResponse({
            'result': 200,
            'recordsTotal': total,
            'recordsFiltered': total,
            'draw': draw,
            'data': rows,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# Pospal(银豹) POS 연동 — FRS 판매 자동감지 + VPN 자동연장
# ============================================================
import hashlib
import urllib.request
import ssl
import gzip
import calendar

POSPAL_APP_ID = "3C3F51AED8FFF46FE17AC8CDF07FB096"
POSPAL_APP_KEY = "685523063614039568"
POSPAL_HOST = "https://area4-win.pospal.cn:443"

# Pospal 결제수단 코드 → 표시명
POSPAL_PAY_MAP = {
    'payCode_1': '现金',
    'payCode_2': '储值卡',
    'payCode_3': '银联',
    'payCode_4': '次卡',
    'payCode_100': '云闪付',
    'payCode_101': '门店码',
    'payCode_102': '公司转账',
    'payCode_103': '攸淘转账',
    'payCode_105': '美团',
    'payCode_106': '手机付款',
}

# Pospal 바코드 → UTO 요금제 매핑
# months: 연장 개월수, session: VPN 동시접속 세션수, is_new: 신규계정여부
POSPAL_BARCODE_MAP = {
    '2003253000115': {'name': 'FRS 新ID 1个月',  'months': 1,  'session': 1,  'is_new': True,  'price': 100},
    '2554998127990': {'name': 'FRS1 1Mo',         'months': 1,  'session': 1,  'is_new': False, 'price': 100},
    '2003253000139': {'name': 'FRS 新ID 6个月',  'months': 6,  'session': 1,  'is_new': True,  'price': 400},
    '2003253000122': {'name': 'FRS 新ID 1年',    'months': 12, 'session': 1,  'is_new': True,  'price': 600},
    '2003253000146': {'name': 'FRS 延长 6个月',   'months': 6,  'session': 1,  'is_new': False, 'price': 600},
    '2001061105510': {'name': 'FRS 1M延长 1年',   'months': 12, 'session': 1,  'is_new': False, 'price': 300},
    '2101182101405': {'name': 'FRS 1M新ID 一年',  'months': 12, 'session': 1,  'is_new': True,  'price': 600},
    '2101182115099': {'name': 'FRS1 new 6Mo',      'months': 6,  'session': 1,  'is_new': True,  'price': 400},
    '2101182222407': {'name': 'FRS1 6Mo',          'months': 6,  'session': 1,  'is_new': False, 'price': 200},
    '2003253000023': {'name': 'FRS 2M 新ID 1年',  'months': 12, 'session': 2,  'is_new': True,  'price': 1200},
    '2003253000030': {'name': 'FRS 2M 新ID 6个月','months': 6,  'session': 2,  'is_new': True,  'price': 800},
    '2003253000047': {'name': 'FRS 5M速度 1个月',  'months': 1,  'session': 5,  'is_new': False, 'price': 500},
    '2003253000054': {'name': 'FRS K2 个人2M 路由器 1年',   'months': 12, 'session': 2, 'is_new': True,  'price': 1200},
    '2003253000061': {'name': 'FRS K2 个人2M 路由器 6个月', 'months': 6,  'session': 2, 'is_new': True,  'price': 1000},
    '2003253000078': {'name': 'FRS 4M企业路由器1年K2',       'months': 12, 'session': 4, 'is_new': True,  'price': 2400},
    '2003253000085': {'name': 'FRS 4M企业路由器半年',        'months': 6,  'session': 4, 'is_new': True,  'price': 1800},
    '2003253000092': {'name': 'FRS K2延长 个人2M 路由器 1年',   'months': 12, 'session': 2, 'is_new': False, 'price': 600},
    '2003253000108': {'name': 'FRS K2延长 个人2M 路由器 6个月', 'months': 6,  'session': 2, 'is_new': False, 'price': 400},
    '2975912904815': {'name': 'FRS10 1Yr',         'months': 12, 'session': 10, 'is_new': False, 'price': 5000},
}

# 처리 완료된 ticket SN을 DB에 저장하여 중복 처리 방지
# (uto_pospal_log 테이블 사용)

# 세션별 연간 가격 (세션 변경 시 남은기간 가격비례 환산용)
SESSION_YEARLY_PRICE = {
    1: 600,
    2: 1200,
    4: 2400,
    5: 3100,   # ¥600(기본) + ¥500×5(속도)
    10: 5000,
}

# hyid별 기본 속도 (K 단위)
HYID_BASE_SPEED = {1: 0, 2: 2048, 3: 4096, 4: 10240, 5: 20480, 7: 51200, 8: 102400}

def _calc_uto_speed(hyid, session_count):
    """hyid와 세션 수로 속도(updk/downdk) 계산.
    일반회원(hyid=2): session × 2048K
    기타(라우터/무료/내부): hyid별 고정 속도
    """
    base = HYID_BASE_SPEED.get(hyid, 2048)
    if hyid == 2:  # 일반회원만 세션×속도
        return session_count * base
    return base


def _pospal_call(path, body_dict):
    """Pospal Open API 호출 헬퍼"""
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


def _extend_lastdate(vuser, months, session_val=None, admin_user='pospal', source='pospal'):
    """VPN 만료일 연장 (내부 공통 헬퍼)
    세션 감소 시 남은기간을 가격비례로 환산 후 연장
    Returns: (success: bool, message: str, new_lastdate: str or None)
    """
    with _uto_cursor() as cur:
        cur.execute("SELECT id, vuser, lastdate, `session`, `groups`, hyid FROM vpnuser WHERE vuser = %s", [vuser])
        row = cur.fetchone()
        if not row:
            return False, f'사용자를 찾을 수 없습니다: {vuser}', None

        user_id, vuser_db, lastdate, cur_session, groups_val, hyid = row

        now = datetime.now()
        base_date = lastdate if (lastdate and lastdate > now) else now

        # 가격 비례 환산: 세션 줄어들 때 남은기간 × (기존가격/신규가격)
        new_session_int = int(session_val) if session_val else cur_session
        if lastdate and lastdate > now and new_session_int < cur_session:
            remaining_days = (lastdate - now).total_seconds() / 86400.0
            old_price = SESSION_YEARLY_PRICE.get(cur_session, cur_session * 600)
            new_price = SESSION_YEARLY_PRICE.get(new_session_int, new_session_int * 600)
            ratio = old_price / new_price
            from datetime import timedelta
            base_date = now + timedelta(days=int(remaining_days * ratio))

        new_month = base_date.month + months
        new_year = base_date.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1
        max_day = calendar.monthrange(new_year, new_month)[1]
        new_day = min(base_date.day, max_day)
        new_lastdate = base_date.replace(year=new_year, month=new_month, day=new_day)

        old_lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else 'NULL'
        new_lastdate_str = new_lastdate.strftime('%Y-%m-%d %H:%M:%S')

        cur.execute("UPDATE vpnuser SET lastdate = %s WHERE id = %s", [new_lastdate_str, user_id])

        if groups_val == 'NEW':
            cur.execute("UPDATE vpnuser SET `groups` = 'BY' WHERE id = %s", [user_id])
            _log_uto_change(vuser, 'extend', 'groups', 'NEW', 'BY', 'Pospal 판매 자동연장', admin_user, source=source)

        old_session = cur_session
        if session_val and int(session_val) != cur_session:
            new_sess = int(session_val)
            cur.execute("UPDATE vpnuser SET `session` = %s WHERE id = %s", [new_sess, user_id])
            # 속도 자동 조정 (일반회원: 세션×2048K)
            new_speed = _calc_uto_speed(hyid, new_sess)
            old_speed = _calc_uto_speed(hyid, cur_session)
            if new_speed != old_speed:
                cur.execute("UPDATE vpnuser SET updk = %s, downdk = %s WHERE id = %s", [new_speed, new_speed, user_id])

        return True, new_lastdate_str, old_lastdate_str, old_session


# [render] Pospal POS 연동 페이지
@allow_admin
def pospal_sales(request):
    return render(request, 'admin/pospal_sales.html')


# [api] Pospal 최근 판매 조회 (오늘 FRS 상품만)
@allow_admin
def api_read_pospal_tickets(request):
    try:
        date_str = request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
        # Pospal ticket API는 1일 범위만 허용
        start_time = f"{date_str} 00:00:00"
        end_time = f"{date_str} 23:59:59"

        all_tickets = []
        pbp = {"parameterType": "String", "parameterValue": ""}
        for _ in range(10):
            r = _pospal_call("/pospal-api2/openapi/v1/ticketOpenApi/queryTicketPages", {
                "startTime": start_time,
                "endTime": end_time,
                "postBackParameter": pbp,
            })
            if r.get("status") != "success":
                return JsonResponse({'result': 400, 'msg': r.get('messages', ['Pospal API 오류'])[0]})
            batch = r["data"].get("result", [])
            all_tickets.extend(batch)
            if len(batch) < 100:
                break
            pbp = r["data"]["postBackParameter"]

        # 이미 처리된 ticket SN 목록 조회 — {sn: {vuser, refunded}}
        processed_map = {}
        try:
            with _uto_cursor() as cur:
                cur.execute("SELECT ticket_sn, vuser, refunded FROM uto_pospal_log")
                for row in cur.fetchall():
                    processed_map[row[0]] = {'vuser': row[1], 'refunded': row[2]}
        except Exception:
            pass  # 테이블 없으면 무시

        # 전체 ticket 반환 (FRS + 비FRS, 결제수단 포함)
        result_tickets = []
        frs_count = 0
        total_amount = 0
        for t in all_tickets:
            sn = t.get('sn', '')
            frs_items = []
            other_items = []
            for item in t.get('items', []):
                barcode = item.get('productBarcode', '')
                if barcode in POSPAL_BARCODE_MAP:
                    mapping = POSPAL_BARCODE_MAP[barcode]
                    frs_items.append({
                        'barcode': barcode,
                        'name': item.get('name', mapping['name']),
                        'quantity': item.get('quantity', 1),
                        'amount': item.get('totalAmount', 0),
                        'months': mapping['months'],
                        'session': mapping['session'],
                        'is_new': mapping['is_new'],
                    })
                else:
                    other_items.append({
                        'barcode': barcode,
                        'name': item.get('productName', item.get('name', barcode or '상품')),
                        'quantity': item.get('quantity', 1),
                        'amount': item.get('totalAmount', 0),
                    })
            # 결제수단
            payments = []
            for p in t.get('payments', []):
                code = p.get('code', '')
                payments.append({
                    'code': code,
                    'name': POSPAL_PAY_MAP.get(code, code),
                    'amount': p.get('amount', 0),
                })
            if frs_items:
                frs_count += 1
            amt = t.get('totalAmount', 0)
            total_amount += amt
            pinfo = processed_map.get(sn)
            result_tickets.append({
                'sn': sn,
                'datetime': t.get('datetime', ''),
                'totalAmount': amt,
                'cashier': t.get('cashier', {}).get('name', ''),
                'remark': t.get('remark', ''),
                'processed': bool(pinfo) and not pinfo.get('refunded'),
                'refunded': bool(pinfo) and bool(pinfo.get('refunded')),
                'processed_vuser': pinfo['vuser'] if pinfo else '',
                'has_frs': bool(frs_items),
                'frs_items': frs_items,
                'other_items': other_items,
                'payments': payments,
            })

        return JsonResponse({
            'result': 200,
            'tickets': result_tickets,
            'total_count': len(all_tickets),
            'frs_count': frs_count,
            'total_amount': total_amount,
            'date': date_str,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


HYID_MAP = {1: '무료회원', 2: '일반회원', 3: '고급회원', 4: '기업회원', 5: '전용선회원', 7: '대기업회원', 8: '내부사용'}

# [api] Pospal 유저 조회 (연장 전 확인용)
@allow_admin
def api_read_pospal_user(request):
    try:
        vuser = (request.GET.get('vuser') or '').strip()
        barcode = (request.GET.get('barcode') or '').strip()
        if not vuser:
            return JsonResponse({'result': 400, 'msg': '사용자명을 입력하세요.'})

        with _uto_cursor() as cur:
            cur.execute("""SELECT id, vuser, `groups`, `session`, lastdate, creatdate, hqq, kz, hyid
                           FROM vpnuser WHERE vuser = %s""", [vuser])
            row = cur.fetchone()
            if not row:
                return JsonResponse({'result': 404, 'msg': f'사용자를 찾을 수 없습니다: {vuser}'})

            uid, vuser_db, groups, cur_session, lastdate, creatdate, hqq, kz, hyid = row
            now = datetime.now()
            is_expired = lastdate < now if lastdate else True
            lastdate_str = lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else 'N/A'
            creatdate_str = creatdate.strftime('%Y-%m-%d %H:%M:%S') if creatdate else 'N/A'

            # 현재 접속 세션 수
            cur.execute("""SELECT COUNT(*) FROM radacct
                           WHERE username = %s AND acctstoptime IS NULL""", [vuser])
            active_cnt = cur.fetchone()[0]

            # 연장 후 만료일 계산 (세션 변경 시 남은기간 비례 환산)
            new_lastdate_str = None
            new_session = cur_session
            session_changed = False
            converted_remaining_days = 0
            if barcode and barcode in POSPAL_BARCODE_MAP:
                m = POSPAL_BARCODE_MAP[barcode]
                months = m['months']
                new_session = m['session']
                session_changed = (new_session != cur_session)

                # 가격 비례 환산: 남은기간 × (기존세션가격/신규세션가격)
                if lastdate and lastdate > now and session_changed and cur_session > new_session:
                    remaining_days = (lastdate - now).total_seconds() / 86400.0
                    old_price = SESSION_YEARLY_PRICE.get(cur_session, cur_session * 600)
                    new_price = SESSION_YEARLY_PRICE.get(new_session, new_session * 600)
                    ratio = old_price / new_price
                    converted_remaining_days = int(remaining_days * ratio - remaining_days)
                    from datetime import timedelta
                    base = now + timedelta(days=int(remaining_days * ratio))
                else:
                    base = lastdate if (lastdate and lastdate > now) else now

                new_month = base.month + months
                new_year = base.year + (new_month - 1) // 12
                new_month = ((new_month - 1) % 12) + 1
                import calendar as _cal
                max_day = _cal.monthrange(new_year, new_month)[1]
                new_day = min(base.day, max_day)
                new_lastdate = base.replace(year=new_year, month=new_month, day=new_day)
                new_lastdate_str = new_lastdate.strftime('%Y-%m-%d %H:%M:%S')

        return JsonResponse({
            'result': 200,
            'user': {
                'id': uid,
                'vuser': vuser_db,
                'groups': groups,
                'session': cur_session,
                'lastdate': lastdate_str,
                'expired': is_expired,
                'creatdate': creatdate_str,
                'phone': hqq or '',
                'kz': '정상' if kz == 1 else ('정지' if kz == 0 else str(kz)),
                'hyname': HYID_MAP.get(hyid, str(hyid) if hyid else ''),
                'active_sessions': active_cnt,
            },
            'preview': {
                'new_lastdate': new_lastdate_str,
                'new_session': new_session,
                'session_changed': session_changed,
                'old_session': cur_session,
                'converted_days': converted_remaining_days,
                'old_yearly_price': SESSION_YEARLY_PRICE.get(cur_session, cur_session * 600) if session_changed else 0,
                'new_yearly_price': SESSION_YEARLY_PRICE.get(new_session, new_session * 600) if session_changed else 0,
            } if new_lastdate_str else None,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# [api] 전화번호로 유저 검색 (동일 번호 복수 계정)
@allow_admin
def api_read_pospal_user_by_phone(request):
    try:
        phone = (request.GET.get('phone') or '').strip()
        if not phone:
            return JsonResponse({'result': 400, 'msg': '전화번호를 입력하세요.'})

        # 입력값 정규화: 숫자만 추출 후 국가코드 변환
        import re
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 2:
            return JsonResponse({'result': 400, 'msg': '전화번호 숫자를 2자리 이상 입력하세요.'})
        # 국가코드 변환: 86→제거, 82→0 (82 10 → 010)
        clean = digits
        if len(digits) >= 12 and digits.startswith('86'):
            clean = digits[2:]
        elif len(digits) >= 12 and digits.startswith('82'):
            clean = '0' + digits[2:]

        with _uto_cursor() as cur:
            # hqq 필드에서 검색 — DB값의 공백/하이픈/+ 제거 후 비교
            # MySQL REPLACE로 특수문자 제거, 국가코드 변환 (86→제거, 82→0)
            # hqq_norm: 86으로 시작→86 제거, 82로 시작→82를 0으로 변환, 나머지→그대로
            cur.execute("""
                SELECT id, vuser, `groups`, `session`, lastdate, creatdate, hqq, kz, hyid,
                       REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', '') AS hqq_clean,
                       CASE
                         WHEN LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', '')) >= 12
                              AND LEFT(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', ''), 2) = '86'
                         THEN SUBSTRING(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', ''), 3)
                         WHEN LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', '')) >= 12
                              AND LEFT(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', ''), 2) = '82'
                         THEN CONCAT('0', SUBSTRING(REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', ''), 3))
                         ELSE REPLACE(REPLACE(REPLACE(REPLACE(hqq, ' ', ''), '-', ''), '+', ''), '_', '')
                       END AS hqq_norm
                FROM vpnuser
                WHERE hqq IS NOT NULL AND hqq != ''
                HAVING hqq_norm LIKE %s
                ORDER BY creatdate DESC LIMIT 20
            """, ['%' + clean + '%'])
            rows = cur.fetchall()
            now = datetime.now()
            users = []
            for uid, vuser, groups, session, lastdate, creatdate, hqq, kz, hyid, _clean, _norm in rows:
                is_expired = lastdate < now if lastdate else True
                users.append({
                    'id': uid,
                    'vuser': vuser,
                    'groups': groups,
                    'session': session,
                    'lastdate': lastdate.strftime('%Y-%m-%d %H:%M:%S') if lastdate else 'N/A',
                    'expired': is_expired,
                    'creatdate': creatdate.strftime('%Y-%m-%d') if creatdate else '',
                    'phone': hqq or '',
                    'kz': '정상' if kz == 1 else ('정지' if kz == 0 else str(kz)),
                    'hyname': HYID_MAP.get(hyid, str(hyid) if hyid else ''),
                })

        if not users:
            return JsonResponse({'result': 404, 'msg': f'전화번호 "{phone}"에 해당하는 사용자가 없습니다.'})
        return JsonResponse({'result': 200, 'users': users, 'count': len(users)})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# [api] Pospal 판매 → VPN 자동연장 처리
@allow_admin
def api_create_pospal_extend(request):
    try:
        ticket_sn = (request.POST.get('ticket_sn') or '').strip()
        vuser = (request.POST.get('vuser') or '').strip()
        barcode = (request.POST.get('barcode') or '').strip()

        if not ticket_sn or not vuser or not barcode:
            return JsonResponse({'result': 400, 'msg': '필수 항목이 누락되었습니다 (ticket_sn, vuser, barcode).'})

        if barcode not in POSPAL_BARCODE_MAP:
            return JsonResponse({'result': 400, 'msg': f'매핑되지 않은 바코드: {barcode}'})

        mapping = POSPAL_BARCODE_MAP[barcode]
        admin_user = request.session.get('username', 'pospal')

        # 중복 처리 방지
        with _uto_cursor() as cur:
            try:
                cur.execute("SELECT id FROM uto_pospal_log WHERE ticket_sn = %s AND barcode = %s", [ticket_sn, barcode])
                if cur.fetchone():
                    return JsonResponse({'result': 400, 'msg': f'이미 처리된 판매건입니다: {ticket_sn}'})
            except Exception:
                pass  # 테이블 없으면 무시 (아래에서 생성)

        # 신규 계정인 경우: vpnuser에 이미 존재하는지 확인
        if mapping['is_new']:
            with _uto_cursor() as cur:
                cur.execute("SELECT id FROM vpnuser WHERE vuser = %s", [vuser])
                if cur.fetchone():
                    # 이미 존재하면 연장으로 처리
                    pass
                else:
                    # 신규 VPN 계정 생성
                    # port 자동 부여 (중복 방지)
                    next_port = _next_uto_port(cur)
                    cur.execute("""
                        INSERT INTO vpnuser (vuser, vpwd, `session`, `groups`, lastdate, kz, port)
                        VALUES (%s, %s, %s, 'BY', DATE_ADD(NOW(), INTERVAL %s MONTH), '0', %s)
                    """, [vuser, vuser, mapping['session'], mapping['months'], next_port])
                    from dateutil.relativedelta import relativedelta as _rd
                    new_lastdate = (datetime.now() + _rd(months=mapping['months'])).strftime('%Y-%m-%d %H:%M:%S')
                    _log_uto_change(vuser, 'extend', 'lastdate', 'NULL', new_lastdate,
                                    f'Pospal 신규계정 생성 [{mapping["name"]}] ¥{mapping["price"]}', admin_user, source='pospal')

                    # 처리 로그 저장
                    _save_pospal_log(cur, ticket_sn, barcode, vuser, mapping, admin_user)

                    return JsonResponse({
                        'result': 200,
                        'msg': f'신규 계정 생성 완료: {vuser} ({mapping["months"]}개월, {mapping["session"]}세션)',
                        'action': 'created',
                    })

        # 기존 계정 연장
        success, result_msg, old_lastdate, old_session = _extend_lastdate(vuser, mapping['months'], str(mapping['session']), admin_user)
        if not success:
            return JsonResponse({'result': 400, 'msg': result_msg})

        desc = f'Pospal 판매 자동연장 [{mapping["name"]}] ¥{mapping["price"]}'
        _log_uto_change(vuser, 'extend', 'lastdate', old_lastdate, result_msg, desc, admin_user, source='pospal')
        if int(mapping['session']) != old_session:
            _log_uto_change(vuser, 'extend', 'session', old_session, mapping['session'],
                            f'Pospal 판매 세션 변경 [{mapping["name"]}] {old_session}→{mapping["session"]} (¥{SESSION_YEARLY_PRICE.get(old_session, "?")}/년→¥{SESSION_YEARLY_PRICE.get(mapping["session"], "?")}/년)', admin_user, source='pospal')

        # 처리 로그 저장
        with _uto_cursor() as cur:
            _save_pospal_log(cur, ticket_sn, barcode, vuser, mapping, admin_user,
                             old_lastdate=old_lastdate, old_session=old_session)

        return JsonResponse({
            'result': 200,
            'msg': f'{vuser} — {mapping["months"]}개월 연장 완료 (새 만료일: {result_msg})',
            'new_lastdate': result_msg,
            'old_lastdate': old_lastdate,
            'action': 'extended',
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


def _save_pospal_log(cur, ticket_sn, barcode, vuser, mapping, admin_user, old_lastdate=None, old_session=None):
    """Pospal 처리 로그 저장 (중복 방지용)"""
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uto_pospal_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_sn VARCHAR(50) NOT NULL,
                barcode VARCHAR(30) NOT NULL,
                vuser VARCHAR(100) NOT NULL,
                product_name VARCHAR(200),
                months INT,
                session_val INT,
                price DECIMAL(10,2),
                admin_user VARCHAR(100),
                old_lastdate VARCHAR(30),
                old_session INT,
                refunded TINYINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_ticket_barcode (ticket_sn, barcode)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    except Exception:
        pass
    # old_lastdate, old_session, refunded 컬럼 추가 (기존 테이블 호환)
    for col_sql in [
        "ALTER TABLE uto_pospal_log ADD COLUMN old_lastdate VARCHAR(30) DEFAULT NULL",
        "ALTER TABLE uto_pospal_log ADD COLUMN old_session INT DEFAULT NULL",
        "ALTER TABLE uto_pospal_log ADD COLUMN refunded TINYINT DEFAULT 0",
    ]:
        try:
            cur.execute(col_sql)
        except Exception:
            pass
    cur.execute("""
        INSERT IGNORE INTO uto_pospal_log (ticket_sn, barcode, vuser, product_name, months, session_val, price, admin_user, old_lastdate, old_session)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [ticket_sn, barcode, vuser, mapping['name'], mapping['months'], mapping['session'], mapping['price'], admin_user, old_lastdate, old_session])


# [api] Pospal 환불 처리 — 연장 전 상태로 복원
@allow_admin
def api_create_pospal_refund(request):
    try:
        ticket_sn = (request.POST.get('ticket_sn') or '').strip()
        barcode = (request.POST.get('barcode') or '').strip()

        if not ticket_sn or not barcode:
            return JsonResponse({'result': 400, 'msg': '필수 항목이 누락되었습니다.'})

        admin_user = request.session.get('username', 'pospal')

        with _uto_cursor() as cur:
            cur.execute("""SELECT id, vuser, old_lastdate, old_session, product_name, months, session_val, price, refunded
                           FROM uto_pospal_log WHERE ticket_sn = %s AND barcode = %s""", [ticket_sn, barcode])
            log_row = cur.fetchone()
            if not log_row:
                return JsonResponse({'result': 404, 'msg': '처리 내역을 찾을 수 없습니다.'})

            log_id, vuser, old_lastdate, old_session, product_name, months, session_val, price, refunded = log_row
            if refunded:
                return JsonResponse({'result': 400, 'msg': '이미 환불 처리된 건입니다.'})

            # 현재 유저 상태 조회
            cur.execute("SELECT id, lastdate, `session` FROM vpnuser WHERE vuser = %s", [vuser])
            user_row = cur.fetchone()
            if not user_row:
                return JsonResponse({'result': 404, 'msg': f'사용자를 찾을 수 없습니다: {vuser}'})

            user_id, cur_lastdate, cur_session = user_row
            cur_lastdate_str = cur_lastdate.strftime('%Y-%m-%d %H:%M:%S') if cur_lastdate else 'NULL'

            # 만료일 복원
            if old_lastdate:
                cur.execute("UPDATE vpnuser SET lastdate = %s WHERE id = %s", [old_lastdate, user_id])
                _log_uto_change(vuser, 'refund', 'lastdate', cur_lastdate_str, old_lastdate,
                                f'Pospal 환불 [{product_name}] ¥{price}', admin_user, source='pospal')

            # 세션 복원 + 속도 복원
            if old_session is not None and old_session != cur_session:
                cur.execute("UPDATE vpnuser SET `session` = %s WHERE id = %s", [old_session, user_id])
                _log_uto_change(vuser, 'refund', 'session', cur_session, old_session,
                                f'Pospal 환불 세션 복원 [{product_name}] {cur_session}→{old_session}', admin_user, source='pospal')
                # 속도 복원 (세션 기반)
                cur.execute("SELECT hyid FROM vpnuser WHERE id = %s", [user_id])
                hyid_row = cur.fetchone()
                if hyid_row:
                    restored_speed = _calc_uto_speed(hyid_row[0], old_session)
                    cur.execute("UPDATE vpnuser SET updk = %s, downdk = %s WHERE id = %s", [restored_speed, restored_speed, user_id])

            # 로그에 환불 표시
            cur.execute("UPDATE uto_pospal_log SET refunded = 1 WHERE id = %s", [log_id])

        return JsonResponse({
            'result': 200,
            'msg': f'{vuser} 환불 완료 — 만료일: {old_lastdate or "변경없음"}, 세션: {old_session if old_session is not None else "변경없음"}',
            'vuser': vuser,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# UTO VLESS+Reality 관리
# ============================================================

# Reality 서버 설정
REALITY_SERVERS = {
    'DU3': {
        'ip': '115.71.13.137',
        'domain': 'du3.jobjapan.com',
        'port': 8443,
        'public_key': 'bHqNjsKhoZawCIz6HNxGU2_hEozhlIQweStFqs6EeD8',
        'short_ids': ['f1fa6fbf', '0a35b3cae00891e0'],
        'sni': 'www.microsoft.com',
    },
    'UTOLGDHCP1': {
        'ip': '112.218.79.74',
        'domain': 'utolgdhcp1.jobjapan.net',
        'port': 443,
        'public_key': 'aK_GOUZmyJ8nTVX5cgY7OXB1jpi1rT6f-L9RFp5GxBI',
        'short_ids': ['5779cac6', 'bb22341592110b9f'],
        'sni': 'www.microsoft.com',
    },
    'SK110': {
        'ip': '110.15.180.162',
        'domain': 'sk110-15-180-162.jobjapan.com',
        'port': 443,
        'public_key': 'cpTRmtIhAZwnoBIy2yQ8D1ibqT9efOsYQokCqghkzFk',
        'short_ids': ['8b9a4bb2', '7197819a5f6383f2'],
        'sni': 'www.microsoft.com',
    },
    'KT43': {
        'ip': '211.46.6.241',
        'domain': 'kt211466241.jobjapan.com',
        'port': 8443,
        'public_key': '8HydMGXUtLNaAjgIJ0hG6sRtlBm4sh_dKU-Mdht8DCo',
        'short_ids': ['1aec903a', 'db5a2fad8a740633'],
        'sni': 'www.microsoft.com',
    },
    'UTOLGDHCP2': {
        'ip': '1.221.16.188',
        'domain': 'utolgdhcp2.jobjapan.net',
        'port': 443,
        'public_key': '02DQLI5UNhEzVOvWlmI6_f55_9WshnVeDRY7ocJjRXI',
        'short_ids': ['1aaa6c09', 'a11c120361ba1b2d'],
        'sni': 'www.microsoft.com',
    },
    'KT118238': {
        'ip': '118.34.105.238',
        'domain': 'kt118238.jobjapan.com',
        'port': 8443,
        'public_key': 'q3dKCr8C8kb32pHrRhls4p7GNPdjndFlRKJd4RjEy0w',
        'short_ids': ['64f629de', 'f2ebf856937881ab'],
        'sni': 'www.microsoft.com',
    },
}

UTO_UUID_NAMESPACE = uuid_mod.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')
SUB_SECRET_KEY = b'uto-reality-passwall-sub-2026'


def _generate_reality_uuid(vuser, vpass):
    """vuser+vpass → deterministic UUID5"""
    return str(uuid_mod.uuid5(UTO_UUID_NAMESPACE, f"{vuser}:{vpass}"))


def _generate_sub_token(vuser):
    """vuser → 구독 URL용 인증 토큰 (HMAC-SHA256, 16자)"""
    return hmac_mod.new(SUB_SECRET_KEY, vuser.encode('utf-8'), hashlib_mod.sha256).hexdigest()[:16]


@allow_admin
def uto_reality(request):
    """Reality 설정 관리 페이지 렌더링"""
    if request.session.get('role', 1) != 1:
        return redirect('/uto_user')
    context = {
        'servers': json.dumps(REALITY_SERVERS),
    }
    return render(request, 'admin/uto_reality.html', context)


@allow_admin
def api_read_uto_reality_users(request):
    """Reality 사용자 목록 (유효 사용자 + UUID 표시)"""
    try:
        search = request.POST.get('search', '').strip()
        show_all = request.POST.get('show_all', '0')

        cur = _uto_cursor()

        where = "WHERE 1=1"
        params = []

        if show_all != '1':
            where += " AND v.lastdate > NOW()"

        if search:
            where += " AND (v.vuser LIKE %s OR v.hqq LIKE %s OR v.hmail LIKE %s)"
            params += [f'%{search}%', f'%{search}%', f'%{search}%']

        cur.execute(f"""
            SELECT v.id, v.vuser, v.vpass, v.lastdate, v.session, v.groups,
                   v.kz, v.game, v.hyid,
                   CASE WHEN v.lastdate > NOW() THEN 1 ELSE 0 END as is_active
            FROM vpnuser v
            {where}
            ORDER BY v.lastdate DESC
            LIMIT 500
        """, params)
        rows = dictfetchall(cur)

        users = []
        for r in rows:
            reality_uuid = _generate_reality_uuid(r['vuser'], r['vpass'])
            users.append({
                'id': r['id'],
                'vuser': r['vuser'],
                'uuid': reality_uuid,
                'lastdate': r['lastdate'].strftime('%Y-%m-%d %H:%M') if r['lastdate'] else '',
                'session': r['session'] or 1,
                'groups': r['groups'] or '',
                'is_active': r['is_active'],
                'kz': r['kz'],
                'game': r['game'] or '',
            })

        # 전체 유효 사용자 수
        cur.execute("SELECT COUNT(*) FROM vpnuser WHERE lastdate > NOW()")
        active_count = cur.fetchone()[0]

        return JsonResponse({
            'result': 200,
            'users': users,
            'active_count': active_count,
            'total_shown': len(users),
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


@allow_admin
def api_read_uto_reality_config(request):
    """특정 사용자의 Reality 클라이언트 설정 생성"""
    try:
        vuser = request.POST.get('vuser', '').strip()
        server_name = request.POST.get('server', 'DU3')

        if not vuser:
            return JsonResponse({'result': 400, 'msg': 'vuser 필요'})

        cur = _uto_cursor()
        cur.execute("SELECT vuser, vpass, lastdate, session FROM vpnuser WHERE vuser = %s", [vuser])
        row = cur.fetchone()
        if not row:
            return JsonResponse({'result': 400, 'msg': f'사용자 {vuser} 없음'})

        db_vuser, db_vpass, lastdate, session = row
        reality_uuid = _generate_reality_uuid(db_vuser, db_vpass)

        server = REALITY_SERVERS.get(server_name)
        if not server:
            return JsonResponse({'result': 400, 'msg': f'서버 {server_name} 없음'})

        is_expired = lastdate < datetime.now() if lastdate else True

        config = {
            'vuser': db_vuser,
            'uuid': reality_uuid,
            'is_expired': is_expired,
            'lastdate': lastdate.strftime('%Y-%m-%d %H:%M') if lastdate else '',
            'session': session or 1,
            'server': server_name,
            'passwall_config': {
                'type': 'Xray',
                'protocol': 'VLESS',
                'address': server['domain'],
                'port': server['port'],
                'uuid': reality_uuid,
                'flow': 'xtls-rprx-vision',
                'encryption': 'none',
                'transport': 'tcp',
                'tls': 'Reality',
                'sni': server['sni'],
                'fingerprint': 'chrome',
                'public_key': server['public_key'],
                'short_id': server['short_ids'][0],
            },
            'share_url': (
                f"vless://{reality_uuid}@{server['domain']}:{server['port']}"
                f"?type=tcp&security=reality&sni={server['sni']}"
                f"&fp=chrome&pbk={server['public_key']}"
                f"&sid={server['short_ids'][0]}"
                f"&flow=xtls-rprx-vision&encryption=none"
                f"#{server_name}-Reality-{db_vuser}"
            ),
        }

        return JsonResponse({'result': 200, 'config': config})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


@allow_admin
def api_read_uto_reality_status(request):
    """Reality 서버 상태 확인"""
    try:
        results = {}
        for name, srv in REALITY_SERVERS.items():
            try:
                cmd = [
                    'sshpass', '-p', 'uto6703',
                    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
                    f'root@{srv["ip"]}',
                    'systemctl is-active xray-reality 2>/dev/null; '
                    'ps aux | grep "xray-reality" | grep -v grep | wc -l; '
                    'ss -tlnp | grep ' + str(srv['port']) + ' | wc -l'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                lines = result.stdout.strip().split('\n')
                results[name] = {
                    'ip': srv['ip'],
                    'domain': srv['domain'],
                    'port': srv['port'],
                    'service_active': lines[0] if len(lines) > 0 else 'unknown',
                    'process_count': int(lines[1]) if len(lines) > 1 else 0,
                    'port_listening': int(lines[2]) if len(lines) > 2 else 0,
                    'status': 'online' if (len(lines) > 0 and lines[0] == 'active') else 'offline',
                }
            except Exception as e:
                results[name] = {
                    'ip': srv['ip'],
                    'domain': srv['domain'],
                    'port': srv['port'],
                    'status': 'error',
                    'error': str(e),
                }

        return JsonResponse({'result': 200, 'servers': results})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


@allow_admin
def api_update_uto_reality_sync(request):
    """Reality 사용자 동기화 (수동 트리거)"""
    try:
        if request.session.get('role', 1) != 1:
            return JsonResponse({'result': 403, 'msg': '권한 없음'})

        script_path = '/home/newkorea/project/scripts/sync_uto_reality_users.py'
        venv_python = '/home/newkorea/project/uto-admin/.venv38/bin/python3'

        result = subprocess.run(
            [venv_python, script_path],
            capture_output=True, text=True, timeout=60,
            cwd='/home/newkorea/project/scripts'
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        return JsonResponse({
            'result': 200 if success else 500,
            'msg': '동기화 완료' if success else '동기화 실패',
            'output': output[-2000:],  # 마지막 2000자
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# Reality 서버 SSH 비밀번호 (per-user deploy용)
_REALITY_SSH_PASS = 'uto6703'

def _deploy_user_to_reality_server(server_name, server_conf, user_uuid, user_email):
    """단일 사용자를 Reality 서버에 추가 (기존 config.json에 append)"""
    ip = server_conf['ip']
    config_path = '/usr/local/xray-reality/config.json'
    service_name = 'xray-reality'

    try:
        # 1. 현재 config.json 읽기
        read_cmd = [
            'sshpass', '-p', _REALITY_SSH_PASS,
            'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
            f'root@{ip}', f'cat {config_path}'
        ]
        result = subprocess.run(read_cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return {'server': server_name, 'ok': False, 'msg': f'SSH read failed: {result.stderr[:200]}'}

        config = json.loads(result.stdout)
        clients = config['inbounds'][0]['settings']['clients']

        # 2. 이미 있는지 확인
        for c in clients:
            if c['id'] == user_uuid:
                return {'server': server_name, 'ok': True, 'msg': '이미 배포됨'}

        # 3. 추가
        clients.append({
            'id': user_uuid,
            'email': user_email,
            'flow': 'xtls-rprx-vision',
        })

        config_str = json.dumps(config, indent=2, ensure_ascii=False)

        # 4. 임시 파일 → SCP → 재시작
        tmp_file = f'/tmp/xray_reality_deploy_{server_name}.json'
        with open(tmp_file, 'w') as f:
            f.write(config_str)

        scp_cmd = [
            'sshpass', '-p', _REALITY_SSH_PASS,
            'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
            tmp_file, f'root@{ip}:{config_path}'
        ]
        result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=15)
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        if result.returncode != 0:
            return {'server': server_name, 'ok': False, 'msg': f'SCP failed: {result.stderr[:200]}'}

        restart_cmd = [
            'sshpass', '-p', _REALITY_SSH_PASS,
            'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
            f'root@{ip}', f'systemctl restart {service_name} && echo OK'
        ]
        result = subprocess.run(restart_cmd, capture_output=True, text=True, timeout=15)
        if 'OK' in result.stdout:
            return {'server': server_name, 'ok': True, 'msg': '배포 완료'}
        else:
            return {'server': server_name, 'ok': False, 'msg': f'Restart failed: {result.stderr[:200]}'}

    except Exception as e:
        return {'server': server_name, 'ok': False, 'msg': str(e)[:200]}


@allow_admin
def api_update_uto_reality_deploy_user(request):
    """단일 사용자를 모든 Reality 서버에 배포"""
    try:
        if request.session.get('role', 1) != 1:
            return JsonResponse({'result': 403, 'msg': '권한 없음'})

        vuser = request.POST.get('vuser', '').strip()
        if not vuser:
            return JsonResponse({'result': 400, 'msg': 'vuser 필수'})

        # DB에서 사용자 조회
        cur = _uto_cursor()
        cur.execute("SELECT vuser, vpass, lastdate FROM vpnuser WHERE vuser = %s", [vuser])
        row = cur.fetchone()
        if not row:
            return JsonResponse({'result': 404, 'msg': '사용자 없음'})

        db_vuser, db_vpass, lastdate = row
        if lastdate and lastdate < datetime.now():
            return JsonResponse({'result': 400, 'msg': '만료된 사용자는 배포할 수 없습니다'})

        user_uuid = _generate_reality_uuid(db_vuser, db_vpass)
        user_email = f"{db_vuser}@uto"

        # 모든 Reality 서버에 병렬 배포
        results = []
        threads = []

        def _deploy_thread(sname, sconf):
            r = _deploy_user_to_reality_server(sname, sconf, user_uuid, user_email)
            results.append(r)

        for sname, sconf in REALITY_SERVERS.items():
            t = threading.Thread(target=_deploy_thread, args=(sname, sconf))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        ok_count = sum(1 for r in results if r['ok'])
        total = len(REALITY_SERVERS)

        return JsonResponse({
            'result': 200 if ok_count == total else 207,
            'msg': f'{ok_count}/{total} 서버 배포 완료',
            'details': results,
            'uuid': user_uuid,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# PassWall Node Subscribe (공개 API — OpenWrt에서 직접 호출)
# ============================================================

def _urlsafe_b64(s):
    """SSR URL용 URL-safe base64 (패딩 제거)"""
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')


def _build_ssr_url(domain, port, protocol, method, obfs, password, obfs_param='', protocol_param='', remarks=''):
    """SSR URL 생성 (ssr://base64(...))"""
    password_b64 = _urlsafe_b64(password)
    params = []
    if obfs_param:
        params.append(f"obfsparam={_urlsafe_b64(obfs_param)}")
    if protocol_param:
        params.append(f"protoparam={_urlsafe_b64(protocol_param)}")
    if remarks:
        params.append(f"remarks={_urlsafe_b64(remarks)}")
    param_str = '&'.join(params)
    raw = f"{domain}:{port}:{protocol}:{method}:{obfs}:{password_b64}"
    if param_str:
        raw += f"/?{param_str}"
    return 'ssr://' + _urlsafe_b64(raw)


@csrf_exempt
def api_passwall_subscribe(request, vuser, token):
    """PassWall Node Subscribe용 공개 엔드포인트
    GET /sub/reality/<vuser>/<token>
    → base64 인코딩된 SSR + VLESS Reality URL 목록 반환
    """
    if request.method != 'GET':
        return HttpResponse('Method not allowed', status=405, content_type='text/plain')

    try:
        # 토큰 검증 (timing-safe 비교)
        expected = _generate_sub_token(vuser)
        if not hmac_mod.compare_digest(token, expected):
            return HttpResponse('Invalid token', status=403, content_type='text/plain')

        # 사용자 조회
        cur = _uto_cursor()
        cur.execute("SELECT vuser, vpass, lastdate, port FROM vpnuser WHERE vuser = %s", [vuser])
        row = cur.fetchone()
        if not row:
            return HttpResponse('User not found', status=404, content_type='text/plain')

        db_vuser, db_vpass, lastdate, user_port = row

        # 만료 체크
        if lastdate and lastdate < datetime.now():
            return HttpResponse('Subscription expired', status=403, content_type='text/plain')

        # DB에서 활성 서버 목록 조회
        cur.execute("""
            SELECT name, server_type, domain, port,
                   encrypt_method, ssr_protocol, obfs, obfs_param, protocol_param,
                   public_key, short_id, sni, flow, fingerprint
            FROM uto_openwrt_servers
            WHERE is_active = 1
            ORDER BY sort_order
        """)
        servers = cur.fetchall()

        urls = []
        reality_uuid = _generate_reality_uuid(db_vuser, db_vpass)

        for srv in servers:
            (name, stype, domain, srv_port,
             enc_method, ssr_proto, obfs, obfs_param, proto_param,
             pub_key, short_id, sni, flow, fp) = srv

            if stype == 'ssr':
                # SSR: 포트는 vpnuser.port, 비밀번호는 vpnuser.vpass
                ssr_port = user_port or 8007
                url = _build_ssr_url(
                    domain=domain,
                    port=ssr_port,
                    protocol=ssr_proto or 'auth_sha1_v4',
                    method=enc_method or 'aes-256-cfb',
                    obfs=obfs or 'tls1.2_ticket_auth',
                    password=db_vpass,
                    obfs_param=obfs_param or '',
                    protocol_param=proto_param or '',
                    remarks=f"{name}-SSR-{db_vuser}",
                )
                urls.append(url)

            elif stype == 'reality':
                # VLESS Reality
                sid = short_id.split(',')[0] if short_id else ''
                url = (
                    f"vless://{reality_uuid}@{domain}:{srv_port}"
                    f"?type=tcp&security=reality&sni={sni}"
                    f"&fp={fp or 'chrome'}&pbk={pub_key}"
                    f"&sid={sid}"
                    f"&flow={flow or 'xtls-rprx-vision'}&encryption=none"
                    f"#{name}-Reality-{db_vuser}"
                )
                urls.append(url)

        # base64 인코딩 (PassWall 표준 포맷)
        plain_text = '\n'.join(urls)
        encoded = base64.b64encode(plain_text.encode('utf-8')).decode('utf-8')

        return HttpResponse(encoded, content_type='text/plain; charset=utf-8')
    except Exception as e:
        traceback.print_exc()
        return HttpResponse('Server error', status=500, content_type='text/plain')


@allow_admin
def api_read_uto_reality_sub_url(request):
    """특정 사용자의 구독 URL 생성 (관리자 API)"""
    try:
        vuser = request.POST.get('vuser', '').strip()
        if not vuser:
            return JsonResponse({'result': 400, 'msg': 'vuser 필요'})

        token = _generate_sub_token(vuser)
        sub_url = f"https://uto.shanghai.co.kr/sub/passwall/{vuser}/{token}"

        return JsonResponse({'result': 200, 'sub_url': sub_url, 'vuser': vuser})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})
