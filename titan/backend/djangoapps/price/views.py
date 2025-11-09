import os
import json
import datetime
import hashlib
import uuid
import re
from pytz import timezone
from dateutil.relativedelta import relativedelta
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
from backend.djangoapps.common.swal import get_swal
import requests

import logging
from django.utils.timezone import now
from django.http import JsonResponse
from django.db import connections
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)  # 로그 설정

@csrf_exempt
def api_check_recent_payments(request):
    return JsonResponse({'hasRecentPayments': False})


@csrf_exempt
def api_prepare_extension_target(request):
    """
    결제 대상 계정 설정 API
    - 입력: email, password
    - 동작: 
        * 본인 계정이면 검증 후 그대로 반환
        * 다른 계정이면 비밀번호 검증 후 오너의 서브계정으로 전환(email을 owner_email_숫자 로 변경)
          그리고 라디우스 Radcheck.username 도 함께 변경
    - 반환: { result: 200, target_user_id, target_email }
    """
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'message': 'Not logged in'})

    LANGUAGE_CODE = request.LANGUAGE_CODE
    owner_id = request.session['id']
    owner = TblUser.objects.get(id=owner_id)
    base_email = owner.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)

    target_email = (request.POST.get('email') or '').strip()
    target_password = request.POST.get('password') or ''

    if not target_email:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    if not target_password:
        title, text = get_swal(LANGUAGE_CODE, 'NULL_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    def ok_response(user):
        return JsonResponse({'result': 200, 'target_user_id': user.id, 'target_email': user.email})

    # 본인 계정인 경우
    if target_email == owner.email:
        if not matchHashedText(owner.password, target_password):
            title, text = get_swal(LANGUAGE_CODE, 'ERROR_PASSWORD')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
        return ok_response(owner)

    # 이미 자신의 서브계정인지 확인
    try:
        sub_user = TblUser.objects.get(email=target_email, delete_yn='N')
    except TblUser.DoesNotExist:
        title, text = get_swal(LANGUAGE_CODE, 'INCORRECT_LOGIN')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    if not matchHashedText(sub_user.password, target_password):
        title, text = get_swal(LANGUAGE_CODE, 'ERROR_PASSWORD')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    if sub_user.email.startswith(base_email + '_'):
        # 이미 오너의 서브계정
        return ok_response(sub_user)

    # 다른 사람의 메인 계정 -> 오너의 서브계정으로 변환 (email rename)
    # 유니크한 suffix 생성
    suffix = 1
    while TblUser.objects.filter(email=f"{base_email}_{suffix}").exists():
        suffix += 1
    new_email = f"{base_email}_{suffix}"

    # radius 업데이트 (존재하는 경우에만)
    try:
        Radcheck.objects.using('radius').filter(username=sub_user.email).update(username=new_email)
    except Exception:
        pass

    sub_user.email = new_email
    sub_user.save()

    return ok_response(sub_user)


@csrf_exempt
def api_list_subaccounts(request):
    """현재 로그인 사용자의 메인/서브계정 리스트를 반환"""
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'message': 'Not logged in'})

    owner_id = request.session['id']
    owner = TblUser.objects.get(id=owner_id)
    base_email = owner.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)

    # 소유자 + 서브계정 목록
    items = [{'id': owner.id, 'email': owner.email}]
    subs = list(TblUser.objects.filter(email__startswith=base_email + '_', delete_yn='N').values('id', 'email'))
    items.extend(subs)
    return JsonResponse({'result': 200, 'items': items})

#pushplus 알림
def send_pushplus_notification(title, content):
    url = 'http://www.pushplus.plus/send'
    token = 'f15a46f5e2aa4a4da92f6ec17ad53362'
    data = {
        "token": token,
        "title": title,
        "content": content
    }
    response = requests.post(url, json=data)
    return response.json()


# 이용가격 테이블 (2020-03-10)
def price_table(request):
    context = {}
    return render(request, 'new/price_table.html', context)


