# 결제/가격 관리 — 요금제 CRUD, 원격승인(500/600), 결제 리다이렉트, 결제내역 조회
import json
import datetime
import smtplib
import requests
from dateutil.relativedelta import relativedelta
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
from backend.djangoapps.common.swal import get_swal
from django.utils import translation
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from backend.djangoapps.common.paybox import Paybox
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

#원격 자동승인프로그램용 API 25-02-19
from django.http import JsonResponse
import json
import os
# from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings  # ✅ settings.py에서 API_SECRET_KEY 가져오기
from backend.models import TblPaymentRequest  # ✅ `backend.` 추가 
from django.test import RequestFactory
from importlib import import_module  # ✅ 동적 import 사용
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.db import SessionStore  # ✅ 세션 저장소 추가
import pytz
from django.utils.timezone import now


@csrf_exempt
def approve_payment_api(request):
    if request.method == "POST":
        try:
            raw_body = request.body.decode('utf-8')
            data = json.loads(raw_body)
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            payment_type = data.get("payment_type")
            payment_amount = data.get("payment_amount")
            payment_time = data.get("payment_time")

            log_entry = TblPaymentApiLog.objects.create(
                payment_type=payment_type,
                payment_amount=payment_amount,
                payment_time=payment_time,
                ip_address=ip_address,
                user_agent=user_agent,
                raw_payload=raw_body,
                result_message='수신 대기 중',
                status='PENDING',
                request_time=datetime.datetime.now()
            )
        except Exception as e:
            TblPaymentApiLog.objects.create(
                payment_type=None,
                payment_amount=None,
                payment_time=None,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                raw_payload=request.body.decode('utf-8'),
                result_message=str(e),
                status='ERROR',
                request_time=datetime.datetime.now()
            )
            return JsonResponse({"status": "error", "message": f"서버 오류: {str(e)}"}, status=500)

        try:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {settings.API_SECRET_KEY}":
                log_entry.result_message = "인증 실패"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "인증 실패"}, status=403)

            type_mapping = {"alipay": "A", "wechat": "W"}
            mapped_type = type_mapping.get(payment_type.lower())
            if not mapped_type:
                log_entry.result_message = "잘못된 결제 유형"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "잘못된 결제 유형"}, status=400)

            cst = pytz.timezone('Asia/Shanghai')
            kst = pytz.timezone('Asia/Seoul')
            today_cst = datetime.datetime.now(cst).date()

            try:
                api_datetime_cst = datetime.datetime.combine(
                    today_cst,
                    datetime.datetime.strptime(payment_time, "%H:%M").time()
                )
            except ValueError:
                log_entry.result_message = f"잘못된 시간 형식: {payment_time}"
                log_entry.status = "ERROR"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "잘못된 시간 형식"}, status=501)

            api_datetime_cst = cst.localize(api_datetime_cst)
            api_datetime_kst = api_datetime_cst.astimezone(kst)
            api_datetime_naive = api_datetime_kst.replace(tzinfo=None)

            now_naive = datetime.datetime.now()
            if api_datetime_naive > now_naive:
                api_datetime_naive -= datetime.timedelta(days=1)

            existing_payment = TblSendHistory.objects.filter(
                type=mapped_type,
                krw=str(payment_amount),
                api_date=api_datetime_naive,
                status="A"
            ).exists()

            if existing_payment:
                log_entry.result_message = "이미 승인된 결제 정보입니다."
                log_entry.save()
                return JsonResponse({"status": "error", "message": "이미 승인된 결제 정보입니다."}, status=400)

            payment_request = TblSendHistory.objects.filter(
                type=mapped_type,
                krw=str(payment_amount),
                status="R"
            ).order_by('-regist_date').first()

            if not payment_request:
                same_amount_diff_time = TblSendHistory.objects.filter(
                    type=mapped_type,
                    krw=str(payment_amount),
                    status="R"
                ).exclude(regist_date__minute=api_datetime_naive.minute).exists()

                if same_amount_diff_time:
                    log_entry.result_message = "같은 금액의 승인대기 있지만 시간이 다름"
                    log_entry.save()
                    return JsonResponse({"status": "error", "message": "같은 금액의 승인대기 있지만 시간이 다름"}, status=501)

                same_time_diff_amount = TblSendHistory.objects.filter(
                    type=mapped_type,
                    status="R",
                    regist_date__minute=api_datetime_naive.minute
                ).exclude(krw=str(payment_amount)).exists()

                if same_time_diff_amount:
                    log_entry.result_message = "같은 시간의 승인대기 있지만 금액 다름"
                    log_entry.save()
                    return JsonResponse({"status": "error", "message": "같은 시간의 승인대기 있지만 금액 다름"}, status=502)

                completely_different = TblSendHistory.objects.filter(
                    type=mapped_type,
                    status="R"
                ).exclude(krw=str(payment_amount)).exclude(regist_date__minute=api_datetime_naive.minute).exists()

                if completely_different:
                    log_entry.result_message = "금액과 시간이 모두 다름"
                    log_entry.save()
                    return JsonResponse({"status": "error", "message": "금액과 시간이 모두 다름"}, status=503)

                other_type = TblSendHistory.objects.exclude(type=mapped_type).filter(status="R")
                for other in other_type:
                    time_match = other.regist_date.minute == api_datetime_naive.minute
                    amount_match = other.krw == str(payment_amount)

                    if time_match and amount_match:
                        log_entry.result_message = "시간·금액 동일하지만 결제방식 다름"
                        log_entry.save()
                        return JsonResponse({"status": "error", "message": "시간·금액 동일하지만 결제방식 다름"}, status=510)
                    if not time_match and amount_match:
                        log_entry.result_message = "금액은 같지만 시간이 다르고 결제방식도 다름"
                        log_entry.save()
                        return JsonResponse({"status": "error", "message": "시간 다르고 결제방식도 다름"}, status=511)
                    if time_match and not amount_match:
                        log_entry.result_message = "시간은 같지만 금액 다르고 결제방식도 다름"
                        log_entry.save()
                        return JsonResponse({"status": "error", "message": "금액 다르고 결제방식도 다름"}, status=512)
                    if not time_match and not amount_match:
                        log_entry.result_message = "시간·금액·방식 모두 다름"
                        log_entry.save()
                        return JsonResponse({"status": "error", "message": "시간·금액·방식 모두 다름"}, status=513)

                log_entry.result_message = "일치하는 결제 요청 없음"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "승인대기하는 결제 요청 없음"}, status=404)

            db_payment_time = payment_request.regist_date
            time_difference = (api_datetime_naive - db_payment_time).total_seconds()

            if time_difference < -90:
                log_entry.result_message = "결제 시간이 DB보다 90초 이상 빠름"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "결제 시간이 DB보다 90초 이상 빠를 수 없습니다."}, status=400)

            if time_difference > 180:
                log_entry.result_message = "결제 시간이 DB보다 3분 초과 늦음"
                log_entry.save()
                return JsonResponse({"status": "error", "message": "결제 시간이 DB보다 3분 초과로 늦습니다."}, status=400)

            user_id = payment_request.user_id
            session = str(payment_request.session)
            month_type = str(payment_request.month_type)

            with transaction.atomic():
                giveServiceTime(user_id, session, month_type)
                payment_request.status = "A"
                payment_request.accept_date = datetime.datetime.now()
                payment_request.api_date = api_datetime_naive
                payment_request.save()

                # 같은 사용자의 나머지 대기/취소 건 정리 (R=요청, U=사용자취소, C=관리자취소)
                TblSendHistory.objects.filter(
                    user_id=user_id,
                    status__in=['R', 'U', 'C']
                ).exclude(id=payment_request.id).update(
                    status='D',
                    cancel_date=datetime.datetime.now()
                )

                log_entry.status = "APPROVED"
                log_entry.result_message = "결제 승인 완료"
                log_entry.save()

            return JsonResponse({"status": "success", "message": "결제 승인 완료"})

        except Exception as e:
            log_entry.result_message = f"서버 오류: {str(e)}"
            log_entry.status = "ERROR"
            log_entry.save()
            return JsonResponse({"status": "error", "message": f"서버 오류: {str(e)}"}, status=500)

    return JsonResponse({"status": "error", "message": "잘못된 요청 방식"}, status=405)

