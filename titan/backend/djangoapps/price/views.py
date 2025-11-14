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
from django.db.models import Q
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
def api_preview_session_change(request):
    """세션/기간 변경 시 남은 기간 변환과 예상 만료일을 미리 안내하는 API.
    - 입력: session(신규), month_type, optional target_user_id
    - 출력: { result:200, show:bool, message, details:{old_session, remain_days, converted_days, expected_expire_date} }
    조건:
      * 로그인 필요
      * 현재 만료일이 미래이고 old_session != new_session 인 경우에만 show=True
    """
    if 'id' not in request.session:
        return JsonResponse({'result': 403, 'message': 'Not logged in'})

    try:
        new_session = int((request.POST.get('session') or '1'))
        month_type = int((request.POST.get('month_type') or '1'))
    except Exception:
        return JsonResponse({'result': 400, 'message': 'Invalid parameters'})

    # 결제 대상 사용자 식별 (본인 또는 서브계정)
    target_user_id = request.POST.get('target_user_id')
    user_id = request.session['id']
    target_user = TblUser.objects.get(id=user_id)
    if target_user_id:
        try:
            target_user_id = int(target_user_id)
            owner = TblUser.objects.get(id=user_id)
            base_email = owner.email
            m = re.match(r'^(.+@[^@]+?)_\d+$', base_email)
            if m:
                base_email = m.group(1)
            tu = TblUser.objects.get(id=target_user_id, delete_yn='N')
            if tu.id == owner.id or tu.parent_user_id == owner.id or (tu.parent_user_id is None and tu.email.startswith(base_email + '_')):
                target_user = tu
            else:
                return JsonResponse({'result': 403, 'message': 'Not allowed target user'})
        except Exception:
            return JsonResponse({'result': 400, 'message': 'Invalid target_user_id'})

    email = target_user.email

    # 현재 세션/만료일 조회
    old_session = my_radius_session(email)
    expire_dt = my_radius_time(email, 'datetime')

    # Fallback: 라디우스 정보가 비어있으면 DB 이력으로 추정
    if old_session is None:
        try:
            last_paid = TblSendHistory.objects.filter(user_id=target_user.id, status__in=['A','S']).order_by('-id').first()
            if last_paid:
                old_session = int(last_paid.session)
        except Exception:
            pass
    if expire_dt is None:
        try:
            last_st = TblServiceTime.objects.filter(user_id=target_user.id).order_by('-id').first()
            if last_st and last_st.after_time:
                expire_dt = last_st.after_time  # 그대로 사용하고 이후 단계에서 tz 정규화
        except Exception:
            pass

    if old_session is None or expire_dt is None:
        # 정보 부족 시 미리보기 스킵
        logger.info('preview_skip: no_data user=%s old_session=%s expire=%s new_session=%s month_type=%s', email, old_session, expire_dt, new_session, month_type)
        return JsonResponse({'result': 200, 'show': False, 'details': {'reason': 'NO_DATA'}})

    try:
        old_session = int(old_session)
    except Exception:
        return JsonResponse({'result': 200, 'show': False})

    # 만료가 지났거나 세션이 동일하면 안내 불필요
    tz = timezone('Asia/Seoul')
    now_aware = datetime.datetime.now(tz)

    def to_aware(dt):
        if dt is None:
            return None
        return dt if getattr(dt, 'tzinfo', None) else tz.localize(dt)

    expire_aware = to_aware(expire_dt)

    if expire_aware is None:
        logger.info('preview_skip: expire_dt None after normalization user=%s', email)
        return JsonResponse({'result': 200, 'show': False, 'details': {'reason': 'NO_EXPIRE'}})

    if expire_aware <= now_aware or old_session == new_session:
        # 만료되었거나 동일세션: 만료되었지만 세션이 실제로 바뀌는지 재확인 후 안내 생성 가능
        reason_code = 'EXPIRED_OR_EQUAL'
        if old_session != new_session:
            # 남은기간 정보가 없거나 만료라 변환 계산 없음 -> 단순 안내만
            month_label_map = {1: '1개월', 2: '2개월', 3: '3개월', 6: '6개월', 12: '12개월'}
            month_label = month_label_map.get(month_type, f"{month_type}개월")
            simple_msg = (
                f"동시접속사용수가 달라집니다. 기존 {old_session}기기에서 {new_session}기기로 변경됩니다. 남은기간이 없거나 계산할 수 없어 변환 안내를 생략하고 바로 {new_session}기기 {month_label}이 추가 적용됩니다."\
            )
            logger.info('preview_simple: user=%s old=%s new=%s remain=0 reason=%s', email, old_session, new_session, reason_code)
            return JsonResponse({'result': 200, 'show': True, 'message': simple_msg, 'details': {
                'old_session': old_session,
                'new_session': new_session,
                'remain_days': 0,
                'converted_days': 0,
                'expected_expire_date': None,
                'reason': reason_code
            }})
        logger.info('preview_hide: user=%s old=%s new=%s reason=%s', email, old_session, new_session, reason_code)
        return JsonResponse({'result': 200, 'show': False, 'details': {
            'old_session': old_session,
            'new_session': new_session,
            'reason': reason_code
        }})

    # 남은 일수 계산: 올림 적용 (부분일 포함)
    total_seconds = (expire_aware - now_aware).total_seconds()
    diff_days = int((total_seconds + 86399) // 86400)  # ceil without math import
    if diff_days < 0:
        return JsonResponse({'result': 200, 'show': False})

    # 세션 환산 비율 (기존 giveServiceTime 로직 일반화)
    scale = {1: 83, 2: 140, 3: 220, 4: 280, 5: 350, 6: 433}
    if old_session not in scale or new_session not in scale:
        return JsonResponse({'result': 200, 'show': False})

    converted_days = int(diff_days * scale[old_session] / scale[new_session])

    # 예상 만료일 계산: now + months + converted_days
    expected_expire = now_aware + relativedelta(months=month_type) + datetime.timedelta(days=converted_days)
    # 한국식 표기: M월 D일
    expected_label = f"{expected_expire.month}월 {expected_expire.day}일"

    # 증감 표현
    verb = '줄어들고' if converted_days < diff_days else ('늘어나고' if converted_days > diff_days else '변함없고')

    month_label_map = {1: '1개월', 2: '2개월', 3: '3개월', 6: '6개월', 12: '12개월'}
    month_label = month_label_map.get(month_type, f"{month_type}개월")

    msg = (
        f"동시접속사용수가 달라집니다. 현재 {old_session}기기로 {diff_days}일의 기간이 남아있습니다만 "
        f"{new_session}기기로 변경되면서 {converted_days}일로 {verb} {new_session}기기로 변경된후 "
        f"{new_session}기기 {month_label}이 추가됩니다. {new_session}기기 변경및 추가입금후 예상 만료일자는 {expected_label}입니다."
    )

    logger.info('preview_normal: user=%s old=%s new=%s remain=%s converted=%s expected=%s', email, old_session, new_session, diff_days, converted_days, expected_expire)
    return JsonResponse({
        'result': 200,
        'show': True,
        'message': msg,
        'details': {
            'old_session': old_session,
            'new_session': new_session,
            'remain_days': diff_days,
            'converted_days': converted_days,
            'expected_expire_date': expected_expire.strftime('%Y-%m-%d %H:%M:%S'),
            'reason': 'NORMAL'
        }
    })


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

    # 자기 자신을 다시 추가하려는 경우 방지
    if sub_user.id == owner.id:
        return JsonResponse({'result': 500, 'code': 'SELF_ASSIGN', 'message': 'Cannot attach yourself.'})

    # 이미 다른 계정의 하위계정인지 확인 (신규 parent 필드 우선)
    if sub_user.parent_user_id:
        if sub_user.parent_user_id == owner.id:
            return ok_response(sub_user)
        return JsonResponse({'result': 500, 'code': 'ALREADY_SUB', 'message': 'Already assigned to another owner.'})

    # 레거시: 이메일 패턴이 다른 오너를 가리키면 중단
    other_owner_match = re.match(r'^(.+@[^@]+?)_\d+$', sub_user.email)
    if other_owner_match and other_owner_match.group(1) != base_email:
        return JsonResponse({'result': 500, 'code': 'ALREADY_SUB', 'message': 'Already assigned to another owner.'})

    if sub_user.email.startswith(base_email + '_'):
        # 레거시 데이터: parent_user_id를 보정 후 반환
        sub_user.parent_user_id = owner.id
        sub_user.save(update_fields=['parent_user_id'])
        return ok_response(sub_user)

    # 하위계정을 보유한 계정은 또 다른 하위계정이 될 수 없음
    if TblUser.objects.filter(parent_user_id=sub_user.id, delete_yn='N').exists():
        return JsonResponse({'result': 500, 'code': 'HAS_CHILD', 'message': 'Target account already manages subaccounts.'})

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
    sub_user.parent_user_id = owner.id
    sub_user.save(update_fields=['email', 'parent_user_id'])

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

    # 소유자 + 서브계정 목록 (parent_user_id 기반, 레거시 패턴 보정)
    items = [{'id': owner.id, 'email': owner.email}]
    subs_qs = TblUser.objects.filter(
        delete_yn='N'
    ).filter(
        Q(parent_user_id=owner.id) |
        Q(parent_user_id__isnull=True, email__startswith=base_email + '_')
    ).exclude(id=owner.id).order_by('id')

    subs_list = list(subs_qs)
    legacy_ids = [su.id for su in subs_list if su.parent_user_id is None]
    if legacy_ids:
        TblUser.objects.filter(id__in=legacy_ids).update(parent_user_id=owner.id)
        for su in subs_list:
            if su.id in legacy_ids:
                su.parent_user_id = owner.id

    items.extend({'id': su.id, 'email': su.email} for su in subs_list)
    return JsonResponse({'result': 200, 'items': items})

# pushplus 알림 (settings 기반)
def send_pushplus_notification(title, content):
    token = getattr(settings, 'PUSHPLUS_TOKEN', '')
    endpoint = getattr(settings, 'PUSHPLUS_ENDPOINT', 'https://www.pushplus.plus/send')
    if not token:
        return {'result': 'skip', 'reason': 'no_token'}
    data = {"token": token, "title": title, "content": content}
    try:
        resp = requests.post(endpoint, json=data, timeout=3)
        return {'status_code': resp.status_code, 'text': resp.text[:200]}
    except Exception as e:
        return {'result': 'error', 'error': str(e)}


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
    if not price:
        notification_title = "결제요청 실패"
        notification_content = f"사용자 {user_name} 금액없음"
        send_pushplus_notification(notification_title, notification_content)
        return JsonResponse({'result': 404, 'message': 'PRICE_NOT_FOUND', 'detail': {
            'session': session,
            'month_type': month_type,
            'currency': 'KRW'
        }})
    if price is None:
        # 가격정보 누락: 404 응답 (기존엔 500 발생)
        return JsonResponse({'result': 404, 'message': 'PRICE_NOT_FOUND', 'detail': {
            'session': session,
            'month_type': month_type,
            'currency': 'KRW'
        }})

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
    pgcode = request.POST.get('pgcode') or 'BANK'
    session = request.POST.get('session') or '1'
    month_type = request.POST.get('month_type') or '1'
    type = request.POST.get('type') or 'A'
    create_type = request.POST.get('create_type') or 'F'
    product_name = makeProductName(session, month_type)

    price = getProductPirce(session, month_type, 'KRW')
    if not price:
        # 가격 누락: PushPlus로 간단 알림 후 404 반환
        try:
            send_pushplus_notification("결제요청 실패", f"{user_name} 금액없음")
        except Exception:
            pass
        logger.warning('api_create_payment price missing: user=%s session=%s month_type=%s', user_name, session, month_type)
        return JsonResponse({'result': 404, 'message': 'PRICE_NOT_FOUND', 'detail': {
            'session': session,
            'month_type': month_type,
            'currency': 'KRW'
        }})

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
            if target_user.id == owner.id:
                pass
            elif target_user.parent_user_id == owner.id:
                pass
            elif target_user.parent_user_id is None and target_user.email.startswith(base_email + '_'):
                TblUser.objects.filter(id=target_user.id, parent_user_id__isnull=True).update(parent_user_id=owner.id)
                target_user.parent_user_id = owner.id
            else:
                return JsonResponse({'result': 403, 'message': 'Not allowed target user'})
            user_id = target_user.id  # 실제 결제 대상 사용자로 치환
            target_email_for_response = target_user.email
        except Exception:
            return JsonResponse({'result': 400, 'message': 'Invalid target_user_id'})

    # PushPlus 알림 (간결 버전)
    notification_title = f"{user_name} {price}"
    notification_content = notification_title
    push_result = {}
    try:
        push_result = send_pushplus_notification(notification_title, notification_content) or {}
        logger.info('pushplus payment notify: user=%s price=%s status=%s', user_name, price, push_result.get('status_code') or push_result.get('result'))
    except Exception as e:
        logger.warning('pushplus notify failed: %s', e)

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

    # Security: ensure target account is a subaccount of the owner
    if target_user.parent_user_id == owner.id:
        pass
    elif target_user.parent_user_id is None and target_user.email.startswith(base_email + '_'):
        TblUser.objects.filter(id=target_user.id, parent_user_id__isnull=True).update(parent_user_id=owner.id)
        target_user.parent_user_id = owner.id
    else:
        return JsonResponse({'result': 403, 'message': 'Not allowed for this target user'}, status=403)

    pgcode = request.POST.get('pgcode') or 'BANK'
    session = request.POST.get('session') or '1'
    month_type = request.POST.get('month_type') or '1'
    type = request.POST.get('type') or 'A'
    create_type = request.POST.get('create_type') or 'F'

    product_name = makeProductName(session, month_type)
    price = getProductPirce(session, month_type, 'KRW')
    if not price:
        try:
            send_pushplus_notification("결제요청 실패", f"{owner.username} 금액없음")
        except Exception:
            pass
        logger.warning('api_create_payment_for price missing: owner=%s target=%s session=%s month_type=%s', owner.username, target_user.email, session, month_type)
        return JsonResponse({'result': 404, 'message': 'PRICE_NOT_FOUND', 'detail': {
            'session': session,
            'month_type': month_type,
            'currency': 'KRW'
        }})

    # Pushplus 알림 전송 (대상 이메일 포함) + 로깅
    notification_title = f"{owner.username} {price}"
    notification_content = notification_title
    push_result = {}
    try:
        push_result = send_pushplus_notification(notification_title, notification_content) or {}
        logger.info('pushplus payment notify (for): owner=%s target=%s price=%s status=%s', owner.username, target_user.email, price, push_result.get('status_code') or push_result.get('result'))
    except Exception as e:
        logger.warning('pushplus notify (for) failed: %s', e)

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
