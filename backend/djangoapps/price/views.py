import json
import datetime
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
from backend.djangoapps.common.views import *

from django.utils import translation


def price(request):


    return render(request, 'price/admin_price.html')


def api_price_read(request):
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    id = request.POST.get('id')
    email = request.POST.get('email')
    username = request.POST.get('username')
    gender = request.POST.get('gender')
    delete = request.POST.get('delete')
    black = request.POST.get('black')
    active = request.POST.get('active')
    staff = request.POST.get('staff')

    column_name = ['id', 'email', 'username', 'gender', 'birth_date', 'sns', 'phone', 'delete_yn', 'black_yn', 'is_active','is_staff']

    # search
    print('start -> ', start)
    print('length -> ', length)
    print('draw -> ', draw)
    print('orderby_col -> ', orderby_col)
    print('orderby_opt -> ', orderby_opt)

    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from (
            	select @rnum := @rnum + 1 AS rnum, x.*
            	from (
                    select  x.id,
                            x.tid,
                            x.pgcode,
                            x.product_name,
                            x.amount,
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
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format()

        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]

    print('---------------------------------')
    print("total -> ", total)
    print('---------------------------------')


    with connections['default'].cursor() as cur:
        query = '''
                select  id,
                        tid,
                        pgcode,
                        product_name,
                        amount,
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
                            x.amount,
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
                    order by {orderby_col} {orderby_opt}
                    ) x
                    JOIN ( SELECT @rnum := -1 ) AS r
                ) t1
                where t1.rnum BETWEEN {start} AND {end};
        '''.format(
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            end=start+length-1
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    print('---------------------------------')
    for r in rows:
        print(r)
    print('---------------------------------')

    test = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(test)