# 관리자 페이지에서 API 로그 확인 뷰(26-06-05)
# 기존 API: JSON 반환용 => 유지합니다
@allow_admin
def api_view_payment_logs(request):
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    draw = int(request.GET.get('draw', 1))

    logs = TblPaymentApiLog.objects.all().order_by('-request_time')
    total = logs.count()
    logs = logs[start:start+length]

    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'request_time': log.request_time.strftime("%Y-%m-%d %H:%M:%S"),
            'payment_type': log.payment_type,
            'payment_amount': log.payment_amount,
            'payment_time': log.payment_time,
            'ip_address': log.ip_address,
            'status': log.status,
            'result_message': log.result_message,
            'user_agent': log.user_agent[:100],
        })

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": data
    })

    # 관리자 HTML 페이지 반환용 => 신규 추가

# views.py (예시)
# backend/djangoapps/price/views.py

from django.shortcuts import render
from backend.models import TblPaymentApiLog  # 또는 정확한 경로

def admin_payment_logs_page(request):
    logs = TblPaymentApiLog.objects.all().order_by('-request_time')
    return render(request, 'admin/view_payment_logs.html', {'logs': logs})





# 무통장내역 렌더링 (2020-03-18)
@allow_admin
def account_history(request):
    return render(request, 'admin/price_bank.html')


# 계좌관리 렌더링 (2020-03-18)
@allow_admin
def account_setting(request):
    return render(request, 'admin/price_account.html')


# 결제관리 페이지 렌더링 (2020-03-18)
@allow_admin
def price(request):
    return render(request, 'admin/price_payment.html')


