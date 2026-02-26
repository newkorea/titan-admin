import os
import json
import datetime
import hashlib
import uuid
from pytz import timezone
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from backend.models import *
from backend.models_radius import Radcheck


# 페이박스 위쳇페이 - 리턴 (2019.11.10 11.35 점검완료)
@csrf_exempt
def paybox_return(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_PAYBOX_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # return body 데이터 로깅
    f = open(payment_root + 'return_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # return post 데이터 로깅
    f = open(payment_root + 'return_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    context = {}
    return redirect('/mypage')


# 페이레터 해외 리턴 (2019.09.21 12:36 점검완료)
@csrf_exempt
def globalpayletter_return(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    print('API PARAM DEBUG -> test : ', 'test')
    payment_root = settings.PAYMENT_GLOBAL_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # return body 데이터 로깅
    f = open(payment_root + 'return_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # return post 데이터 로깅
    f = open(payment_root + 'return_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    context = {}
    return render(request, 'new/payletter_return.html', context)


# 페이레터 국내 리턴 (2019.09.21 12:36 점검완료)
@csrf_exempt
def payletter_return(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_KOREA_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # return body 데이터 로깅
    f = open(payment_root + 'return_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # return post 데이터 로깅
    f = open(payment_root + 'return_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    context = {}

    # 가상계좌인 경우 계좌 정보를 화면에 전달
    pgcode = request.POST.get('pgcode', '')
    if pgcode == 'virtualaccount':
        context['is_virtual'] = True
        context['bank_name'] = request.POST.get('bank_name', '')
        context['account_no'] = request.POST.get('account_no', '')
        context['account_holder'] = request.POST.get('account_holder', '')
        context['amount'] = request.POST.get('amount', '')
        context['expire_date'] = request.POST.get('expire_date', '')
        context['product_name'] = request.POST.get('product_name', '')

        # 만기일 포맷 변환 (20260305 -> 2026-03-05)
        ed = context['expire_date']
        if ed and len(ed) == 8:
            context['expire_date_fmt'] = ed[:4] + '-' + ed[4:6] + '-' + ed[6:8]
        else:
            context['expire_date_fmt'] = ed

        # 금액 포맷 (콤마)
        try:
            context['amount_fmt'] = '{:,}'.format(int(context['amount']))
        except:
            context['amount_fmt'] = context['amount']

    return render(request, 'new/payletter_return.html', context)


# 엑심베이 국내 리턴 (2020-07-14)
@csrf_exempt
def eximbay_return(request):

    # 디렉토리가 없다면 로깅 디렉토리 생성
    payment_root = settings.PAYMENT_EXIMBAY_ROOT
    if not os.path.exists(payment_root):
        os.makedirs(payment_root)

    now = datetime.datetime.now().strftime('%Y%m%d')
    logTime = datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')

    # return body 데이터 로깅
    f = open(payment_root + 'return_body_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.body) + '\n')
    f.close()

    # return post 데이터 로깅
    f = open(payment_root + 'return_post_' + now, 'a', encoding='utf-8')
    f.write(logTime + '\t' + str(request.POST) + '\n')
    f.close()

    # -------------------------------------------------------
    '''
    # 반환값 파싱
    try:
        body = request.body.decode('ascii')
        data_set = body.split('&')
        result_data = {}
        for data in data_set:
            data = data.split('=')
            data[0]
            data[1]
            result_data[data[0]] = data[1]
    except BaseException as err:
        print('ERROR -> err : ', err)
        return HttpResponse("rescode=5000&resmsg=Error")

    # 정상 데이터인 경우 결제 처리
    if result_data['rescode'] == '0000':
        try:
            tid = result_data['transid']
            user_id = int(result_data['param2'])
            pgcode = result_data['paymethod']
            custom = result_data['param1']
            custom_parameter = custom.split('_')
            session = custom_parameter[0]
            month_type = custom_parameter[1]
            product_name = makeProductName(session, month_type)
            price = result_data['amt']
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
            return HttpResponse("rescode=5000&resmsg=Error")

        # 요금 충전
        giveServiceTime(user_id, session, month_type)

        # 결제 내역 데이터베이스 기록 (엑심베이)
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
        return HttpResponse("rescode=0000&resmsg=Success")
    else:
        return HttpResponse("rescode=5000&resmsg=Error")
    '''
    # -------------------------------------------------------
    return redirect('/price')
    