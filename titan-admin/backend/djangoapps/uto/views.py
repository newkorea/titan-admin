# UTO VPN 관리 — 별도 DB(vcsvpn2013)를 사용하는 독립 모듈
# titan-admin 기존 코드에 영향 없음
import json
import os
import tempfile
import traceback
import subprocess
import threading
import time
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from backend.djangoapps.common.views import allow_admin, dictfetchall


# ============================================================
# UTO DB 헬퍼 — 'uto' / 'uto_radius' 커넥션만 사용
# ============================================================
def _uto_cursor():
    """vcsvpn2013 DB 커서"""
    return connections['uto'].cursor()

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
        with _uto_cursor() as cur:
            # 전체
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            total = cur.fetchone()[0]

            # 정상 (kz=1)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE kz = 1")
            active = cur.fetchone()[0]

            # 차단 (kz=2)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE kz = 2")
            blocked = cur.fetchone()[0]

            # 접속중 (radacct NULL 기준 — 실제 활성 세션)
            cur.execute("SELECT COUNT(DISTINCT username) FROM radacct WHERE acctstoptime IS NULL")
            online = cur.fetchone()[0]

            # 세션 초과 (radacct NULL 세션수 > vpnuser.session)
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
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE lastdate IS NOT NULL AND lastdate < NOW() AND kz = 1")
            expired = cur.fetchone()[0]

            # BY(월정액) / LL(트래픽)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE `groups` = 'BY'")
            by_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE `groups` = 'LL'")
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
                GROUP BY r.username
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
        with _uto_cursor() as cur:
            cur.execute("""
                SELECT id, vuser, vpass, `groups`, onlines, onlines2, sess, cash, session,
                       DATE_FORMAT(lastdate, '%%Y-%%m-%%d %%H:%%i:%%s') as lastdate,
                       DATE_FORMAT(creatdate, '%%Y-%%m-%%d %%H:%%i:%%s') as creatdate,
                       DATE_FORMAT(lasttime, '%%Y-%%m-%%d %%H:%%i:%%s') as lasttime,
                       userip, nasip, vpnip, forcedip, kz, game, member, hyid,
                       hmail, hqq, hmemo, flow, vpntype,
                       port, updk, downdk, ddh, haddr
                FROM vpnuser WHERE id = %s
            """, [user_id])
            rows = dictfetchall(cur)

        if not rows:
            return JsonResponse({'result': 404, 'msg': '사용자를 찾을 수 없습니다'})

        return JsonResponse({'result': 200, 'data': rows[0]})
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
            'port': 'port',
            'updk': 'updk',
            'downdk': 'downdk',
        }

        if field not in allowed_fields:
            return JsonResponse({'result': 400, 'msg': f'허용되지 않는 필드: {field}'})

        col = allowed_fields[field]

        with _uto_cursor() as cur:
            cur.execute(f"UPDATE vpnuser SET {col} = %s WHERE id = %s", [value, user_id])

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
        with _uto_cursor() as cur:
            cur.execute("UPDATE vpnuser SET kz = %s WHERE id = %s", [kz_value, user_id])

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
        with _uto_cursor() as cur:
            cur.execute("UPDATE vpnuser SET sess = 0 WHERE id = %s", [user_id])

        return JsonResponse({'result': 200, 'msg': '세션 종료 완료'})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [api] UTO 세션 실제 강제 종료 (SSH로 VPN 서버에서 킥 + radacct 정리)
# ============================================================

# ROS API 헬퍼 (MikroTik RouterOS Binary Protocol)
ROS_SERVERS = {
    '27.115.70.46':  {'user': 'admin',   'pw': 'vkfksgksmf', 'port': 8728},
    '27.115.51.226': {'user': 'admin',   'pw': 'vkfksgksmf', 'port': 8728},
    '58.246.240.2':  {'user': 'Oserver', 'pw': 'vkfksgksmf', 'port': 8728},
}