# (2020-03-18)
@allow_admin
def api_read_payment(request):

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
    type = request.POST.get('type')
    regist_start = request.POST.get('regist_start')
    regist_end = request.POST.get('regist_end')

    # 로깅 (datatables 기본 파라미터)
    #print('DEBUG -> start : ', start)
    #print('DEBUG -> length : ', length)
    #print('DEBUG -> draw : ', draw)
    #print('DEBUG -> orderby_col : ', orderby_col)
    #print('DEBUG -> orderby_opt : ', orderby_opt)

    # 로깅 (검색필터 파라미터)
    #print('DEBUG -> email : ', email)
    #print('DEBUG -> session : ', session)
    #print('DEBUG -> month : ', month)
    #print('DEBUG -> refund : ', refund)
    #print('DEBUG -> regist_start : ', regist_start)
    #print('DEBUG -> regist_end : ', regist_end)

    # where 절 필터링 생성
    wc = ' where 1=1 '
    if email != '':
        wc += " and y.email like '%{email}%' ".format(email=email)
    if session != '0':
        wc += " and x.session = '{session}' ".format(session=session)
    if month != '0':
        wc += " and x.month_type = '{month}' ".format(month=month)
    if type != '':
        wc += " and x.pgcode = '{type}' ".format(type=type)
    if refund != '0':
        wc += " and x.refund_yn = '{refund}' ".format(refund=refund)
    if regist_start != '':
        wc += '''
            and x.regist_date >= '{regist_start}'
        '''.format(regist_start=regist_start)
    if regist_end != '':
        wc += '''
            and x.regist_date < '{regist_end}'
        '''.format(regist_end=regist_end)

    # order by 리스트
    column_name = [
        'x.id',
        'x.tid',
        'x.pgcode',
        'x.product_name',
        'x.krw',
        'x.usd',
        'x.cny',
        'y.email',
        'x.refund_yn',
        'x.regist_date',
        'x.refund_date'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_price_history x
            join tbl_user y
            on x.user_id = y.id
            {wc}
        '''.format(wc=wc)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
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
            		x.auto_end_date,
                    concat(x.id, '+', x.refund_yn, '+', x.pgcode) as refund,
                    COALESCE(x.tid, '') as receipt,
                    concat(COALESCE(x.tid, ''), '+', y.email) as receipt_send
            from tbl_price_history x
            join tbl_user y
            on x.user_id = y.id
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            end=start+length-1
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2020-03-18)
@allow_admin
def api_update_refund(request):

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
    
    session = str(tph.session)
    month_type = str(tph.month_type)
    user_id = tph.user_id
    
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
            tph.refund_date = datetime.datetime.now()
            tph.save()
            #initServiceTime(user_id)
            print("National Refund: ", "TRUE")
            refundPayment(user_id, session, month_type)
            title, text = get_swal('PAYMENT_SUCCESS')
            return JsonResponse({'result': 200, 'title': title, 'text': text})
        else:
            # 환불 실패
            title, text = get_swal('PAYMENT_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    # 해외환불
    elif usd != None:
        p = PayletterGlobal(settings.PAYLETTER_MODE)
        res = p.payments_cancel(pgcode, user_id, tid, usd)
        # 환불 성공
        if res == 200:
            tph.refund_yn = 'Y'
            tph.refund_date = datetime.datetime.now()
            tph.save()
            #initServiceTime(user_id)
            print("National Refund: ", "FALSE")
            refundPayment(user_id, session, month_type)
            title, text = get_swal('PAYMENT_SUCCESS')
            return JsonResponse({'result': 200, 'title': title, 'text': text})
        elif res == 400:
            # 환불 실패 (이미 처리된 트랜잭션)
            title, text = get_swal('PAYMENT_ALREADY')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
        else:
            # 환불 실패
            title, text = get_swal('PAYMENT_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    # 위챗환불
    elif cny != None:
        p = Paybox(settings.PAYBOX_MODE)
        token = p.load_token()
        if token != 500:
            res = p.payments_cancel(pgcode, user_id, tid, cny, token)
            # 환불성공
            if res != 500:
                tph.refund_yn = 'Y'
                tph.refund_date = datetime.datetime.now()
                tph.save()
                #initServiceTime(user_id)
                refundPayment(user_id, session, month_type)
                title, text = get_swal('PAYMENT_SUCCESS')
                return JsonResponse({'result': 200, 'title': title, 'text': text})
            else:
                title, text = get_swal('PAYMENT_ERROR')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        else:
            title, text = get_swal('PAYMENT_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    else:
        title, text = get_swal('PAYMENT_UNKNOWN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2020-03-18)
@allow_admin
def api_update_account(request):
    person_name = request.POST.get('person_name')
    bank_name = request.POST.get('bank_name')
    bank_number = request.POST.get('bank_number')
    try:
        bank = TblBankAccount.objects.get(type='main')
        bank.person_name = person_name
        bank.bank_name = bank_name
        bank.bank_number = bank_number
        bank.save()
        title, text = get_swal('SUCCESS_ACCOUNT')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})



# (2020-03-18)
@allow_admin
def api_read_account(request):
    try:
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
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# 오늘 결제건수 (메뉴 뱃지용)
@allow_admin
def api_read_today_payment_count(request):
    from datetime import date
    today = date.today()
    today_payment = TblPriceHistory.objects.filter(regist_date__date=today).count()
    return JsonResponse({'result': 200, 'today_payment': today_payment})


# (2020-03-18)
@allow_admin
def api_read_ready_count(request):
    from datetime import date
    history = TblSendHistory.objects.filter(status='R')
    ready_count = len(history)
    today = date.today()
    today_approved = TblSendHistory.objects.filter(status__in=['A', 'S'], accept_date__date=today).count()
    return JsonResponse({'result': 200, 'ready_count': ready_count, 'today_approved': today_approved})


# (2020-03-18) 2025-08-25 D를 안보이게 처리
@allow_admin
def api_read_bank(request):

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
    type_code = (request.POST.get('type') or '').strip().upper()
    regist_start = request.POST.get('regist_start')
    regist_end = request.POST.get('regist_end')

    # where 절 필터링 생성
    wc = ' where 1=1 '

    # ✅ 기본은 D 숨김
    if status == '0' or status == '' or status is None:
        wc += ' and x.status <> "D" '
    else:
        wc += " and x.status = '{status}' ".format(status=status)

    if number != '':
        wc += " and x.id = '{number}' ".format(number=number)
    if email != '':
        wc += " and y.email like '%{email}%' ".format(email=email)
    if username != '':
        wc += " and y.username like '%{username}%' ".format(username=username)
    if session != '0':
        wc += " and x.session = '{session}' ".format(session=session)
    if month != '0':
        wc += " and x.month_type = '{month}' ".format(month=month)
    if type_code != '':
        wc += " and UPPER(TRIM(x.type)) = '{type_code}' ".format(type_code=type_code)
    if regist_start != '':
        wc += " and x.regist_date >= '{regist_start}' ".format(regist_start=regist_start)
    if regist_end != '':
        wc += " and x.regist_date < '{regist_end}' ".format(regist_end=regist_end)

    # order by 리스트
    column_name = [
        'x.id',
        'y.email',
        'y.username',
        'y.regist_date',
        'x.session',
        'x.month_type',
        'x.krw',
        'x.status',
        'x.regist_date',
        'x.status',
        'x.cancel_date',
        'x.status',
        'x.accept_date',
        'x.status',
        'x.refund_date',
        'x.type',
        'x.id',
        'x.id'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_send_history x
            join tbl_user y
            on x.user_id = y.id
            {wc}
        '''.format(wc=wc)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  x.id,
                    y.email,
                    y.username,
                    DATE_FORMAT(y.regist_date, "%Y-%m-%d %H:%i:%S") as regist_date,
                    DATE_FORMAT(x.regist_date, "%Y-%m-%d %H:%i:%S") as request_date,
                    x.session,
                    x.month_type,
                    x.krw,
                    x.status as status,
                    concat(x.status, '@', x.id, '@', y.username, '@', x.product_name, '@', x.krw) as cancel,
                    DATE_FORMAT(x.cancel_date, "%Y-%m-%d %H:%i:%S") as cancel_date,
                    concat(x.status, '&', x.id, '&', y.username, '&', x.product_name, '&', x.krw, '&', x.session, '&', y.email, '&', y.black_yn) as accept,
                    DATE_FORMAT(x.accept_date, "%Y-%m-%d %H:%i:%S") as accept_date,
                    concat(x.status, '@', x.id, '@', y.username, '@', x.product_name, '@', x.krw) as refund,
                    DATE_FORMAT(x.refund_date, "%Y-%m-%d %H:%i:%S") as refund_date,
                    UPPER(TRIM(x.type)) as type,
                    concat(x.id, '|', x.status, '|', COALESCE(inv.id, ''), '|', x.user_id, '|', COALESCE(x.product_name,''), '|', COALESCE(x.session,''), '|', COALESCE(x.month_type,''), '|', COALESCE(x.krw,''), '|', COALESCE(UPPER(TRIM(x.type)),'M'), '|', DATE_FORMAT(x.regist_date, '%%Y-%%m-%%dT%%H:%%i:%%S')) as invoice,
                    concat(x.id, '|', COALESCE(inv.id, ''), '|', y.email) as invoice_send
            from tbl_send_history x
            join tbl_user y
            on x.user_id = y.id
            left join tbl_invoice inv
            on inv.source_table = 'send_history' and inv.source_id = x.id
            {wc}
            order by {orderby_col} {orderby_opt}
            limit {start}, {length}
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            length=length
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2020-03-18) 25-08-25 수정 
@allow_admin
def api_create_bank(request):
    note_email = (request.POST.get('note_email') or '').strip()  # ✅ 앞뒤 공백 제거
    note_session = request.POST.get('note_session')
    note_month = request.POST.get('note_month')
    note_type = (request.POST.get('note_type') or '').strip().upper()   # ✅ 정규화
    if note_type not in ('A', 'W', 'M', 'V'):
        note_type = 'M'  # ✅ 기본 무통장

    print("note_email -> ", note_email)
    print("note_session -> ", note_session)
    print("note_month -> ", note_month)
    print("note_type -> ", note_type)

    try:
        user = TblUser.objects.get(email=note_email)
    except BaseException as err:
        title, text = get_swal('NOT_USER')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    force = (request.POST.get('force') or '').upper() == 'Y'
    # 이메일 활성화 (본인인증) 여부 확인: 비활성 상태면 안내 후 409 반환, force=Y 면 통과
    try:
        if user.is_active != 1 and not force:  # 1 이 활성(본인인증 완료)로 가정
            # 프론트에서 '계속연장' 버튼을 제공하여 재요청(force=Y) 가능
            title, text = get_swal('NOT_ACTIVE')
            # 클라이언트가 먼저 "등록 확인" 단계에서 경고 문구를 추가로 보여줄 수 있도록 플래그 전달
            return JsonResponse({'result': 409, 'title': title, 'text': text, 'can_force': True, 'inactive': True})
        # 연장불가 / 지역차단 상태(X) 인 경우 생성 자체를 막음 (override 불가)
        if (user.black_yn or '').upper() == 'X':
            title = '알림'
            text = '연장불가 상태의 사용자입니다 (black_yn = X)'
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    except BaseException:
        # 예외시 오류 처리
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
        
    price = getProductPirce(note_session, note_month, 'KRW')
    product_name = makeProductName(note_session, note_month)

    try:
        sh = TblSendHistory(
            user_id=user.id,
            product_name=product_name,
            session=note_session,
            month_type=note_month,
            krw=price,
            usd=None,
            jpy=None,
            cny=None,
            status='R',
            type=note_type,
            regist_date=datetime.datetime.now(),
            accept_date=None,
            cancel_date=None,
            refund_date=None
        )
        sh.save()
        title, text = get_swal('SUCCESS_BANK')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})



