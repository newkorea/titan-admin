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
from backend.models_radius import Radcheck
from backend.djangoapps.common.views import *
from django.utils import translation
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from backend.djangoapps.common.paybox import Paybox


# 무통장내역 상태변경 (2019.11.24 11:22 점검완료)
def api_set_status(request):
    id = request.POST.get('id')
    type = request.POST.get('type')

    history = TblSendHistory.objects.get(id=id)
    session = str(history.session)
    month_type = str(history.month_type)
    user_id = history.user_id

    history.status = type
    if type == 'C':
        history.cancel_date = datetime.datetime.now()
    elif type == 'A':
        history.accept_date = datetime.datetime.now()
        # 시간충전
        giveServiceTime(user_id, session, month_type)
    elif type == 'Z':
        history.refund_date = datetime.datetime.now()
        # 시간초기화
        initServiceTime(user_id)
    history.save()

    return JsonResponse({'result': 200})


# 계좌관리 내용편집 (2019.11.24 11:22 점검완료)
@allow_cs
def api_update_bank(request):
    person_name = request.POST.get('person_name')
    bank_name = request.POST.get('bank_name')
    bank_number = request.POST.get('bank_number')

    bank = TblBankAccount.objects.get(type='main')
    bank.person_name = person_name
    bank.bank_name = bank_name
    bank.bank_number = bank_number
    bank.save()

    return JsonResponse({'result': 200})


# 계좌관리 내용로드 (2019.11.24 11:22 점검완료)
@allow_cs
def api_read_bank(request):

    bank = TblBankAccount.objects.get(type='main')
    person_name = bank.person_name
    bank_name = bank.bank_name
    bank_number = bank.bank_number

    send = {
        'person_name': person_name,
        'bank_name': bank_name,
        'bank_number': bank_number
    }

    return JsonResponse({'result': 200, 'bank': send})


# 무통장내역 렌더링 (2019.11.24 11:22 점검완료)
@allow_cs
def account_history(request):
    return render(request, 'price/admin_account_history.html')


# 계좌관리 렌더링 (2019.11.24 11:22 점검완료)
@allow_cs
def account_setting(request):
    return render(request, 'price/admin_account_setting.html')


# 결제관리 페이지 렌더링 (2019.09.21 13:56 점검완료)
@allow_cs
def price(request):
    return render(request, 'price/admin_price.html')


# 환불 API (2019.09.25 09:54 개발중)
@allow_cs
def api_price_refund(request):

    # 파라미터 로드
    id = request.POST.get('id')

    # 결제 테이블 조회
    tph = TblPriceHistory.objects.get(id=id)
    krw = tph.krw
    usd = tph.usd
    cny = tph.cny
    tid = tph.tid
    user_id = tph.user_id
    pgcode = tph.pgcode

    # 파라미터 로깅
    print('DEBUG -> id : ', id)
    print('DEBUG -> krw : ', krw)
    print('DEBUG -> usd : ', usd)
    print('DEBUG -> cny : ', cny)
    print('DEBUG -> tid : ', tid)
    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> pgcode : ', pgcode)

    # 사용자 객체
    user = TblUser.objects.get(id=user_id)
    email = user.email

    # 국내환불
    if krw != None:
        p = Payletter(settings.PAYLETTER_MODE)
        res = p.payments_cancel(pgcode, user_id, tid, krw)
        # 환불 성공
        if res == 200:
            tph.refund_yn = 'Y'
            tph.refund_date = datetime.now()
            tph.save()
            initServiceTime(user_id)
            return JsonResponse({'result': 200})
        else:
            # 환불 실패
            return JsonResponse({'result': 500})
    # 해외환불
    elif usd != None:
        p = PayletterGlobal(settings.PAYLETTER_MODE)
        res = p.payments_cancel(pgcode, user_id, tid, usd)
        # 환불 성공
        if res == 200:
            tph.refund_yn = 'Y'
            tph.refund_date = datetime.now()
            tph.save()
            initServiceTime(user_id)
            return JsonResponse({'result': 200})
        elif res == 400:
            # 환불 실패 (이미 처리된 트랜잭션)
            return JsonResponse({'result': 400})
        else:
            # 환불 실패
            return JsonResponse({'result': 500})
        return JsonResponse({'result': 200})
    # 위챗환불
    elif cny != None:
        p = Paybox(settings.PAYBOX_MODE)
        token = p.load_token()
        if token != 500:
            res = p.payments_cancel(pgcode, user_id, tid, cny, token)
            # 환불성공
            if res != 500:
                tph.refund_yn = 'Y'
                tph.refund_date = datetime.now()
                tph.save()
                initServiceTime(user_id)
                return JsonResponse({'result': 200})
            else:
                return JsonResponse({'result': 404})
            return JsonResponse({'result': 404})
        else:
            return JsonResponse({'result': 404})
    else:
        # 알 수 없는 분기
        return JsonResponse({'result': 404})


