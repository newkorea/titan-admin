import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from datetime import datetime, timedelta


# 대쉬보드 렌더링 (2019.09.15 11:11 점검완료)
@allow_admin
def dashboard(request):
    now_year = datetime.today().year
    now_month = datetime.today().month
    now_day = datetime.today().day
    now = datetime.now().strftime('%Y-%m-%d')

    with connections['default'].cursor() as cur:
        query = '''
            select
            count(if(date(regist_date) = date(now()), regist_date, null)) as regist_today,
            count(if(is_staff = '0', is_staff, null)) as user_count,
            count(if(is_staff = '1', is_staff, null)) as admin_count,
            count(if(is_staff = '2', is_staff, null)) as cs_count,
            count(if(is_staff = '3', is_staff, null)) as chongpan_count,
            count(if(is_active = '1', is_active, null)) as active_count,
            count(if(is_active = '0', is_active, null)) as deactive_count,
            count(if(delete_yn = 'Y', delete_yn, null)) as delete_count,
            count(if(black_yn = 'Y', black_yn, null)) as black_count,
            count(if(gender = 'm', gender, null)) as men,
            count(if(gender = 'f', gender, null)) as female,
            (select count(*) from tbl_user_login where date(login_date) = date(now())) as login_today,
            (select sum(krw) from tbl_price_history where refund_yn = 'N' and date(regist_date) = date(now())) as today_profit,
            (select sum(krw) from tbl_price_history where refund_yn = 'Y' and date(refund_date) = date(now())) as today_refund,
            (select sum(usd) from tbl_price_history where refund_yn = 'N' and date(regist_date) = date(now())) as today_profit_usd,
            (select sum(usd) from tbl_price_history where refund_yn = 'Y' and date(refund_date) = date(now())) as today_refund_usd
            from tbl_user;
        '''.format(now = now)
        cur.execute(query)
        rows = cur.fetchall()

        regist_today = rows[0][0]
        user_count = rows[0][1]
        admin_count = rows[0][2]
        cs_count = rows[0][3]
        chongpan_count = rows[0][4]
        active_count = rows[0][5]
        deactive_count = rows[0][6]
        delete_count = rows[0][7]
        black_count = rows[0][8]
        men = rows[0][9]
        female = rows[0][10]
        login_today = rows[0][11]
        try:
            profit = rows[0][12]
            if profit == None:
                profile = 0
        except BaseException as err:
            print('ERROR -> err : ', err)
            profit = 0
        try:
            refund = rows[0][13]
            if refund == None:
                refund = 0
        except BaseException as err:
            print('ERROR -> err : ', err)
            refund = 0
        try:
            profit_usd = rows[0][14]
            if profit_usd == None:
                profit_usd = 0
        except BaseException as err:
            print('ERROR -> err : ', err)
            profit_usd = 0
        try:
            refund_usd = rows[0][15]
            if refund_usd == None:
                refund_usd = 0
        except BaseException as err:
            print('ERROR -> err : ', err)
            refund_usd = 0

    with connections['default'].cursor() as cur:
        query = '''
                select
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 10 and 19 , 1, 0)) as age_10,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 20 and 29 , 1, 0)) as age_20,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 30 and 39 , 1, 0)) as age_30,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 40 and 49 , 1, 0)) as age_40,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 50 and 59 , 1, 0)) as age_50,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 60 and 69 , 1, 0)) as age_60,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 70 and 79 , 1, 0)) as age_70,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 80 and 89 , 1, 0)) as age_80,
                sum(if(date_format(now(),'%Y')-substring(birth_date,1,4) between 90 and 110 , 1, 0)) as etc
                from tbl_user;ㅅ
        '''.format(now = now)
        cur.execute(query)
        rows = cur.fetchall()
        ages = [ str(rows[0][0]), str(rows[0][1]), str(rows[0][2]), str(rows[0][3]), str(rows[0][4]), str(rows[0][5]), str(rows[0][6]), str(rows[0][7]), str(rows[0][8]),  ]

    gender_list = []
    gender_list.append(men)
    gender_list.append(female)

    context = {
        'regist_today': regist_today,
        'login_today': login_today,
        'profit': profit,
        'refund': refund,
        'profit_usd': profit_usd,
        'refund_usd': refund_usd,
        'user_count': user_count,
        'admin_count': admin_count,
        'cs_count': cs_count,
        'chongpan_count': chongpan_count,
        'active_count': active_count,
        'deactive_count': deactive_count,
        'delete_count': delete_count,
        'black_count': black_count,
        'men': men,
        'female': female,
        'ages': ages
    }
    return render(request, 'dashboard/dashboard.html', context)
