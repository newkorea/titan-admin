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
from backend.djangoapps.common.gom import GomPay
from backend.djangoapps.common.paybox import Paybox
from backend.models import *
from backend.models_radius import Radcheck


# 페이박스 위쳇페이 - 결제페이지 요청 (2019.11.10 11.35 점검완료)
def api_make_paybox(request):
    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    product_name = makeProductName(session, month_type)
    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> user_name : ', user_name)
    print('DEBUG -> pgcode : ', pgcode)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month_type : ', month_type)
    print('DEBUG -> product_name : ', product_name)

    price = getProductPirce(session, month_type, 'CNY')
    print('DEBUG -> price : ', price)
    print('DEBUG -> price : ', type(price))

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(u1):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    box = Paybox(settings.PAYBOX_MODE)
    html = box.payments_request(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email
    )

    print('DEBUG -> html : ', html)

    return JsonResponse({'result': html})


# 페이레터 해외 - 결제 페이지 요청 (2019.09.10 10:35 점검완료) payletter global 
def api_make_globalpayletter(request):

    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    product_name = makeProductName(session, month_type)
    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> user_name : ', user_name)
    print('DEBUG -> pgcode : ', pgcode)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month_type : ', month_type)
    print('DEBUG -> product_name : ', product_name)

    price = getProductPirce(session, month_type, 'USD')
    print('DEBUG -> price : ', price)

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(u1):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    gp = PayletterGlobal(settings.PAYLETTER_MODE)
    payload = gp.payments_request(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email,
        'web'
    )

    print('DEBUG -> payload : ', payload)

    return JsonResponse({'result': payload})


# 페이레터 국내 - 결제 페이지 요청 (2019.09.10 10:35 점검완료)
def api_make_payletter(request):

    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    product_name = makeProductName(session, month_type)

    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> user_name : ', user_name)
    print('DEBUG -> pgcode : ', pgcode)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month_type : ', month_type)
    print('DEBUG -> product_name : ', product_name)

    price = getProductPirce(session, month_type, 'KRW')
    print('DEBUG -> price : ', price)

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(u1):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    p = Payletter(settings.PAYLETTER_MODE)
    res = p.payments_request(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email
    )
    res = json.loads(res)
    online_url = res['online_url']

    print('DEBUG -> online_url : ', online_url)

    return JsonResponse({'result': online_url})


# 페이레터 국내 - 자동결제 등록 결제 요청 (autopay_flag=Y)
def api_make_payletter_autopay(request):

    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    product_name = makeProductName(session, month_type)

    print('DEBUG [AUTOPAY] -> user_id : ', user_id)
    print('DEBUG [AUTOPAY] -> pgcode : ', pgcode)
    print('DEBUG [AUTOPAY] -> session : ', session)
    print('DEBUG [AUTOPAY] -> month_type : ', month_type)

    # 자동결제는 신용카드만 가능
    if pgcode not in ('creditcard', 'PLCreditCardMpi'):
        return JsonResponse({'result': 'fail', 'message': '자동결제는 신용카드만 가능합니다'})

    price = getProductPirce(session, month_type, 'KRW')
    u1 = TblUser.objects.get(id=user_id)

    if duplicatePaymentProtect(u1):
        return JsonResponse({'result': 'fail'})

    order_no = createOrderNumber(user_id)
    # custom_parameter에 autopay 표시 추가: session_month_autopay
    custom_parameter = str(session) + '_' + str(month_type) + '_autopay'

    p = Payletter(settings.PAYLETTER_MODE)
    res = p.payments_request_autopay(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email
    )
    res = json.loads(res)
    online_url = res.get('online_url', '')

    if not online_url:
        print('ERROR [AUTOPAY] -> no online_url:', res)
        return JsonResponse({'result': 'fail'})

    return JsonResponse({'result': online_url})