# 결제모듈 데이터 로드 (2019.09.21 13:56 점검완료)
@allow_cs
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
        # print(query)
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
                        cny,
                        taxfree_amount,
                        tax_amount,
                        email,
                        autopay_flag,
                        refund_yn,
                        DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i:%S") as regist_date,
                        DATE_FORMAT(refund_date, "%Y-%m-%d %H:%i:%S") as refund_date,
                        auto_end_date,
                        concat(id, '+', refund_yn) as refund
                from (
                    select @rnum := @rnum + 1 AS rnum, x.*
                    from (
                    select  x.id,
                            x.tid,
                            x.pgcode,
                            x.product_name,
                            x.krw as krw,
                            x.usd as usd,
                            x.cny as cny,
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
        # print(query)
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(ret)


# 무통장내역 데이터 로드 (2019.11.24 11:57 점검완료)
@allow_cs
def api_read_ah(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    # 검색필터 파라미터
    number = request.POST.get('number')
    email = request.POST.get('email')
    username = request.POST.get('username')
    session = request.POST.get('session')
    month = request.POST.get('month')
    status = request.POST.get('status')
    regist_start = request.POST.get('regist_start')
    regist_end = request.POST.get('regist_end')

    # 로깅 (datatables 기본 파라미터)
    print('DEBUG -> start : ', start)
    print('DEBUG -> length : ', length)
    print('DEBUG -> draw : ', draw)
    print('DEBUG -> orderby_col : ', orderby_col)
    print('DEBUG -> orderby_opt : ', orderby_opt)

    # 로깅 (검색필터 파라미터)
    print('DEBUG -> number : ', number)
    print('DEBUG -> email : ', email)
    print('DEBUG -> username : ', username)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month : ', month)
    print('DEBUG -> status : ', status)
    print('DEBUG -> regist_start : ', regist_start)
    print('DEBUG -> regist_end : ', regist_end)

    # where 절 필터링 생성
    filter = ' where 1=1 '
    if number != '':
        filter += " and x.id = '{number}' ".format(number=number)
    if email != '':
        filter += " and y.email = '{email}' ".format(email=email)
    if username != '':
        filter += " and y.username = '{username}' ".format(username=username)
    if session != '0':
        filter += " and x.session = '{session}' ".format(session=session)
    if month != '0':
        filter += " and x.month_type = '{month}' ".format(month=month)
    if status != '0':
        filter += " and x.status = '{status}' ".format(status=status)
    filter += '''
        and x.regist_date >= '{regist_start} 00:00:00'
        and x.regist_date < '{regist_end} 00:00:00'
    '''.format(regist_start=regist_start, regist_end=regist_end)

    # order by 리스트
    column_name = [
        'x.id',
        'y.email',
        'y.username',
        'phone',
        'x.session',
        'x.month_type',
        'x.krw'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from (
            	select @rnum := @rnum + 1 AS rnum, x.*
            	from (
            		select  x.id
            		from tbl_send_history x
            		join tbl_user y
            		on x.user_id = y.id
            		{filter}
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format(filter=filter)
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
    print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
                    email,
                    username,
                    phone,
                    session,
                    month_type,
                    krw,
                    status,
                    cancel,
                    DATE_FORMAT(cancel_date, "%Y-%m-%d %H:%i:%S") as cancel_date,
                    accept,
                    DATE_FORMAT(accept_date, "%Y-%m-%d %H:%i:%S") as accept_date,
                    refund,
                    DATE_FORMAT(refund_date, "%Y-%m-%d %H:%i:%S") as refund_date
            from (
            	select @rnum := @rnum + 1 AS rnum, x.*
            	from (
            		select  x.id,
                            y.email,
                            y.username,
                            concat('(', y.phone_country, ') ', y.phone) as phone,
                            x.session,
                            x.month_type,
                            x.krw,
                            x.status as status,
                            concat(x.status, '@', x.id, '@', y.username, '@', x.product_name, '@', x.krw) as cancel,
                            x.cancel_date,
                            concat(x.status, '@', x.id, '@', y.username, '@', x.product_name, '@', x.krw) as accept,
                            x.accept_date,
                            concat(x.status, '@', x.id, '@', y.username, '@', x.product_name, '@', x.krw) as refund,
                            x.refund_date
            		from tbl_send_history x
            		join tbl_user y
            		on x.user_id = y.id
            		{filter}
                    order by {orderby_col} {orderby_opt}
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1
            where t1.rnum BETWEEN {start} and {end};
        '''.format(
            filter=filter,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            end=start+length-1
        )
        # print(query)
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(ret)
