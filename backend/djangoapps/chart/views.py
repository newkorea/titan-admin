import json
import datetime
import smtplib
import paramiko
import socket
import traceback
import re
import uuid
import requests
import time
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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.models import *
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from django.utils import translation
from django.conf import settings
from calendar import monthrange


LINE_COLOR_BLUE = 'rgba(0, 123, 255, 1)'
BACK_COLOR_BLUE = 'rgba(0, 123, 255, 0.2)'

LINE_COLOR_RED = 'rgba(255, 99, 132, 1)'
BACK_COLOR_RED = 'rgba(255, 99, 132, 0.2)'

LINE_COLOR_YELLOW = 'rgba(255, 193, 7, 1)'
BACK_COLOR_YELLOW = 'rgba(255, 193, 7, 0.2)'

LINE_COLOR_PURPLE = 'rgba(136, 80, 255, 1)'
BACK_COLOR_PURPLE = 'rgba(136, 80, 255, 0.2)'

COLOR_BLUE = 'rgba(0, 0, 255, 1)'
COLOR_RED = 'rgba(255, 0, 0, 1)'
COLOR_YELLOW = 'rgba(255, 255, 0, 1)'
COLOR_PURPLE = 'rgba(136, 80, 255, 1)'

# 검색필터 생성 [ 2019 ~ 현재 yyyy ]
def make_yaer_list():
    year_list = []
    this_year = datetime.datetime.now().year
    for years in range(2019, this_year + 1):
      year_list.append(years)
    return year_list


# 검색필터 생성 [ 2019 ~ 현재 yyyy ]
def make_day_list():
    day_list = []
    for day in range(1, 32):
      day_list.append(day)
    return day_list


# x축 생성 (일별통계)
def make_axisX_dd(year, month):
    days = monthrange(year, month)[1]
    list_day = []
    for day in range(1, days+1):
        day = str(day) + "일"
        list_day.append(day)
    return list_day


# x축 생성 (월별통계)
def make_axisX_mm():
    return ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']


# y축 리스트 시리얼라이즈 (일별통계)
def serialize_rows_dd(rows, x_axis):
    template = [0] * len(x_axis)
    for row in rows:
        template[int(row[0])-1] = row[1]
    return template


# y축 리스트 시리얼라이즈 (월별통계)
def serialize_rows_mm(rows, use):
    y_axis1 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    y_axis2 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    y_axis3 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    y_axis4 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    

    for row in rows:
        idx = -1
        for mm in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
            idx += 1
            if row['mm'] == mm:
                if use in [4, 3, 2, 1]:
                    y_axis1[idx] = row['cnt1']
                if use in [4, 3, 2]:
                    y_axis2[idx] = row['cnt2']
                if use in [4, 3]:
                    y_axis3[idx] = row['cnt3']
                if use == [4]:
                    y_axis4[idx] = row['cnt4']
                
    if use == 1:
        return y_axis1
    elif use == 2:
        return y_axis1, y_axis2
    elif use == 3:
        return y_axis1, y_axis2, y_axis3
    elif use == 4:
        return y_axis1, y_axis2, y_axis3, y_axis4


# 헤더 텍스트 생성
def make_html_title(type, main):
    if main == 'mm':
        if type == 'user':
            title = '월별 가입계정 및 활성계정 통계'
            desc = 'TITAN VPN에 월별 가입계정 및 활성계정 통계를 차트로 확인할 수 있습니다'
        elif type == 'money':
            title = '월별 결제금액 통계'
            desc = 'TITAN VPN에 결제한 금액 통계를 차트로 확인할 수 있습니다'    
        elif type == 'money_cnt':
            title = '월별 결제건수 통계'
            desc = 'TITAN VPN에 결제한 건수 통계를 차트로 확인할 수 있습니다'    
    elif main == 'dd':
        if type == 'user':
            title = '일별 가입계정 및 활성계정 통계'
            desc = 'TITAN VPN에 일별 가입계정 및 활성계정 통계를 차트로 확인할 수 있습니다'
        elif type == 'money':
            title = '일별 결제금액 통계'
            desc = 'TITAN VPN에 결제한 금액 통계를 차트로 확인할 수 있습니다'
        elif type == 'money_cnt':
            title = '일별 결제건수 통계'
            desc = 'TITAN VPN에 결제한 건수 통계를 차트로 확인할 수 있습니다'
        elif type == 'saler_user':
            title = '[추천인] 일별 가입계정 및 활성계정 통계'
            desc = 'TITAN VPN에 일별 가입계정 및 활성계정 통계를 차트로 확인할 수 있습니다'
        elif type == 'saler_money':
            title = '[추천인] 일별 결제금액 통계'
            desc = 'TITAN VPN에 결제한 금액 통계를 차트로 확인할 수 있습니다'
    elif main == 'total':
        if type == 'rec':
            title = '추천인 보유수 통계'
            desc = 'TITAN VPN 회원 중 추천인 보유수가 높은 순서대로 보여줍니다'
        elif type == 'nas':
            title = 'NAS별 실시간 접속자수'
            desc = '실시간 접속수입니다.'
    endpoint = '/api/v1/read/{main}/{type}'.format(type=type, main=main)
    return title, desc, endpoint


# 실시간 사용자 렌더
def realtime_user(request):
    context = {}
    return render(request, 'chart/realtime_user.html', context)

def device_info(request):
    context = {}
    return render(request, 'chart/device_info.html', context)

def connection_info(request):
    context = {}
    return render(request, 'chart/connection_info.html', context)

def disconnection_info(request):
    context = {}
    return render(request, 'chart/disconnection_info.html', context)

def failed_info(request):
    context = {}
    return render(request, 'chart/failed_info.html', context)

def reward_info(request):
    context = {}
    return render(request, 'chart/reward_info.html', context)

# 서버관리 (NAS 서버 리스트/수정)
@allow_admin
def server_admin(request):
    context = {}
    return render(request, 'admin/server.html', context)

