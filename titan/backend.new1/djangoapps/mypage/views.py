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


# 마이페이지 렌더링 (2020-03-11)
def mypage(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
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

    context = {}
    context['xinfo'] = xinfo
    context['res'] = res
    context['user'] = u1
    return render(request, 'new/mypage.html', context)
