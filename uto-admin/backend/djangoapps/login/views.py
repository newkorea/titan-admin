# 로그인/인증 — 관리자 로그인, 세션 관리 (24시간 타임아웃)
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


# 로그인 API — vcsvpn2013.admins 테이블 인증
def api_login(request):
    import hashlib

    login_id = request.POST.get('input_id', '').strip()
    login_password = request.POST.get('input_pw', '').strip()
    login_ip = get_client_ip(request)

    print('INFO -> login_id : ', login_id)
    print('INFO -> login_ip : ', login_ip)

    # 입력 파라미터 공백 유효성 체크
    if login_id == '':
        title, text = get_swal('NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    elif login_password == '':
        title, text = get_swal('NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # vcsvpn2013.admins 테이블에서 아이디 조회
    cursor = connections['uto'].cursor()
    cursor.execute("SELECT id, adminuser, adminpass, role, dealer_name FROM admins WHERE adminuser = %s", [login_id])
    row = cursor.fetchone()

    if not row:
        title, text = get_swal('INCORRECT_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    admin_id = row[0]
    admin_user = row[1]
    admin_pass = row[2]
    admin_role = row[3]       # 1=최고관리자, 2=관리자, 3=대리점
    admin_dealer = row[4]     # vpnuser.member 매칭명

    # MD5 비밀번호 검증
    input_hash = hashlib.md5(login_password.encode('utf-8')).hexdigest()
    if input_hash != admin_pass:
        title, text = get_swal('INCORRECT_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 로그인 성공 — 세션 설정
    request.session['id'] = admin_id
    request.session['email'] = admin_user
    request.session['username'] = admin_user
    request.session['is_staff'] = 1
    request.session['role'] = admin_role
    request.session['dealer_name'] = admin_dealer or ''
    request.session['rec'] = ''
    print("INFO -> Login Success (admins table) : ", admin_user, "role:", admin_role, "dealer:", admin_dealer)
    return JsonResponse({'result': 200})
