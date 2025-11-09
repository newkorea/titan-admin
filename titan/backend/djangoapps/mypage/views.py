import json
import datetime
import re
import uuid
import requests
from django.shortcuts import render
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.db import transaction
from django.db.models import Max
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
from django.utils import translation
from django.contrib.sessions.models import Session


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
    if expire_time != None:
        expire_time = datetime.datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.now(timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S')
        if expire_time < now:
            expire_time = None
            xinfo['expire_time'] = expire_time
        else:
            xinfo['expire_time'] = expire_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        xinfo['expire_time'] = None

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

    context = {}
    context['xinfo'] = xinfo
    context['res'] = res
    context['user'] = u1
    context['sessions'] = sessions
    context['show_history'] = show_history
    # Subaccounts: emails like baseEmail_1, baseEmail_2 ...
    base_email = u1.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)
    # Build detailed subaccount list with name, concurrent devices and expiry
    subaccounts = []
    try:
        subs = TblUser.objects.filter(email__startswith=base_email + '_', delete_yn='N').order_by('id')
        for su in subs:
            email_s = su.email
            # concurrent devices from radius
            try:
                concurrent = my_radius_session(email_s)
            except Exception:
                concurrent = ''
            # expiry time string
            try:
                expire_str = my_radius_time(email_s, 'str')
            except Exception:
                expire_str = None
            subaccounts.append({
                'id': su.id,
                'email': email_s,
                'username': su.username,
                'concurrent': concurrent,
                'expire_time': expire_str,
                'regist_date': su.regist_date,
            })
    except Exception:
        pass
    context['subaccounts'] = subaccounts
    context['base_email'] = base_email
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
