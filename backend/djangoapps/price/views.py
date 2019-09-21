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
from django.utils import translation


# 결제관리 페이지 렌더링 (2019.09.21 13:56 점검완료)
def price(request):
    return render(request, 'price/admin_price.html')


# 결제관리 데이터 로드 (2019.09.21 13:56 점검완료)
def api_price_read(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    email = request.POST.get('email')
    session = request.POST.get('session')
    month = request.POST.get('month')
    refund = request.POST.get('refund')
    regist_start = request.POST.get('regist_start')
    regist_end = request.POST.get('regist_end')

    # 로깅 (datatables 기본 파라미터)
    print('DEBUG -> start : ', start)
    print('DEBUG -> length : ', length)
    print('DEBUG -> draw : ', draw)
    print('DEBUG -> orderby_col : ', orderby_col)
    print('DEBUG -> orderby_opt : ', orderby_opt)

    # 로깅 (검색필터 파라미터)
    print('DEBUG -> email : ', email)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month : ', month)
    print('DEBUG -> refund : ', refund)
    print('DEBUG -> regist_start : ', regist_start)
    print('DEBUG -> regist_end : ', regist_end)

    # where 절 필터링 생성
    filter = ' where 1=1 '
    if email != '':
        filter += " and y.email = '{email}' ".format(email=email)
    if session != '0':
        filter += " and x.session = '{session}' ".format(session=session)
    if month != '0':
        filter += " and x.month_type = '{month}' ".format(month=month)
    if refund != '0':
        filter += " and x.refund_yn = '{refund}' ".format(refund=refund)
    filter += '''
        and x.regist_date >= '{regist_start} 00:00:00'
        and x.regist_date < '{regist_end} 00:00:00'
    '''.format(regist_start=regist_start, regist_end=regist_end)

    # order by 리스트
    column_name = [
        'x.id',
        'x.tid',
        'x.pgcode',
        'x.product_name',
        'x.amount',
        'x.taxfree_amount',
        'x.tax_amount',
        'y.email',
        'x.autopay_flag',
        'x.refund_yn',
        'x.regist_date',
        'x.refund_date',
        'x.auto_end_date'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from (
            	select @rnum := @rnum + 1 AS rnum, x.*
            	from (
                    select  x.id
                    from tbl_price_history x
                    join tbl_user y
                    on x.user_id = y.id
                    {filter}
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format(filter=filter)
        print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
    print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
                select  id,
                        tid,
                        pgcode,
                        product_name,
                        krw,
                        usd,
                        taxfree_amount,
                        tax_amount,
                        email,
                        autopay_flag,
                        refund_yn,
                        DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i:%S") as regist_date,
                        DATE_FORMAT(refund_date, "%Y-%m-%d %H:%i:%S") as refund_date,
                        auto_end_date
                from (
                    select @rnum := @rnum + 1 AS rnum, x.*
                    from (
                    select  x.id,
                            x.tid,
                            x.pgcode,
                            x.product_name,
                            x.krw as krw,
                            x.usd as usd,
                            x.taxfree_amount,
                            x.tax_amount,
                            y.email,
                            x.autopay_flag,
                            x.refund_yn,
                            x.regist_date,
                            x.refund_date,
                            x.auto_end_date
                    from tbl_price_history x
                    join tbl_user y
                    on x.user_id = y.id
                    {filter}
                    order by {orderby_col} {orderby_opt}
                    ) x
                    JOIN ( SELECT @rnum := -1 ) AS r
                ) t1
                where t1.rnum BETWEEN {start} AND {end};
        '''.format(
            filter=filter,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            end=start+length-1
        )
        print(query)
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(ret)