def _ros_api_login_and_cmd(ip, username_to_kick):
    """MikroTik API로 PPP 세션 킥"""
    import socket, hashlib, binascii
    info = ROS_SERVERS.get(ip)
    if not info:
        return False, f'Unknown ROS server {ip}'

    def _encode_len(l):
        if l < 0x80: return bytes([l])
        elif l < 0x4000: return bytes([((l >> 8) & 0x3F) | 0x80, l & 0xFF])
        elif l < 0x200000: return bytes([((l >> 16) & 0x1F) | 0xC0, (l >> 8) & 0xFF, l & 0xFF])
        elif l < 0x10000000: return bytes([((l >> 24) & 0x0F) | 0xE0, (l >> 16) & 0xFF, (l >> 8) & 0xFF, l & 0xFF])
        else: return bytes([0xF0, (l >> 24) & 0xFF, (l >> 16) & 0xFF, (l >> 8) & 0xFF, l & 0xFF])

    def _encode_word(w):
        b = w.encode('utf-8')
        return _encode_len(len(b)) + b

    def _encode_sentence(words):
        r = b''
        for w in words:
            r += _encode_word(w)
        r += b'\x00'  # end of sentence
        return r

    def _read_len(s):
        b = s.recv(1)
        if not b: return -1
        v = b[0]
        if (v & 0x80) == 0: return v
        elif (v & 0xC0) == 0x80:
            b2 = s.recv(1)
            return ((v & 0x3F) << 8) | b2[0]
        elif (v & 0xE0) == 0xC0:
            b2 = s.recv(2)
            return ((v & 0x1F) << 16) | (b2[0] << 8) | b2[1]
        elif (v & 0xF0) == 0xE0:
            b2 = s.recv(3)
            return ((v & 0x0F) << 24) | (b2[0] << 16) | (b2[1] << 8) | b2[2]
        else:
            b2 = s.recv(4)
            return (b2[0] << 24) | (b2[1] << 16) | (b2[2] << 8) | b2[3]

    def _read_sentence(s):
        words = []
        while True:
            l = _read_len(s)
            if l <= 0: break
            words.append(s.recv(l).decode('utf-8', errors='replace'))
        return words

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect((ip, info['port']))

        # Login
        s.sendall(_encode_sentence(['/login']))
        resp = _read_sentence(s)

        if any('=ret=' in w for w in resp):
            # old-style challenge-response
            challenge = [w.split('=ret=')[1] for w in resp if '=ret=' in w][0]
            ch_bytes = binascii.unhexlify(challenge)
            md = hashlib.md5()
            md.update(b'\x00')
            md.update(info['pw'].encode('utf-8'))
            md.update(ch_bytes)
            hashed = '00' + md.hexdigest()
            s.sendall(_encode_sentence(['/login', '=name=' + info['user'], '=response=' + hashed]))
        else:
            s.sendall(_encode_sentence(['/login', '=name=' + info['user'], '=password=' + info['pw']]))
        login_resp = _read_sentence(s)
        if not any('!done' in w for w in login_resp):
            s.close()
            return False, f'ROS login failed: {login_resp}'

        # Get active PPP sessions
        s.sendall(_encode_sentence(['/ppp/active/print', '?name=' + username_to_kick]))
        result_words = []
        while True:
            sentence = _read_sentence(s)
            if not sentence:
                break
            result_words.extend(sentence)
            if '!done' in sentence:
                break

        # Find .id
        ids_to_remove = []
        for w in result_words:
            if w.startswith('=.id='):
                ids_to_remove.append(w.split('=.id=')[1])

        removed = 0
        for rid in ids_to_remove:
            s.sendall(_encode_sentence(['/ppp/active/remove', '=.id=' + rid]))
            _read_sentence(s)
            removed += 1

        s.close()
        if removed > 0:
            return True, f'ROS: {removed} session(s) removed'
        return True, 'ROS: no active session found'

    except Exception as e:
        return False, f'ROS API error: {e}'


