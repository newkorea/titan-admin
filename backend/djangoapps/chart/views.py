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


# 일일 통계 (가입계정 및 활성계정) (2020-03-27)
def dd_user(request):
    year_list = []
    this_year = datetime.datetime.now().year
    for years in range(2019, this_year + 1):
      year_list.append(years)
    context = {}
    context['year_list'] = year_list
    return render(request, 'chart/dd_user.html', context)


# 월별 통계 (가입계정 및 활성계정) (2020-03-27)
def mm_user(request):
    return render(request, 'chart/mm_user.html')


# 일일 통계 (가입계정 및 활성계정) 데이터 반환 함수 (2020-03-27)
def api_read_dd_user_chart(request):

    # 특정 달의 마지막 일을 가져온다
    year = int(request.POST.get('year'))
    month = int(request.POST.get('month'))
    days = monthrange(year, month)[1]

    list_day = []
    regist = []
    active = []

    # y축 생성 / x축 초기화
    for day in range(1, days+1):
        day = str(day) + "일"
        list_day.append(day)
        regist.append(0)
        active.append(0)

    # y축 - 가입자 수
    with connections['default'].cursor() as cur:
        query = '''
            SELECT day(regist_date), count(id) as value
            FROM tbl_user
            WHERE Month(regist_date) = {month} and date_format(regist_date, "%Y") = {year}
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
            WHERE Month(active_date) = {month} and date_format(active_date, "%Y") = {year}
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
    return JsonResponse({"x_axis": list_day, "y_axis": y_axis})