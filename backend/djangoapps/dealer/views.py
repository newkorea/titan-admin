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


# 총판관리 -> 수익관리 페이지 렌더링 (2019.10.19 10:56 점검완료)
@allow_dealer
def dealer(request):
    id = request.session['id']
    u1 = TblUser.objects.get(id=id)
    myRec = u1.rec    # 로그인 된 사용자의 추천코드

    startYear = 2019
    currentYear = int(datetime.datetime.today().strftime('%Y'))

    searchYear = []
    for n in range(startYear, currentYear+1):
        searchYear.append(n)

    context = {}
    context['rec'] = myRec
    context['searchYear'] = searchYear
    return render(request, 'dealer/admin_dealer.html', context)


# 총판관리 -> 회원관리 페이지 렌더링 (2019.10.19 10:56 점검완료)
@allow_dealer
def dealer_user(request):
    id = request.session['id']
    u1 = TblUser.objects.get(id=id)
    myRec = u1.rec  # 로그인 된 사용자의 추천코드

    users = TblUser.objects.filter(regist_rec=myRec)

    dumps = []
    cnt = 1
    for user in users:
        dump = {
            'seq': cnt,
            'email': user.email,
            'username': user.username,
            'regist_rec': user.regist_rec,
            'regist_date': user.regist_date,
        }
        cnt += 1
        dumps.append(dump)

    context = {}
    context['dumps'] = dumps
    return render(request, 'dealer/admin_dealer_user.html', context)


# 수익관리 데이터 로드 API (2019.09.21 13:55 개발필요)
@allow_dealer
def api_dealer_read(request):

    id = request.session['id']
    u1 = TblUser.objects.get(id=id)
    myRec = u1.rec  # 로그인 된 사용자의 추천코드

    year = request.POST.get('year')
    with connections['default'].cursor() as cur:
        query = '''
            select t1.year, t1.month, t1.amount_krw, t1.amount_usd, t1.amount_cny, t2.amount_free
            from (
            	select year, month, amount_krw, amount_usd, amount_cny
            	from (
            		select
            			DATE_FORMAT(x.regist_date, "%Y") as 'year',
            			CAST(DATE_FORMAT(x.regist_date, "%c") as UNSIGNED) as 'month',
            			sum(krw) as 'amount_krw',
            			sum(usd) as 'amount_usd',
            			sum(cny) as 'amount_cny'
            		from tbl_price_history x
            		join tbl_user y
            		on x.user_id = y.id
            		where y.rec = '{myRec}'
            		and refund_yn = 'N'
            		group by year, month
            	) x
            	where x.year = '{year}'
            	order by month desc
            ) t1
            join (
            	select year, month, amount_free
            	from (
            		select  DATE_FORMAT(x.accept_date, "%Y") as year,
            				CAST(DATE_FORMAT(x.regist_date, "%c") as UNSIGNED) as 'month',
            				IFNULL(sum(krw), 0) as amount_free
            		from tbl_send_history x
            		join tbl_user y
            		on x.user_id = y.id
            		where y.rec = '{myRec}'
            		and x.status = 'A'
            		group by year
            	) x
            	where x.year = '{year}'
            ) t2
            on t1.year = t2.year
            and t1.month = t2.month;
        '''.format(year=year, myRec=myRec)
        cur.execute(query)
        rows = dictfetchall(cur)

        query = '''
            select IFNULL(amount_krw, 0) as amount_krw,
            	   IFNULL(amount_usd, 0) as amount_usd,
            	   IFNULL(amount_cny, 0) as amount_cny
            from (
            	select DATE_FORMAT(x.regist_date, "%Y") as year,
            			CAST(DATE_FORMAT(x.regist_date, "%c") as UNSIGNED) as month,
            			sum(krw) as 'amount_krw',
            			sum(usd) as 'amount_usd',
            			sum(cny) as 'amount_cny'
            	from tbl_price_history x
            	join tbl_user y
            	on x.user_id = y.id
            	where y.rec = '{myRec}'
                and refund_yn = 'N'
            	group by year, month
            ) x
            where x.year = '{year}'
            order by month desc;
        '''.format(year=year, myRec=myRec)
        cur.execute(query)
        sums = cur.fetchall()

        query = '''
            select IFNULL(amount_free, 0) as amount_free
            from (
            	select DATE_FORMAT(x.accept_date, "%Y") as year, IFNULL(sum(krw), 0) as amount_free
            	from tbl_send_history x
            	join tbl_user y
            	on x.user_id = y.id
            	where y.rec = 'hackx3'
            	and x.status = 'A'
            	group by year
            ) x
            where x.year = '2019';
        '''.format(year=year, myRec=myRec)
        cur.execute(query)
        free_sums = cur.fetchall()

        amount_krw = sums[0][0]
        amount_usd = sums[0][1]
        amount_cny = sums[0][2]
        amount_free = free_sums[0][0]

    return JsonResponse({
        'result': rows,
        'amount_krw': amount_krw,
        'amount_usd': amount_usd,
        'amount_cny': amount_cny,
        'amount_free': amount_free
    })
