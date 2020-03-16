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
from backend.djangoapps.common.swal import get_swal
from django.utils import translation
from django.conf import settings


# 로그인 페이지 렌더링 (2020-03-16)
def login(request):
    return render(request, 'admin/login.html')


# 로그아웃 API (2020-03-16)
@login_check
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


# 로그인 API (2020-03-16)
def api_login(request):

    login_email = request.POST.get('input_id')
    login_password = request.POST.get('input_pw')
    login_ip = get_client_ip(request)

    # 입력 파라미터 로깅
    print('INFO -> login_email : ', login_email)
    print('INFO -> login_password : ', login_password)
    print('INFO -> login_ip : ', login_ip)

    # allow ip 체크
    try:
        allow_ip = TblAllowIp.objects.get(ip=login_ip)
    except BaseException as err:
        title, text = get_swal('NOT_ALLOW_IP')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 입력 파라미터 공백 유효성 체크
    if login_email == '':
        title, text = get_swal('NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    elif login_password == '':
        title, text = get_swal('NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 아이디 존재 여부 확인
    try:
        u1 = TblUser.objects.get(email=login_email)
    except BaseException as err:
        title, text = get_swal('INCORRECT_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    user_password = u1.password
    user_id = u1.id

    # 로그인횟수 존재 여부 확인
    try:
        u2 = TblUserLogin.objects.get(user_id=user_id)
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    user_attempt = u2.attempt
    print('INFO -> user_attempt : ', user_attempt)

    # 비밀번호 시도 회수 초과 시 계정 잠금
    if user_attempt >= settings.LOGIN_FAIL_ATTEMPT:
        title, text = get_swal('OVER_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    match_result = matchHashedText(user_password, login_password)
    # 로그인 성공
    if match_result == True:
        try:
            with transaction.atomic():
                # 관리자 계정 정상 접근 시
                u1.login_ip = login_ip
                u2.attempt = 0
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()
                request.session['id'] = u1.id
                request.session['email'] = u1.email
                request.session['username'] = u1.username
                request.session['is_staff'] = u1.is_staff
                print("INFO -> Login Success")
                return JsonResponse({'result': 200})
        except BaseException as err:
            title, text = get_swal('UNKNOWN_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    # 로그인 실패
    else:
        try:
            with transaction.atomic():
                u1.login_ip = login_ip
                u2.attempt = u2.attempt + 1
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()
                title, text = get_swal('INCORRECT_LOGIN')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        except BaseException as err:
            title, text = get_swal('UNKNOWN_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
