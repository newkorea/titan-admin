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
    this_year = datetime.datetime.now().year
    year_list = []
    with connections['default'].cursor() as cur:
        query = '''
        select min(date_format(regist_date, "%Y")) as first_year from tbl_user;
        '''.format()
        cur.execute(query)
        rows = cur.fetchall()
    first_year = int(rows[0][0])

    for years in range(first_year, this_year+1):
      year_list.append(years)
    context = {}
    context['year_list'] = year_list

    print(year_list)
    

    return render(request, 'chart/dd_user.html', context)



# 월별 통계 (가입계정 및 활성계정) (2020-03-27)
def mm_user(request):
    return render(request, 'chart/mm_user.html')

# 일일 통계 (가입계정 및 활성계정) 데이터 반환 함수 (2020-03-27)
def api_read_dd_user_chart(request):
    filter_datas = request.POST.getlist("filter_datas[]")

    # print("filter data=> ", filter_datas)

    # 특정 달의 마지막 일을 가져온다.
    year = int(filter_datas[0])
    month = int(filter_datas[1])
    days = monthrange(year, month)[1]

    list_day = []
    list_value = []

    # list_day에 1부터 마지막 일까지 리스트로 만들고 list_value엔 0값을 삽입하여 리스트의 길이를 맞게 설정한다.
    for day in range(1, days+1):
        day = str(day) + "일"
        list_day.append(day)
        list_value.append(0)
    # print("list_day=> ", list_day)
    # print("list_value=> ", list_value)


    # 특정 일의 가입된 사용자의 수를 가져오는 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT date_format(regist_date, "%e") as day, count(id) as value
            FROM tbl_user
            WHERE Month(regist_date) = {month} and date_format(regist_date, "%Y") = {year}
            GROUP BY day(regist_date);
        '''.format(
              month=month,
              year=year
            )
        # print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = cur.fetchall()
        # print('DEBUG -> rows : ', rows)
    
    # 위 쿼리로 가져온 데이터를 list_value의 순서에 맞게 데이터 삽입
    for row in rows:
        list_value[int(row[0])-1] = row[1]

    return JsonResponse({"x_axis":list_day, "y_axis":list_value})