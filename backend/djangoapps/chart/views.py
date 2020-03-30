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


# 검색필터 생성 [ 2019 ~ 현재 yyyy ]
def make_yaer_list():
    year_list = []
    this_year = datetime.datetime.now().year
    for years in range(2019, this_year + 1):
      year_list.append(years)
    return year_list


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


# y축 리스트 시리얼라이즈
def serialize_rows(rows):
    y_axis = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    for row in rows:
        if row['mm'] == '01':
            y_axis[0] = row['cnt']
        if row['mm'] == '02':
            y_axis[1] = row['cnt']
        if row['mm'] == '03':
            y_axis[2] = row['cnt']
        if row['mm'] == '04':
            y_axis[3] = row['cnt']
        if row['mm'] == '05':
            y_axis[4] = row['cnt']
        if row['mm'] == '06':
            y_axis[5] = row['cnt']
        if row['mm'] == '07':
            y_axis[6] = row['cnt']
        if row['mm'] == '08':
            y_axis[7] = row['cnt']
        if row['mm'] == '09':
            y_axis[8] = row['cnt']
        if row['mm'] == '10':
            y_axis[9] = row['cnt']
        if row['mm'] == '11':
            y_axis[10] = row['cnt']
        if row['mm'] == '12':
            y_axis[11] = row['cnt']
    return y_axis


# 일일 통계 (가입계정 및 활성계정) 렌더 (2020-03-27)
def dd_user(request):
    context = {}
    context['year_list'] = make_yaer_list()
    return render(request, 'chart/dd_user.html', context)


# 월별 통계 (가입계정 및 활성계정) 렌더 (2020-03-27)
def mm_user(request):
    context = {}
    context['year_list'] = make_yaer_list()
    return render(request, 'chart/mm_user.html', context)


# 일일 통계 (가입계정 및 활성계정) 데이터 반환 (2020-03-27)
def api_read_dd_user_chart(request):
    # 입력 파라미터
    year = int(request.POST.get('year'))
    month = int(request.POST.get('month'))

    # 초기화
    x_axis = make_axisX_dd(year, month)
    regist = []
    active = []

    # y축 생성 / x축 초기화
    for n in x_axis:
        regist.append(0)
        active.append(0)

    # y축 - 가입자 수
    with connections['default'].cursor() as cur:
        query = '''
            SELECT day(regist_date), count(id) as value
            FROM tbl_user
            WHERE Month(regist_date) = {month} 
            AND date_format(regist_date, "%Y") = {year}
            GROUP BY day(regist_date);
        '''.format(
              month=month,
              year=year
            )
        cur.execute(query)
        rows = cur.fetchall()
        for row in rows:
            regist[int(row[0])-1] = row[1]

    # y축 - 활성화 수
    with connections['default'].cursor() as cur:
        query = '''
            SELECT day(active_date), count(id) as value
            FROM tbl_user
            WHERE Month(active_date) = {month} 
            AND date_format(active_date, "%Y") = {year}
            GROUP BY day(active_date);
        '''.format(
              month=month,
              year=year
            )
        cur.execute(query)
        rows = cur.fetchall()
        for row in rows:
            active[int(row[0])-1] = row[1]

    y_axis = {
        'regist': regist,
        'active': active
    }
    return JsonResponse({"x_axis": x_axis, "y_axis": y_axis})


# 일일 통계 (가입계정 및 활성계정) 데이터 반환 (2020-03-30)
def api_read_mm_user_chart(request):
    # 입력 파라미터
    year = int(request.POST.get('year'))

    with connections['default'].cursor() as cur:
        query = '''
            select *
            from (
                select yyyy, mm, count(*) as cnt
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
        regist = serialize_rows(rows)

        query = '''
            select *
            from (
                select yyyy, mm, count(*) as cnt
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
        active = serialize_rows(rows)

    y_axis = {
        'regist': regist,
        'active': active
    }
    return JsonResponse({"x_axis": make_axisX_mm(), "y_axis": y_axis})