# (2020-03-18)
@allow_admin
def api_update_bank(request):
    id = request.POST.get('id')
    type = request.POST.get('type')
    try:
        history = TblSendHistory.objects.get(id=id)
        session = str(history.session)
        month_type = str(history.month_type)
        user_id = history.user_id

        history.status = type
        if type == 'C':
            history.cancel_date = datetime.datetime.now()
        elif type == 'A' or type == 'S':
            history.accept_date = datetime.datetime.now()
            # 시간충전
            giveServiceTime(user_id, session, month_type)
            # 같은 사용자의 나머지 대기/취소 건 정리 (R=요청, U=사용자취소, C=관리자취소)
            TblSendHistory.objects.filter(
                user_id=user_id,
                status__in=['R', 'U', 'C']
            ).exclude(id=history.id).update(
                status='D',
                cancel_date=datetime.datetime.now()
            )
        elif type == 'Z':
            history.refund_date = datetime.datetime.now()
            # 시간초기화
            #initServiceTime(user_id)
            refundPayment(user_id, session, month_type)
        history.save()

        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

# (2025-08-25) 무통장관리페이지에서  C R U 를 모두 D로 변경해서 관리자에서 안보이게함
@allow_admin
@require_POST
def api_delete_by_status(request):
    status = request.POST.get('status', '').strip().upper()
    valid = {'R', 'C', 'U'}
    if status not in valid:
        return JsonResponse({'result': 400, 'text': f'허용되지 않은 status: {status}'})

    try:
        # 삭제 대신 status='D' 로 업데이트
        q = TblSendHistory.objects.filter(status=status)
        count = q.count()
        q.update(status='D', cancel_date=datetime.datetime.now())

        return JsonResponse({
            'result': 200,
            'text': f'status={status} 항목 {count}건 → D(삭제처리)로 변경 완료'
        })
    except Exception as e:
        return JsonResponse({'result': 500, 'text': f'업데이트 중 오류: {str(e)}'})


# (2022-08-08)
def refundPayment(user_id, session, month_type):
    """환불 처리: tbl_service_time에서 해당 결제의 '변경 전' 상태를 찾아서 복원한다.

    giveServiceTime이 결제 시 기록한 tbl_service_time의 prev_time_rad(결제 전 만료일),
    diff 필드(세션 변경 정보 포함)를 사용하여 결제 직전 상태로 되돌린다.
    """
    import re as _re
    print("================ User Refund ===============", "")
    u1 = TblUser.objects.get(id=user_id)
    email = u1.email

    # 이 결제에 해당하는 tbl_service_time 기록 찾기
    # giveServiceTime이 만든 기록: diff 에 '구매' 또는 시간(분) 값, reason=''
    # 가장 최근 구매 기록을 찾는다
    purchase_st = TblServiceTime.objects.filter(
        user_id=user_id
    ).exclude(
        diff='환불'
    ).exclude(
        diff='회원탈퇴'
    ).exclude(
        reason='추천보상'
    ).order_by('-id').first()

    if purchase_st and purchase_st.prev_time_rad:
        # 결제 전 만료일 복원
        restore_time_rad = purchase_st.prev_time_rad
        restore_time = str(purchase_st.prev_time)
        print("Restore From ServiceTime ID  ====> ", purchase_st.id)
        print("Restore Time (rad)           ====> ", restore_time_rad)

        # 세션 변경이 있었는지 확인: diff 에 "구매 + 세션 변경(X->Y)" 패턴
        restore_session = None
        diff_str = str(purchase_st.diff) if purchase_st.diff else ''
        session_match = _re.search(r'세션 변경\((\d+)->(\d+)\)', diff_str)
        if session_match:
            restore_session = session_match.group(1)  # 변경 전 세션으로 복원
            print("Restore Session              ====> ", restore_session)

        # Radcheck Expiration 복원
        rce = Radcheck.objects.using('radius').filter(
            username=email,
            attribute='Expiration'
        )
        if rce.exists():
            rceu = rce.first()
            prev_time_rad = rceu.value
            prev_time = dec_radius_time(rceu.value)
            rceu.value = restore_time_rad
            rceu.save(using='radius')
        else:
            rcei = Radcheck(
                username=email,
                attribute='Expiration',
                op=':=',
                value=restore_time_rad
            )
            rcei.save(using='radius')
            prev_time_rad = ''
            prev_time = ''

        # 세션 복원 (세션 변경이 있었던 경우)
        if restore_session:
            rc = Radcheck.objects.using('radius').filter(
                username=email,
                attribute='Simultaneous-Use'
            )
            if rc.exists():
                rcu = rc.first()
                print("Session Before Refund        ====> ", rcu.value)
                rcu.value = int(restore_session)
                rcu.save(using='radius')
                print("Session After Refund         ====> ", restore_session)

        after_time = restore_time
        after_time_rad = restore_time_rad
    else:
        # fallback: tbl_service_time 기록이 없는 경우 만료 처리
        print("No purchase ServiceTime record found, setting expired")
        rce = Radcheck.objects.using('radius').filter(
            username=email,
            attribute='Expiration'
        )
        if rce.exists():
            rceu = rce.first()
            prev_time_rad = rceu.value
            prev_time = dec_radius_time(rceu.value)
            rceu.value = '01 Jan 2010 00:00:00 KST'
            rceu.save(using='radius')
        else:
            rcei = Radcheck(
                username=email,
                attribute='Expiration',
                op=':=',
                value='01 Jan 2010 00:00:00 KST'
            )
            rcei.save(using='radius')
            prev_time_rad = ''
            prev_time = ''
        after_time = '2010-01-01 00:00:00'
        after_time_rad = '01 Jan 2010 00:00:00 KST'

    # 환불 기록 저장
    reason = "환불"
    st = TblServiceTime(
        user_id=user_id,
        prev_time=prev_time,
        prev_time_rad=prev_time_rad,
        after_time=after_time,
        after_time_rad=after_time_rad,
        diff=reason,
        reason=reason,
        regist_date=datetime.datetime.now()
    )
    st.save()

    print("=============== User Refund END ============", "")
    

