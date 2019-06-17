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


def login(request):

    print('this is login views')

    return render(request, 'login/admin_login.html')


def api_logout(request):
    
    if 'id' in request.session:
        del request.session['id']
    if 'email' in request.session:
        del request.session['email']
    if 'username' in request.session:
        del request.session['username']
    if 'is_staff' in request.session:
        del request.session['is_staff']

    return JsonResponse({'result': 200})


def api_login(request):

    login_email = request.POST.get('input_id')
    login_password = request.POST.get('input_pw')
    login_ip = get_client_ip(request)

    print('login_email -> ', login_email)
    print('login_password -> ', login_password)
    print('login_ip -> ', login_ip)

    # 백엔드 유효성 체크
    if login_email == '':
        return JsonResponse({'result': 400})
    elif login_password == '':
        return JsonResponse({'result': 400})

    try:
        u1 = TblUser.objects.get(email=login_email)
    except BaseException as err:
        print('-----------------------')
        print(err)
        print('-----------------------')
        return JsonResponse({'result': 600}) # 아이디 존재 X

    user_password = u1.password
    user_id = u1.id

    try:
        u2 = TblUserLogin.objects.get(user_id=user_id)
    except BaseException as err:
        print('-----------------------')
        print(err)
        print('-----------------------')
        return JsonResponse({'result': 500}) # 데이터 꼬임 버그

    user_attempt = u2.attempt

    print('user_id -> ', user_id)
    print('user_attempt -> ', user_attempt)

    if user_attempt >= 5:
        return JsonResponse({'result': 300}) # 계정 잠금

    match_result = matchHashedText(user_password, login_password)
    if match_result == True:
        try:
            with transaction.atomic():
                print('u1.is_staff -> ', u1.is_staff)
                if u1.is_staff == 0:
                    u2.attempt = 99999
                    u2.save()
                    return JsonResponse({'result': 700}) # 접근 권한 없음

                u1.login_ip = login_ip
                u2.attempt = 0
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()

                # session up
                request.session['id'] = u1.id
                request.session['email'] = u1.email
                request.session['username'] = u1.username
                request.session['is_staff'] = u1.is_staff

                return JsonResponse({'result': 200}) # 로그인 성공
        except BaseException as err:
            print('-----------------------')
            print(err)
            print('-----------------------')
            return JsonResponse({'result': 500}) # 데이터 꼬임 버그

    else:
        try:
            with transaction.atomic():
                u1.login_ip = login_ip
                u2.attempt = u2.attempt + 1
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()
                return JsonResponse({'result': 600}) # 비밀번호 틀림
        except BaseException as err:
            print('-----------------------')
            print(err)
            print('-----------------------')
            return JsonResponse({'result': 500}) # 데이터 꼬임 버그

    return JsonResponse({'result': 200})