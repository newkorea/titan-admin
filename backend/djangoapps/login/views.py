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
from django.conf import settings


# 로그인 페이지 렌더링 (2019.09.15 10:21 점검완료)
def login(request):
    return render(request, 'login/admin_login.html')


# 로그아웃 API (2019.09.15 10:21 점검완료)
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


# 로그인 API (2019.09.15 10:21 점검완료)
def api_login(request):

    login_email = request.POST.get('input_id')
    login_password = request.POST.get('input_pw')
    login_ip = get_client_ip(request)

    # 입력 파라미터 로깅
    print('INFO -> login_email : ', login_email)
    print('INFO -> login_password : ', login_password)
    print('INFO -> login_ip : ', login_ip)

    # 입력 파라미터 공백 유효성 체크
    if login_email == '':
        return JsonResponse({'result': 400})
    elif login_password == '':
        return JsonResponse({'result': 400})

    # 아이디 존재 여부 확인
    try:
        u1 = TblUser.objects.get(email=login_email)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return JsonResponse({'result': 600})

    user_password = u1.password
    user_id = u1.id

    # 로그인횟수 존재 여부 확인
    try:
        u2 = TblUserLogin.objects.get(user_id=user_id)
    except BaseException as err:
        print('ERROR -> err : ', err)
        return JsonResponse({'result': 601})

    user_attempt = u2.attempt
    print('INFO -> user_attempt : ', user_attempt)

    # 비밀번호 시도 회수 초과 시 계정 잠금
    if user_attempt >= settings.LOGIN_FAIL_ATTEMPT:
        return JsonResponse({'result': 300})

    match_result = matchHashedText(user_password, login_password)
    # 로그인 성공
    if match_result == True:
        try:
            with transaction.atomic():
                # 일반 계정 접근 시
                if u1.is_staff == 0:
                    u2.attempt = 99999
                    u2.save()
                    print('INFO -> You have locked your account by trying to access the general account')
                    return JsonResponse({'result': 700})

                # 관리자 계정 정상 정급 시
                u1.login_ip = login_ip
                u2.attempt = 0
                u2.login_date = datetime.now()
                u1.save()
                u2.save()
                request.session['id'] = u1.id
                request.session['email'] = u1.email
                request.session['username'] = u1.username
                request.session['is_staff'] = u1.is_staff
                print("INFO -> Login Success")
                return JsonResponse({'result': 200})
        except BaseException as err:
            print('ERROR -> err : ', err)
            return JsonResponse({'result': 500})
    # 로그인 실패
    else:
        try:
            with transaction.atomic():
                u1.login_ip = login_ip
                u2.attempt = u2.attempt + 1
                u2.login_date = datetime.now()
                u1.save()
                u2.save()
                print("INFO -> Login Fail")
                return JsonResponse({'result': 600})
        except BaseException as err:
            print('ERROR -> err : ', err)
            return JsonResponse({'result': 500})

    return JsonResponse({'result': 200})