@allow_admin
def api_read_agents(request):
    # Params with safe defaults (supporting GET/POST)
    def _gp(key, default=None):
        return request.POST.get(key) or request.GET.get(key) or default

    try:
        start = int(_gp('start', 0) or 0)
    except Exception:
        start = 0
    try:
        length = int(_gp('length', 10) or 10)
    except Exception:
        length = 10
    try:
        draw = int(_gp('draw', 1) or 1)
    except Exception:
        draw = 1
    try:
        orderby_col = int(_gp('order[0][column]', 0) or 0)
    except Exception:
        orderby_col = 0
    orderby_opt = (_gp('order[0][dir]', 'desc') or 'desc').lower()
    if orderby_opt not in ['asc', 'desc']:
        orderby_opt = 'desc'

    # Filters
    host = (_gp('host', '') or '').strip()
    telecom = (_gp('telecom', '') or '').strip()
    is_active = (_gp('is_active', '') or '').strip()
    is_status = (_gp('is_status', '') or '').strip()

    # where clause
    wc = ' where 1=1 '
    if host:
        wc += " and (hostip like '%{h}%' or hostdomain like '%{h}%') ".format(h=host)
    if telecom:
        wc += " and telecom = '{tel}' ".format(tel=telecom)
    if is_active in ['0','1']:
        wc += " and is_active = {v} ".format(v=is_active)
    if is_status in ['0','1']:
        wc += " and is_status = {v} ".format(v=is_status)

    column_name = [
        'id',
        'name',
        'hostdomain',
        'hostip',
        'telecom',
        'is_active',
        'is_status',
        'is_auto',
        'protocol'
    ]
    if orderby_col < 0 or orderby_col >= len(column_name):
        orderby_col = 0

    # count
    with connections['default'].cursor() as cur:
        cur.execute('''
            SELECT count(*) FROM titan.tbl_agent3 {wc}
        '''.format(wc=wc))
        total = cur.fetchall()[0][0]

    # main: try full schema first (with config/v2config), fallback otherwise
    with connections['default'].cursor() as cur:
        query_full = '''
            SELECT id, name, hostdomain, hostip, telecom, is_active, is_status, is_auto, protocol,
                   config, v2config, username, password
            FROM titan.tbl_agent3
            {wc}
            ORDER BY {orderby_col} {orderby_opt}
            LIMIT {start}, {length}
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            length=length
        )
        try:
            cur.execute(query_full)
            rows = dictfetchall(cur)
        except Exception:
            query_fb = '''
                SELECT id, name, hostdomain, hostip, telecom, is_active, is_status, is_auto, protocol,
                       username, password
                FROM titan.tbl_agent3
                {wc}
                ORDER BY {orderby_col} {orderby_opt}
                LIMIT {start}, {length}
            '''.format(
                wc=wc,
                orderby_col=column_name[orderby_col],
                orderby_opt=orderby_opt,
                start=start,
                length=length
            )
            cur.execute(query_fb)
            rows = dictfetchall(cur)
            for r in rows:
                r['config'] = r.get('config', '')
                r['v2config'] = r.get('v2config', '')

    return JsonResponse({
        'recordsTotal': total,
        'recordsFiltered': total,
        'draw': draw,
        'data': rows
    })

@allow_admin
def api_update_agent(request):
    id = request.POST.get('id')
    name = request.POST.get('name')
    hostdomain = request.POST.get('hostdomain')
    hostip = request.POST.get('hostip')
    telecom = request.POST.get('telecom')
    username = request.POST.get('username')
    password = request.POST.get('password')
    is_active = request.POST.get('is_active')
    is_status = request.POST.get('is_status')
    is_auto = request.POST.get('is_auto')
    protocol = request.POST.get('protocol')
    config = request.POST.get('config')
    v2config = request.POST.get('v2config')

    try:
        with connections['default'].cursor() as cur:
            try:
                # try new schema with config/v2config
                cur.execute('''
                    UPDATE titan.tbl_agent3
                    SET name=%s, hostdomain=%s, hostip=%s, telecom=%s,
                        username=%s, password=%s, is_active=%s, is_status=%s,
                        is_auto=%s, protocol=%s,
                        config=%s, v2config=%s
                    WHERE id=%s
                ''', [name, hostdomain, hostip, telecom, username, password, is_active, is_status, is_auto, protocol, config, v2config, id])
            except Exception:
                # fallback to old schema (no config/v2config)
                cur.execute('''
                    UPDATE titan.tbl_agent3
                    SET name=%s, hostdomain=%s, hostip=%s, telecom=%s,
                        username=%s, password=%s, is_active=%s, is_status=%s,
                        is_auto=%s, protocol=%s
                    WHERE id=%s
                ''', [name, hostdomain, hostip, telecom, username, password, is_active, is_status, is_auto, protocol, id])
        return JsonResponse({'result': 200, 'title': 'Success', 'text': '수정되었습니다'})
    except Exception:
        print('api_update_agent failed:', traceback.format_exc())
        return JsonResponse({'result': 500, 'title': 'Failed', 'text': '수정 중 오류가 발생했습니다'})
    
# (2022-08-08)
@allow_admin
def api_read_device(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    email = request.POST.get('email')
    app_version = request.POST.get('app_version')
    device_ip = request.POST.get('device_ip')
    device_country = request.POST.get('device_country')
    device_city = request.POST.get('device_city')
    device_type = request.POST.get('device_type')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    api_url = request.POST.get('api_url')
    load_balancer = request.POST.get('load_balancer')

    # 로깅 (datatables 기본 파라미터)
    print('DEBUG -> start : ', start)
    print('DEBUG -> length : ', length)
    print('DEBUG -> draw : ', draw)
    print('DEBUG -> orderby_col : ', orderby_col)
    print('DEBUG -> orderby_opt : ', orderby_opt)

    # 로깅 (검색필터 파라미터)
    print('DEBUG -> number : ', number)
    print('DEBUG -> email : ', email)
    print('DEBUG -> app_version : ', app_version)
    print('DEBUG -> device_ip : ', device_ip)
    print('DEBUG -> device_country : ', device_country)
    print('DEBUG -> device_city : ', device_city)
    print('DEBUG -> device_type : ', device_type)
    print('DEBUG -> api_url : ', api_url)
    print('DEBUG -> load_balancer : ', load_balancer)
    print('DEBUG -> start_time : ', start_time)
    print('DEBUG -> end_time : ', end_time)

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if number != '':
        wc += " and x.id = '{number}' ".format(number=number)
    if email != '':
        wc += " and y.email like '%{email}%' ".format(email=email)
    if app_version != '':
        wc += " and x.app_version = '{app_version}' ".format(app_version=app_version)
    if device_ip != '':
        wc += " and x.device_ip like '{device_ip}%' ".format(device_ip=device_ip)
    if device_country != '':
        wc += " and x.device_country like '{device_country}%' ".format(device_country=device_country)
    if device_city != '':
        wc += " and x.device_city like '{device_city}%' ".format(device_city=device_city)
    if device_type != '':
        if device_type != "All" :
    	    wc += " and x.device_type like '%{device_type}%' ".format(device_type=device_type)
    if api_url != '':
        wc += " and x.api_url = '{api_url}' ".format(api_url=api_url)
    if load_balancer != '':
        wc += " and x.load_balancer = '{load_balancer}' ".format(load_balancer=load_balancer)
    if start_time != '':
        wc += '''
            and x.login_time >= '{start_time}'
        '''.format(start_time=start_time)
    if end_time != '':
        wc += '''
            and x.login_time < '{end_time}'
        '''.format(end_time=end_time)

    # order by 리스트
    column_name = [
        'x.id',
        'y.email',
        'y.app_version',
        'y.device_type',
        'x.device_ip',
        'x.device_country',
        'x.device_city',
        'x.device_isp',
        'x.api_url',
        'x.load_balancer',
        'x.login_time'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_device_info x
            join tbl_user y
            on x.user_id = y.id
            {wc}
        '''.format(wc=wc)
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  x.id,
            		y.email,
            		x.app_version,
            		x.device_type,
            		x.device_ip,
            		x.device_uuid,
            		x.device_country,
            		x.device_city,
            		x.device_isp,
            		x.api_url,
            		x.load_balancer,
            		x.login_time
            from tbl_device_info x
            join tbl_user y
            on x.user_id = y.id
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)

