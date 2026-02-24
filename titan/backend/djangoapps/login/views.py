import json
import datetime
import re
import uuid
import requests
from django.shortcuts import render
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt, ensure_csrf_cookie
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
from backend.models_radius import *
from backend.djangoapps.common.views import *
from backend.djangoapps.common.smtp import send_email
from backend.djangoapps.common.swal import get_swal
from django.utils import translation
from django.utils.translation import ugettext as _
import ipaddress
from django.middleware.csrf import get_token
import logging

logger = logging.getLogger(__name__)


# 로그인 페이지 렌더링 (2020-03-09)
@ensure_csrf_cookie
def login(request):
    request.session['x'] = 'x'
    # 로그인 후 이동링크
    try:
        next = request.GET.get('next')
        if next == '' or next == None:
            next = ''
        print('DEBUG -> next : ', next)
    except BaseException:
        next = ''
    # 로그인 세션이 이미 있다면 바로 마이페이지로 이동시켜 중복 로그인 단계를 건너뜀
    if 'email' in request.session:
        return redirect('/mypage')
    context = {}
    context['next'] = next
    return render(request, 'new/login.html', context)


# 회원가입 페이지 렌더링 (2020-03-09)
def regist(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    # QR CODE 추천인
    try:
        code = request.GET.get('code')
        if code == '' or code == None:
            code = ''
        print('DEBUG -> QR code : ', code)
    except BaseException:
        code = ''
    context = {}
    context['code'] = code
    context['LANGUAGE_CODE'] = LANGUAGE_CODE
    return render(request, 'new/sign-up.html', context)


# 비밀번호찾기 렌더링 (2020-03-09)
def forgot_password(request):
    email = request.GET.get('email', '')
    context = {
        'email': email,
        'csrf_token': get_token(request),
    }
    return render(request, 'new/password-reset.html', context)


# 비밀번호 변경 페이지 렌더링 (2020-03-09)
def change_password(request):
    context = {}
    return render(request, 'new/change-password.html', context)


# 로그인 API (2020-03-10)
def api_login_signin(request):

    # 입력 파라미터
    LANGUAGE_CODE = request.LANGUAGE_CODE
    login_email = request.POST.get('login_email')
    login_password = request.POST.get('login_password')
    login_ip = get_client_ip(request)
    print('INFO -> LANGUAGE_CODE : ', LANGUAGE_CODE)
    print('INFO -> login_email : ', login_email)
    print('INFO -> login_password : ', login_password)
    print('INFO -> login_ip : ', login_ip)

    # 백엔드 유효성 체크
    if login_email == '':
        title, text = get_swal(LANGUAGE_CODE, 'NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    elif login_password == '':
        title, text = get_swal(LANGUAGE_CODE, 'NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 아이디 존재여부 체크
    try:
        u1 = TblUser.objects.get(email=login_email)
    except BaseException:
        title, text = get_swal(LANGUAGE_CODE, 'INCORRECT_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    user_password = u1.password
    user_id = u1.id

    # 활성화 여부 체크
    if u1.is_active == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_ACTIVE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # ===== 접속금지(차단) 체크 (2026-02-11) =====
    try:
        from backend.models import TblBannedDevice
        from django.db.models import Q
        ban_q = Q(email=login_email)
        if login_ip:
            ban_q |= Q(device_ip=login_ip)
        if TblBannedDevice.objects.filter(ban_q, is_active=1).exclude(device_ip='', email='').exists():
            return JsonResponse({'result': 500, 'title': '접속 차단', 'text': '이 계정은 접속이 금지되었습니다.'})
    except Exception as ban_err:
        print('WARN -> web login ban check error:', ban_err)

    # 로그인 테이블 체크
    try:
        u2 = TblUserLogin.objects.get(user_id=user_id)
    except BaseException:
        title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    user_attempt = u2.attempt

    print('INFO -> user_id : ', user_id)
    print('INFO -> user_attempt : ', user_attempt)

    # 로그인 시도 초과 시 계정 잠금
    if user_attempt >= 100:
        title, text = get_swal(LANGUAGE_CODE, 'OVER_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 비밀번호 체크
    match_result = matchHashedText(user_password, login_password)
    print('INFO -> match_result : ', match_result)
    if match_result == True:
        try:
            with transaction.atomic():
                u1.login_ip = login_ip
                u2.attempt = 0
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()

                # 로그인 성공
                request.session['id'] = u1.id
                request.session['email'] = u1.email
                request.session['username'] = u1.username
                request.session['rec'] = u1.rec
                return JsonResponse({'result': 200})
        except BaseException as err:
            print("err => ", err)
            title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    else:
        try:
            with transaction.atomic():
                # 로그인 실패
                u1.login_ip = login_ip
                u2.attempt = u2.attempt + 1
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()
                title, text = get_swal(LANGUAGE_CODE, 'INCORRECT_LOGIN')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        except BaseException as err:
            print("err => ", err)
            title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})


# 로그아웃 API (2020-03-10)
def logout(request):
    if 'id' in request.session:
        del request.session['id']
    if 'email' in request.session:
        del request.session['email']
    if 'username' in request.session:
        del request.session['username']
    return redirect('/login')


# 오너 계정이 자신의 서브계정으로 로그인 후 이동 (2025-11-04)
def login_as_subaccount(request):
    next_url = request.GET.get('next', '/price')
    if 'id' not in request.session:
        return redirect('/login?next=' + quote(next_url))

    try:
        owner = TblUser.objects.get(id=request.session['id'])
    except TblUser.DoesNotExist:
        return redirect('/login?next=' + quote(next_url))

    base_email = owner.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)

    try:
        target_user_id = int(request.GET.get('target_user_id'))
    except Exception:
        return redirect('/price')

    try:
        target = TblUser.objects.get(id=target_user_id, delete_yn='N')
    except TblUser.DoesNotExist:
        return redirect('/price')

    # 보안: 대상 계정이 오너의 서브계정인지 확인
    if target.parent_user_id == owner.id:
        pass
    elif target.parent_user_id is None and target.email.startswith(base_email + '_'):
        TblUser.objects.filter(id=target.id, parent_user_id__isnull=True).update(parent_user_id=owner.id)
        target.parent_user_id = owner.id
    else:
        return redirect('/price')

    # 세션 전환: 기존 세션 위에 서브계정으로 덮어씀, parent_id 기록
    request.session['parent_id'] = owner.id
    request.session['id'] = target.id
    request.session['email'] = target.email
    request.session['username'] = target.username
    request.session['rec'] = target.rec

    return redirect(next_url)


# 회원가입 API (2020-03-10)
def api_login_signup(request):

    # 입력 파라미터
    LANGUAGE_CODE = request.LANGUAGE_CODE
    regist_email = request.POST.get('regist_email').strip()
    regist_username = request.POST.get('regist_username').strip()
    regist_password = request.POST.get('regist_password').strip()
    regist_password_re = request.POST.get('regist_password_re').strip()
    regist_rec = request.POST.get('regist_rec').strip()
    regist_check1 = request.POST.get('regist_check1')
    regist_check2 = request.POST.get('regist_check2')
    regist_ip = get_client_ip(request)
    regist_hash_password = hashText(regist_password)
    regist_my_rec = gernerateRec(regist_email)
    
    # 입력 파라미터 (로깅)
    print('INFO -> LANGUAGE_CODE : ', LANGUAGE_CODE)
    print('INFO -> regist_email : ', regist_email)
    print('INFO -> regist_username : ', regist_username)
    print('INFO -> regist_password : ', regist_password)
    print('INFO -> regist_password_re : ', regist_password_re)
    print('INFO -> regist_rec : ', regist_rec)
    print('INFO -> regist_check1 : ', regist_check1)
    print('INFO -> regist_check2 : ', regist_check2)
    print('INFO -> regist_ip : ', regist_ip)
    print('INFO -> regist_my_rec : ', regist_my_rec)

    # 차단 리스트 생성
    dm_ban = TblRegistBan.objects.filter(type='DM', delete_yn='N')
    ip_ban = TblRegistBan.objects.filter(type='IP', delete_yn='N')
    dm_list = [dm.content for dm in dm_ban]
    ip_list = [ip.content for ip in ip_ban]

    # 1. 도메인 차단
    try:
        email_domain = regist_email.split('@')[1]
        for dm in dm_list:
            if email_domain.find(dm) != -1:
                print('INFO -> DOMAIN BAN ({dm})'.format(dm=dm))
                title, text = get_swal(LANGUAGE_CODE, 'BAN_DOMAIN')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 2. 아이피 차단
    for banned_ip in ip_list:
        # CIDR 표기법 사용 여부 확인
        if '/' in banned_ip:
            banned_network = ipaddress.IPv4Network(banned_ip, strict=False)
            if ipaddress.IPv4Address(regist_ip) in banned_network:
                print('INFO -> IP BAN ({regist_ip})'.format(regist_ip=regist_ip))
                title, text = get_swal(LANGUAGE_CODE, 'BAN_IP')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        else:
            # CIDR 표기법이 아닌 경우 일반적인 IP 비교
            if regist_ip == banned_ip:
                print('INFO -> IP BAN ({regist_ip})'.format(regist_ip=regist_ip))
                title, text = get_swal(LANGUAGE_CODE, 'BAN_IP')
                return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 공백 유효성 체크
    if len(regist_email) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_username) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_USERNAME')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_password) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_password_re) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_RE_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 특수 유효성 체크
    if regist_check1 == 'false':
        title, text = get_swal(LANGUAGE_CODE, 'NON_CHECK_SERVICE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if regist_check2 == 'false':
        title, text = get_swal(LANGUAGE_CODE, 'NON_CHECK_PRIVACY')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if regist_email.find('@') == -1:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if regist_password != regist_password_re:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_MATCH_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_password) < 8:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 이메일 존재여부 체크
    user = TblUser.objects.filter(email=regist_email)
    if len(user) != 0:
        title, text = get_swal(LANGUAGE_CODE, 'EXIST_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 비밀번호 2조합 이상 체크
    rule_cnt = 0
    sp_txt = re.findall("[\!\@\#\$\%\^\&\*\(\)\-\=\_\+\~]", regist_password)
    if len(sp_txt) > 0:
        rule_cnt += 1
    ap_txt = re.findall("[a-zA-Z]", regist_password)
    if len(ap_txt) > 0:
        rule_cnt += 1
    dg_txt = re.findall("[0-9]", regist_password)
    if len(dg_txt) > 0:
        rule_cnt += 1
    if rule_cnt < 2:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 회원가입 메인 로직
    try:
        with connections['default'].cursor() as cur:
            # 회원정보 생성
            event = TblEventCode.objects.filter(event_code=regist_rec, delete_yn='N')
            referrer = TblUser.objects.filter(rec=regist_rec, delete_yn='N')
            now = datetime.datetime.now(timezone('Asia/Seoul'))
            if regist_rec != "" and len(event) == 0 and len(referrer) == 0 :
                title, text = get_swal(LANGUAGE_CODE, 'ERROR_CODE')
                return JsonResponse({'result': 700, 'title': title, 'text': text})

            if event.count() != 0:
                eventinfo = event[0]
                now = now.strftime('%Y-%m-%d %H:%M:%S') # str
                now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S') # datetime
                if now < eventinfo.start or now > eventinfo.end:
                    title, text = get_swal(LANGUAGE_CODE, 'CODE_EXPIRED')
                    return JsonResponse({'result': 800, 'title': title, 'text': text})
            
            parent_user_id = None
            legacy_match = re.match(r'^(.+@[^@]+?)_\d+$', regist_email)
            if legacy_match:
                base_candidate = legacy_match.group(1)
                try:
                    parent_candidate = TblUser.objects.get(email=base_candidate, delete_yn='N')
                    parent_user_id = parent_candidate.id
                except TblUser.DoesNotExist:
                    parent_user_id = None

            u1 = TblUser(
                email=regist_email,
                password=regist_hash_password,
                username=regist_username,
                phone='',
                phone_country='',
                gender='',
                birth_date='',
                rec=regist_my_rec,
                sns_code='',
                sns_name='',
                regist_rec=regist_rec,
                regist_ip=regist_ip,
                regist_date=datetime.datetime.now(),
                modify_date=None,
                is_active=0,
                is_staff=0,
                delete_yn='N',
                black_yn='N',
                parent_user_id=parent_user_id,
                v2ray_uuid=str(uuid.uuid4()),
            )
            u1.save()

            # 회원정보(로그인) 생성
            u2 = TblUserLogin(
                user_id=u1.id,
                attempt=0
            )
            u2.save()

            # radius 기본정보 생성
            rc = Radcheck(
                username = regist_email,
                attribute = 'Cleartext-Password',
                op = ':=',
                value = str(uuid.uuid4()).replace('-','')
            )
            rc.save(using='radius')

            # FREE_DAY radius 자료형으로 변환
            afterDay = now + datetime.timedelta(settings.FREE_DAY)
            radius_time = enc_radius_time(afterDay)

            # 이벤트 적용 대상 확인
            # 적용 대상일 경우 위 로직 overwrite
            if event.count() == 0:
                print('DEBUG -> 이벤트 대상이 아닙니다')
                pass
            else:
                event = event[0]
                now = now.strftime('%Y-%m-%d %H:%M:%S') # str
                now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S') # datetime
                if now > event.start and now < event.end:
                    print('DEBUG -> 이벤트 코드[{event_code}]가 적용되었습니다'.format(event_code=event.event_code))
                    afterDay = now + datetime.timedelta(event.free_day)
                    radius_time = enc_radius_time(afterDay)
                    sql = '''
                        INSERT INTO tbl_reward_log (rewarder_id, reward_days, event_code, register_date)
                        VALUES ({rewarder_id},{reward_days}, '{event_code}', '{date}')
                        '''.format(rewarder_id=u1.id, reward_days=event.free_day * 24 * 60, event_code=event.event_code, date = datetime.datetime.now())
                    cur.execute(sql)
                    
                    st = TblServiceTime(
                        user_id = u1.id,
                        prev_time = '',
                        prev_time_rad = '',
                        after_time = afterDay,
                        after_time_rad = radius_time,
                        diff = event.free_day * 24 * 60,
                        reason = '이벤트',
                        regist_date = now)
                    st.save()

            print('DEBUG -> now : ', now)
            print('DEBUG -> afterDay : ', afterDay)
            print('DEBUG -> radius_time : ', radius_time)

            # 1. 회원 가입 시 무료 기간 제공
            #   1.1 회원가입 기본 세션
            rci = Radcheck(
                username = regist_email,
                attribute = 'Simultaneous-Use',
                op = ':=',
                value = settings.FREE_SESSION
            )
            rci.save(using='radius')
            #   1.2 회원가입 기본 기간 (FREE_DAY 적용)
            if settings.FREE_FIX_DAY == None:
                rcei = Radcheck(
                    username = regist_email,
                    attribute = 'Expiration',
                    op = ':=',
                    value = radius_time
                )
                rcei.save(using='radius')
            #   1.3 회원가입 기본 기간 (FREE_FIX_DAY 적용)
            else:
                FREE_FIX_DAY = settings.FREE_FIX_DAY
                FREE_FIX_DAY = datetime.datetime.strptime(FREE_FIX_DAY, '%Y-%m-%d %H:%M:%S')
                rcei = Radcheck(
                    username = regist_email,
                    attribute = 'Expiration',
                    op = ':=',
                    value = enc_radius_time(FREE_FIX_DAY)
                )
                rcei.save(using='radius')

            # 이메일 인증 로직
            if settings.SIGNUP_SMTP == True:
                print('INFO -> SMTP logic start')
                # Support alias login IDs like "softcan@naver.com_1" by sending the email to the base mailbox
                # while the activation link targets the actual account email (with suffix).
                base_email = regist_email
                m = re.match(r"^(.+@[^@]+?)_\d+$", regist_email)
                if m:
                    base_email = m.group(1)
                lang = 'ko'
                if LANGUAGE_CODE == 'en':
                    lang = 'en'
                elif LANGUAGE_CODE == 'zh':
                    lang = 'zh'
                send_email(base_email, 1, lang, account_email=u1.email)
                print('INFO -> SMTP logic end')
                title, text = get_swal(LANGUAGE_CODE, 'SUCCESS_SIGNUP')
                return JsonResponse({'result': 200, 'title': title, 'text': text})
            else:
                title, text = get_swal(LANGUAGE_CODE, 'SUCCESS_SIGNUP_SP')
                return JsonResponse({'result': 200, 'title': title, 'text': text})

    except BaseException as err:
        print('[ERROR] api_login_signup = ', err)
        title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# 비밀번호 찾기 API (2020-03-10)
def api_login_forgotpassword(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    forgot_email = request.POST.get('forgot_email')
    print('INFO -> LANGUAGE_CODE : ', LANGUAGE_CODE)
    print('INFO -> forgot_email : ', forgot_email)
    try:
        u1 = TblUser.objects.get(email=forgot_email)
    except BaseException:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_USER')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    if u1:
        try:
            # 이메일 전송 로직
            print('INFO -> SMTP logic start')

            # Support alias login IDs like "softcan@naver.com_1" by sending the email to the base mailbox
            # while the activation link targets the actual account email (with suffix).
            base_email = u1.email
            m = re.match(r"^(.+@[^@]+?)_\d+$", u1.email)
            if m:
                base_email = m.group(1)

            if LANGUAGE_CODE == 'en':
                send_email(base_email, 2, 'en', account_email=u1.email)
            elif LANGUAGE_CODE == 'zh':
                send_email(base_email, 2, 'zh', account_email=u1.email)
            else:
                send_email(base_email, 2, 'ko', account_email=u1.email)
            print('INFO -> SMTP logic end')
            title, text = get_swal(LANGUAGE_CODE, 'SUCCESS_FORGOT')
            return JsonResponse({'result': 200, 'title': title, 'text': text})
        except Exception as err:
            logger.exception('SMTP send failed for forgot password email to %s', u1.email)
            return JsonResponse({
                'result': 500,
                'title': _('Error!'),
                'text': _('Failed to send email. Please contact the administrator.')
            }, status=500)
    else:
        title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# 계정 활성화 API (2020-03-10)
def api_login_active(request):
    active_code = unquote(request.GET.get('active_code'))
    if active_code == None:
        return JsonResponse({'result': 404})

    print('INFO -> active_code : ', active_code)

    try:
        aes = AESCipher()
        dec_email = aes.decrypt(active_code.encode('ascii')).split('|')[1]
    except BaseException:
        return JsonResponse({'result': 404})

    print('INFO -> dec_email : ', dec_email)

    u1 = TblUser.objects.get(email=dec_email)
    u1.is_active = 1
    u1.active_date = datetime.datetime.now()
    u1.save()
    return redirect('/login')


# 비밀번호 찾기 active 코드 체크 API (2020-03-10)
def api_login_fgp(request):

    active_code = unquote(request.GET.get('active_code'))
    if active_code == None:
        return JsonResponse({'result': 404})

    print('INFO -> active_code : ', active_code)

    try:
        aes = AESCipher()
        dec_time_email = aes.decrypt(active_code.encode('ascii'))
    except BaseException:
        return JsonResponse({'result': 404})

    print('INFO -> dec_time_email : ', dec_time_email)

    send_time, dec_email = dec_time_email.split('|')
    now = datetime.datetime.now()
    now_time = now.strftime('%Y-%m-%d %H:%M')
    FMT = '%Y-%m-%d %H:%M'
    time_diff = datetime.datetime.strptime(now_time, FMT) - datetime.datetime.strptime(send_time, FMT)

    print('INFO -> time_diff : ', time_diff)
    print('INFO -> time_diff.days : ', time_diff.days)

    # 하루 이상 경과 시 만료
    if time_diff.days >= 1:
        print('INFO -> Your time has expired and you are going to the Expiration page')
        return redirect('/password_expire')
    else:
        print('INFO -> Go to the Password Change page')
        request.session['fgp_email'] = dec_email
        return redirect('/change_password')


# 비밀번호 변경 페이지 렌더링 (2020-03-10)
def password_expire(request):
    context = {}
    return render(request, 'new/expire.html', context)


# 비밀번호 변경 API (2020-03-10)
def api_reset_password(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    regist_password = request.POST.get('regist_password')
    regist_password_re = request.POST.get('regist_password_re')
    regist_hash_password = hashText(regist_password)
    print('INFO -> LANGUAGE_CODE : ', LANGUAGE_CODE)
    print('INFO -> regist_password : ', regist_password)
    print('INFO -> regist_password_re : ', regist_password_re)

    # 공백 유효성 체크
    if len(regist_password) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_password_re) == 0:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_RE_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if len(regist_password) < 8:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 비밀번호 2조합 이상 체크
    rule_cnt = 0
    sp_txt = re.findall("[\!\@\#\$\%\^\&\*\(\)\-\=\_\+\~]", regist_password)
    if len(sp_txt) > 0:
        rule_cnt += 1
    ap_txt = re.findall("[a-zA-Z]", regist_password)
    if len(ap_txt) > 0:
        rule_cnt += 1
    dg_txt = re.findall("[0-9]", regist_password)
    if len(dg_txt) > 0:
        rule_cnt += 1
    if rule_cnt < 2:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    try:
        target_email = request.session['fgp_email']
    except BaseException as err:
        title, text = get_swal(LANGUAGE_CODE, 'NOT_SESSION')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    u1 = TblUser.objects.get(email=target_email)
    u1.password = regist_hash_password
    # 비활성 계정도 비밀번호 재설정 시 활성화 처리
    if getattr(u1, 'is_active', 0) == 0:
        u1.is_active = 1
        try:
            u1.active_date = datetime.datetime.now()
        except Exception:
            pass
    u1.save()
    title, text = get_swal(LANGUAGE_CODE, 'SUCCESS_RESET')
    return JsonResponse({'result': 200, 'title': title, 'text': text})


# 메일 인증 재전송 (사용자용)
@csrf_protect
def api_send_verify_email(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'title': _('Notification'), 'text': _('Please log in.')})

    try:
        u1 = TblUser.objects.get(id=request.session['id'], delete_yn='N')
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'title': _('Error!'), 'text': _('User not found.')})

    try:
        base_email = u1.email
        m = re.match(r"^(.+@[^@]+?)_\d+$", u1.email)
        if m:
            base_email = m.group(1)

        lang = 'ko'
        if LANGUAGE_CODE == 'en':
            lang = 'en'
        elif LANGUAGE_CODE == 'zh':
            lang = 'zh'

        send_email(base_email, 1, lang, account_email=u1.email)
        title, text = get_swal(LANGUAGE_CODE, 'SUCCESS_SIGNUP')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except Exception as err:
        logger.exception('SMTP send failed for verification email to %s', u1.email)
        return JsonResponse({
            'result': 500,
            'title': _('Error!'),
            'text': _('Failed to send email. Please contact the administrator.')
        }, status=500)