# 이용가격 렌더링 (2020-03-11)
def price(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    # 이용 데이터가 존재하지 않거나 현재보다 작을 경우 결제화면 렌더링
    lock = 0
    if 'id' in request.session:
        id = request.session['id']
        u1 = TblUser.objects.get(id = id)

        ph = TblPriceHistory.objects.filter(user_id=id, refund_yn='N')
        sh = TblSendHistory.objects.filter(user_id=id, status='A')
        st = TblServiceTime.objects.filter(user_id=id)

        # 결제 기록이 없으면 통과
        if len(ph) == 0 and len(sh) == 0 and len(st) == 0:
            pass
        # 결제 기록이 있으면 이력 체크
        else:
            try:
                r = Radcheck.objects.using('radius').get(
                    username=u1.email,
                    attribute='Expiration'
                )
                expire_time = r.value
                expire_time = dec_radius_time(expire_time)
                print('INFO -> expire_time : ', expire_time)
                now = datetime.datetime.now(timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
                now = datetime.datetime.strptime(now, '%Y-%m-%d %H:%M:%S')
                print('INFO -> now : ', now)
                if expire_time > now:
                    lock = 1
            except BaseException as err:
                print('ERROR -> err : ', err)
                pass
    else:
        return redirect('/login?next=price')

    print('INFO -> lock : ', lock)

    # bank info
    try:
        bank_info = TblBankAccount.objects.get(type='main')
        person_name = bank_info.person_name
        bank_name = bank_info.bank_name
        bank_number = bank_info.bank_number
    except BaseException:
        person_name = 'error'
        bank_name = 'error'
        bank_number = 'error'

    context = {}
    context['LANGUAGE_CODE'] = LANGUAGE_CODE
    context['lock'] = lock
    context['person_name'] = person_name
    context['bank_name'] = bank_name
    context['bank_number'] = bank_number
    context['owner_id'] = id
    return render(request, 'new/price.html', context)


# 무통장 결제요청 (2020-03-12)
def api_plz_payment(request):
    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    type = request.POST.get('type')
    product_name = makeProductName(session, month_type)

    price = getProductPirce(session, month_type, 'KRW')

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    #if duplicatePaymentProtect(u1):
    #    return JsonResponse({'result': 'fail'})
    #sh = TblSendHistory.objects.filter(user_id=u1.id, status='R', type=type)
    
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT id, session, type, month_type, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i:%S") as regist_date
            FROM titan.tbl_send_history
            WHERE user_id = '{user_id}' AND status = 'R' AND (type = 'A' OR type = 'W') ORDER BY id desc
            '''.format(user_id=user_id)
        cur.execute(sql)
        rows = dictfetchall(cur)
        if len(rows) == 0:
            return JsonResponse({'result': 200})
        # 결제 기록이 있으면 이력 체크
        else:
            return JsonResponse({'result': 300, 'data':rows[0]})

# 계정삭제 (2024-02-27)
def api_delete_account(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if 'id' in request.session:
        change_reason = 'Web'
        user_id = request.session['id']
        user = TblUser.objects.get(id = user_id)
        
        password = request.POST.get('password')
        
        if password == '':
            title, text = get_swal(LANGUAGE_CODE, 'NULL_PASSWORD')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
        else:
            match_result = matchHashedText(user.password, password)
            if match_result != True:
                title, text = get_swal(LANGUAGE_CODE, 'ERROR_PASSWORD')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        
        # 이메일(삭제)
        delete_email = 'delete__' + user.email + '#' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # racheck 처리
        Radcheck.objects.using('radius').filter(username=user.email).update(username=delete_email)
        # tbl_user 처리
        user.email = delete_email
        user.delete_yn = 'Y'
        user.save()
        # 내역 기록
        st = TblServiceTime(
            user_id = user_id,
            prev_time = '',
            prev_time_rad = '',
            after_time = '',
            after_time_rad = '',
            diff = '회원탈퇴',
            reason = change_reason,
            regist_date = datetime.datetime.now())
        st.save()
        title, text = get_swal(LANGUAGE_CODE, 'DELETE_ACCOUNT')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    else:
        title, text = get_swal(LANGUAGE_CODE, 'UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
 
# 무통장 결제요청 (2023-08-29) (2025-06-30) 자동결제를위한 함수추가
# 무통장 결제요청 (2023-08-29) (2025-06-30) 자동결제를위한 함수추가
def api_create_payment(request):
    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')
    type = request.POST.get('type')
    create_type = request.POST.get('create_type')
    product_name = makeProductName(session, month_type)

    price = getProductPirce(session, month_type, 'KRW')

    # 대상 사용자 지정 확장: target_user_id가 들어오면 해당 사용자로 결제 요청 생성
    target_user_id = request.POST.get('target_user_id')
    target_email_for_response = None
    if target_user_id:
        try:
            target_user_id = int(target_user_id)
            target_user = TblUser.objects.get(id=target_user_id)
            # 보안: 요청 사용자가 대상 계정에 대해 권한이 있는지 확인
            owner = TblUser.objects.get(id=user_id)
            base_email = owner.email
            m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
            if m:
                base_email = m.group(1)
            if not (target_user.email == owner.email or target_user.email.startswith(base_email + '_')):
                return JsonResponse({'result': 403, 'message': 'Not allowed target user'})
            user_id = target_user.id  # 실제 결제 대상 사용자로 치환
            target_email_for_response = target_user.email
        except Exception:
            return JsonResponse({'result': 400, 'message': 'Invalid target_user_id'})

    # Pushplus 알림 전송
    notification_title = f"결제요청 {type}{price}"
    notification_content = f"사용자 {user_name}이 결제를 요청하였습니다. 금액: {price}"
    send_pushplus_notification(notification_title, notification_content)

    # 기존 결제 내역 취소 (이중 결제 방지)
    if create_type == 'F':
        TblSendHistory.objects.filter(
            user_id=user_id,
            session=session,
            month_type=month_type,
            type=type,
            status='R'
        ).update(status='U', cancel_date=now())

    # 새로운 결제 내역 추가
    history = TblSendHistory.objects.create(
        user_id=user_id,
        product_name=product_name,
        session=session,
        month_type=month_type,
        krw=price,
        status='R',
        type=type,
        regist_date=now()
    )

    # 응답 이메일: 타깃 사용자 지정 시 해당 이메일, 아니면 세션 이메일
    resp_email = target_email_for_response or request.session.get('email', '이메일 없음')
    return JsonResponse({
        'result': 200,
        'payment_id': history.id,
        'data': {
            'email': resp_email
        }
    })




# 페이레터 국내 취소 리다이렉트 (2020-03-12)
@csrf_exempt
def payletter_cancel(request):
    return redirect('/price')


# 페이레터 해외 취소 리다이렉트 (2020-03-12)
@csrf_exempt
def globalpayletter_cancel(request):
    return redirect('/price')


# 위쳇페이 취소 리다이렉트 (2020-03-12)
@csrf_exempt
def paybox_cancel(request):
    return redirect('/price')

from django.views.decorators.http import require_POST
from django.utils.timezone import now

@csrf_exempt
@require_POST
def api_check_payment_status(request):
    """결제 상태를 확인하는 API"""
    payment_id = request.POST.get('payment_id')

    if not payment_id:
        return JsonResponse({'result': 'error', 'message': 'No payment ID provided'})

    with connections['default'].cursor() as cur:
        sql = '''
            SELECT status FROM titan.tbl_send_history
            WHERE id = %s
        '''
        cur.execute(sql, [payment_id])
        row = cur.fetchone()

    if row:
        status = row[0]
        # 'A' 또는 'S'를 결제 완료로 간주
        if status in ('A', 'S'):
            return JsonResponse({'result': 'success', 'status': status})
        else:
            return JsonResponse({'result': 'pending', 'status': status})
    else:
        return JsonResponse({'result': 'error', 'status': 'unknown', 'message': 'Payment record not found'})


@csrf_exempt
def api_create_payment_for(request):
    """Create a payment request (send history) for a specific subaccount of the current user."""
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'message': 'Not logged in'}, status=403)

    owner_id = request.session['id']
    owner = TblUser.objects.get(id=owner_id)
    base_email = owner.email
    m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
    if m:
        base_email = m.group(1)

    target_user_id = request.POST.get('target_user_id')
    if not target_user_id:
        return JsonResponse({'result': 400, 'message': 'Missing target_user_id'}, status=400)

    try:
        target_user = TblUser.objects.get(id=target_user_id, delete_yn='N')
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'message': 'Target user not found'}, status=404)

    # Security: ensure target account is a subaccount of the owner (email prefix match)
    if not target_user.email.startswith(base_email + '_'):
        return JsonResponse({'result': 403, 'message': 'Not allowed for this target user'}, status=403)

    pgcode = request.POST.get('pgcode') or 'BANK'
    session = request.POST.get('session') or '1'
    month_type = request.POST.get('month_type') or '1'
    type = request.POST.get('type') or 'A'
    create_type = request.POST.get('create_type') or 'F'

    product_name = makeProductName(session, month_type)
    price = getProductPirce(session, month_type, 'KRW')

    # Pushplus 알림 전송 (대상 이메일 포함)
    notification_title = f"결제요청 {type}{price}"
    notification_content = f"사용자 {owner.username}이(가) 서브계정 {target_user.email} 연장 결제를 요청하였습니다. 금액: {price}"
    try:
        send_pushplus_notification(notification_title, notification_content)
    except Exception:
        pass

    if create_type == 'F':
        TblSendHistory.objects.filter(
            user_id=target_user.id,
            session=session,
            month_type=month_type,
            type=type,
            status='R'
        ).update(status='U', cancel_date=now())

    history = TblSendHistory.objects.create(
        user_id=target_user.id,
        product_name=product_name,
        session=session,
        month_type=month_type,
        krw=price,
        status='R',
        type=type,
        regist_date=now()
    )

    return JsonResponse({'result': 200, 'payment_id': history.id, 'data': {'email': target_user.email}})
