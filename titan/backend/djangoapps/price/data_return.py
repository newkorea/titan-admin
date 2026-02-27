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

    