# (2022-08-08)
def change_date(old_date):
    try:
        return old_date.strftime("%d %b %Y %H:%M:%S") + " KST"
    except BaseException:
        return None

# (2022.08.08)
def my_expire_time(email, return_type):
    try:
        r = Radcheck.objects.using('radius').get(
            username=email,
            attribute='Expiration'
        )
        expire_time = r.value
        expire_time = dec_radius_time(expire_time)
        if return_type == 'datetime':
            return expire_time
        elif return_type == 'str':
            return expire_time.strftime("%Y-%m-%d %H:%M:%S")
    except BaseException:
        return None
        
# (2020-03-18)
@allow_admin
def api_read_ready_data(request):
    ready_list = ''
    history = TblSendHistory.objects.filter(status='R')
    total = len(history)
    for h in history:
        ready_list += str(h.id) + '  '
    return JsonResponse({'result': 200, 'ready_list': ready_list, 'total': total})

# (2020-03-18)
@allow_admin
def api_check_session(request):
    email = request.POST.get('email')
    session = request.POST.get('session')
    # 이메일 활성화 상태 확인 (없으면 False)
    inactive = False
    try:
        u = TblUser.objects.get(email=email)
        inactive = (u.is_active != 1)
    except BaseException:
        inactive = False
    rc = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Simultaneous-Use'
    )
    if len(rc) == 0:
        print("New User")
        return JsonResponse({'result': 400, 'inactive': inactive})
    else:
        rcu = rc.first()
        if rcu.value != session :
            return JsonResponse({'result': 200, 'old_session':rcu.value, 'inactive': inactive})
        else :
            return JsonResponse({'result': 400, 'inactive': inactive})

# 국제 결제 방식(WeChat, Alipay) 활성화 여부 읽기
@allow_admin
def api_read_payment_methods(request):
    try:
        wechat_enabled = True
        alipay_enabled = True
        
        with connections['default'].cursor() as cur:
            cur.execute("SELECT config_value FROM tbl_global_config WHERE config_key = 'wechat_enabled'")
            row = cur.fetchone()
            if row:
                wechat_enabled = (row[0] == 'true')
            
            cur.execute("SELECT config_value FROM tbl_global_config WHERE config_key = 'alipay_enabled'")
            row = cur.fetchone()
            if row:
                alipay_enabled = (row[0] == 'true')
        
        return JsonResponse({
            'result': 200,
            'wechat_enabled': wechat_enabled,
            'alipay_enabled': alipay_enabled,
            'title': '조회 성공',
            'text': '결제 방식 설정을 조회했습니다.'
        })
    except Exception as e:
        return JsonResponse({
            'result': 400,
            'title': '조회 실패',
            'text': str(e)
        })

# 국제 결제 방식(WeChat, Alipay) 활성화 여부 업데이트
@allow_admin
def api_update_payment_methods(request):
    try:
        wechat_enabled = 'true' if request.POST.get('wechat_enabled') == 'true' else 'false'
        alipay_enabled = 'true' if request.POST.get('alipay_enabled') == 'true' else 'false'
        
        with connections['default'].cursor() as cur:
            # Wechat 업데이트
            cur.execute("INSERT INTO tbl_global_config (config_key, config_value, description) VALUES ('wechat_enabled', %s, 'Enable WeChat Pay') ON DUPLICATE KEY UPDATE config_value=%s", [wechat_enabled, wechat_enabled])
            
            # Alipay 업데이트
            cur.execute("INSERT INTO tbl_global_config (config_key, config_value, description) VALUES ('alipay_enabled', %s, 'Enable AliPay') ON DUPLICATE KEY UPDATE config_value=%s", [alipay_enabled, alipay_enabled])
        
        return JsonResponse({
            'result': 200,
            'title': '저장 성공',
            'text': '결제 방식 설정이 저장되었습니다 (전체 서버 적용).'
        })
    except Exception as e:
        return JsonResponse({
            'result': 400,
            'title': '저장 실패',
            'text': str(e)
        })  


# 영수증 URL 조회 (페이레터 API)
@allow_admin
def api_read_receipt(request):
    """페이레터 API를 통해 영수증(거래명세서) URL을 조회"""
    tid = request.POST.get('tid', '').strip()
    if not tid:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '트랜잭션 ID가 없습니다.'})

    try:
        api_url = f"{settings.PAYLETTER_KOR_LIVE_ENDPOINT}v1.0/receipt/info/{tid}/?client_id={settings.PAYLETTER_KOR_LIVE_SHOPID}"
        headers = {"Authorization": f"PLKEY {settings.PAYLETTER_KOR_LIVE_APIKEY_SEARCH}"}
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            receipt_url = data.get('receipt_url')
            if receipt_url:
                return JsonResponse({'result': 200, 'receipt_url': receipt_url})

        return JsonResponse({'result': 500, 'title': '오류', 'text': '영수증 URL을 가져올 수 없습니다.'})
    except Exception as e:
        return JsonResponse({'result': 500, 'title': '오류', 'text': f'API 요청 실패: {str(e)}'})