# (2022-12-03)
@allow_admin
def api_read_connection(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    username = request.POST.get('username')
    nasipaddress = request.POST.get('nasipaddress')
    nasporttype = request.POST.get('nasporttype')
    calledstationid = request.POST.get('calledstationid')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    callingstationid = request.POST.get('callingstationid')
    framedipaddress = request.POST.get('framedipaddress')

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if number != '':
        wc += " and radacctid = '{number}' ".format(number=number)
    if username != '':
        wc += " and username like '%{username}%' ".format(username=username)
    if nasipaddress != '':
        wc += " and nasipaddress = '{nasipaddress}' ".format(nasipaddress=nasipaddress)
    if nasporttype != '':
        wc += " and nasporttype = '{nasporttype}' ".format(nasporttype=nasporttype)
    #if acctinputoctets != '':
    #    wc += " and acctinputoctets = '{acctinputoctets}' ".format(acctinputoctets=acctinputoctets)
    #if acctoutputoctets != '':
    #    wc += " and acctoutputoctets = '{acctoutputoctets}' ".format(acctoutputoctets=acctoutputoctets)
    #if server == 'EM':
    #    wc += " and s.telecom = 'EM' "
    if calledstationid != '':
        wc += " and calledstationid like '{calledstationid}%' ".format(calledstationid=calledstationid)
    if callingstationid != '':
        wc += " and callingstationid like '{callingstationid}%' ".format(callingstationid=callingstationid)
    if framedipaddress != '':
        wc += " and framedipaddress = '{framedipaddress}' ".format(framedipaddress=framedipaddress)
    if start_time != '':
        wc += '''
            and acctstarttime >= '{start_time}'
        '''.format(start_time=start_time)
    if end_time != '':
        wc += '''
            and acctstarttime < '{end_time}'
        '''.format(end_time=end_time)
    
    print(wc)
    # order by 리스트
    column_name = [
        'radacctid',
        'username',
        'nasipaddress',
        'nasporttype',
        'acctstarttime',
        'acctstoptime',
        'acctinputoctets',
        'acctoutputoctets',
        'calledstationid',
        'callingstationid',
        'framedipaddress'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT count(*)
            FROM   radius.radacct
            {wc}
        '''.format(
            wc=wc
        )
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  radacctid,
            		username,
            		nasipaddress,
            		nasporttype,
            		acctstarttime,
            		acctstoptime,
            		acctinputoctets,
            		acctoutputoctets,
            		calledstationid,
            		callingstationid,
            		framedipaddress
            from radius.radacct
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2022-12-03)
@allow_admin
def api_read_disconnection(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    username = request.POST.get('username')
    user_session = request.POST.get('session')
    connected_count = request.POST.get('connected')
    protocol = request.POST.get('protocol')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if number != '':
        wc += " and id = '{number}' ".format(number=number)
    if username != '':
        wc += " and username like '%{username}%' ".format(username=username)
    if user_session != '':
        wc += " and user_session = '{user_session}' ".format(user_session=user_session)
    if connected_count != '':
        wc += " and connected_count = '{connected_count}' ".format(connected_count=connected_count)
    if protocol != '':
        wc += " and protocol = '{protocol}' ".format(protocol=protocol)
    if start_time != '':
        wc += '''
            and disconnected_time >= '{start_time}'
        '''.format(start_time=start_time)
    if end_time != '':
        wc += '''
            and disconnected_time < '{end_time}'
        '''.format(end_time=end_time)
    
    print(wc)
    # order by 리스트
    column_name = [
        'id',
        'username',
        'user_session',
        'connected_count',
        'protocol',
        'disconnected_time'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT count(id)
            FROM   tbl_disconnection
            {wc}
        '''.format(
            wc=wc
        )
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
                    username,
                    user_session,
                    connected_count,
                    protocol,
                    disconnected_time,
                    old_ip,
                    new_ip
            from tbl_disconnection
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)

# (2023-05-03)
@allow_admin
def api_read_failed(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    username = request.POST.get('username')
    platform = request.POST.get('platform')
    app_version = request.POST.get('app_version')
    server_name = request.POST.get('server_name')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    server_domain = request.POST.get('server_domain')
    server_ip = request.POST.get('server_ip')
    user_ip = request.POST.get('user_ip')
    user_location = request.POST.get('user_location')
    server_protocol = request.POST.get('server_protocol')

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if number != '':
        wc += " and id = '{number}' ".format(number=number)
    if username != '':
        wc += " and username like '%{username}%' ".format(username=username)
    if platform != 'All':
        wc += " and platform = '{platform}' ".format(platform=platform)
    if server_protocol != 'All':
        wc += " and server_protocol = '{server_protocol}' ".format(server_protocol=server_protocol)
    if app_version != '':
        wc += " and app_version = '{app_version}' ".format(app_version=app_version)
    if server_name != '':
        wc += " and server_name like '{server_name}%' ".format(server_name=server_name)
    if server_domain != '':
        wc += " and server_domain like '{server_domain}%' ".format(server_domain=server_domain)
    if user_location != '':
        wc += " and user_location like '{user_location}%' ".format(user_location=user_location)
    if server_ip != '':
        wc += " and server_ip = '{server_ip}' ".format(server_ip=server_ip)
    if user_ip != '':
        wc += " and user_ip = '{user_ip}' ".format(user_ip=user_ip)
    if start_time != '':
        wc += '''
            and failed_time >= '{start_time}'
        '''.format(start_time=start_time)
    if end_time != '':
        wc += '''
            and failed_time < '{end_time}'
        '''.format(end_time=end_time)
    
    print(wc)
    # order by 리스트
    column_name = [
        'id',
        'username',
        'platform',
        'app_version',
        'server_name',
        'server_domain',
        'server_ip',
        'server_protocol',
        'failed_time'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT count(*)
            FROM   tbl_agent_failed
            {wc}
        '''.format(
            wc=wc
        )
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
            		username,
            		platform,
            		app_version,
            		server_name,
            		server_domain,
            		server_protocol,
            		user_ip,
            		user_location,
            		device_info,
            		failed_time
            from tbl_agent_failed
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2022-12-08)
@allow_admin
def api_read_reward(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    refferer_email = request.POST.get('refferer_email')
    register_email = request.POST.get('register_email')
    refferer_name = request.POST.get('refferer_name')
    register_name = request.POST.get('register_name')
    code = request.POST.get('code')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if number != '':
        wc += " and tr.id = '{number}' ".format(number=number)
    if refferer_email != '':
        wc += " and tx.email like '%{refferer_email}%' ".format(refferer_email=refferer_email)
    if register_email != '':
        wc += " and ty.email like '%{register_email}%'  ".format(register_email=register_email)
    if code != '':
        wc += " and tx.rec like '{code}%' ".format(code=code)
    if refferer_name != '':
        wc += " and tx.username like '{refferer_name}%' ".format(refferer_name=refferer_name)
    if register_name != '':
        wc += " and ty.username like '{register_name}%' ".format(register_name=register_name)
    if start_time != '':
        wc += '''
            and tr.register_date >= '{start_time}'
        '''.format(start_time=start_time)
    if end_time != '':
        wc += '''
            and tr.register_date < '{end_time}'
        '''.format(end_time=end_time)

    # order by 리스트
    column_name = [
        'tr.id',
        'tx.email',
        'tx.username',
        'tr.event_code',
        'ty.email',
        'ty.username',
        'tr.reward_days',
        'tr.type',
        'tr.register_date'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT count(*)
            FROM tbl_reward_log tr
            JOIN tbl_user tx ON tr.rewarder_id = tx.id
            JOIN tbl_user ty ON tr.registrant_id = ty.id
            {wc}
        '''.format(wc=wc)
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT tr.id, tx.rec, tx.email AS refferer_email, tx.username AS refferer_name, ty.email AS register_email, 
                   ty.username AS register_username, tr.reward_days, tr.register_date, tr.type, tr.event_code
            FROM tbl_reward_log tr
            LEFT JOIN tbl_user tx ON tr.rewarder_id = tx.id
            LEFT JOIN tbl_user ty ON tr.registrant_id = ty.id
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# 실시간 사용자 API
def api_realtime_user(request):
    with connections['default'].cursor() as cur:
        query = '''
            SELECT acctsessionid    AS sessionid,  
                acctuniqueid, 
                username            AS email, 
                nasipaddress        AS agent_ip,  
                DATE_FORMAT(acctstarttime, "%Y-%m-%d %H:%i:%S") as starttime,
                callingstationid    AS client_ip, 
                framedipaddress     AS private_ip,
                nasporttype       AS nas_type
            FROM   radius.radacct 
            WHERE  acctstoptime IS NULL; 
        '''.format()
        cur.execute(query)
        rows = dictfetchall(cur)
    return JsonResponse({'result': rows})

def realtime_user2(request):
    context = {}
    return render(request, 'chart/realtime_user2.html', context)


# 실시간 사용자 API
def api_realtime_user2(request):
    with connections['default'].cursor() as cur:
        query = '''
            SELECT acctsessionid    AS sessionid, acctuniqueid,
                username            AS email, 
                nasipaddress        AS agent_ip,  
                DATE_FORMAT(acctstarttime, "%Y-%m-%d %H:%i:%S") as starttime,
                callingstationid    AS client_ip, 
                framedipaddress     AS private_ip,
                nasporttype       AS nas_type
            FROM   radius.radacct 
            WHERE  acctstoptime IS NULL ORDER BY nasipaddress; 
        '''.format()
        cur.execute(query)
        rows = dictfetchall(cur)
    return JsonResponse({'result': rows})

def realtime_user3(request):
    context = {}
    return render(request, 'chart/realtime_user3.html', context)

def api_realtime_user3(request):
    with connections['default'].cursor() as cur:
        query = '''
            SELECT acctsessionid    AS sessionid, 
                username            AS email, 
                nasipaddress        AS agent_ip,  
                DATE_FORMAT(acctstarttime, "%Y-%m-%d %H:%i:%S") as starttime,
                callingstationid    AS client_ip, 
                framedipaddress     AS private_ip,
                nasporttype       AS nas_type
            FROM   radius.radacct 
            WHERE  acctstoptime IS NULL and nasipaddress='218.158.57.201'; 
        '''.format()
        cur.execute(query)
        rows = dictfetchall(cur)
    return JsonResponse({'result': rows})

# 트래픽 사용량 렌더
@allow_admin
def use_traffic(request):
    context = {}
    context['year_list'] = make_yaer_list()
    context['day_list'] = make_day_list()
    return render(request, 'chart/use_traffic.html', context)


# 트래픽 사용량 API
@allow_admin
def api_use_traffic(request):    
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))

    # 검색 필터 파라미터
    id = request.POST.get('id')
    year = request.POST.get('year')
    month = request.POST.get('month')
    day = request.POST.get('day')
    
    if len(month) == 1:
        month = '0' + month
    if len(day) == 1:
        day = '0' + day

    # 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT  username
            FROM radius.radacct
            where acctstarttime like  "{year}-{month}-{day}%" 
            group by username
        '''.format(year=year, month=month, day=day)
        cur.execute(query)
        rows = cur.fetchall()
        
        if len(rows) == 0 :
            total = 0
        else :
            total = rows[0][0]
        

    # 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT  username,
                    sum(acctoutputoctets)/1e+9 as acctoutputoctets,
                    sum(acctinputoctets)/1e+9 as acctinputoctets
            FROM radius.radacct 
            where acctstarttime like  "{year}-{month}-{day}%" 
            group by username
            order by acctoutputoctets desc
            limit {start}, 10
        '''.format(
            year=year, month=month, day=day,
            start=start)
        # print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = dictfetchall(cur)

    returnData = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(returnData)

# 트래픽 사용량 렌더
@allow_admin
def use_traffic_sum(request):
    context = {}
    context['year_list'] = make_yaer_list()
    context['day_list'] = make_day_list()
    return render(request, 'chart/use_traffic_sum.html', context)


# 트래픽 사용량 API
@allow_admin
def api_use_traffic_sum(request):
    year = request.POST.get('year')
    month = request.POST.get('month')
    day = request.POST.get('day')

    if len(month) == 1:
        month = '0' + month
    if len(day) == 1:
        day = '0' + day

    with connections['default'].cursor() as cur:
        query = '''
            SELECT  username,
                    sum(acctoutputoctets)/1e+9 as acctoutputoctets,
                    sum(acctinputoctets)/1e+9 as acctinputoctets
            FROM radius.radacct 
            where acctstarttime like  "{year}-{month}-{day}%" 
            group by username
            order by acctoutputoctets desc;
        '''.format(year=year, month=month, day=day)
        cur.execute(query)
        rows = dictfetchall(cur)

    return JsonResponse({'result': rows})

def use_traffic_monthsum(request):
    context = {}
    context['year_list'] = make_yaer_list()
#    context['day_list'] = make_day_list()
    return render(request, 'chart/use_traffic_monthsum.html', context)


# 트래픽 월별 사용량 API
@allow_admin
def api_use_traffic_monthsum(request):
    year = request.POST.get('year')
    month = request.POST.get('month')


    if len(month) == 1:
        month = '0' + month


    with connections['default'].cursor() as cur:
        query = '''
            SELECT  username,
                    sum(acctoutputoctets)/1e+9 as acctoutputoctets,
                    sum(acctinputoctets)/1e+9 as acctinputoctets
            FROM radius.radacct 
            where acctstarttime like  "{year}-{month}%" 
            group by username
            order by acctoutputoctets desc;
        '''.format(year=year, month=month)
        cur.execute(query)
        rows = dictfetchall(cur)

    return JsonResponse({'result': rows})

# 일별 통계 공통 렌더
@allow_dealer
def dd(request, type):
    title, desc, endpoint = make_html_title(type, 'dd')
    context = {}
    context['year_list'] = make_yaer_list()
    context['box_title'] = title
    context['box_desc'] = desc
    context['endpoint'] = endpoint
    context['type'] = type
    return render(request, 'chart/dd.html', context)


# 월별 통계 공통 렌더
@allow_dealer
def mm(request, type):
    title, desc, endpoint = make_html_title(type, 'mm')
    context = {}
    context['year_list'] = make_yaer_list()
    context['box_title'] = title
    context['box_desc'] = desc
    context['endpoint'] = endpoint
    context['type'] = type
    return render(request, 'chart/mm.html', context)


# 월별 통계 공통 렌더
@allow_dealer
def total(request, type):
    print('type = ', type)
    title, desc, endpoint = make_html_title(type, 'total')
    print('title = ', title)
    print('desc = ', desc)
    print('endpoint = ', endpoint)
    context = {}
    context['box_title'] = title
    context['box_desc'] = desc
    context['endpoint'] = endpoint
    context['type'] = type
    return render(request, 'chart/total.html', context)


# 일별 통계 공통 엔드포인트
@allow_dealer
def api_dd(request, type):
    rec = request.session['rec']
    year = int(request.POST.get('year'))
    month = int(request.POST.get('month'))
    x_axis = make_axisX_dd(year, month)

    # 분기 포인트
    if type == 'user':
        y_axis = [
            {
                'label': '가입자',
                'data': get_dd_regist(year, month, x_axis),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '활성화',
                'data': get_dd_active(year, month, x_axis),
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            }
        ]
    elif type == 'money':
        y_axis = [
            {
                'label': '무통장(krw)',
                'data': get_dd_send(year, month, x_axis),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(krw)',
                'data': get_dd_payment(year, month, x_axis, 'krw'),
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(usd)',
                'data': get_dd_payment(year, month, x_axis, 'usd'),
                'borderColor': LINE_COLOR_YELLOW,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(cny)',
                'data': get_dd_payment(year, month, x_axis, 'cny'),
                'borderColor': LINE_COLOR_PURPLE,
                'borderWidth': 1
            }
        ]  
    elif type == 'money_cnt':
        y_axis = [
            {
                'label': '결제건수 (수동)',
                'data': get_dd_send_cnt(year, month, x_axis),
                'borderColor': LINE_COLOR_PURPLE,
                'borderWidth': 1
            },
            {
                'label': '결제건수 (결제모듈)',
                'data': get_dd_payment_cnt(year, month, x_axis),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            }
        ]
    if type == 'saler_user':
        y_axis = [
            {
                'label': '가입자',
                'data': get_dd_regist(year, month, x_axis, 'saler', rec),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '활성화',
                'data': get_dd_active(year, month, x_axis, 'saler', rec),
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            }
        ]
    elif type == 'saler_money':
        y_axis = [
            {
                'label': '무통장(krw)',
                'data': get_dd_send(year, month, x_axis, 'saler', rec),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(krw)',
                'data': get_dd_payment(year, month, x_axis, 'krw', 'saler', rec),
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(usd)',
                'data': get_dd_payment(year, month, x_axis, 'usd', 'saler', rec),
                'borderColor': LINE_COLOR_YELLOW,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(cny)',
                'data': get_dd_payment(year, month, x_axis, 'cny', 'saler', rec),
                'borderColor': LINE_COLOR_PURPLE,
                'borderWidth': 1
            }
        ]  

    return JsonResponse({"x_axis": x_axis, "y_axis": y_axis})


# 월별 통계 공통 엔드포인트
@allow_dealer
def api_mm(request, type):
    year = int(request.POST.get('year'))

    # 분기 포인트
    if type == 'user':
        y_axis = [
            {
                'label': '가입자',
                'data': get_mm_regist(year),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '활성화',
                'data': get_mm_active(year),
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            }
        ]
    elif type == 'money':
        y_axis = [
            {
                'label': '무통장(krw)',
                'data': get_mm_send(year),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(krw)',
                'data': get_mm_payment(year)[0],
                'borderColor': LINE_COLOR_BLUE,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(usd)',
                'data': get_mm_payment(year)[1],
                'borderColor': LINE_COLOR_YELLOW,
                'borderWidth': 1
            },
            {
                'label': '결제모듈(cny)',
                'data': get_mm_payment(year)[2],
                'borderColor': LINE_COLOR_PURPLE,
                'borderWidth': 1
            }
        ]  
    elif type == 'money_cnt':
        y_axis = [
            {
                'label': '결제건수 (수동)',
                'data': get_mm_send_cnt(year),
                'borderColor': LINE_COLOR_PURPLE,
                'borderWidth': 1
            },
            {
                'label': '결제건수 (결제모듈)',
                'data': get_mm_payment_cnt(year),
                'borderColor': LINE_COLOR_RED,
                'borderWidth': 1
            }
        ]  
    return JsonResponse({"x_axis": make_axisX_mm(), "y_axis": y_axis})


# 전체 통계 공통 엔드포인트
@allow_dealer
def api_total(request, type):

    # 분기 포인트
    if type == 'rec':
        x_axis = get_total_rec()[0]
        y_axis = [
            {   
                'label': '추천인 보유수',
                'data': get_total_rec()[1],
                'borderColor': LINE_COLOR_PURPLE,
                'backgroundColor': BACK_COLOR_PURPLE,
                'borderWidth': 1,
                'barThickness': 20
            }
        ]
    elif type == 'nas':
        x_axis = get_total_nas('')[0]
        y_axis = [
            {   
                'label': 'IKEV2',
                'data': get_total_nas('IKEV2')[1],
                'borderColor': COLOR_BLUE,
                'backgroundColor': COLOR_BLUE,
                'borderWidth': 1,
                'barThickness': 10
            }, 
            {   
                'label': 'OpenVPN',
                'data': get_total_nas('OpenVPN')[1],
                'borderColor': COLOR_RED,
                'backgroundColor': COLOR_RED,
                'borderWidth': 1,
                'barThickness': 10
            }, 
            {   
                'label': 'SSTP',
                'data': get_total_nas('SSTP')[1],
                'borderColor': COLOR_YELLOW,
                'backgroundColor': COLOR_YELLOW,
                'borderWidth': 1,
                'barThickness': 10
            }, 
            {   
                'label': 'V2RAY',
                'data': get_total_nas('V2RAY')[1],
                'borderColor': COLOR_PURPLE,
                'backgroundColor': COLOR_PURPLE,
                'borderWidth': 1,
                'barThickness': 10
            }, 
        ]

    return JsonResponse({"x_axis": x_axis, "y_axis": y_axis})


# 코어 / 일별 / 추천인 랭킹
def get_total_rec():
    with connections['default'].cursor() as cur:
        query = '''
            select *
            from (
                select regist_rec, count(*) as cnt
                from tbl_user
                where LOWER(regist_rec) != 'kok'
                group by regist_rec
                union
                select regist_rec, count(*) as cnt
                from tbl_user
                where LOWER(regist_rec) = 'kok'
                and delete_yn = 'N'
                and is_active = 1
                group by regist_rec
            ) x
            where regist_rec != ''
            and cnt > 1
            order by cnt desc
            limit 20
        '''
        cur.execute(query)
        rows = dictfetchall(cur)
    x_axis = []
    y_axis = []
    for row in rows:
        x_axis.append(row['regist_rec'])
        y_axis.append(row['cnt'])
    return x_axis, y_axis

def get_total_nas(protocol):
    with connections['default'].cursor() as cur:
        subquery = ''
        if protocol == 'OpenVPN' :
            subquery = '''
                AND nasporttype = 'ISDN'
             '''
        elif protocol == 'SSTP' :
            subquery = '''
                AND nasporttype = 'Virtual' AND nasportid = 443
             '''    
        elif protocol == 'V2RAY' :
            subquery = '''
                AND nasporttype = 'V2RAY'
             '''  	    
        else :
           subquery = '''
                AND nasporttype = 'Virtual' AND nasportid != 443
             '''
        query = '''
                SELECT                                  
                        t1.hostdomain,
						t2.count
                        FROM titan.tbl_agent3 t1,
                        (SELECT t1.hostip,
                                Count(t2.nasipaddress) AS count
                            FROM titan.tbl_agent3 t1
                                LEFT JOIN (SELECT *
                                            FROM radius.radacct
                                            WHERE acctstoptime IS NULL {subquery}
                                            ) t2
                                        ON t1.hostip = t2.nasipaddress
                            WHERE is_active = 1
                                    AND is_status = 1
                            GROUP BY t1.hostip)t2
                    WHERE t1.hostip = t2.hostip
                    ORDER BY t1.telecom, t1.name
            '''.format(subquery=subquery)
        cur.execute(query)
        rows = dictfetchall(cur)
    x_axis = []
    y_axis = []
    for row in rows:
        x_axis.append(row['hostdomain'])
        y_axis.append(row['count'])
    return x_axis, y_axis

# 코어 / 일별 / 가입자
def get_dd_regist(year, month, x_axis, add_type='', rec=''):
    with connections['default'].cursor() as cur:
        if add_type == 'saler':
            add_query = "AND regist_rec = '{rec}'".format(rec=rec)
        else:
            add_query = ''
        query = '''
            SELECT day(regist_date), count(id) as value
            FROM tbl_user
            WHERE Month(regist_date) = {month} 
            AND date_format(regist_date, "%Y") = {year}
            {add_query}
            GROUP BY day(regist_date);
        '''.format(month=month, year=year, add_query=add_query)
        cur.execute(query)
        rows = cur.fetchall()
        regist = serialize_rows_dd(rows, x_axis)
    return regist


# 코어 / 일별 / 활성화
def get_dd_active(year, month, x_axis, add_type='', rec=''):
    with connections['default'].cursor() as cur:
        if add_type == 'saler':
            add_query = "AND regist_rec = '{rec}'".format(rec=rec)
        else:
            add_query = ''
        query = '''
            SELECT day(active_date), count(id) as value
            FROM tbl_user
            WHERE Month(active_date) = {month} 
            AND date_format(active_date, "%Y") = {year}
            {add_query}
            GROUP BY day(active_date);
        '''.format(month=month, year=year, add_query=add_query)
        cur.execute(query)
        rows = cur.fetchall()
        active = serialize_rows_dd(rows, x_axis)
    return active


# 코어 / 일별 / 무통장 건수
def get_dd_send_cnt(year, month, x_axis):
    with connections['default'].cursor() as cur:
        query = """
            SELECT DAY(x.accept_date) AS d, COUNT(*) AS value
            FROM tbl_send_history x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE x.status IN ('A','S')
              AND MONTH(x.accept_date) = %s
              AND YEAR(x.accept_date)  = %s
            GROUP BY DAY(x.accept_date)
            ORDER BY d
        """
        cur.execute(query, [month, year])  # ✅ 파라미터 바인딩
        rows = cur.fetchall()
        send = serialize_rows_dd(rows, x_axis)  # (day, value) -> x_axis 정렬
    return send


# 코어 / 일별 / 결제모듈 건수
def get_dd_payment_cnt(year, month, x_axis):
    with connections['default'].cursor() as cur:
        query = '''
            select day(x.regist_date), count(x.id) as value
            from tbl_price_history x
            join tbl_user y
            on x.user_id = y.id
            where refund_yn = 'N'
            and Month(x.regist_date) = {month} 
            and date_format(x.regist_date, "%Y") = {year}
            GROUP BY day(x.regist_date);
        '''.format(month=month, year=year)
        cur.execute(query)
        rows = cur.fetchall()
        send = serialize_rows_dd(rows, x_axis)
    return send


# 코어 / 일별 / 무통장
def get_dd_send(year, month, x_axis, add_type='', rec=''):
    with connections['default'].cursor() as cur:
        extra = ""
        params = [month, year]

        if add_type == 'saler' and rec:
            extra = "AND y.regist_rec = %s"
            params.append(rec)

        query = f"""
            SELECT DAY(x.accept_date) AS d, SUM(COALESCE(x.krw, 0)) AS value
            FROM tbl_send_history x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE x.status IN ('A','S')
              AND MONTH(x.accept_date) = %s 
              AND YEAR(x.accept_date)  = %s
              {extra}
            GROUP BY DAY(x.accept_date)
            ORDER BY d
        """
        cur.execute(query, params)
        rows = cur.fetchall()  # [(day, value), ...]
        send = serialize_rows_dd(rows, x_axis)
    return send



# 코어 / 일별 / 결제모듈(krw)
def get_dd_payment(year, month, x_axis, type, add_type='', rec=''):
    with connections['default'].cursor() as cur:
        if add_type == 'saler':
            add_query = "AND regist_rec = '{rec}'".format(rec=rec)
        else:
            add_query = ''
        query = '''
            select day(x.regist_date), ifnull(sum({type}), 0) as value
            from tbl_price_history x
            join tbl_user y
            on x.user_id = y.id
            where refund_yn = 'N'
            and Month(x.regist_date) = {month} 
            and date_format(x.regist_date, "%Y") = {year}
            {add_query}
            GROUP BY day(x.regist_date);
        '''.format(month=month, year=year, type=type, add_query=add_query)
        cur.execute(query)
        rows = cur.fetchall()
        print('-----------------------')
        print('type = ', type)
        for row in rows:
            print('row = ', row)
        print('-----------------------')
        payment = serialize_rows_dd(rows, x_axis)
    return payment


# 코어 / 월별 / 가입자
def get_mm_regist(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, cnt1
            from (
                select yyyy, mm, count(*) as cnt1
                from (
                    select  date_format(regist_date, "%Y") as yyyy, 
                            date_format(regist_date, "%m") as mm
                    from tbl_user
                ) x
                group by yyyy, mm
            ) y
            where y.yyyy = '{year}'
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
        regist = serialize_rows_mm(rows, 1)
    return regist


# 코어 / 월별 / 활성화
def get_mm_active(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, cnt1
            from (
                select yyyy, mm, count(*) as cnt1
                from (
                    select  date_format(active_date, "%Y") as yyyy, 
                            date_format(active_date, "%m") as mm
                    from tbl_user
                ) x
                group by yyyy, mm
            ) y
            where y.yyyy = '{year}'
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
        active = serialize_rows_mm(rows, 1)
    return active


# 코어 / 월별 / 무통장
def get_mm_send(year: int):
    start = date(year, 1, 1)
    end   = date(year + 1, 1, 1)

    with connections['default'].cursor() as cur:
        query = """
            SELECT
                MONTH(accept_date) AS mm,                  -- 1~12 (int)
                SUM(COALESCE(krw, 0)) AS cnt1
            FROM tbl_send_history
            WHERE status IN ('A', 'S')
              AND accept_date >= %s AND accept_date < %s
            GROUP BY MONTH(accept_date)
            ORDER BY mm
        """
        cur.execute(query, [start, end])
        rows = dictfetchall(cur)           # [{'mm':1,'cnt1':...}, ...]
        # ✅ serializer가 '01'~'12'를 기대한다면 아래 변환
        rows = [{'mm': f'{r["mm"]:02d}', 'cnt1': r['cnt1']} for r in rows]
        send = serialize_rows_mm(rows, 1)
    return send

# 코어 / 월별 / 결제모듈
def get_mm_payment(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, 
                    ifnull(sum(krw), 0) as cnt1, 
                    ifnull(sum(usd), 0) as cnt2, 
                    ifnull(sum(cny), 0) as cnt3
            from (
                select  date_format(regist_date, "%Y") as yyyy, 
                        date_format(regist_date, "%m") as mm, 
                        krw,
                        usd,
                        cny
                from tbl_price_history
                where refund_yn = 'N'
            ) x
            where x.yyyy = '{year}'
            group by mm;
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
        krw, usd, cny = serialize_rows_mm(rows, 3)
    return krw, usd, cny


# 코어 / 월별 / 무통장 건수
def get_mm_send_cnt(year: int):
    start = date(year, 1, 1)
    end   = date(year + 1, 1, 1)

    with connections['default'].cursor() as cur:
        query = """
            SELECT
                MONTH(accept_date) AS mm,
                COUNT(*)           AS cnt1
            FROM tbl_send_history
            WHERE status IN ('A','S')
              AND accept_date >= %s AND accept_date < %s
            GROUP BY MONTH(accept_date)
            ORDER BY mm
        """
        cur.execute(query, [start, end])   # ✅ 파라미터 바인딩
        rows = dictfetchall(cur)           # [{'mm':1,'cnt1':...}, ...]
        send = serialize_rows_mm(rows, 1)  # 기존 함수와 호환
    return send



# 코어 / 월별 / 결제모듈 건수
def get_mm_payment_cnt(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, count(*) as cnt1
            from (
                select  date_format(regist_date, "%Y") as yyyy, 
                        date_format(regist_date, "%m") as mm, 
                        krw,
                        usd,
                        cny
                from tbl_price_history
                where refund_yn = 'N'
            ) x
            where x.yyyy = '{year}'
            group by mm;
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
        ret = serialize_rows_mm(rows, 1)
    return ret

# Set current time to acctstoptime
@allow_admin
def api_update_status(request):
    acctuniqueid = request.POST.get('acctuniqueid')
    with connections['default'].cursor() as cur:
        query = '''
            UPDATE radius.radacct set acctstoptime = '{date}' where acctuniqueid = '{acctuniqueid}';
                    COMMIT;
                '''.format(date = datetime.datetime.now() , acctuniqueid = acctuniqueid)
        cur.execute(query)
    return JsonResponse({'result': 200, 'title': 'Success', 'text': 'Set successfully'})


# Force Disconnect
@allow_admin
def api_user_disconnect(request):
    acctuniqueid = request.POST.get('acctuniqueid')
    print('acctuniqueid => ', acctuniqueid)
    with connections['default'].cursor() as cur:
        sql = '''
        SELECT acctsessionid, nasportid, nasipaddress, nasporttype, username FROM radius.radacct where acctuniqueid = '{acctuniqueid}';
        '''.format(acctuniqueid = acctuniqueid)
        cur.execute(sql)
        rows = dictfetchall(cur)
        nasportid = rows[0]['nasportid']
        nasipaddress = rows[0]['nasipaddress']
        nasporttype = rows[0]['nasporttype']
        sessionid = rows[0]['acctsessionid']
        id = rows[0]['username']
        print('acctsessionid => ', sessionid)
        print('nasporttype => ', nasporttype)
        print('nasportid => ', nasportid)
        print('nasipaddress => ', nasipaddress)
# 서버 접속정보 가져오기
        sql = '''
        SELECT username,password FROM titan.tbl_agent3 WHERE hostip='{ip}' or hostdomain='{ip}';
        '''.format(ip=nasipaddress)
        cur.execute(sql)
        ssh_info_rows = dictfetchall(cur)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #print('username => ', ssh_info_rows[0]['username'])
        #print('password => ', ssh_info_rows[0]['password'])
        try:
            # timeout 1초
            ssh.connect(nasipaddress,
                        username=ssh_info_rows[0]['username'],
                        password=ssh_info_rows[0]['password'],
                        timeout = 1)
            
            if nasporttype == 'ISDN' : # openvpn
                print('INFO -> Openvpn Server telnet login:' + id)
                channel = ssh.invoke_shell()
                channel.send("telnet 127.0.0.1 1199\n")
                time.sleep(0.5)
                channel.send("mykakao9898\n")
                time.sleep(0.2)
                command = 'kill '+id+'\n'
                channel.send(command)
                time.sleep(0.2)
                channel.send("exit\n")
                time.sleep(0.2)
                channel.send("exit\n")
                time.sleep(0.2)
                output = channel.recv(65535).decode("utf-8")
                print(output)
            elif nasportid == '443' : # softether sstp
                print('INFO -> SSTP Force Stop:' + id)
                sessionid = sessionid.replace('=5BSSTP=5D','[SSTP]')
                command = "/usr/local/vpnserver/vpncmd "+nasipaddress+" /SERVER /HUB:"+settings.SOFTETHER_HUB+" /PASSWORD:'"+settings.SOFTETHER_PASS+"' /CMD SessionDisconnect "+sessionid
                print('cmd => ',command)
                ssh.exec_command(command)
            elif nasporttype == 'V2RAY' : # V2RAY
                print('INFO -> V2RAY Force Stop:' + id)
            else :
                print('INFO -> IKEV2 Force Stop:' + id)
                command = 'strongswan statusall | grep '+id
                stdin, stdout, stderr = ssh.exec_command(command)
                sa = stdout.read().decode("utf-8").split('\n')[0].split(':')[0].strip()

                command = 'strongswan stroke down-nb '+sa
                print('cmd => ',command)
                # strongswan 종료시에 alive packet 을 5번 보냄 같은 명령어 두번쓰면 바로 강제종료함.
                ssh.exec_command(command)
                ssh.exec_command(command)
            sql = '''
                UPDATE radius.radacct set acctstoptime = '{date}' where acctuniqueid = '{acctuniqueid}';
                COMMIT;
            '''.format(date = datetime.datetime.now() , acctuniqueid = acctuniqueid)
            cur.execute(sql)
        except socket.timeout:
            #timeout 걸렸을때 radius 강제 업데이트
            sql = '''
                UPDATE radius.radacct set acctstoptime = '{date}' where acctuniqueid = '{acctuniqueid}';
                COMMIT;
            '''.format(date = datetime.datetime.now() , acctuniqueid = acctuniqueid)
            cur.execute(sql)
        except BaseException as err:
            print('ERROR -> err : ', err)
            return JsonResponse({'result': 600, 'title': 'Failed', 'text': 'Exception happened'})
                    
        finally:
            ssh.close()
    
    return JsonResponse({'result': 200, 'title': 'Success', 'text': 'Set successfully'})
