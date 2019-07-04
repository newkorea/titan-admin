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


def dealer(request):

    id = request.session['id']
    u1 = TblUser.objects.get(id=id)
    rec = u1.rec # 본인 추천인코드

    context = {}
    context['rec'] = rec
    return render(request, 'dealer/admin_dealer.html', context)


def api_dealer_read(request):

    year = request.POST.get('year')

    with connections['default'].cursor() as cur:
        query = '''
            select *
            from (
                select
                    DATE_FORMAT(regist_date, "%Y") as year,
                    CAST(DATE_FORMAT(regist_date, "%c") as UNSIGNED) as month,
                    sum(amount) as amount
                from tbl_price_history x
                group by year, month
            ) x
            where x.year = '{year}'
            order by month desc;
        '''.format(year=year)
        cur.execute(query)
        rows = dictfetchall(cur)

        query = '''
            select sum(amount)
            from (
                select
                    DATE_FORMAT(regist_date, "%Y") as year,
                    CAST(DATE_FORMAT(regist_date, "%c") as UNSIGNED) as month,
                    sum(amount) as amount
                from tbl_price_history x
                group by year, month
            ) x
            where x.year = '{year}'
            order by month desc;
        '''.format(year=year)
        cur.execute(query)
        sum_amount = cur.fetchall()[0][0]

    return JsonResponse({'result': rows, 'sum_amount': sum_amount})