# 영수증 이메일 발송
@allow_admin
def api_send_receipt_email(request):
    """페이레터 영수증 URL을 조회하여 고객 이메일로 발송"""
    tid = request.POST.get('tid', '').strip()
    email = request.POST.get('email', '').strip()

    if not tid:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '트랜잭션 ID가 없습니다.'})
    if not email:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '이메일 주소가 없습니다.'})

    # 1. 페이레터 API에서 영수증 URL 조회
    try:
        api_url = f"{settings.PAYLETTER_KOR_LIVE_ENDPOINT}v1.0/receipt/info/{tid}/?client_id={settings.PAYLETTER_KOR_LIVE_SHOPID}"
        headers = {"Authorization": f"PLKEY {settings.PAYLETTER_KOR_LIVE_APIKEY_SEARCH}"}
        response = requests.get(api_url, headers=headers, timeout=10)

        receipt_url = None
        if response.status_code == 200:
            data = response.json()
            receipt_url = data.get('receipt_url')

        if not receipt_url:
            return JsonResponse({'result': 500, 'title': '오류', 'text': '영수증 URL을 가져올 수 없습니다.'})
    except Exception as e:
        return JsonResponse({'result': 500, 'title': '오류', 'text': f'영수증 API 오류: {str(e)}'})

    # 2. 이메일 발송
    try:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f'[TITAN VPN] 결제 영수증 안내'
        html_body = f'''
        <html>
        <body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
            <div style="max-width:600px;margin:0 auto;padding:20px;">
                <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px;">
                    TITAN VPN 결제 영수증
                </h2>
                <p>안녕하세요, TITAN VPN을 이용해 주셔서 감사합니다.</p>
                <p>고객님의 결제 영수증을 아래 링크에서 확인하실 수 있습니다.</p>
                <div style="text-align:center;margin:30px 0;">
                    <a href="{receipt_url}" target="_blank"
                       style="display:inline-block;padding:14px 40px;background-color:#3498db;color:#ffffff;
                              text-decoration:none;border-radius:6px;font-size:16px;font-weight:bold;">
                        영수증 확인하기
                    </a>
                </div>
                <p style="font-size:12px;color:#888;">
                    트랜잭션 ID: {tid}<br>
                    발송 시간: {now_str}
                </p>
                <hr style="border:none;border-top:1px solid #eee;margin-top:30px;">
                <p style="font-size:11px;color:#aaa;">
                    본 메일은 TITAN VPN에서 자동 발송된 메일입니다.<br>
                    문의사항이 있으시면 고객센터로 연락해 주세요.
                </p>
            </div>
        </body>
        </html>
        '''

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_EMAIL
        msg['To'] = email
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.login(settings.SMTP_ID, settings.SMTP_PW)
            smtp.sendmail(settings.SMTP_EMAIL, [email], msg.as_string())

        return JsonResponse({'result': 200, 'title': '발송 완료', 'text': f'{email}로 영수증을 발송했습니다.'})
    except Exception as e:
        return JsonResponse({'result': 500, 'title': '발송 실패', 'text': f'이메일 발송 오류: {str(e)}'})


# ──────────────────────────────────────────────────────────────
# 무통장(send_history) 인보이스 발급 / 조회 / 이메일 발송
# ──────────────────────────────────────────────────────────────

def _invoice_amount(krw, payment_type):
    """무통장/알리/위챗 금액 포맷"""
    sym = '₩'; code = 'KRW'
    raw = str(krw or '0').replace(',', '')
    try:
        formatted = f"{float(raw):,.2f}"
    except (ValueError, TypeError):
        formatted = raw or '0.00'
    return formatted, sym, code


def _invoice_payment_label(ptype):
    labels = {
        'M': 'Bank Transfer', 'A': 'AliPay', 'W': 'WeChat Pay', 'V': 'Virtual Currency',
    }
    return labels.get((ptype or 'M').upper(), 'Bank Transfer')


