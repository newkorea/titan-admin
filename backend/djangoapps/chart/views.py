import json
import datetime
import smtplib
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
    endpoint = '/api/v1/read/{main}/{type}'.format(type=type, main=main)
    return title, desc, endpoint


# 실시간 사용자 렌더
def realtime_user(request):
    context = {}
    return render(request, 'chart/realtime_user.html', context)


# 실시간 사용자 API
def api_realtime_user(request):
    with connections['default'].cursor() as cur:
        query = '''
            SELECT acctsessionid    AS sessionid, 
                username            AS email, 
                nasipaddress        AS agent_ip,  
                DATE_FORMAT(acctstarttime, "%Y-%m-%d %H:%i:%S") as starttime,
                callingstationid    AS client_ip, 
                framedipaddress     AS private_ip 
            FROM   radius.radacct 
            WHERE  acctstoptime IS NULL; 
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
                    DATE_FORMAT(acctstarttime, "%Y-%m-%d %H:%i:%S") as acctstarttime,
                    DATE_FORMAT(acctstoptime, "%Y-%m-%d %H:%i:%S") as acctstoptime,
                    nasipaddress,
                    callingstationid,
                    acctoutputoctets/1e+9 as acctoutputoctets
            FROM radius.radacct 
            where acctstarttime like  "{year}-{month}-{day}%" 
            order by acctoutputoctets desc;
        '''.format(year=year, month=month, day=day)
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
        query = '''
            select day(x.accept_date), count(x.id) as value
            from tbl_send_history x
            join tbl_user y
            on x.user_id = y.id
            where status = 'A'
            and Month(x.accept_date) = {month} 
            and date_format(x.accept_date, "%Y") = {year}
            GROUP BY day(x.accept_date);
        '''.format(month=month, year=year)
        cur.execute(query)
        rows = cur.fetchall()
        send = serialize_rows_dd(rows, x_axis)
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
        if add_type == 'saler':
            add_query = "AND regist_rec = '{rec}'".format(rec=rec)
        else:
            add_query = ''
        query = '''
            select day(x.accept_date), sum(krw) as value
            from tbl_send_history x
            join tbl_user y
            on x.user_id = y.id
            where status = 'A'
            and Month(x.accept_date) = {month} 
            and date_format(x.accept_date, "%Y") = {year}
            {add_query}
            GROUP BY day(x.accept_date);
        '''.format(month=month, year=year, add_query=add_query)
        cur.execute(query)
        rows = cur.fetchall()
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
def get_mm_send(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, 
                    sum(krw) as cnt1
            from (
                select  date_format(accept_date, "%Y") as yyyy, 
                        date_format(accept_date, "%m") as mm, 
                        krw
                from tbl_send_history
                where status = 'A'
            ) x
            where x.yyyy = '{year}'
            group by mm;
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
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
def get_mm_send_cnt(year):
    with connections['default'].cursor() as cur:
        query = '''
            select  mm, 
                    count(krw) as cnt1
            from (
                select  date_format(accept_date, "%Y") as yyyy, 
                        date_format(accept_date, "%m") as mm, 
                        krw
                from tbl_send_history
                where status = 'A'
            ) x
            where x.yyyy = '{year}'
            group by mm;
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)
        send = serialize_rows_mm(rows, 1)
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