def _kick_strongswan(nas_ip, username):
    """strongSwan 세션 킥 (SSH)"""
    # Get SA name
    cmd = f"strongswan statusall 2>/dev/null | grep -B2 '{username}'"
    out, ok = _ssh_exec(nas_ip, cmd, timeout=10)
    if not ok or not out:
        return False, 'SSH failed or no session found'

    # Extract SA IDs like ikev2-vpn[1234]
    import re
    sa_matches = re.findall(r'(ikev2-vpn\[\d+\])', out)
    if not sa_matches:
        return False, f'No SA found in output: {out[:200]}'

    results = []
    for sa in set(sa_matches):
        kill_cmd = f"strongswan stroke down-nb '{sa}'"
        kill_out, kill_ok = _ssh_exec(nas_ip, kill_cmd, timeout=10)
        results.append(f'{sa}: {"OK" if kill_ok else "FAIL"}')

    return True, '; '.join(results)


def _kick_openvpn(nas_ip, username):
    """OpenVPN 세션 킥 (SSH → telnet management)"""
    cmd = (
        f"(echo 'mykakao9898'; sleep 0.3; echo 'kill {username}'; sleep 0.3; echo 'quit') "
        f"| telnet 127.0.0.1 1199 2>/dev/null"
    )
    out, ok = _ssh_exec(nas_ip, cmd, timeout=10)
    return True, f'OpenVPN kill sent: {out[:200]}'


def _close_radacct_session(cur, radacctid):
    """radacct 레코드 종료 처리"""
    cur.execute("""
        UPDATE radacct
        SET acctstoptime = NOW(),
            acctterminatecause = 'Admin-Reset',
            acctsessiontime = GREATEST(0, TIMESTAMPDIFF(SECOND, acctstarttime, NOW()))
        WHERE radacctid = %s AND acctstoptime IS NULL
    """, [radacctid])
    return cur.rowcount


@allow_admin
def api_update_uto_force_disconnect(request):
    """실제 VPN 서버에 SSH 접속하여 세션을 강제 종료하고 radacct 정리"""
    try:
        radacctid = request.POST.get('radacctid')
        kick_all = request.POST.get('kick_all')  # 'true' 이면 해당 유저 전체 세션 킥
        user_id = request.POST.get('user_id')

        with _uto_cursor() as cur:
            if kick_all == 'true' and user_id:
                # ── 전체 세션 강제종료 ──
                cur.execute("""
                    SELECT radacctid, username, nasipaddress, nasporttype
                    FROM radacct
                    WHERE username = (SELECT vuser FROM vpnuser WHERE id = %s)
                      AND acctstoptime IS NULL
                """, [user_id])
            elif radacctid:
                # ── 개별 세션 강제종료 ──
                cur.execute("""
                    SELECT radacctid, username, nasipaddress, nasporttype
                    FROM radacct
                    WHERE radacctid = %s AND acctstoptime IS NULL
                """, [radacctid])
            else:
                return JsonResponse({'result': 400, 'msg': 'radacctid 또는 user_id 필요'})

            sessions = dictfetchall(cur)
            if not sessions:
                return JsonResponse({'result': 404, 'msg': '활성 세션이 없습니다'})

            results = []
            for sess in sessions:
                rid = sess['radacctid']
                nas_ip = sess['nasipaddress']
                proto = (sess['nasporttype'] or '').strip()
                username = sess['username']

                kick_ok = False
                kick_msg = ''

                if proto == 'strongSwan':
                    kick_ok, kick_msg = _kick_strongswan(nas_ip, username)
                elif proto in ('openvpn', 'INDIA1'):
                    kick_ok, kick_msg = _kick_openvpn(nas_ip, username)
                elif proto in ('W ros', 'WS ros', 'O ros'):
                    kick_ok, kick_msg = _ros_api_login_and_cmd(nas_ip, username)
                elif proto == 'v2ray':
                    kick_ok = True
                    kick_msg = 'v2ray: radacct만 종료 (실시간 킥 불가)'
                else:
                    kick_ok = False
                    kick_msg = f'Unknown protocol: {proto}'

                # radacct 종료
                closed = _close_radacct_session(cur, rid)
                results.append({
                    'radacctid': rid,
                    'nas_ip': nas_ip,
                    'protocol': proto,
                    'kick_ok': kick_ok,
                    'kick_msg': kick_msg,
                    'radacct_closed': closed > 0,
                })

            # vpnuser.sess = 0
            if sessions:
                cur.execute("UPDATE vpnuser SET sess = 0 WHERE vuser = %s", [sessions[0]['username']])

            success_count = sum(1 for r in results if r['kick_ok'])
            total = len(results)
            return JsonResponse({
                'result': 200,
                'msg': f'{success_count}/{total}건 강제종료 완료',
                'details': results
            })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})