def _render_invoice_html(data):
    """Invoice HTML 문자열 생성"""
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>Invoice - TITAN VPN</title>
<style>
@media print {{ .no-print {{ display:none!important; }} body {{ margin:0; }} }}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f0f0;color:#333;}}
.invoice-wrap{{max-width:800px;margin:20px auto;background:#fff;box-shadow:0 0 10px rgba(0,0,0,.15);}}
.invoice-inner{{padding:40px 50px;}}
.inv-header{{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #4285f4;padding-bottom:20px;margin-bottom:25px;}}
.inv-logo-text{{font-size:22px;font-weight:700;color:#4285f4;margin-top:4px;}}
.inv-logo-sub{{font-size:11px;color:#888;}}
.inv-title{{text-align:right;}}
.inv-title h1{{font-size:32px;color:#333;letter-spacing:2px;}}
.inv-title p{{font-size:12px;color:#666;margin-top:4px;}}
.inv-info{{display:flex;justify-content:space-between;margin-bottom:30px;}}
.inv-info-block h4{{font-size:11px;text-transform:uppercase;color:#999;margin-bottom:4px;letter-spacing:1px;}}
.inv-info-block p{{font-size:14px;color:#333;}}
.inv-table{{width:100%;border-collapse:collapse;margin-bottom:30px;}}
.inv-table thead{{background:#4285f4;color:#fff;}}
.inv-table th{{padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.5px;}}
.inv-table td{{padding:12px 14px;font-size:13px;border-bottom:1px solid #eee;}}
.inv-table .text-right{{text-align:right;}}
.inv-stamp{{text-align:center;margin:20px 0;}}
.inv-stamp span{{display:inline-block;border:3px solid #e74c3c;color:#e74c3c;font-size:22px;font-weight:900;padding:8px 18px;border-radius:6px;transform:rotate(-5deg);letter-spacing:2px;}}
.inv-totals{{display:flex;justify-content:flex-end;margin-bottom:30px;}}
.inv-totals table{{width:280px;border-collapse:collapse;}}
.inv-totals td{{padding:6px 14px;font-size:13px;}}
.inv-totals .total-row td{{border-top:2px solid #4285f4;font-weight:700;font-size:15px;padding-top:10px;}}
.inv-totals .label{{text-align:right;color:#666;}}
.inv-totals .value{{text-align:right;}}
.inv-footer{{border-top:1px solid #ddd;padding-top:20px;text-align:center;}}
.inv-footer p{{font-size:11px;color:#888;margin-bottom:3px;}}
.btn-bar{{text-align:center;padding:15px;background:#f8f8f8;}}
.btn-bar button{{padding:10px 30px;font-size:14px;border:none;border-radius:4px;cursor:pointer;margin:0 5px;}}
.btn-print{{background:#4285f4;color:#fff;}}
.btn-close{{background:#888;color:#fff;}}
</style></head><body>
<div class="no-print btn-bar">
  <button class="btn-print" onclick="window.print();">&#128424; Download / Print</button>
  <button class="btn-close" onclick="window.close();">Close</button>
</div>
<div class="invoice-wrap"><div class="invoice-inner">
  <div class="inv-header">
    <div><div class="inv-logo-text">TITAN VPN</div><div class="inv-logo-sub">TITANVPN Co.,LTD</div></div>
    <div class="inv-title"><h1>INVOICE</h1><p>Date: {data['date_display']}</p><p>Invoice #: {data['inv_no']}</p></div>
  </div>
  <div class="inv-info">
    <div class="inv-info-block"><h4>Bill To</h4><p style="font-size:16px;font-weight:600;">{data['company_name']}</p></div>
    <div class="inv-info-block" style="text-align:right;"><h4>Payment Method</h4><p>{data['payment_label']}</p></div>
  </div>
  <table class="inv-table"><thead><tr>
    <th>Qty</th><th>Description</th><th class="text-right">Unit Price</th><th class="text-right">Discount</th><th class="text-right">Line Total</th>
  </tr></thead><tbody><tr>
    <td>1</td><td>{data['product_name']}</td>
    <td class="text-right">{data['inv_currency']}{data['inv_amount']}</td>
    <td class="text-right">{data['inv_currency']}0.00</td>
    <td class="text-right">{data['inv_currency']}{data['inv_amount']}</td>
  </tr></tbody></table>
  <div class="inv-stamp"><span>TITAN VPN</span></div>
  <div class="inv-totals"><table>
    <tr><td class="label">Subtotal</td><td class="value">{data['inv_currency']}{data['inv_amount']}</td></tr>
    <tr><td class="label">Sales Tax</td><td class="value">0%</td></tr>
    <tr class="total-row"><td class="label">Total</td><td class="value">{data['inv_currency']}{data['inv_amount']}</td></tr>
  </table></div>
  <div class="inv-footer">
    <p><strong>Thank you for your business!</strong></p>
    <p>DaeHwaLo160, DaeDukKu, DaejunCity, Korea &nbsp; TEL: 070-8016-3303 &nbsp; Mail: admin@titanvpn.kr</p>
  </div>
</div></div></body></html>'''


@allow_admin
def api_generate_bank_invoice(request):
    """무통장(send_history) 인보이스 발급 — DB 저장"""
    send_id = request.POST.get('send_id', '').strip()
    company_name = request.POST.get('company_name', '').strip() or 'N/A'

    if not send_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    # 이미 발급 여부 확인
    with connections['default'].cursor() as cur:
        cur.execute("SELECT id FROM tbl_invoice WHERE source_table='send_history' AND source_id=%s", [send_id])
        existing = cur.fetchone()
        if existing:
            return JsonResponse({'result': 409, 'title': '알림', 'text': '이미 발급된 인보이스가 있습니다. 보기 버튼을 이용하세요.'})

    # send_history + user 정보 조회
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT x.user_id, x.product_name, x.session, x.month_type, x.krw,
                   UPPER(TRIM(x.type)) as ptype, x.regist_date
            FROM tbl_send_history x
            WHERE x.id = %s
        """, [send_id])
        row = cur.fetchone()

    if not row:
        return JsonResponse({'result': 404, 'title': '오류', 'text': '해당 결제 건을 찾을 수 없습니다.'})

    user_id, product_name, session_cnt, month_type, krw, ptype, regist_date = row

    inv_amount, inv_currency, inv_currency_code = _invoice_amount(krw, ptype)
    payment_label = _invoice_payment_label(ptype)

    try:
        date_display = regist_date.strftime('%B %d, %Y')
        inv_no = regist_date.strftime('%Y%m%d') + str(send_id).zfill(3)
    except Exception:
        date_display = str(regist_date)
        inv_no = datetime.datetime.now().strftime('%Y%m%d') + str(send_id).zfill(3)

    # DB 저장
    with connections['default'].cursor() as cur:
        cur.execute("""
            INSERT INTO tbl_invoice
                (user_id, source_table, source_id, company_name, product_name,
                 payment_type, inv_amount, inv_currency, inv_currency_code,
                 inv_no, date_display, payment_label, session_cnt, month_type)
            VALUES (%s, 'send_history', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [user_id, send_id, company_name, product_name or '',
              ptype or 'M', inv_amount, inv_currency, inv_currency_code,
              inv_no, date_display, payment_label,
              str(session_cnt or ''), str(month_type or '')])

    return JsonResponse({'result': 200, 'title': '발급 완료', 'text': '인보이스가 발급되었습니다.'})


@allow_admin
def api_view_bank_invoice(request):
    """인보이스 HTML 렌더링 (발급된 인보이스 보기)"""
    invoice_id = request.GET.get('invoice_id', '').strip() or request.POST.get('invoice_id', '').strip()
    send_id = request.GET.get('send_id', '').strip() or request.POST.get('send_id', '').strip()

    row = None
    with connections['default'].cursor() as cur:
        if invoice_id:
            cur.execute("""
                SELECT company_name, product_name, payment_label, inv_amount, inv_currency,
                       inv_currency_code, inv_no, date_display, session_cnt, month_type
                FROM tbl_invoice WHERE id=%s
            """, [invoice_id])
            row = cur.fetchone()
        elif send_id:
            cur.execute("""
                SELECT company_name, product_name, payment_label, inv_amount, inv_currency,
                       inv_currency_code, inv_no, date_display, session_cnt, month_type
                FROM tbl_invoice WHERE source_table='send_history' AND source_id=%s
            """, [send_id])
            row = cur.fetchone()

    if not row:
        return HttpResponse('<h2>Invoice not found</h2>', status=404)

    data = {
        'company_name': row[0], 'product_name': row[1], 'payment_label': row[2],
        'inv_amount': row[3], 'inv_currency': row[4], 'inv_currency_code': row[5],
        'inv_no': row[6], 'date_display': row[7], 'session_cnt': row[8], 'month_type': row[9],
    }
    return HttpResponse(_render_invoice_html(data), content_type='text/html; charset=utf-8')


@allow_admin
def api_send_bank_invoice_email(request):
    """발급된 인보이스를 이메일로 발송"""
    send_id = request.POST.get('send_id', '').strip()
    email = request.POST.get('email', '').strip()

    if not send_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})
    if not email:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '이메일이 없습니다.'})

    # 인보이스 조회
    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT company_name, product_name, payment_label, inv_amount, inv_currency,
                   inv_currency_code, inv_no, date_display
            FROM tbl_invoice WHERE source_table='send_history' AND source_id=%s
        """, [send_id])
        row = cur.fetchone()

    if not row:
        return JsonResponse({'result': 404, 'title': '오류', 'text': '인보이스가 아직 발급되지 않았습니다. 먼저 발급해주세요.'})

    data = {
        'company_name': row[0], 'product_name': row[1], 'payment_label': row[2],
        'inv_amount': row[3], 'inv_currency': row[4], 'inv_currency_code': row[5],
        'inv_no': row[6], 'date_display': row[7],
    }
    invoice_html = _render_invoice_html(data)

    try:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f'[TITAN VPN] Invoice #{data["inv_no"]}'
        html_body = f'''
        <html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px;">
                TITAN VPN Invoice
            </h2>
            <p>안녕하세요, TITAN VPN을 이용해 주셔서 감사합니다.</p>
            <p>고객님의 인보이스를 아래와 같이 안내드립니다.</p>
            <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;width:140px;">Invoice #</td>
                    <td style="padding:8px;border:1px solid #ddd;">{data["inv_no"]}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Date</td>
                    <td style="padding:8px;border:1px solid #ddd;">{data["date_display"]}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Product</td>
                    <td style="padding:8px;border:1px solid #ddd;">{data["product_name"]}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Amount</td>
                    <td style="padding:8px;border:1px solid #ddd;">{data["inv_currency"]}{data["inv_amount"]}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Payment</td>
                    <td style="padding:8px;border:1px solid #ddd;">{data["payment_label"]}</td></tr>
            </table>
            <p style="font-size:12px;color:#888;">발송 시간: {now_str}</p>
            <hr style="border:none;border-top:1px solid #eee;margin-top:30px;">
            <p style="font-size:11px;color:#aaa;">
                본 메일은 TITAN VPN에서 자동 발송된 메일입니다.<br>
                문의사항이 있으시면 고객센터로 연락해 주세요.
            </p>
        </div></body></html>
        '''

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_EMAIL
        msg['To'] = email

        from email.mime.base import MIMEBase
        from email import encoders
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        attachment = MIMEBase('text', 'html')
        attachment.set_payload(invoice_html.encode('utf-8'))
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment', filename=f'TITAN_Invoice_{data["inv_no"]}.html')
        msg.attach(attachment)

        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.login(settings.SMTP_ID, settings.SMTP_PW)
            smtp.sendmail(settings.SMTP_EMAIL, [email], msg.as_string())

        return JsonResponse({'result': 200, 'title': '발송 완료', 'text': f'{email}로 인보이스를 발송했습니다.'})
    except Exception as e:
        return JsonResponse({'result': 500, 'title': '발송 실패', 'text': f'이메일 발송 오류: {str(e)}'})

# ===== 자동결제 관리 =====

# 자동결제 관리 페이지 렌더링
@allow_admin
def autopay(request):
    return render(request, 'admin/autopay.html')


# 자동결제 통계 API
@allow_admin
def api_read_autopay_stats(request):
    cursor = connections['default'].cursor()

    cursor.execute("SELECT COUNT(*) FROM tbl_autopay WHERE status = 'active'")
    active_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tbl_autopay WHERE status = 'cancelled'")
    cancelled_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tbl_autopay WHERE fail_count > 0 AND status = 'active'")
    failed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tbl_autopay")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT IFNULL(SUM(amount), 0) FROM tbl_autopay WHERE status = 'active'")
    monthly_revenue = cursor.fetchone()[0]

    return JsonResponse({
        'result': 200,
        'active_count': active_count,
        'cancelled_count': cancelled_count,
        'failed_count': failed_count,
        'total_count': total_count,
        'monthly_revenue': int(monthly_revenue),
    })


# 자동결제 목록 API
@allow_admin
def api_read_autopay_list(request):
    status = request.POST.get('status', '')
    email = request.POST.get('email', '')

    where_clauses = []
    params = []

    if status:
        where_clauses.append("a.status = %s")
        params.append(status)

    if email:
        where_clauses.append("u.email LIKE %s")
        params.append('%' + email + '%')

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    cursor = connections['default'].cursor()
    cursor.execute('''
        SELECT a.id, a.user_id, u.email, u.username, a.pgcode, a.session, a.month_type,
               a.product_name, a.amount, a.discount_rate, a.status, a.fail_count,
               a.last_paid_date, a.next_pay_date, a.created_date, a.cancelled_date
        FROM tbl_autopay a
        LEFT JOIN tbl_user u ON a.user_id = u.id
        ''' + where_sql + '''
        ORDER BY a.id DESC
        LIMIT 500
    ''', params)

    columns = [col[0] for col in cursor.description]
    rows = []
    for row in cursor.fetchall():
        r = dict(zip(columns, row))
        for key in ['last_paid_date', 'next_pay_date', 'created_date', 'cancelled_date']:
            if r.get(key) and hasattr(r[key], 'strftime'):
                r[key] = r[key].strftime('%Y-%m-%d %H:%M')
        rows.append(r)

    return JsonResponse({'result': 200, 'rows': rows})


# 자동결제 관리자 해지 API
@allow_admin
def api_update_autopay_cancel(request):
    autopay_id = request.POST.get('autopay_id')
    if not autopay_id:
        return JsonResponse({'result': 400, 'message': '자동결제 ID가 필요합니다.'})

    cursor = connections['default'].cursor()
    cursor.execute(
        "UPDATE tbl_autopay SET status = 'cancelled', cancelled_date = NOW() WHERE id = %s AND status = 'active'",
        [autopay_id]
    )

    if cursor.rowcount > 0:
        print('INFO [ADMIN AUTOPAY] -> 관리자 해지: autopay_id=%s' % autopay_id)
        return JsonResponse({'result': 200, 'message': '자동결제가 해지되었습니다.'})
    else:
        return JsonResponse({'result': 400, 'message': '활성화된 자동결제를 찾을 수 없습니다.'})


# 자동결제 할인율 조회 API
@allow_admin
def api_read_autopay_discount(request):
    cursor = connections['default'].cursor()
    cursor.execute("SELECT config_value FROM tbl_site_config WHERE config_key = 'autopay_discount_rate'")
    row = cursor.fetchone()
    rate = int(row[0]) if row else 0
    return JsonResponse({'result': 200, 'discount_rate': rate})


# 자동결제 할인율 설정 API
@allow_admin
def api_update_autopay_discount(request):
    rate = request.POST.get('discount_rate', '0')
    try:
        rate = int(rate)
        if rate < 0 or rate > 50:
            return JsonResponse({'result': 400, 'message': '할인율은 0~50% 범위만 가능합니다.'})
    except (ValueError, TypeError):
        return JsonResponse({'result': 400, 'message': '올바른 숫자를 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute(
        "INSERT INTO tbl_site_config (config_key, config_value, description) VALUES ('autopay_discount_rate', %s, '자동결제 할인율') "
        "ON DUPLICATE KEY UPDATE config_value = %s",
        [str(rate), str(rate)]
    )
    print('INFO [ADMIN AUTOPAY] -> 할인율 변경: %d%%' % rate)
    return JsonResponse({'result': 200, 'message': '할인율이 %d%%로 설정되었습니다.' % rate})
