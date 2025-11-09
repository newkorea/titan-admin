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
from backend.djangoapps.common.eximbay import EximBay
from backend.djangoapps.common.eximbay_aes import AesCrypt256
from backend.models import *
from backend.models_radius import Radcheck


# 엑심베이 위쳇페이 - 결제페이지 요청 (2020-06-28)
def api_make_eximbay(request):
    target_email = request.POST.get('target_email')
    try:
        if target_email:
            target_user = TblUser.objects.get(email=target_email)
            user_id = target_user.id
            user_name = target_user.username
        else:
            user_id = request.session['id']
            user_name = request.session['username']
            target_user = TblUser.objects.get(id=user_id)
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 'fail', 'message': 'User not found'})

    pgcode = request.POST.get('pgcode')
    pgcode = convertEximbayCode(pgcode)
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
    print('DEBUG -> price : ', type(price))

    u1 = target_user

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(u1):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    if settings.EXIMBAY_MODE == 'TEST':
        url = settings.EXIMBAY_TEST_ENDPOINT
        mid = settings.EXIMBAY_TEST_MID
        secret_key = settings.EXIMBAY_TEST_SECRET_KEY
    else: 
        url = settings.EXIMBAY_LIVE_ENDPOINT
        mid = settings.EXIMBAY_LIVE_MID
        secret_key = settings.EXIMBAY_LIVE_SECRET_KEY
    ver = 230
    not_use = 'not_use'
    paymethod = pgcode # P141 (Wechat), P101 (VISA), P003 (ALIPAY)
    txntype = 'PAYMENT'
    ref = order_no
    cur = 'USD'
    buyer = 'Buyer'
    lang = 'KR'
    item_0_quantity = '1'
    displaytype = 'P'
    if settings.HTTPS == True:
        returnurl = 'https://{}/eximbay_return'.format(settings.FULL_URL)
        statusurl = 'https://{}/eximbay_callback'.format(settings.FULL_URL)
    elif settings.HTTPS == False:
        returnurl = 'http://{}/eximbay_return'.format(settings.FULL_URL)
        statusurl = 'http://{}/eximbay_callback'.format(settings.FULL_URL)
    payload = {
        'ver': ver,
        'mid': mid,
        'txntype': txntype,
        'ref': ref,
        'cur': cur,
        'amt': price,
        'paymethod': paymethod,
        'buyer': buyer,
        'email': u1.email,
        'lang': lang,
        'returnurl': returnurl,
        'statusurl': statusurl,
        'item_0_product': product_name,
        'item_0_quantity': item_0_quantity,
        'item_0_unitPrice': price,
        'shipTo_city': not_use,
        'shipTo_country': not_use,
        'shipTo_firstName': not_use,
        'shipTo_lastName': not_use,
        'shipTo_phoneNumber': not_use,
        'shipTo_postalCode': not_use,
        'shipTo_state': not_use,
        'shipTo_street1': not_use,
        'displaytype': displaytype,
        'param1': custom_parameter, # <session>_<month_type>
        'param2': user_id # user_id
    }
    sort_payload = dict(sorted(payload.items()))

    a = '&'.join(['%s=%s' % (key, value) for (key, value) in sort_payload.items()])
    b = '{secret_key}?{string_sort_payload}'.format(secret_key=secret_key, string_sort_payload=a)
    c = hashlib.sha256(b.encode('utf-8')).hexdigest()

    print('a = ', a)
    print('b = ', b)
    print('c = ', c)

    payload['fgkey'] = c
    return JsonResponse({
        'fgkey': c,
        'ver': ver,
        'mid': mid,
        'txntype': txntype,
        'ref': ref,
        'cur': cur,
        'amt': price,
        'paymethod': paymethod,
        'buyer': buyer,
        'email': u1.email,
        'lang': lang,
        'returnurl': returnurl,
        'statusurl': statusurl,
        'item_0_product': product_name,
        'item_0_quantity': item_0_quantity,
        'item_0_unitPrice': price,
        'shipTo_city': not_use,
        'shipTo_country': not_use,
        'shipTo_firstName': not_use,
        'shipTo_lastName': not_use,
        'shipTo_phoneNumber': not_use,
        'shipTo_postalCode': not_use,
        'shipTo_state': not_use,
        'shipTo_street1': not_use,
        'displaytype': displaytype,
        'param1': custom_parameter, # <session>_<month_type>
        'param2': user_id, # user_id
        'url': url
    })


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
    target_email = request.POST.get('target_email')
    try:
        if target_email:
            target_user = TblUser.objects.get(email=target_email)
            user_id = target_user.id
            user_name = target_user.username
        else:
            user_id = request.session['id']
            user_name = request.session['username']
            target_user = TblUser.objects.get(id=user_id)
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 'fail', 'message': 'User not found'})
        
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

    u1 = target_user

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
    target_email = request.POST.get('target_email')
    try:
        if target_email:
            target_user = TblUser.objects.get(email=target_email)
            user_id = target_user.id
            user_name = target_user.username
        else:
            user_id = request.session['id']
            user_name = request.session['username']
            target_user = TblUser.objects.get(id=user_id)
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 'fail', 'message': 'User not found'})

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

    u1 = target_user

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