# ============================================================
# [render] UTO 서버 관리 페이지
# ============================================================
@allow_admin
def uto_server(request):
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

    # 2) SSH 체크 (55만 가능, 나머지는 skip)
    # API 서버면 Apache/PHP 상세 정보도 수집
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
        ssh_cmd += """echo "===HTTPD_COUNT==="
ps aux 2>/dev/null | grep -c '[h]ttpd'
echo "===HTTPD_STATUS==="
systemctl is-active httpd 2>/dev/null || service httpd status 2>&1 | head -1
echo "===PHP_ERRORS_1H==="
awk -v d="$(date -d '1 hour ago' '+%a %b %d %H:%M:%S' 2>/dev/null)" '$0 >= "[" d {c++} END {print c+0}' /var/log/httpd/error_log 2>/dev/null || echo 0
echo "===ACCESS_1H==="
awk -v d="$(date -d '1 hour ago' '+%d/%b/%Y:%H' 2>/dev/null)" '$0 ~ d {c++} END {print c+0}' /var/log/httpd/access_log 2>/dev/null || echo 0
echo "===CONN_COUNT==="
ss -s 2>/dev/null | grep estab | head -1
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

        # API 서버 전용: Apache/PHP 상세 정보 파싱
        if is_api:
            httpd_count = sections.get('HTTPD_COUNT', [])
            if httpd_count:
                try:
                    result['httpd_count'] = int(httpd_count[0])
                except:
                    result['httpd_count'] = 0

            httpd_status = sections.get('HTTPD_STATUS', [])
            if httpd_status:
                status_str = httpd_status[0].strip().lower()
                result['services']['Apache'] = 'active' in status_str or 'running' in status_str
                if not result['services'].get('Apache'):
                    result['criticals'].append('Apache 비활성!')

            php_errors = sections.get('PHP_ERRORS_1H', [])
            if php_errors:
                try:
                    err_count = int(php_errors[0])
                    result['php_errors_1h'] = err_count
                    if err_count >= 100:
                        result['criticals'].append(f'PHP 에러 {err_count}건/1h')
                    elif err_count >= 20:
                        result['warnings'].append(f'PHP 에러 {err_count}건/1h')
                except:
                    result['php_errors_1h'] = 0

            access_count = sections.get('ACCESS_1H', [])
            if access_count:
                try:
                    result['access_1h'] = int(access_count[0])
                except:
                    result['access_1h'] = 0

            conn_count = sections.get('CONN_COUNT', [])
            if conn_count:
                # ss output: "TCP:   142 (estab 87, ...)"
                import re
                m = re.search(r'estab\s+(\d+)', conn_count[0])
                if m:
                    result['tcp_estab'] = int(m.group(1))

    # 3) HTTP 서비스 체크 (API 서버) — 응답 시간도 측정
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
                    result['http_response_time'] = round(float(parts[1]), 3)
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

        return JsonResponse({'result': 200, 'data': {
            'account': account,
            'active_sessions': active_sessions,
            'recent_sessions': recent_sessions,
            'proto_summary': proto_summary,
            'server_map': server_map,
        }})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'result': 400, 'msg': str(e)})
