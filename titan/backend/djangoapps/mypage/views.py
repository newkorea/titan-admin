import json
import datetime
import re
import uuid
import requests
from datetime import timedelta
from django.shortcuts import render
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.db import transaction
from django.db.models import Max, Q
from django.core.exceptions import ObjectDoesNotExist
from pytz import timezone
from urllib.parse import quote
from urllib.parse import unquote
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.models import *
from backend.models_radius import *
from backend.djangoapps.common.views import *
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.smtp import send_email
from django.utils import translation
from django.utils.translation import gettext as _
from django.contrib.sessions.models import Session


# 프로토콜 매핑 (radacct nasporttype → 실제 프로토콜명)
PROTOCOL_MAP = {
    'Virtual': 'IKEv2',
    'ISDN': 'PPTP',
    'V2RAY': 'V2Ray',
    '61': 'WireGuard',
}


def to_china_time(dt):
    """서버 시간(KST, UTC+9) → 중국 시간(CST, UTC+8): 1시간 빼기"""
    if dt and isinstance(dt, datetime.datetime):
        return dt - timedelta(hours=1)
    return dt


# 마이페이지 렌더링 (2020-03-11)
def mypage(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    # Ensure the active language matches the user's selection so template i18n resolves correctly
    try:
        translation.activate(LANGUAGE_CODE)
    except Exception:
        pass
    if 'id' in request.session:
        email = request.session['email']
        id = request.session['id']

        # radius 기본정보 획득
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT username
                        ,attribute
                        ,op
                        ,value
                FROM   radius.radcheck
                WHERE  username = '{id}'
            '''.format(id=email)
            cur.execute(sql)
            rows = dictfetchall(cur)
            username = rows[0]['username']
            for row in rows:
                # VPN 세션 수
                if row["attribute"] == "Simultaneous-Use":
                    simultaneous_use = row["value"]

                # VPN 접속 비밀번호
                if row["attribute"] == "Cleartext-Password":
                    password = row["value"]

                # VPN 접속 만료기한
                if row["attribute"] == "Expiration":
                    expiration  = row["value"]

            # VPN 사용기한 확인
            try:
                date = datetime.datetime.strptime(expiration, "%d %b %Y %H:%M:%S %Z")
                now = datetime.datetime.now()
                if date < now:
                    print('INFO -> The period of use has expired')
                    res = {'vpn_hostname': '', 'vpn_username': '', 'vpn_password': ''}
            except BaseException as err:
                print('ERROR -> err : ', err)
                res = {'vpn_hostname': '', 'vpn_username': '', 'vpn_password': ''}

            # radius 사용자 수 체크
            sql = '''
                SELECT Count(*) AS count
                FROM   radius.radacct
                WHERE  acctstoptime IS NULL
                AND username = '{id}'
            '''.format(id=email)
            cur.execute(sql)
            rows = dictfetchall(cur)
            for row in rows:
                count = row['count']

            try:
                if count >= int(simultaneous_use) :
                   print('INFO -> The number of service users has been exceeded')
                   res = {'vpn_hostname': '', 'vpn_username': '', 'vpn_password': ''}
            except BaseException as err:
                print('ERROR -> err : ', err)
                res = {'vpn_hostname': '', 'vpn_username': '', 'vpn_password': ''}

            # VPN Agent 매칭
            sql = '''
                SELECT t3.count,
                    t3.hostdomain
                FROM   (
                    SELECT Count(radacctid) AS count,
                           t2.hostdomain
                    FROM   radius.radacct t1
                    INNER JOIN (
                        SELECT hostip,
                               hostdomain
                        FROM   titan.tbl_agent
                        WHERE  is_active
                        OR is_active = 1
                        AND is_status = 1
                    ) t2
                    ON t1.nasipaddress = t2.hostip
                    WHERE  acctstoptime IS NULL
                    GROUP  BY nasipaddress, t2.hostdomain
                    UNION ALL
                    SELECT 99999999999 AS count,
                           hostdomain
                    FROM   titan.tbl_agent
                    WHERE  is_active
                    OR is_active = 1
                    AND is_status = 1
                ) t3
                ORDER  BY t3.count
            '''.format(id=email)
            cur.execute(sql)
            rows = dictfetchall(cur)
            if len(rows) == 0:
                print('INFO -> Agent does not exist')
                res = {'vpn_hostname': '', 'vpn_username': '', 'vpn_password': ''}
            else:
                res = {
                    'result' : 200,
                    'vpn_hostname' : rows[0]['hostdomain'],
                    'vpn_username' : username,
                    'vpn_password' : password
                }
    else:
        return redirect('/login')

    xinfo = {}
    u1 = TblUser.objects.get(id=id)

    # Check user level; show history only when level == 1
    show_history = False
    try:
        with connections['default'].cursor() as cur:
            cur.execute("SELECT level FROM tbl_user WHERE id = %s", [id])
            row = cur.fetchone()
            if row is not None:
                # When using cursor without dictfetch, first column is level
                level_val = row[0]
                try:
                    show_history = int(level_val) == 1
                except Exception:
                    show_history = False
    except Exception:
        show_history = False

    # 만료시간 획득
    expire_time = my_radius_time(u1.email, 'str')
    expire_label = None
    is_expired = False
    if expire_time:
        try:
            parsed_expire = datetime.datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
            now = datetime.datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
            now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S')
            if parsed_expire < now:
                expire_label = parsed_expire.strftime('%Y-%m-%d %H:%M:%S')
                is_expired = True
            else:
                expire_label = parsed_expire.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            expire_label = expire_time
    xinfo['expire_time'] = expire_label
    xinfo['is_expired'] = is_expired

    # 세션 수 획득
    my_session = my_radius_session(u1.email)
    xinfo['my_session'] = my_session

    # Get user app login history only when allowed
    sessions = []
    if show_history:
        try:
            device_infos = TblDeviceInfo.objects.filter(user_id=id).order_by('-login_time')
            for device in device_infos:
                country = device.device_country
                city = device.device_city
                # Backfill missing country/city from IP lookup (best-effort)
                if (not country or not city) and device.device_ip:
                    try:
                        resp = requests.get("http://ip-api.com/json/" + device.device_ip, timeout=2)
                        if resp.status_code == 200:
                            data = resp.json()
                            country = country or data.get('country')
                            city = city or data.get('city')
                            # Persist backfill for future loads (ignore failures)
                            try:
                                changed = False
                                if country and not device.device_country:
                                    device.device_country = country
                                    changed = True
                                if city and not device.device_city:
                                    device.device_city = city
                                    changed = True
                                if changed:
                                    device.save(update_fields=['device_country','device_city'])
                            except Exception:
                                pass
                    except Exception:
                        pass

                sessions.append({
                    'device_type': device.device_type,
                    'app_version': device.app_version,
                    'device_isp': device.device_isp,
                    'device_country': country,
                    'device_city': city,
                    'login_time': device.login_time,
                    'session_key': device.session_key,
                })
        except TblDeviceInfo.DoesNotExist:
            pass # No devices found

    # 계정 일시차단 상태 확인
    is_suspended = False
    try:
        with connections['default'].cursor() as cur:
            cur.execute("SELECT is_suspended FROM tbl_user WHERE id = %s", [id])
            row = cur.fetchone()
            if row and int(row[0]) == 1:
                is_suspended = True
    except Exception:
        pass

    context = {}
    context['xinfo'] = xinfo
    context['res'] = res
    context['user'] = u1
    context['sessions'] = sessions
    context['show_history'] = show_history
    context['is_suspended'] = is_suspended
    # Subaccounts: emails like baseEmail_1, baseEmail_2 ...
    base_email = u1.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)

    subaccounts = []
    try:
        subs_qs = TblUser.objects.filter(
            delete_yn='N'
        ).filter(
            Q(parent_user_id=u1.id) |
            Q(parent_user_id__isnull=True, email__startswith=base_email + '_')
        ).exclude(id=u1.id).order_by('id')

        subs = list(subs_qs)
        legacy_ids = [su.id for su in subs if su.parent_user_id is None]
        if legacy_ids:
            TblUser.objects.filter(id__in=legacy_ids).update(parent_user_id=u1.id)
            for su in subs:
                if su.id in legacy_ids:
                    su.parent_user_id = u1.id

        for su in subs:
            email_s = su.email
            try:
                concurrent = my_radius_session(email_s)
            except Exception:
                concurrent = ''
            try:
                expire_str = my_radius_time(email_s, 'str')
            except Exception:
                expire_str = None
            is_sub_expired = False
            if expire_str:
                try:
                    parsed_sub_expire = datetime.datetime.strptime(expire_str, '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S')
                    if parsed_sub_expire < now:
                        is_sub_expired = True
                    expire_display = parsed_sub_expire.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    expire_display = expire_str
            else:
                expire_display = ''
            subaccounts.append({
                'id': su.id,
                'email': email_s,
                'username': su.username,
                'concurrent': concurrent,
                'expire_time': expire_display,
                'is_expired': is_sub_expired,
                'regist_date': su.regist_date,
            })
    except Exception:
        pass

    context['subaccounts'] = subaccounts
    context['base_email'] = base_email
    context['LANGUAGE_CODE'] = LANGUAGE_CODE

    # Determine next available subaccount email suffix; fall back gracefully on error
    next_email = ''
    try:
        suffix = 1
        base_prefix = base_email or ''
        if base_prefix:
            while TblUser.objects.filter(email=f"{base_prefix}_{suffix}", delete_yn='N').exists():
                suffix += 1
            next_email = f"{base_prefix}_{suffix}"
    except Exception:
        next_email = base_email + '_1' if base_email else ''
    context['next_sub_email'] = next_email
    return render(request, 'new/mypage.html', context)


@csrf_protect
def delete_session(request):
    if 'id' not in request.session:
        return JsonResponse({'result': '403', 'text': _('Please log in.')})

    if request.method == 'POST':
        session_key = request.POST.get('session_key')
        user_id = request.session['id']

        if not session_key:
            return JsonResponse({'result': '400', 'text': _('Invalid parameters.')})

        # 1) Delete from django_session table (idempotent)
        Session.objects.filter(session_key=session_key).delete()

        # 2) Remove mapping(s) from TblDeviceInfo for this user and key (idempotent)
        TblDeviceInfo.objects.filter(user_id=user_id, session_key=session_key).update(session_key=None)

        return JsonResponse({'result': '200', 'text': _('Session deleted successfully.')})
    
    return JsonResponse({'result': '400', 'text': _('Invalid request method.')})


@csrf_protect
def delete_all_sessions(request):
    if 'id' not in request.session:
        return JsonResponse({'result': '403', 'text': _('Please log in.')})

    if request.method == 'POST':
        user_id = request.session['id']
        
        device_infos = TblDeviceInfo.objects.filter(user_id=user_id, session_key__isnull=False)
        keys = list(device_infos.values_list('session_key', flat=True))

        if keys:
            Session.objects.filter(session_key__in=keys).delete()
        # Nullify all mappings in one query
        device_infos.update(session_key=None)

        return JsonResponse({'result': '200', 'text': _('All sessions have been deleted successfully.')})

    return JsonResponse({'result': '400', 'text': _('Invalid request method.')})


@csrf_protect
def password_change_page(request):
    if 'id' not in request.session:
        return redirect('/login')
    context = {}
    return render(request, 'new/password_change.html', context)


@csrf_protect
def change_password_action(request):
    if 'id' not in request.session:
        return JsonResponse({'result': '403', 'text': _('Please log in.')})

    if request.method == 'POST':
        user_id = request.session['id']
        email = request.session['email']
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if not all([old_password, new_password1, new_password2]):
            return JsonResponse({'result': '400', 'text': _('Please fill in all fields.')})

        if new_password1 != new_password2:
            return JsonResponse({'result': '400', 'text': _('New passwords do not match.')})

        try:
            user = TblUser.objects.get(id=user_id)
        except TblUser.DoesNotExist:
            return JsonResponse({'result': '404', 'text': _('User not found.')})

        if not user.check_password(old_password):
            return JsonResponse({'result': '400', 'text': _('Current password is not correct.')})

        try:
            with transaction.atomic(using='default'), transaction.atomic(using='radius'):
                # Update password in titan DB
                user.set_password(new_password1)
                user.save(using='default')

                # Update password in radius DB
                radcheck = Radcheck.objects.using('radius').get(username=email, attribute='Cleartext-Password')
                radcheck.value = new_password1
                radcheck.save(using='radius')

            return JsonResponse({'result': '200', 'text': _('Your password has been changed successfully.')})
        except Radcheck.DoesNotExist:
            return JsonResponse({'result': '500', 'text': _('Could not find password record in Radius DB.')})
        except Exception as e:
            return JsonResponse({'result': '500', 'text': _('An error occurred while changing the password.') + f' {str(e)}'})

    return JsonResponse({'result': '400', 'text': _('Invalid request method.')})


@csrf_protect
def api_change_sub_password_direct_v2(request):
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'text': _('Please log in.')})
    
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'text': _('Invalid request method.')})

    master_id = request.session['id']
    target_user_id = request.POST.get('target_user_id')
    master_password = request.POST.get('master_password')
    new_password = request.POST.get('new_password')

    if not all([target_user_id, master_password, new_password]):
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 1. Verify Master Password
    try:
        master_user = TblUser.objects.get(id=master_id)
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'text': _('User not found.')})

    if not master_password:
         return JsonResponse({'result': 400, 'text': _('Master password is required.')})

    # Inline password check to ensure no import issues
    try:
        hashed_text = master_user.password
        if ':' not in hashed_text:
             # Fallback for legacy passwords or plain text (should not happen but for safety)
             if hashed_text != master_password:
                 return JsonResponse({'result': 400, 'text': _('Master password is incorrect (legacy).')})
        else:
            _hashed, salt = hashed_text.split(':')
            calculated = hashlib.sha256(salt.encode() + master_password.encode()).hexdigest()
            if _hashed != calculated:
                return JsonResponse({'result': 400, 'text': _('Master password is incorrect.')})
    except Exception as e:
        print(f"DEBUG: Password check error: {e}")
        return JsonResponse({'result': 400, 'text': _('Master password check failed.')})

    # 2. Verify Target User is a sub-account of Master
    try:
        target_user = TblUser.objects.get(id=target_user_id, delete_yn='N')
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'text': _('Sub-account not found.')})

    base_email = master_user.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)
        
    is_child = False
    if target_user.parent_user_id == master_user.id:
        is_child = True
    elif target_user.parent_user_id is None and target_user.email.startswith(base_email + '_'):
        is_child = True
        
    if not is_child:
        return JsonResponse({'result': 403, 'text': _('Not authorized to modify this account.')})

    # 3. Verify Target User is a "created" sub-account (ends with _number)
    if not re.search(r'_\d+$', target_user.email):
        return JsonResponse({'result': 400, 'text': _('This account requires email verification to change password.')})

    # 4. Update Password
    try:
        new_hash = hashText(new_password)
        target_user.password = new_hash
        target_user.save()
        
        # Update Radius if needed
        try:
            radcheck = Radcheck.objects.using('radius').get(username=target_user.email, attribute='Cleartext-Password')
            radcheck.value = new_password
            radcheck.save(using='radius')
        except Radcheck.DoesNotExist:
            pass
            
        return JsonResponse({'result': 200})
    except Exception as e:
        return JsonResponse({'result': 500, 'text': str(e)})


# ===== 마이페이지 로그 조회 API =====

@csrf_protect
def api_my_app_login_logs(request):
    """앱로그인로그 (tbl_device_info) - 최근 50건"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    user_id = request.session['id']
    email = request.session['email']
    with connections['default'].cursor() as cur:
        # NAS IP → 이름 매핑
        cur.execute("SELECT hostip, name FROM tbl_agent3")
        nas_map = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT x.id, x.app_version, x.device_type, x.device_ip,
                   x.device_country, x.device_city, x.device_isp, x.login_time
            FROM tbl_device_info x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE y.email = %s
            ORDER BY x.login_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()
    logs = []
    for r in rows:
        ip = r[3] or ''
        nas_name = nas_map.get(ip, '')
        login_cst = to_china_time(r[7])
        logs.append({
            'device_type': r[2] or '',
            'app_version': r[1] or '',
            'device_ip': ip,
            'nas_name': nas_name,
            'country': r[4] or '',
            'city': r[5] or '',
            'isp': r[6] or '',
            'login_time': str(login_cst) if login_cst else '',
        })
    return JsonResponse({'result': 200, 'logs': logs})


@csrf_protect
def api_my_connection_logs(request):
    """접속로그 (radacct) - 최근 50건"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    email = request.session['email']
    # NAS IP → 이름 매핑
    with connections['default'].cursor() as cur:
        cur.execute("SELECT hostip, name FROM tbl_agent3")
        nas_map = {r[0]: r[1] for r in cur.fetchall()}
        # IP → 지역/ISP 매핑 (tbl_device_info)
        cur.execute("""
            SELECT DISTINCT x.device_ip, x.device_country, x.device_city, x.device_isp
            FROM tbl_device_info x JOIN tbl_user y ON x.user_id = y.id
            WHERE y.email = %s AND x.device_ip IS NOT NULL AND x.device_ip != ''
        """, [email])
        ip_loc_map = {}
        for r in cur.fetchall():
            ip_loc_map[r[0]] = {'country': r[1] or '', 'city': r[2] or '', 'isp': r[3] or ''}
    with connections['radius'].cursor() as cur:
        cur.execute("""
            SELECT radacctid, nasipaddress, nasporttype,
                   acctstarttime, acctstoptime,
                   acctinputoctets, acctoutputoctets,
                   callingstationid, framedipaddress
            FROM radacct
            WHERE username = %s
            ORDER BY acctstarttime DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    # ISP가 비어있는 IP 보완 조회 (전체 tbl_device_info에서)
    missing_ips = set()
    for r in rows:
        csid = r[7] or ''
        idx = csid.find('=5B')
        client_ip = csid[:idx] if idx > 0 else csid
        if client_ip and client_ip not in ip_loc_map:
            missing_ips.add(client_ip)

    if missing_ips:
        with connections['default'].cursor() as cur:
            ph = ','.join(['%s'] * len(missing_ips))
            cur.execute(f"""
                SELECT DISTINCT device_ip, device_country, device_city, device_isp
                FROM tbl_device_info
                WHERE device_ip IN ({ph}) AND device_ip IS NOT NULL
            """, list(missing_ips))
            for r in cur.fetchall():
                if r[0] and r[0] not in ip_loc_map:
                    ip_loc_map[r[0]] = {'country': r[1] or '', 'city': r[2] or '', 'isp': r[3] or ''}

    logs = []
    for r in rows:
        csid = r[7] or ''
        idx = csid.find('=5B')
        client_ip = csid[:idx] if idx > 0 else csid
        nas_ip = r[1] or ''
        nas_name = nas_map.get(nas_ip, '')
        raw_protocol = r[2] or ''
        protocol = PROTOCOL_MAP.get(raw_protocol, raw_protocol)
        start_cst = to_china_time(r[3])
        stop_cst = to_china_time(r[4])
        loc = ip_loc_map.get(client_ip, {})
        logs.append({
            'nas_ip': nas_ip,
            'nas_name': nas_name,
            'protocol': protocol,
            'start_time': str(start_cst) if start_cst else '',
            'stop_time': str(stop_cst) if stop_cst else '',
            'input_bytes': r[5] or 0,
            'output_bytes': r[6] or 0,
            'client_ip': client_ip,
            'country': loc.get('country', ''),
            'city': loc.get('city', ''),
            'isp': loc.get('isp', ''),
        })
    return JsonResponse({'result': 200, 'logs': logs})


@csrf_protect
def api_my_fail_logs(request):
    """접속실패로그 (tbl_agent_failed) - 최근 50건"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    email = request.session['email']
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT id, platform, app_version, server_name,
                   server_protocol, user_ip, user_location, failed_time
            FROM tbl_agent_failed
            WHERE username = %s
            ORDER BY failed_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()
    logs = []
    for r in rows:
        failed_cst = to_china_time(r[7])
        logs.append({
            'platform': r[1] or '',
            'app_version': r[2] or '',
            'server_name': r[3] or '',
            'protocol': r[4] or '',
            'ip': r[5] or '',
            'location': r[6] or '',
            'failed_time': str(failed_cst) if failed_cst else '',
        })
    return JsonResponse({'result': 200, 'logs': logs})


@csrf_protect
def api_my_disconnect_logs(request):
    """강제종료로그 (tbl_disconnection) - 최근 50건"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    email = request.session['email']

    with connections['default'].cursor() as cur:
        # NAS IP → 이름/텔레콤 매핑
        cur.execute("SELECT hostip, name, telecom FROM tbl_agent3")
        nas_name_map = {}
        nas_telecom_map = {}
        for r in cur.fetchall():
            nas_name_map[r[0]] = r[1] or ''
            nas_telecom_map[r[1] or ''] = r[2] or ''

        # 사용자 IP 지역/ISP 매핑 (tbl_device_info - 해당 유저)
        cur.execute("""
            SELECT DISTINCT x.device_ip, x.device_country, x.device_city, x.device_isp
            FROM tbl_device_info x JOIN tbl_user y ON x.user_id = y.id
            WHERE y.email = %s AND x.device_ip IS NOT NULL AND x.device_ip != ''
        """, [email])
        ip_loc_map = {}
        for r in cur.fetchall():
            ip_loc_map[r[0]] = {'country': r[1] or '', 'city': r[2] or '', 'isp': r[3] or ''}

        cur.execute("""
            SELECT d.id, d.connected_count, d.protocol,
                   IFNULL(d.server_name, '') as server_name,
                   IFNULL(a.telecom, '') as telecom,
                   d.disconnected_time, d.old_ip, d.new_ip
            FROM tbl_disconnection d
            LEFT JOIN tbl_agent3 a ON a.name = d.server_name
            WHERE d.username = %s
            ORDER BY d.disconnected_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    # server_name이 비어있는 row를 위해 radacct에서 매칭 시도
    empty_server_times = []
    for r in rows:
        if not r[3]:  # server_name empty
            if r[5]:  # disconnected_time exists
                empty_server_times.append(r[5])

    radacct_server_map = {}  # disconnected_time → (nas_name, telecom, protocol)
    if empty_server_times:
        with connections['radius'].cursor() as cur:
            # 해당 유저의 최근 접속 기록 전체 가져와서 매칭
            cur.execute("""
                SELECT nasipaddress, nasporttype, acctstarttime, acctstoptime
                FROM radacct
                WHERE username = %s
                ORDER BY acctstarttime DESC
                LIMIT 200
            """, [email])
            rad_rows = cur.fetchall()

        for disc_time in empty_server_times:
            best_match = None
            best_diff = None
            for rr in rad_rows:
                rad_start = rr[2]
                rad_stop = rr[3]
                if not rad_start:
                    continue
                # 세션이 disconnect 시점을 포함하거나 가장 가까운 것
                if rad_stop:
                    if rad_start <= disc_time <= rad_stop:
                        best_match = rr
                        break
                else:
                    if rad_start <= disc_time:
                        best_match = rr
                        break
                # 가장 가까운 시작 시간
                diff = abs((disc_time - rad_start).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_match = rr

            if best_match:
                nas_ip = best_match[0] or ''
                nas_name = nas_name_map.get(nas_ip, '')
                telecom = nas_telecom_map.get(nas_name, '')
                raw_pt = best_match[1] or ''
                protocol = PROTOCOL_MAP.get(raw_pt, raw_pt)
                radacct_server_map[disc_time] = (nas_name, telecom, protocol)

    # ISP가 비어있는 IP 보완 조회 (전체 tbl_device_info에서)
    missing_ips = set()
    for r in rows:
        old_ip = r[6] or ''
        if old_ip and old_ip not in ip_loc_map:
            missing_ips.add(old_ip)
        new_ip = r[7] or ''
        if new_ip and new_ip not in ip_loc_map:
            missing_ips.add(new_ip)

    if missing_ips:
        with connections['default'].cursor() as cur:
            ph = ','.join(['%s'] * len(missing_ips))
            cur.execute(f"""
                SELECT DISTINCT device_ip, device_country, device_city, device_isp
                FROM tbl_device_info
                WHERE device_ip IN ({ph}) AND device_ip IS NOT NULL
            """, list(missing_ips))
            for r in cur.fetchall():
                if r[0] and r[0] not in ip_loc_map:
                    ip_loc_map[r[0]] = {'country': r[1] or '', 'city': r[2] or '', 'isp': r[3] or ''}

    logs = []
    for r in rows:
        disc_cst = to_china_time(r[5])
        old_ip = r[6] or ''
        server_name = r[3] or ''
        telecom = r[4] or ''
        protocol = r[2] or ''

        # server_name 비어있으면 radacct에서 보완
        if not server_name and r[5] and r[5] in radacct_server_map:
            fallback = radacct_server_map[r[5]]
            server_name = fallback[0]
            telecom = fallback[1]
            if not protocol:
                protocol = fallback[2]

        loc = ip_loc_map.get(old_ip, {})
        logs.append({
            'connected_count': r[1],
            'protocol': protocol,
            'server_name': server_name,
            'telecom': telecom,
            'disconnected_time': str(disc_cst) if disc_cst else '',
            'old_ip': old_ip,
            'new_ip': r[7] or '',
            'country': loc.get('country', ''),
            'city': loc.get('city', ''),
            'isp': loc.get('isp', ''),
        })
    return JsonResponse({'result': 200, 'logs': logs})


@csrf_protect
def api_send_password_reset_for_sub(request):
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'text': _('Please log in.')})
        
    target_user_id = request.POST.get('target_user_id')
    master_id = request.session['id']
    LANGUAGE_CODE = request.LANGUAGE_CODE

    try:
        master_user = TblUser.objects.get(id=master_id)
        target_user = TblUser.objects.get(id=target_user_id, delete_yn='N')
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'text': _('User not found.')})

    # Check ownership
    base_email = master_user.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)
        
    is_child = False
    if target_user.parent_user_id == master_user.id:
        is_child = True
    elif target_user.parent_user_id is None and target_user.email.startswith(base_email + '_'):
        is_child = True
        
    if not is_child:
        return JsonResponse({'result': 403, 'text': _('Not authorized.')})

    # Send Email
    try:
        lang = 'ko'
        if LANGUAGE_CODE == 'en':
            lang = 'en'
        elif LANGUAGE_CODE == 'zh':
            lang = 'zh'
            
        send_email(target_user.email, 2, lang)
        return JsonResponse({'result': 200})
    except Exception as e:
        return JsonResponse({'result': 500, 'text': _('Failed to send email.')})


# ===== VPN 사용기록 페이지 =====

def vpn_history(request):
    """VPN 사용기록 페이지 렌더"""
    if 'id' not in request.session:
        return redirect('/login')
    LANGUAGE_CODE = request.LANGUAGE_CODE
    try:
        translation.activate(LANGUAGE_CODE)
    except Exception:
        pass
    context = {'LANGUAGE_CODE': LANGUAGE_CODE}
    return render(request, 'new/vpn_history.html', context)


@csrf_protect
def api_active_connections(request):
    """현재 VPN 접속 중인 세션 목록 — radacct × tbl_vpn_client_map 시간 매칭"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    email = request.session['email']
    import re

    with connections['default'].cursor() as cur:
        # NAS IP→이름
        cur.execute("SELECT hostip, name FROM tbl_agent3")
        nas_map = {r[0]: r[1] for r in cur.fetchall()}

        # IP → 위치/ISP
        cur.execute("""
            SELECT DISTINCT x.device_ip, x.device_country, x.device_city, x.device_isp
            FROM tbl_device_info x JOIN tbl_user y ON x.user_id = y.id
            WHERE y.email = %s AND x.device_ip IS NOT NULL AND x.device_ip != ''
        """, [email])
        ip_loc_map = {}
        for r in cur.fetchall():
            ip_loc_map[r[0]] = {'country': r[1] or '', 'city': r[2] or '', 'isp': r[3] or ''}

        # app_start_vpn 호출 기록 (최근 것부터)
        cur.execute("""
            SELECT id, device_type, device_os, app_version, client_ip, created_at
            FROM tbl_vpn_client_map
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, [email])
        vpn_starts = cur.fetchall()  # [(id, dtype, device_os, app_ver, client_ip, created_at), ...]

        # tbl_device_info 최근 로그인 기록 (시간 매칭 폴백용)
        cur.execute("""
            SELECT id, device_type, device_os, app_version, device_ip,
                   login_time, device_country, device_city, device_isp
            FROM tbl_device_info
            WHERE user_id = (SELECT id FROM tbl_user WHERE email = %s LIMIT 1)
            ORDER BY id DESC
            LIMIT 50
        """, [email])
        device_logins = cur.fetchall()  # [(id, dtype, os, appver, ip, login_time, country, city, isp), ...]

    # radacct 현재 활성 세션
    with connections['radius'].cursor() as cur:
        cur.execute("""
            SELECT radacctid, nasipaddress, nasporttype,
                   acctstarttime, acctinputoctets, acctoutputoctets,
                   callingstationid, framedipaddress, username, acctsessionid
            FROM radacct
            WHERE username = %s AND acctstoptime IS NULL
            ORDER BY acctstarttime DESC
        """, [email])
        rows = cur.fetchall()

    # 활성 세션 octets가 0인 경우 → 오늘 같은 NAS+IP 종료 세션의 최근 트래픽 조회
    nas_ip_traffic = {}
    if rows:
        zero_pairs = [(r[1], (r[6] or '').split('=5B')[0]) for r in rows if (r[4] or 0) == 0 and (r[5] or 0) == 0]
        if zero_pairs:
            with connections['radius'].cursor() as cur:
                cur.execute("""
                    SELECT nasipaddress, callingstationid,
                           acctinputoctets, acctoutputoctets
                    FROM radacct
                    WHERE username = %s AND acctstoptime IS NOT NULL
                      AND acctstarttime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    ORDER BY acctstoptime DESC
                """, [email])
                for sr in cur.fetchall():
                    cip = (sr[1] or '').split('=5B')[0]
                    key = (sr[0], cip)
                    if key not in nas_ip_traffic and (sr[2] or 0) > 0:
                        nas_ip_traffic[key] = (sr[2] or 0, sr[3] or 0)

    def parse_device_detail(dtype, device_os_raw):
        """device_os(User-Agent)에서 사람 읽기 좋은 기기정보 추출"""
        if dtype == 'Android' and device_os_raw:
            m_ver = re.search(r'Android\s+([\d.]+)', device_os_raw)
            m_model = re.search(r';\s*([^;)]+)\s*Build', device_os_raw)
            parts = []
            if m_ver: parts.append('Android ' + m_ver.group(1))
            if m_model: parts.append(m_model.group(1).strip())
            return ', '.join(parts) if parts else 'Android'
        elif dtype == 'iOS':
            m_ver = re.search(r'(?:OS|iOS)[/ ]([\d_.]+)', device_os_raw or '')
            m_dev = re.search(r'(iPhone|iPad)\d+,\d+', device_os_raw or '')
            parts = []
            if m_ver: parts.append('iOS ' + m_ver.group(1).replace('_', '.'))
            if m_dev: parts.append(m_dev.group(0))
            if not parts and device_os_raw:
                m2 = re.search(r'iOS/([\d.]+)', device_os_raw)
                if m2: parts.append('iOS ' + m2.group(1))
            return ', '.join(parts) if parts else 'iOS'
        elif dtype == 'Windows':
            return 'Windows'
        return dtype or ''

    # 시간 매칭: radacct.acctstarttime과 가장 가까운 vpn_client_map.created_at
    used_map_ids = set()  # 이미 매칭된 vpn_client_map id
    used_di_ids = set()   # 이미 매칭된 device_info id

    logs = []
    for r in rows:
        csid = r[6] or ''
        idx = csid.find('=5B')
        client_ip = csid[:idx] if idx > 0 else csid
        nas_ip = r[1] or ''
        nas_name = nas_map.get(nas_ip, nas_ip)
        raw_protocol = r[2] or ''
        protocol = PROTOCOL_MAP.get(raw_protocol, raw_protocol)
        acct_start = r[3]  # datetime
        start_cst = to_china_time(acct_start)
        loc = ip_loc_map.get(client_ip, {})

        # 1순위: tbl_vpn_client_map에서 시간 매칭 (60초 이내, 가장 가까운 것)
        best_match = None
        best_diff = None
        for vs in vpn_starts:
            vs_id, vs_dtype, vs_os, vs_appver, vs_ip, vs_created = vs
            if vs_id in used_map_ids:
                continue
            if acct_start and vs_created:
                diff = abs((acct_start - vs_created).total_seconds())
                if diff <= 60 and (best_diff is None or diff < best_diff):
                    best_match = vs
                    best_diff = diff

        device_type = ''
        device_detail = ''
        app_version = ''

        if best_match:
            used_map_ids.add(best_match[0])
            dtype_raw = (best_match[1] or '').capitalize()
            if dtype_raw == 'Ios': dtype_raw = 'iOS'
            device_type = dtype_raw
            device_detail = parse_device_detail(device_type, best_match[2])
            app_version = best_match[3] or ''
        else:
            # 2순위 폴백: tbl_device_info 시간 매칭 (login_time ↔ acctstarttime, 120초 이내)
            best_di = None
            best_di_diff = None
            for dl in device_logins:
                dl_id = dl[0]
                if dl_id in used_di_ids:
                    continue
                dl_login_time = dl[5]
                if acct_start and dl_login_time:
                    diff = abs((acct_start - dl_login_time).total_seconds())
                    if diff <= 120 and (best_di_diff is None or diff < best_di_diff):
                        best_di = dl
                        best_di_diff = diff
            if best_di:
                used_di_ids.add(best_di[0])
                dtype_raw = (best_di[1] or '').capitalize()
                if dtype_raw == 'Ios': dtype_raw = 'iOS'
                device_type = dtype_raw
                device_detail = parse_device_detail(device_type, best_di[2])
                app_version = best_di[3] or ''
                # 위치정보도 device_info에서 보충
                if not loc.get('country') and best_di[6]:
                    loc = {'country': best_di[6] or '', 'city': best_di[7] or '', 'isp': best_di[8] or ''}

            # 3순위 폴백: tbl_vpn_client_map에 없는 VPN 연결 (IKEv2 등 네이티브 VPN)
            # → 접속IP가 같고 acctstarttime 이전 6시간 이내에 app_check_login한 기기 매칭
            if not device_type and device_logins:
                # IP + 시간 근접 매칭 (acctstarttime 이전, 6시간 이내, 가장 가까운 것)
                best_ip_di = None
                best_ip_diff = None
                for dl in device_logins:
                    if dl[0] in used_di_ids:
                        continue
                    dl_ip = dl[4] or ''
                    dl_login_time = dl[5]
                    if dl_ip == client_ip and acct_start and dl_login_time:
                        diff = (acct_start - dl_login_time).total_seconds()
                        # login이 VPN 접속보다 먼저여야 하고, 6시간(21600초) 이내
                        if 0 <= diff <= 21600 and (best_ip_diff is None or diff < best_ip_diff):
                            best_ip_di = dl
                            best_ip_diff = diff
                # IP 매칭 실패 시 그냥 가장 최근 기기 정보 사용
                fallback_di = best_ip_di or next(
                    (dl for dl in device_logins if dl[0] not in used_di_ids), None
                )
                if fallback_di:
                    used_di_ids.add(fallback_di[0])
                    dtype_raw = (fallback_di[1] or '').capitalize()
                    if dtype_raw == 'Ios': dtype_raw = 'iOS'
                    device_type = dtype_raw
                    device_detail = parse_device_detail(device_type, fallback_di[2])
                    app_version = fallback_di[3] or ''
                    if not loc.get('country') and fallback_di[6]:
                        loc = {'country': fallback_di[6] or '', 'city': fallback_di[7] or '', 'isp': fallback_di[8] or ''}

        # 트래픽: 활성 세션이 0이면 최근 종료 세션(같은 NAS+IP)에서 대체
        in_bytes = r[4] or 0
        out_bytes = r[5] or 0
        if in_bytes == 0 and out_bytes == 0:
            st = nas_ip_traffic.get((nas_ip, client_ip))
            if st:
                in_bytes, out_bytes = st

        logs.append({
            'radacctid': r[0],
            'nas_ip': nas_ip,
            'nas_name': nas_name,
            'protocol': protocol,
            'start_time': str(start_cst) if start_cst else '',
            'input_bytes': in_bytes,
            'output_bytes': out_bytes,
            'client_ip': client_ip,
            'country': loc.get('country', ''),
            'city': loc.get('city', ''),
            'isp': loc.get('isp', ''),
            'device_type': device_type,
            'device_detail': device_detail,
            'app_version': app_version,
        })
    return JsonResponse({'result': 200, 'logs': logs})


@csrf_protect
def api_force_disconnect(request):
    """현재 접속 중인 VPN 세션 강제종료 (비밀번호 확인 후, SSH로 실제 VPN 연결도 끊음)"""
    import paramiko
    import socket
    import time as _time

    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    email = request.session['email']
    user_id = request.session['id']
    password = request.POST.get('password', '')
    radacctid = request.POST.get('radacctid', '')

    if not password or not radacctid:
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 비밀번호 확인
    try:
        user = TblUser.objects.get(id=user_id)
        if not matchHashedText(user.password, password):
            return JsonResponse({'result': 400, 'text': _('Password is incorrect.')})
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404})

    # radacct에서 연결 정보 조회
    with connections['radius'].cursor() as cur:
        cur.execute("""
            SELECT radacctid, username, nasipaddress, nasporttype, nasportid, acctsessionid
            FROM radacct
            WHERE radacctid = %s AND username = %s AND acctstoptime IS NULL
        """, [radacctid, email])
        row = cur.fetchone()
        if not row:
            return JsonResponse({'result': 404, 'text': _('Session not found or already disconnected.')})

    username = row[1]
    nasipaddress = row[2]
    nasporttype = row[3] or ''
    nasportid = str(row[4] or '')
    acctsessionid = row[5] or ''

    # NAS SSH 접속 정보 조회
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT username, password, name FROM tbl_agent3 WHERE hostip = %s
        """, [nasipaddress])
        ssh_rows = cur.fetchall()

    # SSH로 실제 VPN 연결 끊기
    if ssh_rows:
        ssh_user = ssh_rows[0][0]
        ssh_pass = ssh_rows[0][1]
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(nasipaddress, username=ssh_user, password=ssh_pass, timeout=5)

            if nasporttype == 'ISDN':  # OpenVPN
                channel = ssh.invoke_shell()
                channel.send("telnet 127.0.0.1 1199\n")
                _time.sleep(0.5)
                channel.send("mykakao9898\n")
                _time.sleep(0.2)
                channel.send('kill ' + username + '\n')
                _time.sleep(0.2)
                channel.send("exit\n")
                _time.sleep(0.2)
                channel.send("exit\n")
            elif nasportid == '443':  # SSTP
                sessionid = acctsessionid.replace('=5BSSTP=5D', '[SSTP]')
                cmd = "/usr/local/vpnserver/vpncmd " + nasipaddress + " /SERVER /HUB:TITAN /PASSWORD:'xkdlxksdpdlwjsxm12!@' /CMD SessionDisconnect " + sessionid
                ssh.exec_command(cmd)
            elif nasporttype == 'V2RAY':  # V2RAY → radacct만 업데이트
                pass
            else:  # IKEv2 (strongswan)
                cmd = 'strongswan statusall | grep ' + username
                _stdin, _stdout, _stderr = ssh.exec_command(cmd)
                _time.sleep(0.5)
                try:
                    first = _stdout.readline().strip()
                except Exception:
                    first = ''
                if first:
                    sa = first.split(':')[0].strip()
                    if sa:
                        down_cmd = 'strongswan stroke down-nb ' + sa
                        ssh.exec_command(down_cmd)
                        _time.sleep(0.2)
                        ssh.exec_command(down_cmd)
            ssh.close()
        except (socket.timeout, Exception):
            pass  # SSH 실패해도 radacct 업데이트는 진행

    # radacct acctstoptime + acctsessiontime 업데이트
    with connections['radius'].cursor() as cur:
        cur.execute("""
            UPDATE radacct SET acctstoptime = NOW(),
            acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, NOW()),
            acctterminatecause = 'Admin-Reset'
            WHERE radacctid = %s AND username = %s AND acctstoptime IS NULL
        """, [radacctid, email])

    return JsonResponse({'result': 200, 'text': _('Connection has been disconnected.')})


# ===== 제어센터 페이지 =====

def control_center(request):
    """제어센터 페이지 렌더"""
    if 'id' not in request.session:
        return redirect('/login')
    LANGUAGE_CODE = request.LANGUAGE_CODE
    try:
        translation.activate(LANGUAGE_CODE)
    except Exception:
        pass
    context = {'LANGUAGE_CODE': LANGUAGE_CODE}
    return render(request, 'new/control_center.html', context)


@csrf_protect
def api_my_app_sessions(request):
    """앱 세션 목록 (어드민과 동일 로직: django_session에서 email로 찾고 device_info 매칭)"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    user_id = request.session['id']
    email = request.session['email']

    import base64, json
    now = datetime.datetime.now()

    # Step 1: 모든 활성 django_session에서 이 유저의 세션 찾기
    all_sessions = Session.objects.filter(expire_date__gt=now).only(
        'session_key', 'session_data', 'expire_date'
    )
    user_sessions = []  # [{key, expire, expire_unix, remaining_seconds}]
    for sess in all_sessions:
        try:
            raw = sess.session_data
            decoded = base64.b64decode(raw).decode('utf-8', 'replace')
            idx = decoded.find('{')
            if idx < 0:
                continue
            data = json.loads(decoded[idx:])
            if data.get('email') == email:
                remaining = int((sess.expire_date - now).total_seconds())
                user_sessions.append({
                    'key': sess.session_key,
                    'expire': str(sess.expire_date),
                    'expire_unix': int(sess.expire_date.timestamp()) if sess.expire_date else 0,
                    'remaining_seconds': remaining,
                })
        except Exception:
            continue

    if not user_sessions:
        return JsonResponse({'result': 200, 'sessions': []})

    # Step 2: session_key로 tbl_device_info 매칭
    sk_list = [s['key'] for s in user_sessions]
    device_map = {}
    with connections['default'].cursor() as cur:
        placeholders = ','.join(['%s'] * len(sk_list))
        cur.execute(f"""
            SELECT session_key, device_type, device_os, app_version,
                   device_ip, device_country, device_city, device_isp, login_time, device_uuid
            FROM tbl_device_info
            WHERE session_key IN ({placeholders})
            ORDER BY login_time DESC
        """, sk_list)
        for r in cur.fetchall():
            sk = r[0]
            if sk not in device_map:
                device_map[sk] = {
                    'device_type': r[1] or '',
                    'device_os': r[2] or '',
                    'app_version': r[3] or '',
                    'device_ip': r[4] or '',
                    'device_country': r[5] or '',
                    'device_city': r[6] or '',
                    'device_isp': r[7] or '',
                    'login_time': r[8],
                    'device_uuid': r[9] or '',
                }

    # Step 3: UUID 폴백 제거 (웹 세션이 옛날 기기정보와 잘못 매칭되는 문제 방지)
    # session_key 매칭이 안 되는 세션 = 웹 세션 → Step 4에서 자동 제외됨

    # Step 4: 앱 세션만 반환 (device_map에 있는 것 = 앱)
    sessions = []
    for sess in user_sessions:
        dev = device_map.get(sess['key'])
        if not dev:
            continue  # 웹 세션 → 제외
        login_cst = to_china_time(dev['login_time']) if dev['login_time'] else None
        sessions.append({
            'session_key': sess['key'],
            'expire': sess['expire'],
            'remaining_seconds': sess['remaining_seconds'],
            'device_type': dev['device_type'],
            'device_os': dev['device_os'],
            'app_version': dev['app_version'],
            'device_ip': dev['device_ip'],
            'device_country': dev['device_country'],
            'device_city': dev['device_city'],
            'device_isp': dev['device_isp'],
            'login_time': str(login_cst) if login_cst else '',
            'device_uuid': dev['device_uuid'],
        })

    sessions.sort(key=lambda x: x.get('login_time', ''), reverse=True)
    return JsonResponse({'result': 200, 'sessions': sessions})


@csrf_protect
def api_ban_my_ip(request):
    """자기 기기 IP 차단 (앱 로그인만 차단 — is_app_only=1)"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    user_id = request.session['id']
    email = request.session['email']
    password = request.POST.get('password', '')
    device_ip = request.POST.get('device_ip', '')

    if not password or not device_ip:
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 비밀번호 확인
    try:
        user = TblUser.objects.get(id=user_id)
        if not matchHashedText(user.password, password):
            return JsonResponse({'result': 400, 'text': _('Password is incorrect.')})
    except Exception:
        return JsonResponse({'result': 400, 'text': _('Password verification failed.')})

    # tbl_banned_device에 IP 차단 추가 (앱 전용)
    with connections['default'].cursor() as cur:
        cur.execute("""
            INSERT INTO tbl_banned_device (ban_type, device_ip, reason, banned_by, is_active, email, user_id)
            VALUES ('ip', %s, 'Self-ban from control center (app only)', %s, 1, %s, %s)
        """, [device_ip, f'user:{email}', email, user_id])

    # 해당 IP의 앱 세션도 삭제
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT session_key FROM tbl_device_info
            WHERE user_id = %s AND device_ip = %s AND session_key IS NOT NULL AND session_key != ''
        """, [user_id, device_ip])
        keys = [r[0] for r in cur.fetchall()]
        if keys:
            Session.objects.filter(session_key__in=keys).delete()

    return JsonResponse({'result': 200, 'text': _('IP has been banned for app login.')})


@csrf_protect
def api_ban_my_device(request):
    """자기 기기 UUID 차단"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    user_id = request.session['id']
    email = request.session['email']
    password = request.POST.get('password', '')
    device_uuid = request.POST.get('device_uuid', '')

    if not password or not device_uuid:
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 비밀번호 확인
    try:
        user = TblUser.objects.get(id=user_id)
        if not matchHashedText(user.password, password):
            return JsonResponse({'result': 400, 'text': _('Password is incorrect.')})
    except Exception:
        return JsonResponse({'result': 400, 'text': _('Password verification failed.')})

    # UUID 차단
    with connections['default'].cursor() as cur:
        cur.execute("""
            INSERT INTO tbl_banned_device (ban_type, device_uuid, reason, banned_by, is_active, email, user_id)
            VALUES ('uuid', %s, 'Self-ban from control center', %s, 1, %s, %s)
        """, [device_uuid, f'user:{email}', email, user_id])

    # 해당 UUID의 세션도 삭제
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT session_key FROM tbl_device_info
            WHERE user_id = %s AND device_uuid = %s AND session_key IS NOT NULL AND session_key != ''
        """, [user_id, device_uuid])
        keys = [r[0] for r in cur.fetchall()]
        if keys:
            Session.objects.filter(session_key__in=keys).delete()

    return JsonResponse({'result': 200, 'text': _('Device has been banned.')})


@csrf_protect
def api_unban_my_device(request):
    """자기 기기 차단 해제"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    email = request.session['email']
    ban_id = request.POST.get('ban_id', '')

    if not ban_id:
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    with connections['default'].cursor() as cur:
        cur.execute("""
            UPDATE tbl_banned_device SET is_active = 0
            WHERE id = %s AND email = %s AND is_active = 1
        """, [ban_id, email])
        if cur.rowcount == 0:
            return JsonResponse({'result': 404, 'text': _('Ban record not found.')})

    return JsonResponse({'result': 200, 'text': _('Ban has been lifted.')})


@csrf_protect
def api_my_bans(request):
    """내 차단 목록"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    email = request.session['email']

    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT id, ban_type, COALESCE(device_ip, device_uuid, '') as ban_value, reason, regist_date, is_active
            FROM tbl_banned_device
            WHERE email = %s
            ORDER BY regist_date DESC
        """, [email])
        rows = cur.fetchall()

    bans = []
    for r in rows:
        bans.append({
            'id': r[0],
            'ban_type': r[1] or '',
            'ban_value': r[2] or '',
            'reason': r[3] or '',
            'banned_at': str(r[4]) if r[4] else '',
            'is_active': int(r[5]) if r[5] is not None else 0,
        })
    return JsonResponse({'result': 200, 'bans': bans})


# ===== 기기 삭제 =====

@csrf_protect
def api_delete_device_session(request):
    """기기 삭제 — VPN 연결 강제종료 → tbl_device_info + django_session 삭제"""
    import paramiko
    import socket
    import time as _time

    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    user_id = request.session['id']
    email = request.session['email']
    password = request.POST.get('password', '')
    session_key = request.POST.get('session_key', '')

    if not password or not session_key:
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 비밀번호 확인
    try:
        user = TblUser.objects.get(id=user_id)
        if not matchHashedText(user.password, password):
            return JsonResponse({'result': 400, 'text': _('Password is incorrect.')})
    except Exception:
        return JsonResponse({'result': 400, 'text': _('Password verification failed.')})

    # session_key가 이 유저의 것인지 확인 + device_ip 가져오기
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT id, device_ip FROM tbl_device_info
            WHERE user_id = %s AND session_key = %s
        """, [user_id, session_key])
        row = cur.fetchone()
        if not row:
            return JsonResponse({'result': 400, 'text': _('Device not found or not owned by you.')})
    device_ip = row[1] or ''

    # 현재 자기가 쓰는 세션은 삭제 불가
    if session_key == request.session.session_key:
        return JsonResponse({'result': 400, 'text': _('Cannot delete your current session.')})

    # ── VPN 연결이 있으면 강제종료 ──
    if device_ip:
        with connections['radius'].cursor() as cur:
            cur.execute("""
                SELECT radacctid, username, nasipaddress, nasporttype, nasportid, acctsessionid
                FROM radacct
                WHERE username = %s AND callingStationId = %s AND acctstoptime IS NULL
            """, [email, device_ip])
            active_conns = cur.fetchall()

        for conn in active_conns:
            radacctid = conn[0]
            username = conn[1]
            nasipaddress = conn[2]
            nasporttype = conn[3] or ''
            nasportid = str(conn[4] or '')
            acctsessionid = conn[5] or ''

            # NAS SSH 정보
            with connections['default'].cursor() as cur:
                cur.execute("SELECT username, password FROM tbl_agent3 WHERE hostip = %s", [nasipaddress])
                ssh_rows = cur.fetchall()

            if ssh_rows:
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(nasipaddress, username=ssh_rows[0][0], password=ssh_rows[0][1], timeout=5)

                    if nasporttype == 'ISDN':  # OpenVPN
                        channel = ssh.invoke_shell()
                        channel.send("telnet 127.0.0.1 1199\n")
                        _time.sleep(0.5)
                        channel.send("mykakao9898\n")
                        _time.sleep(0.2)
                        channel.send('kill ' + username + '\n')
                        _time.sleep(0.2)
                        channel.send("exit\n")
                        _time.sleep(0.2)
                        channel.send("exit\n")
                    elif nasportid == '443':  # SSTP
                        sessionid = acctsessionid.replace('=5BSSTP=5D', '[SSTP]')
                        cmd = "/usr/local/vpnserver/vpncmd " + nasipaddress + " /SERVER /HUB:TITAN /PASSWORD:'xkdlxksdpdlwjsxm12!@' /CMD SessionDisconnect " + sessionid
                        ssh.exec_command(cmd)
                    elif nasporttype == 'V2RAY':
                        pass
                    else:  # IKEv2
                        cmd = 'strongswan statusall | grep ' + username
                        _stdin, _stdout, _stderr = ssh.exec_command(cmd)
                        _time.sleep(0.5)
                        try:
                            first = _stdout.readline().strip()
                        except Exception:
                            first = ''
                        if first:
                            sa = first.split(':')[0].strip()
                            if sa:
                                down_cmd = 'strongswan stroke down-nb ' + sa
                                ssh.exec_command(down_cmd)
                                _time.sleep(0.2)
                                ssh.exec_command(down_cmd)
                    ssh.close()
                except (socket.timeout, Exception):
                    pass

            # radacct 종료 마킹
            with connections['radius'].cursor() as cur:
                cur.execute("""
                    UPDATE radacct SET acctstoptime = NOW(), acctterminatecause = 'Admin-Reset'
                    WHERE radacctid = %s AND acctstoptime IS NULL
                """, [radacctid])

    # ── tbl_device_info 삭제 ──
    with connections['default'].cursor() as cur:
        cur.execute("DELETE FROM tbl_device_info WHERE user_id = %s AND session_key = %s", [user_id, session_key])

    # ── django_session 삭제 ──
    with connections['default'].cursor() as cur:
        cur.execute("DELETE FROM django_session WHERE session_key = %s", [session_key])

    return JsonResponse({'result': 200, 'text': _('Device session has been deleted.')})


# ===== 계정 일시차단 =====

@csrf_protect
def api_suspend_account(request):
    """자기 계정 일시차단 / 해제"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403})
    if request.method != 'POST':
        return JsonResponse({'result': 400})

    user_id = request.session['id']
    email = request.session['email']
    password = request.POST.get('password', '')
    action = request.POST.get('action', '')  # 'suspend' or 'resume'

    if not password or action not in ('suspend', 'resume'):
        return JsonResponse({'result': 400, 'text': _('Missing parameters.')})

    # 비밀번호 확인
    try:
        user = TblUser.objects.get(id=user_id)
        if not matchHashedText(user.password, password):
            return JsonResponse({'result': 400, 'text': _('Password is incorrect.')})
    except Exception:
        return JsonResponse({'result': 400, 'text': _('Password verification failed.')})

    if action == 'suspend':
        # radius에서 Auth-Type := Reject 추가 → VPN 접속 차단
        with connections['radius'].cursor() as cur:
            # 이미 있으면 무시
            cur.execute("""
                SELECT id FROM radcheck
                WHERE username = %s AND attribute = 'Auth-Type' AND value = ':= Reject'
            """, [email])
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO radcheck (username, attribute, op, value)
                    VALUES (%s, 'Auth-Type', ':=', 'Reject')
                """, [email])

        # 현재 접속 중인 세션 모두 종료
        with connections['radius'].cursor() as cur:
            cur.execute("""
                UPDATE radacct SET acctstoptime = NOW(), acctterminatecause = 'User-Suspend'
                WHERE username = %s AND acctstoptime IS NULL
            """, [email])

        # tbl_user에 suspended 표시
        with connections['default'].cursor() as cur:
            cur.execute("UPDATE tbl_user SET is_suspended = 1 WHERE id = %s", [user_id])

        return JsonResponse({'result': 200, 'text': _('Account has been suspended. No one can use this account until you resume it.')})

    else:  # resume
        # Auth-Type Reject 삭제
        with connections['radius'].cursor() as cur:
            cur.execute("""
                DELETE FROM radcheck
                WHERE username = %s AND attribute = 'Auth-Type' AND value = ':= Reject'
            """, [email])

        with connections['default'].cursor() as cur:
            cur.execute("UPDATE tbl_user SET is_suspended = 0 WHERE id = %s", [user_id])

        return JsonResponse({'result': 200, 'text': _('Account has been resumed.')})


# 자동결제 상태 조회
@csrf_exempt
def api_autopay_status(request):
    if 'id' not in request.session:
        return JsonResponse({'result': 401})

    user_id = request.session['id']
    cursor = connections['default'].cursor()
    cursor.execute('''
        SELECT id, session, month_type, product_name, amount, status, last_paid_date, next_pay_date, created_date
        FROM tbl_autopay WHERE user_id = %s AND status = 'active' ORDER BY id DESC LIMIT 1
    ''', [user_id])
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    if not rows:
        return JsonResponse({'result': 200, 'has_autopay': False})

    row = dict(zip(columns, rows[0]))
    return JsonResponse({
        'result': 200,
        'has_autopay': True,
        'autopay': {
            'id': row['id'],
            'session': row['session'],
            'month_type': row['month_type'],
            'product_name': row['product_name'],
            'amount': row['amount'],
            'last_paid_date': row['last_paid_date'].strftime('%Y-%m-%d %H:%M') if row['last_paid_date'] else '',
            'next_pay_date': row['next_pay_date'].strftime('%Y-%m-%d %H:%M') if row['next_pay_date'] else '',
            'created_date': row['created_date'].strftime('%Y-%m-%d %H:%M') if row['created_date'] else '',
        }
    })


# 자동결제 해지
@csrf_exempt
def api_autopay_cancel(request):
    if 'id' not in request.session:
        return JsonResponse({'result': 401})

    user_id = request.session['id']
    cursor = connections['default'].cursor()
    cursor.execute('''
        UPDATE tbl_autopay SET status = 'cancelled', cancelled_date = NOW()
        WHERE user_id = %s AND status = 'active'
    ''', [user_id])

    if cursor.rowcount > 0:
        print('INFO [AUTOPAY] -> 자동결제 해지: user_id=%s' % user_id)
        return JsonResponse({'result': 200, 'message': '자동결제가 해지되었습니다.'})
    else:
        return JsonResponse({'result': 200, 'message': '활성화된 자동결제가 없습니다.'})
