import os
import json
import datetime
import hashlib
import uuid
from pytz import timezone
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from backend.models import *
from backend.models_radius import Radcheck


@csrf_exempt
def paybox_callback(request):

    RET_SUCCESS = '<xml><returnCode><![CDATA[SUCCESS]]></returnCode></xml>'
    RET_FAIL = '<xml><returnCode><![CDATA[FAIL]]></returnCode></xml>'

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_PAYBOX_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # callback body 데이터 로깅
    f = open(payment_root + 'callback_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # callback post 데이터 로깅
    f = open(payment_root + 'callback_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    try:
        body = json.loads(request.body)
        # 실제 기록해야될 데이터만 추출
        body = json.loads(request.body)
        transactionId = body['transactionId']
        transactionDateTime = body['transactionDateTime']
        transactionCurrency = body['transactionCurrency']
        transactionPGCode = body['transactionPGCode']
        orderNo = body['orderNo']
        orderInfo = body['orderInfo']
        transAmount = body['transAmount']
        email = body['email']
        additionalInfo = body['additionalInfo']
        exchangeCurrecy = body['exchangeCurrecy']
        exchangeRate = body['exchangeRate']
        exchangeAmount = body['exchangeAmount']

        # 로깅
        print('INFO -> transactionId : ', transactionId)
        print('INFO -> transactionDateTime : ', transactionDateTime)
        print('INFO -> transactionCurrency : ', transactionCurrency)
        print('INFO -> transactionPGCode : ', transactionPGCode)
        print('INFO -> orderNo : ', orderNo)
        print('INFO -> orderInfo : ', orderInfo)
        print('INFO -> transAmount : ', transAmount)
        print('INFO -> email : ', email)
        print('INFO -> additionalInfo : ', additionalInfo)
        print('INFO -> exchangeCurrecy : ', exchangeCurrecy)
        print('INFO -> exchangeRate : ', exchangeRate)
        print('INFO -> exchangeAmount : ', exchangeAmount)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return HttpResponse(RET_FAIL)

    # load user object
    try:
        user = TblUser.objects.get(email=email)
        user_id = user.id
    except BaseException as err:
        print('ERROR -> err : ', err)
        return HttpResponse(RET_FAIL)

    # load session and month type
    try:
        addinfo = additionalInfo.split('_')
        session = addinfo[0]
        month_type = addinfo[1]
    except BaseException as err:
        print('ERROR -> err : ', err)
        return HttpResponse(RET_FAIL)

    # 요금 충전
    giveServiceTime(user_id, session, month_type)

    # 결제 내역 데이터베이스 기록 (해외)
    tph = TblPriceHistory(
        tid = transactionId,
        user_id = user_id,
        pgcode = 'WECHAT',
        product_name = orderInfo,
        session = session,
        month_type = month_type,
        krw = None,
        usd = None,
        jpy = None,
        cny = transAmount,
        taxfree_amount = None,
        tax_amount = None,
        autopay_flag = 'N',
        billkey = None,
        refund_yn = 'N',
        regist_date = datetime.datetime.now(),
        refund_date = None,
        auto_end_date = None
    )
    tph.save()

    return HttpResponse(RET_SUCCESS)


# 페이레터 해외 - 콜백처리 (2019.09.21 13:04 점검완료)
@csrf_exempt
def globalpayletter_callback(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_GLOBAL_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # callback body 데이터 로깅
    f = open(payment_root + 'callback_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # callback post 데이터 로깅
    f = open(payment_root + 'callback_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    try:
        # 실제 기록해야될 데이터만 추출
        tid = request.POST.get('paytoken')
        user_id = request.POST.get('payerid')
        pgcode = request.POST.get('pginfo')
        product_name = request.POST.get('servicename')
        custom = request.POST.get('custom')
        custom_parameter = custom.split('_')
        session = custom_parameter[0]
        month_type = custom_parameter[1]
        price = request.POST.get('payamt')
        taxfree_amount = None
        tax_amount = None
        autopay_flag = 'N'
        billkey = None
        refund_yn = 'N'
        refund_date = None
        auto_end_date = None

        # 로깅
        print('INFO -> tid : ', tid)
        print('INFO -> user_id : ', user_id)
        print('INFO -> pgcode : ', pgcode)
        print('INFO -> custom : ', custom)
        print('INFO -> session : ', session)
        print('INFO -> month_type : ', month_type)
        print('INFO -> product_name : ', product_name)
        print('INFO -> price : ', price)
        print('INFO -> taxfree_amount : ', taxfree_amount)
        print('INFO -> tax_amount : ', tax_amount)
        print('INFO -> autopay_flag : ', autopay_flag)
        print('INFO -> billkey : ', billkey)
        print('INFO -> refund_yn : ', refund_yn)
        print('INFO -> refund_date : ', refund_date)
        print('INFO -> auto_end_date : ', auto_end_date)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return HttpResponse("<RESULT>FAIL</RESULT>")

    ph = TblPriceHistory.objects.filter(tid=tid)
    if len(ph) != 0:
        return HttpResponse("<RESULT>FAIL</RESULT>")
    # 요금 충전
    giveServiceTime(user_id, session, month_type)

    # 결제 내역 데이터베이스 기록 (해외)
    tph = TblPriceHistory(
        tid = tid,
        user_id = user_id,
        pgcode = pgcode,
        product_name = product_name,
        session = session,
        month_type = month_type,
        krw = None,
        usd = price,
        jpy = None,
        cny = None,
        taxfree_amount = taxfree_amount,
        tax_amount = tax_amount,
        autopay_flag = autopay_flag,
        billkey = billkey,
        refund_yn = refund_yn,
        regist_date = datetime.datetime.now(),
        refund_date = refund_date,
        auto_end_date = auto_end_date
    )
    tph.save()

    return HttpResponse("<RESULT>OK</RESULT>")



# 페이레터 국내 - 콜백처리 (2019.09.21 13:04 점검완료)
@csrf_exempt
def payletter_callback(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_KOREA_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # callback body 데이터 로깅 ... 국내 모듈은 callback post 가 없음
    f = open(payment_root + 'callback_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # body 파싱
    try:
        r = json.loads(request.body)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return JsonResponse({"code":1, "message":"JSON 디코딩 실패"})

    try:
        # 실제 기록해야될 데이터만 추출
        tid = r['tid']
        user_id = r['user_id']
        pgcode = r['pgcode']
        product_name = r['product_name']
        custom = r['custom_parameter']
        custom_parameter = custom.split('_')
        session = custom_parameter[0]
        month_type = custom_parameter[1]
        price = r['amount']
        taxfree_amount = r['taxfree_amount']
        tax_amount = r['tax_amount']

        # 자동결제 여부 확인 (custom_parameter: session_month_autopay)
        is_autopay = len(custom_parameter) >= 3 and custom_parameter[2] == 'autopay'
        autopay_flag = 'Y' if is_autopay else 'N'
        billkey = r.get('billkey', None)
        refund_yn = 'N'
        refund_date = None
        auto_end_date = None

        # 로깅
        print('INFO -> tid : ', tid)
        print('INFO -> user_id : ', user_id)
        print('INFO -> pgcode : ', pgcode)
        print('INFO -> custom : ', custom)
        print('INFO -> session : ', session)
        print('INFO -> month_type : ', month_type)
        print('INFO -> product_name : ', product_name)
        print('INFO -> price : ', price)
        print('INFO -> taxfree_amount : ', taxfree_amount)
        print('INFO -> tax_amount : ', tax_amount)
        print('INFO -> autopay_flag : ', autopay_flag)
        print('INFO -> billkey : ', billkey)
        print('INFO -> refund_yn : ', refund_yn)
        print('INFO -> refund_date : ', refund_date)
        print('INFO -> auto_end_date : ', auto_end_date)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return JsonResponse({"code":1, "message":"JSON 디코딩 실패"})

    # 요금 충전
    giveServiceTime(user_id, session, month_type)

    # 결제 내역 데이터베이스 기록 (국내)
    tph = TblPriceHistory(
        tid = tid,
        user_id = user_id,
        pgcode = pgcode,
        product_name = product_name,
        session = session,
        month_type = month_type,
        krw = price,
        usd = None,
        jpy = None,
        cny = None,
        taxfree_amount = taxfree_amount,
        tax_amount = tax_amount,
        autopay_flag = autopay_flag,
        billkey = billkey,
        refund_yn = refund_yn,
        regist_date = datetime.datetime.now(),
        refund_date = refund_date,
        auto_end_date = auto_end_date
    )
    tph.save()

    # 자동결제 등록: billkey가 있으면 tbl_autopay에 저장
    if is_autopay and billkey:
        try:
            from dateutil.relativedelta import relativedelta
            cursor = connections['default'].cursor()

            # 기존 active 자동결제가 있으면 해지 처리
            cursor.execute(
                "UPDATE tbl_autopay SET status='cancelled', cancelled_date=NOW() WHERE user_id=%s AND status='active'",
                [user_id]
            )

            # 다음 결제일 계산
            next_pay = datetime.datetime.now() + relativedelta(months=int(month_type))

            cursor.execute('''
                INSERT INTO tbl_autopay (user_id, billkey, pgcode, session, month_type, product_name, amount, status, last_paid_date, next_pay_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW(), %s)
            ''', [user_id, billkey, pgcode, session, month_type, product_name, price, next_pay])
            print('INFO [AUTOPAY] -> 자동결제 등록 완료: user_id=%s, next_pay=%s' % (user_id, next_pay))
        except BaseException as err:
            print('ERROR [AUTOPAY] -> 자동결제 등록 실패: ', err)

    return JsonResponse({"code":0, "message":""})
