# 사용자 관리 — 회원 CRUD, 검색, 이메일(SMTP) 발송, 사용량 조회
import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from django.db import transaction
from urllib.parse import quote


# (2020-03-16)
@allow_admin
def user(request):
    delete_list = TblCodeDetail.objects.filter(group_code='delete_yn')
    active_list = TblCodeDetail.objects.filter(group_code='is_active')
    staff_list = TblCodeDetail.objects.filter(group_code='is_staff')
    context = {
        'delete_list': delete_list,
        'active_list': active_list,
        'staff_list': staff_list
    }
    return render(request, 'admin/user.html', context)


# (2020-03-16)
@allow_admin
def regist_ban(request):
    with connections['default'].cursor() as cur:
        query = '''
            select  id, 
                    case 
                        when type = 'DM'
                        then '도메인'
                        else '아이피'
                    end type,
                    content, 
                    reason, 
                    case 
                        when delete_yn = 'Y'
                        then '삭제'
                        else '정상'
                    end delete_yn,
                    ifnull(regist_date, '') as regist_date, 
                    ifnull(modify_date, '') as modify_date, 
                    ifnull(delete_date, '') as delete_date
            from tbl_regist_ban
        '''.format()
        print(query)
        cur.execute(query)
        rows = dictfetchall(cur)

    context = {}
    context['rows'] = rows
    return render(request, 'admin/regist_ban.html', context)


# (2020-04-06)
@allow_admin
def block_user(request):
    context = {}
    return render(request, 'admin/block_user.html', context)

# (2024-04-15)
@allow_admin
def block_extend(request):
    context = {}
    return render(request, 'admin/block_extend.html', context)

# (2020-04-06)
@allow_admin
def abuse_user(request):
    context = {}
    return render(request, 'admin/abuse_user.html', context)



def is_active_str(is_active):
    if is_active == 1:
        return '활성화'
    else:
        return '비활성화'
    

# (2020-04-20)
@allow_admin
def api_read_abuse_user_detail(request):
    input_ip = request.POST.get('input_ip')
    
    users = TblUser.objects.filter(regist_ip=input_ip)
    result = []
    for user in users:
        tmp = { 'email': user.email }
        result.append(tmp)
    return JsonResponse({'result': result})


# (2020-04-06)
@allow_admin
def api_read_block_user(request):
    user_list = request.POST.get('user_list')
    try:
        user_list = user_list.split(',')
    except ValueError as err:
        return JsonResponse({'result': []})

    return_list = []
    for user in user_list:
        user = user.strip()
        tmp = {}
        if user.find('@') == -1: # 번호
            try:
                user = TblUser.objects.get(id=int(user))
                rce = Radcheck.objects.using('radius').filter(
                    username = user.email,
                    attribute = 'Expiration'
                )
                radius_time = ''
                if len(rce) != 0:
                    rceu = rce.first()
                    radius_time = dec_radius_time(rceu.value)
                tmp = {
                    'id': user.id,
                    'email': user.email,
                    'regist_date': user.regist_date,
                    'expire_date': radius_time,
                    'regist_ip': user.regist_ip,
                    'is_active': is_active_str(user.is_active)
                }
                return_list.append(tmp)
            except BaseException as err:
                continue
        else:                    # 이메일
            try:
                user = TblUser.objects.get(email=user)
                rce = Radcheck.objects.using('radius').filter(
                    username = user.email,
                    attribute = 'Expiration'
                )
                radius_time = ''
                if len(rce) != 0:
                    rceu = rce.first()
                    radius_time = dec_radius_time(rceu.value)
                tmp = {
                    'id': user.id,
                    'email': user.email,
                    'regist_date': user.regist_date,
                    'expire_date': radius_time,
                    'regist_ip': user.regist_ip,
                    'is_active': is_active_str(user.is_active)
                }
                return_list.append(tmp)
            except BaseException as err:
                continue
    return JsonResponse({'result': return_list})


# (2020-04-20)
@allow_admin
def api_read_abuse_user(request):
    with connections['default'].cursor() as cur:
        query = '''
            select @rownum:=@rownum+1 as row, w.*
            from (
                select regist_ip, count(*) as cnt
                from tbl_user
                group by regist_ip
            ) w, (SELECT @rownum:=0) TMP
            where cnt > 1
            order by cnt desc;
        '''.format()
        # print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = dictfetchall(cur)

    return JsonResponse({'result': rows})


# (2020-04-06)
@allow_admin
def api_update_block_user(request):
    try:
        block_list = request.POST.getlist('block_list[]')
        for user in block_list:
            initServiceTime(user)
        title, text = get_swal('SUCCESS_BLOCK')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except smtplib.SMTPException as err:
        # SMTP 단계에서 실패한 경우: 관리자에게 디버그 메시지 전달
        return JsonResponse({'result': 500, 'title': '알림', 'text': '메일 전송 중 오류가 발생했습니다', 'debug': str(err)})
    except Exception as err:
        # 기타 예외도 동일한 사용자 메시지 + 디버그 포함
        return JsonResponse({'result': 500, 'title': '알림', 'text': '메일 전송 중 오류가 발생했습니다', 'debug': str(err)})

# (2020-04-06)
@allow_admin
def api_update_block_extend(request):
    try:
        block_list = request.POST.getlist('block_list[]')
        for user in block_list:
            print("==================" + user)
            u1 = TblUser.objects.get(id = user)
            print("TEST" + u1.email)
            u1.black_yn = "X"
            u1.save()
        title, text = get_swal('SUCCESS_BLOCK')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

# (2020-03-16)
@allow_admin
def api_read_user_datatables(request):
  try:
    # datatables 기본 파라미터
    start = int(request.POST.get('start', 0))
    length = int(request.POST.get('length', 10))
    draw = int(request.POST.get('draw', 1))
    orderby_col = int(request.POST.get('order[0][column]', 0))
    orderby_opt = request.POST.get('order[0][dir]', 'desc')

    # 안전: 허용값만 통과
    if orderby_opt not in ('asc', 'desc'):
        orderby_opt = 'desc'

    # id 컬럼(0번) 정렬은 항상 desc (최신순) 강제
    if orderby_col == 0:
        orderby_opt = 'desc'

    # 검색 필터 파라미터
    id = request.POST.get('id')
    email = request.POST.get('email')
    username = request.POST.get('username')
    delete = request.POST.get('delete')
    active = request.POST.get('active')
    staff = request.POST.get('staff')
    regist_ip = request.POST.get('regist_ip')

    # where 조건 동적 연산
    wc = ""
    if id != '':
        wc += " and x.id = '" + id + "'"
    if email != '':
        wc += " and x.email like '%" + email + "%'"
    if username != '':
        wc += " and x.username like '%" + username + "%'"
    if regist_ip != '':
        wc += " and x.regist_ip like '%" + regist_ip + "%'"
    if delete != '':
        wc += " and x.delete_yn = '" + delete + "'"
    if active != '':
        wc += " and x.is_active = '" + active + "'"
    if staff != '':
        wc += " and x.is_staff = '" + staff + "'"

    # order by 컬럼
    column_name = ['id', 'email', 'username', 'delete_yn', 'is_active', 'is_staff', 'regist_date']

    # 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  count(*)
            from tbl_user x
            join tbl_code_detail a
            on x.delete_yn = a.code
            join tbl_code_detail b
            on x.is_active = b.code
            join tbl_code_detail c
            on x.is_staff = c.code
            where a.group_code = 'delete_yn'
            and b.group_code = 'is_active'
            and c.group_code = 'is_staff'
            {wc}
        '''.format(wc=wc)
        # print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select w.*,
                   CASE WHEN exp.exp_date IS NOT NULL AND exp.exp_date < NOW() THEN 1 ELSE 0 END as is_expired
            from (
            	select  x.id,
            			x.email,
            			x.username,
            			DATE_FORMAT(x.regist_date, "%Y-%m-%d %H:%i:%s") as regist_date,
            			b.name as is_active,
            		    x.black_yn,
            			c.name as is_staff,
            			a.name as delete_yn,
                        x.regist_ip
            	from tbl_user x
            	join tbl_code_detail a
            	on x.delete_yn = a.code
            	join tbl_code_detail b
            	on x.is_active = b.code
            	join tbl_code_detail c
            	on x.is_staff = c.code
            	where a.group_code = 'delete_yn'
            	and b.group_code = 'is_active'
            	and c.group_code = 'is_staff'
                {wc}
                order by {orderby_col} {orderby_opt}
            	limit {start}, 10
            ) w
            LEFT JOIN (
                SELECT username,
                  CAST(CONCAT(
                    SUBSTRING_INDEX(SUBSTRING_INDEX(value, ' ', 3), ' ', -1), '-',
                    LPAD(FIELD(SUBSTRING_INDEX(SUBSTRING_INDEX(value, ' ', 2), ' ', -1),
                      'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'), 2, '0'), '-',
                    LPAD(SUBSTRING_INDEX(value, ' ', 1), 2, '0'), ' ',
                    SUBSTRING_INDEX(SUBSTRING_INDEX(value, ' ', 4), ' ', -1)
                  ) AS DATETIME) as exp_date
                FROM radius.radcheck
                WHERE attribute = 'Expiration'
            ) exp ON exp.username = w.email
            JOIN ( SELECT @rnum := -1 ) AS r
            ORDER BY w.{orderby_col} {orderby_opt}
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start)
        print('DEBUG SORT -> col={}, opt={}, query_order=order by {} {}'.format(orderby_col, orderby_opt, column_name[orderby_col], orderby_opt), flush=True)
        cur.execute(query)
        rows = dictfetchall(cur)
        if rows:
            print('DEBUG SORT -> first_row_id={}, last_row_id={}'.format(rows[0].get('id','?'), rows[-1].get('id','?')), flush=True)

    returnData = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(returnData)
  except Exception as e:
    import traceback
    traceback.print_exc()
    draw = int(request.POST.get('draw', 1))
    return JsonResponse({
        "recordsTotal": 0,
        "recordsFiltered": 0,
        "draw": draw,
        "data": [],
        "error": str(e)
    })


# (2020-03-17) 회원관리안 추가정보(번호id, 이메일email, 본인추천인코드rec, 가입시입력한추천인코드regist_rec)
@allow_admin
def api_read_user_detail(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    ret = {
        'id': user.id,
        'email': user.email,
#        'rec': user.rec,
        'regist_rec': user.regist_rec,
    }
    return JsonResponse({'result': ret})

# 오늘 신규가입수 + 활성화수 (메뉴 뱃지용)
@allow_admin
def api_read_user_today_stats(request):
    import datetime
    today = datetime.date.today()
    today_registered = TblUser.objects.filter(regist_date__date=today).count()
    today_active = TblUser.objects.filter(regist_date__date=today, is_active=1).count()
    return JsonResponse({'result': 200, 'today_registered': today_registered, 'today_active': today_active})


# (2023-05-04) Added By Zhao Get User Count
@allow_admin
def api_read_user_count(request):
    # 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            SELECT 
            sum(case when username like 'delete%' then 1 else 0 end) AS deleted_user,
            sum(case when STR_TO_DATE(value, "%d %M %Y %T") >= '{today}' then 1 else 0 end) AS purchase_user,
            sum(case when STR_TO_DATE(value, "%d %M %Y %T") < '{today}' then 1 else 0 end) AS expired_user
            FROM radius.radcheck
        '''.format(
            today=datetime.datetime.now())
        cur.execute(query)
        rows = cur.fetchall()
        deleted_user = int(rows[0][0] or 0) // 3
        purchase_user = rows[0][1]
        expired_user = rows[0][2]
        
        query = '''
            SELECT  sum(case when rad.value = '2' then 1 else 0 end) AS session_two_user,
            sum(case when rad.value = '1' then 1 else 0 end) AS session_one_user,
            sum(case when rad.value = '3' then 1 else 0 end) AS session_three_user,
            sum(case when rad.value = '4' then 1 else 0 end) AS session_four_user,
            sum(case when rad.value = '5' then 1 else 0 end) AS session_five_user,
            sum(case when rad.value = '6' then 1 else 0 end) AS session_six_user  
            FROM radius.radcheck rad
            JOIN (SELECT *
            FROM radius.radcheck 
            WHERE STR_TO_DATE( value, "%d %M %Y %T" ) >= '{today}') rc ON rad.username = rc.username
        '''.format(
            today=datetime.datetime.now())
        cur.execute(query)
        rows = cur.fetchall()
        session_two_user = rows[0][0]
        session_one_user = rows[0][1]
        session_three_user = rows[0][2]
        session_four_user = rows[0][3]
        session_five_user = rows[0][4]
        session_six_user = rows[0][5]
        
        ret = {
            'session_one_user': session_one_user,
            'session_two_user': session_two_user,
            'session_three_user': session_three_user,
            'session_four_user': session_four_user,
            'session_five_user': session_five_user,
            'session_six_user': session_six_user,
            'deleted_user': deleted_user,
            'purchase_user': purchase_user,
            'expired_user': expired_user
        }
        return JsonResponse({'result': ret})

# (2020-03-17)
@allow_admin
def api_read_user_service_time(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    service_time = my_radius_time(user.email, 'str')
    return JsonResponse({'result': service_time})


# (2020-03-17)
@allow_admin
def api_read_user_session(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    try:
        session = Radcheck.objects.using('radius').get(username = user.email, attribute = 'Simultaneous-Use').value
    except BaseException as err:
        session = 'ERROR'
    return JsonResponse({'result': session})

# (2020-03-17)
@allow_admin
def api_read_user_password(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    try:
         password = Radcheck.objects.using('radius').get(username = user.email, attribute = 'Cleartext-Password').value
    except BaseException as err:
         password = 'ERROR'
    return JsonResponse({'result': password})

# (2020-03-17)
@allow_admin
def api_update_user_service_time(request):
    change_time = request.POST.get('change_time')
    change_reason = request.POST.get('change_reason')
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)

    # 시간 유효성 체크
    try:
        change_time = datetime.datetime.strptime(change_time, '%Y-%m-%d %H:%M:%S')
        change_time_rad = enc_radius_time(change_time)
    except BaseException as err:
        title, text = get_swal('NOT_TIME_FORMAT')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 서비스 적용 및 서비스 내역 기록
    try:
        with transaction.atomic():
            rce = Radcheck.objects.using('radius').get(
                username = user.email,
                attribute = 'Expiration'
            )
            prev_time_rad = rce.value
            prev_time = dec_radius_time(prev_time_rad)
            time_diff = change_time - prev_time
            time_diff = round((time_diff).total_seconds()/60)
            st = TblServiceTime(
                user_id = user_id,
                prev_time = prev_time,
                prev_time_rad = prev_time_rad,
                after_time = change_time,
                after_time_rad = change_time_rad,
                diff = time_diff,
                reason = change_reason,
                regist_date = datetime.datetime.now()
            )
            rce.value = change_time_rad
            rce.save(using='radius')
            st.save()
        title, text = get_swal('SUCCESS_SERVICE_TIME')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2020-03-17)
@allow_admin
def api_update_user_session(request):
    change_session = request.POST.get('change_session')
    change_reason = request.POST.get('change_reason')
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)

    if change_session == '6' or change_session == '1' or change_session == '2' or change_session == '3' or change_session == '4' or change_session == '5':
        try:
            session = Radcheck.objects.using('radius').get(username = user.email, attribute = 'Simultaneous-Use')
            prev_session = session.value
            session.value = change_session
            session.save()
            after_session = session.value
            st = TblServiceTime(
                user_id = user_id,
                prev_time = prev_session,
                prev_time_rad = '',
                after_time = after_session,
                after_time_rad = '',
                diff = '세션 변경',
                reason = change_reason,
                regist_date = datetime.datetime.now())
            st.save()
            title, text = get_swal('SUCCESS_SESSION')
            return JsonResponse({'result': 200, 'title': title, 'text': text})
        except BaseException as err:
            title, text = get_swal('UNKNOWN_ERROR')
            return JsonResponse({'result': 500, 'title': title, 'text': text})
    else:
        title, text = get_swal('NOT_SESSION_FORMAT')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2020-03-17)
@allow_admin
def api_update_user_password(request):
    change_password = request.POST.get('change_password')
    change_reason = request.POST.get('change_reason')
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)

    # 비밀번호 8자리 이상 체크
    if len(change_password) < 8:
        title, text = get_swal('NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 비밀번호 2조합 이상 체크
    rule_cnt = 0
    sp_txt = re.findall("[\!\@\#\$\%\^\&\*\(\)\-\=\_\+\~]", change_password)
    if len(sp_txt) > 0:
        rule_cnt += 1
    ap_txt = re.findall("[a-zA-Z]", change_password)
    if len(ap_txt) > 0:
        rule_cnt += 1
    dg_txt = re.findall("[0-9]", change_password)
    if len(dg_txt) > 0:
        rule_cnt += 1
    if rule_cnt < 2:
        title, text = get_swal('NOT_PASSWORD_RULE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    prev_password = user.password
    user.password = hashText(change_password)
    user.save()

    st = TblServiceTime(
        user_id = user_id,
        prev_time = '비공개',
        prev_time_rad = '',
        after_time = '비공개',
        after_time_rad = '',
        diff = '비밀번호 변경',
        reason = change_reason,
        regist_date = datetime.datetime.now())
    st.save()
    title, text = get_swal('SUCCESS_PASSWORD')
    return JsonResponse({'result': 200, 'title': title, 'text': text})


# (2020-03-17)
@allow_admin
def api_update_user_active(request):
    change_active = request.POST.get('change_active')
    change_reason = request.POST.get('change_reason')
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)

    prev_is_active = user.is_active
    user.is_active = change_active
    user.save()

    st = TblServiceTime(
        user_id = user_id,
        prev_time = get_active_txt(prev_is_active),
        prev_time_rad = '',
        after_time = get_active_txt(change_active),
        after_time_rad = '',
        diff = '활성화 변경',
        reason = change_reason,
        regist_date = datetime.datetime.now())
    st.save()

    title, text = get_swal('SUCCESS_ACTIVE')
    return JsonResponse({'result': 200, 'title': title, 'text': text})


# (2020-03-17)
@allow_admin
def api_delete_user(request):
    change_reason = request.POST.get('change_reason')
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    
    # 이메일
    email = user.email

    # 이메일(삭제)
    delete_email = 'delete__' + user.email + '#' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    # racheck 처리
    Radcheck.objects.using('radius').filter(username=email).update(username=delete_email)

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

    title, text = get_swal('SUCCESS_DELETE_USER')
    return JsonResponse({'result': 200, 'title': title, 'text': text})


# (2025-11-19) 본인인증 메일 재전송 (관리자)
@allow_admin
def api_send_verify_email(request):
    email = request.POST.get('email', '').strip()
    if not email:
        title, text = get_swal('NULL_EMAIL')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 대상 유저 존재 확인
    try:
        TblUser.objects.get(email=email)
    except BaseException:
        title, text = get_swal('NOT_USER')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 메일 발송 처리
    try:
        print('[verify_email] start for', email)
        aes = AESCipher()
        before = datetime.datetime.now()
        before_time = before.strftime('%Y-%m-%d %H:%M')
        token_bytes = aes.encrypt(before_time + '|' + email)
        enc_email = quote(token_bytes.decode('ascii'))
        print('[verify_email] token generated length=', len(token_bytes))

        subject = 'TITAN NETWORKS Account Activation Email'
        content = (
            f"""
            <div style="width: 600px; border: solid 1px #bbbbbb; text-align: center; border: solid 6px #673AB7;">
              <div style='background-color: #673AB7; text-align: center; color: #ffffff; padding: 15px;'>
                TITAN NETWORKS
              </div>
              <div style="margin-top: 30px; margin-bottom: 10px; font-weight: bold; font-size: 20px;">
                회원가입 인증 메일입니다
              </div>
              <div style="font-size: 14px; margin-bottom: 35px;">
                회원가입이 완료되었습니다
              </div>
              <div style="border-top: solid 1px #bbbbbb; border-bottom: solid 1px #bbbbbb; padding: 20px; font-size: 15px;">
                <div style="font-size: 12px; color: #6f6f6f;">이메일 인증 확인</div>
                <div style="margin-top: 5px;">
                  <a href='http://{settings.FULL_URL}/api_login_active?active_code={enc_email}'>여기를 클릭하시면 인증이 완료됩니다</a>
                </div>
              </div>
              <div style="border-top: solid 1px #bbbbbb; border-bottom: solid 1px #bbbbbb; padding: 20px; font-size: 15px;">
                <div style="font-size: 12px; color: #6f6f6f;">위링크로 확인이 안되시면 아래 링크를 이용해주세요!</div>
                <div style="margin-top: 5px;">
                  <a href='http://{settings.FULL_URL2}/api_login_active?active_code={enc_email}'>이메일인증을 위한 두번째 링크</a>
                </div>
                <div style="margin-top: 5px;">
                  <a href='http://{settings.FULL_URL3}/api_login_active?active_code={enc_email}'>이메일인증을 위한 세번째 링크</a>
                </div>
              </div>
              <div style="padding: 35px; font-size: 14px;">TITAN NETWORKS을 이용해 주셔서 감사합니다</div>
              <div style="padding: 20px; background: #f5f5f5; font-size: 14px;">본 메일은 발신전용 메일입니다</div>
            </div>
            """
        )

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_EMAIL
        msg['To'] = email
        msg.attach(MIMEText(content, 'html', _charset='utf-8'))

        print('[verify_email] smtp connect', settings.SMTP_HOST, settings.SMTP_PORT)
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        print('[verify_email] smtp login as', settings.SMTP_ID)
        server.login(settings.SMTP_ID, settings.SMTP_PW)
        print('[verify_email] smtp send start')
        server.sendmail(settings.SMTP_EMAIL, [email], msg.as_string())
        server.quit()
        print('[verify_email] smtp send ok')

        title, text = get_swal('SUCCESS_SIGNUP')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except smtplib.SMTPException as err:
        import traceback
        print('[verify_email][SMTPException]', repr(err))
        traceback.print_exc()
        return JsonResponse({'result': 500, 'title': '알림', 'text': '메일 전송 중 오류가 발생했습니다', 'debug': str(err)})
    except Exception as err:
        import traceback
        print('[verify_email][Exception]', repr(err))
        traceback.print_exc()
        return JsonResponse({'result': 500, 'title': '알림', 'text': '메일 전송 중 오류가 발생했습니다', 'debug': str(err)})


# (2020-03-17)
@allow_admin
def api_use_user(request):
    with connections['default'].cursor() as cur:
        query = '''
            SELECT count(*) as cnt
            FROM radius.radacct 
            where  acctstoptime is null
        '''
        try:
            cur.execute(query)
            rows = dictfetchall(cur)
            use_count = rows[0]['cnt']
        except BaseException as err:
            use_count = 0
    return JsonResponse({'result': 200, 'use_count': use_count})


# (2020-03-17)
@allow_admin
def api_create_regist_ban(request):
    ban_type = request.POST.get('ban_type')
    ban_content = request.POST.get('ban_content')
    ban_reason = request.POST.get('ban_reason')
    try:
        rb = TblRegistBan(
            type=ban_type,
            content=ban_content,
            reason=ban_reason,
            delete_yn='N',
            regist_date=datetime.datetime.now()
        )
        rb.save()

        title, text = get_swal('SUCCESS_REGIST_BAN')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        print('err => ', err)
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    

# (2020-03-17)
@allow_admin
def api_update_regist_ban(request):
    seq = request.POST.get('seq')
    ban_type = request.POST.get('ban_type')
    ban_content = request.POST.get('ban_content')
    ban_reason = request.POST.get('ban_reason')

    try:
        tb = TblRegistBan.objects.get(id=seq)
        tb.type = ban_type
        tb.content = ban_content
        tb.reason = ban_reason
        tb.modify_date = datetime.datetime.now()
        tb.delete_date = None
        tb.delete_yn = 'N'
        tb.save()

        title, text = get_swal('SUCCESS_REGIST_BAN')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        print('err => ', err)
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2020-03-17)
@allow_admin
def api_delete_regist_ban(request):
    seq = request.POST.get('seq')
    try:
        tb = TblRegistBan.objects.get(id=seq)
        tb.delete_yn = 'Y'
        tb.delete_date = datetime.datetime.now()
        tb.save()
        title, text = get_swal('SUCCESS_REGIST_BAN_DEL')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        print('err => ', err)
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    


# (2020-03-17)
@allow_admin
def api_read_regist_ban(request):
    seq = request.POST.get('seq')
    tb = TblRegistBan.objects.get(id=seq)
    res = {
        'type': tb.type,
        'content': tb.content,
        'reason': tb.reason
    }
    return JsonResponse({
        'resCode': 200,
        'resMsg': 'success',
        'resData': res
    })

# (2025-05-02)(modified on 08/24)  Read user data from django_session for killing app login session
@allow_admin
def api_read_session_list(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    import base64, json
    from datetime import timedelta

    email = request.POST.get('email')
    now = timezone.now()
    result = []

    # 성능: 필요한 컬럼만 select
    sessions = Session.objects.filter(expire_date__gt=now).only(
        'session_key', 'session_data', 'expire_date'
    )

    matched_keys = []
    for s in sessions:
        try:
            # django_session.session_data: base64(b'salt:{"...json..."}')
            decoded = base64.b64decode(s.session_data)
            sep = decoded.find(b':')
            if sep == -1:
                continue

            json_data = decoded[sep + 1:]
            data = json.loads(json_data.decode('utf-8'))

            if data.get('email') == email:
                expire = s.expire_date
                remaining = (expire - now).total_seconds()
                result.append({
                    'key': s.session_key,
                    # 프런트에서 바로 표기 가능하도록 ISO8601 문자열도 제공
                    'expire': expire.isoformat(),     # 예: "2025-09-24T21:15:00+09:00"
                    'expire_unix': int(expire.timestamp()),
                    'remaining_seconds': int(remaining),  # 남은시간(초)
                    # 기기 정보 (아래에서 채움)
                    'device_type': '',
                    'device_os': '',
                    'app_version': '',
                    'device_ip': '',
                    'device_country': '',
                    'device_city': '',
                    'device_isp': '',
                    'login_time': '',
                })
                matched_keys.append(s.session_key)
        except Exception:
            continue

    # tbl_device_info에서 session_key 매칭으로 기기정보 가져오기
    device_map = {}
    if matched_keys:
        from django.db import connections
        with connections['default'].cursor() as cur:
            ph = ','.join(['%s'] * len(matched_keys))
            cur.execute(f"""
                SELECT session_key, device_type, device_os, app_version,
                       device_ip, device_country, device_city, device_isp, login_time
                FROM tbl_device_info
                WHERE session_key IN ({ph})
                ORDER BY login_time DESC
            """, matched_keys)
            for row in cur.fetchall():
                sk = row[0]
                if sk not in device_map:  # 같은 세션키에 여러 row면 최신만
                    device_map[sk] = {
                        'device_type': row[1] or '',
                        'device_os': row[2] or '',
                        'app_version': row[3] or '',
                        'device_ip': row[4] or '',
                        'device_country': row[5] or '',
                        'device_city': row[6] or '',
                        'device_isp': row[7] or '',
                        'login_time': row[8].strftime('%Y-%m-%d %H:%M:%S') if row[8] else '',
                    }

    # session_key 매칭 실패한 세션 → uuid별 최신 device_info로 1:1 매칭
    unmatched = [r for r in result if r['key'] not in device_map]
    if unmatched:
        from django.db import connections
        with connections['default'].cursor() as cur:
            cur.execute("SELECT id FROM tbl_user WHERE email = %s", [email])
            uid_row = cur.fetchone()
            if uid_row:
                uid = uid_row[0]
                # uuid별 최신 1개만 (중복 제거)
                cur.execute("""
                    SELECT di.device_type, di.device_os, di.app_version,
                           di.device_ip, di.device_country, di.device_city, di.device_isp,
                           di.login_time, di.session_key, di.device_uuid
                    FROM tbl_device_info di
                    INNER JOIN (
                        SELECT device_uuid, MAX(id) as max_id
                        FROM tbl_device_info
                        WHERE user_id = %s AND device_uuid != ''
                        GROUP BY device_uuid
                    ) latest ON di.id = latest.max_id
                    ORDER BY di.login_time DESC
                """, [uid])
                uuid_devices = cur.fetchall()

                # 이미 session_key로 매칭된 uuid는 제외
                matched_uuids = set()
                for sk, info in device_map.items():
                    # device_map의 값에서 uuid를 알 수 없으므로, session_key로 매칭된 것만 제외
                    pass

                # 각 unmatched 세션에 uuid별 device를 순서대로 1:1 할당
                used_uuids = set()
                for sess in unmatched:
                    for dev in uuid_devices:
                        dev_uuid = dev[9] or ''
                        if not dev_uuid or dev_uuid in used_uuids:
                            continue
                        dev_sk = dev[8] or ''
                        if dev_sk and dev_sk in device_map:
                            continue  # 이미 session_key 매칭으로 다른 세션에 연결됨
                        device_map[sess['key']] = {
                            'device_type': dev[0] or '',
                            'device_os': dev[1] or '',
                            'app_version': dev[2] or '',
                            'device_ip': dev[3] or '',
                            'device_country': dev[4] or '',
                            'device_city': dev[5] or '',
                            'device_isp': dev[6] or '',
                            'login_time': dev[7].strftime('%Y-%m-%d %H:%M:%S') if dev[7] else '',
                        }
                        used_uuids.add(dev_uuid)
                        break

    # 기기정보 합치기 + 웹/앱 구분
    for sess in result:
        info = device_map.get(sess['key'], {})
        sess['device_type'] = info.get('device_type', '')
        sess['device_os'] = info.get('device_os', '')
        sess['app_version'] = info.get('app_version', '')
        sess['device_ip'] = info.get('device_ip', '')
        sess['device_country'] = info.get('device_country', '')
        sess['device_city'] = info.get('device_city', '')
        sess['device_isp'] = info.get('device_isp', '')
        sess['login_time'] = info.get('login_time', '')
        # device_map에 매칭이 있으면 앱 로그인, 없으면 웹사이트 로그인
        sess['is_web'] = sess['key'] not in device_map

    # NAS 서버 IP 목록 조회 — IP차단 시 서버IP 오차단 방지
    nas_ip_set = set()
    try:
        with connections['default'].cursor() as cur:
            cur.execute("SELECT hostip FROM tbl_agent3 WHERE is_active = 1")
            nas_ip_set = {row[0] for row in cur.fetchall() if row[0]}
    except Exception:
        pass

    # 각 세션에 is_server_ip 플래그 추가
    for sess in result:
        sess['is_server_ip'] = sess['device_ip'] in nas_ip_set

    # ── NAS 연결 정보 (radacct) 조회 ──
    nas_connections = []
    try:
        with connections['default'].cursor() as cur:
            cur.execute("""
                SELECT r.radacctid, r.nasipaddress, r.nasporttype, r.nasportid,
                       r.callingstationid, r.acctstarttime, r.acctuniqueid, r.acctsessionid,
                       COALESCE(a.name, '') AS server_name,
                       COALESCE(a.telecom, '') AS server_telecom
                FROM radius.radacct r
                LEFT JOIN titan.tbl_agent3 a ON r.nasipaddress = a.hostip
                WHERE r.username = %s AND r.acctstoptime IS NULL
                ORDER BY r.radacctid DESC
            """, [email])
            for row in cur.fetchall():
                # callingstationid에서 IP 추출 (27.115.70.46=5B4500=5D → 27.115.70.46)
                csi = row[4] or ''
                client_ip = csi.split('=')[0] if '=' in csi else csi
                # nasporttype → 프로토콜 매핑
                port_type = row[2] or ''
                port_id = str(row[3] or '')
                if port_type == 'V2RAY':
                    protocol = 'V2RAY'
                elif port_type == 'ISDN':
                    protocol = 'OPENVPN'
                elif port_id == '443':
                    protocol = 'SSTP'
                else:
                    protocol = 'IKEv2'
                nas_connections.append({
                    'radacctid': row[0],
                    'nasipaddress': row[1] or '',
                    'nasporttype': port_type,
                    'nasportid': port_id,
                    'client_ip': client_ip,
                    'acctstarttime': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else '',
                    'acctuniqueid': row[6] or '',
                    'acctsessionid': row[7] or '',
                    'server_name': row[8],
                    'server_telecom': row[9],
                    'protocol': protocol,
                })
    except Exception as e:
        logger.exception('api_read_session_list: failed to query NAS connections')

    # 앱 세션에 NAS 연결 매칭: device_ip 기반
    for sess in result:
        sess['nas_connections'] = []
        if sess.get('device_ip'):
            for nc in nas_connections:
                if nc['client_ip'] == sess['device_ip']:
                    sess['nas_connections'].append(nc)

    # 앱 세션 먼저, 그 안에서 만료 임박한 순으로 정렬
    result.sort(key=lambda x: (x.get('is_web', False), x['expire_unix']))

    return JsonResponse({'sessions': result, 'nas_connections': nas_connections})


# (2025-05-02)(modified on 2026-02-11)  Kill user session from django_session for User App kill after changing user password
@allow_admin
def api_delete_session(request):
    from django.contrib.sessions.models import Session
    from django.db import connections

    session_key = request.POST.get('session_key')
    try:
        Session.objects.get(session_key=session_key).delete()
    except Session.DoesNotExist:
        pass  # 세션이 이미 삭제되었더라도 device_info 정리는 계속 진행

    # tbl_device_info에서 session_key 정리 (퇴출된 세션의 기기 참조 제거)
    try:
        with connections['default'].cursor() as cur:
            cur.execute(
                "UPDATE tbl_device_info SET session_key = NULL "
                "WHERE session_key = %s",
                [session_key]
            )
            affected = cur.rowcount
        if affected > 0:
            logger.info(f'api_delete_session: cleared session_key in {affected} device_info rows')
    except Exception:
        logger.exception('api_delete_session: failed to clear device_info session_key')

    return JsonResponse({'result': 200})


# (2026-02-11) NAS VPN 연결 강제종료 API
@allow_admin
def api_disconnect_nas(request):
    import paramiko
    import socket
    import time

    radacctid = request.POST.get('radacctid')
    email = request.POST.get('email', '')
    if not radacctid:
        return JsonResponse({'result': 400, 'message': 'radacctid 필요'})

    try:
        with connections['default'].cursor() as cur:
            # radacct에서 연결 정보 조회
            cur.execute("""
                SELECT radacctid, username, nasipaddress, nasporttype, nasportid,
                       acctsessionid, callingstationid
                FROM radius.radacct
                WHERE radacctid = %s AND acctstoptime IS NULL
            """, [radacctid])
            rows = cur.fetchall()
            if not rows:
                return JsonResponse({'result': 404, 'message': '활성 연결 없음'})

            row = rows[0]
            username = row[1]
            nasipaddress = row[2]
            nasporttype = row[3] or ''
            nasportid = str(row[4] or '')
            acctsessionid = row[5] or ''

            # NAS SSH 접속 정보
            cur.execute("""
                SELECT username, password, name FROM titan.tbl_agent3 WHERE hostip = %s
            """, [nasipaddress])
            ssh_rows = cur.fetchall()

            ssh_done = False
            if ssh_rows:
                ssh_user = ssh_rows[0][0]
                ssh_pass = ssh_rows[0][1]
                nas_name = ssh_rows[0][2]

                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(nasipaddress, username=ssh_user, password=ssh_pass, timeout=3)

                    if nasporttype == 'ISDN':  # OpenVPN
                        channel = ssh.invoke_shell()
                        channel.send("telnet 127.0.0.1 1199\n")
                        time.sleep(0.5)
                        channel.send("mykakao9898\n")
                        time.sleep(0.2)
                        channel.send('kill ' + username + '\n')
                        time.sleep(0.2)
                        channel.send("exit\n")
                        time.sleep(0.2)
                        channel.send("exit\n")
                    elif nasportid == '443':  # SSTP
                        sessionid = acctsessionid.replace('=5BSSTP=5D', '[SSTP]')
                        cmd = "/usr/local/vpnserver/vpncmd " + nasipaddress + " /SERVER /HUB:TITAN /PASSWORD:'xkdlxksdpdlwjsxm12!@' /CMD SessionDisconnect " + sessionid
                        ssh.exec_command(cmd)
                    elif nasporttype == 'V2RAY':  # V2RAY → radacct만 업데이트
                        pass
                    else:  # IKEv2
                        cmd = 'strongswan statusall | grep ' + username
                        _stdin, _stdout, _stderr = ssh.exec_command(cmd)
                        time.sleep(0.5)
                        try:
                            first = _stdout.readline().strip()
                        except Exception:
                            first = ''
                        if first:
                            sa = first.split(':')[0].strip()
                            if sa:
                                down_cmd = 'strongswan stroke down-nb ' + sa
                                ssh.exec_command(down_cmd)
                                time.sleep(0.2)
                                ssh.exec_command(down_cmd)
                    ssh.close()
                    ssh_done = True
                except socket.timeout:
                    logger.warning(f'api_disconnect_nas: SSH timeout for {nasipaddress}')
                    ssh_done = True  # timeout이어도 radacct 정리는 계속
                except Exception as e:
                    logger.exception(f'api_disconnect_nas: SSH error for {nasipaddress}: {e}')
                    ssh_done = True
            else:
                logger.warning(f'api_disconnect_nas: No SSH credentials for {nasipaddress}')
                ssh_done = True

            # radacct acctstoptime + acctsessiontime 업데이트 (연결 종료 마킹)
            import datetime
            cur.execute("""
                UPDATE radius.radacct SET acctstoptime = %s,
                acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, %s)
                WHERE radacctid = %s
            """, [datetime.datetime.now(), datetime.datetime.now(), radacctid])

            logger.info(f'api_disconnect_nas: disconnected {username} from {nasipaddress} (radacctid={radacctid})')
            return JsonResponse({'result': 200, 'message': 'NAS 연결 종료 완료'})

    except Exception as e:
        logger.exception(f'api_disconnect_nas error: {e}')
        return JsonResponse({'result': 500, 'message': str(e)})


# (2025-08-24)  Kill ALL sessions for a user
@allow_admin
def api_delete_all_sessions(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    import base64, json

    email = request.POST.get('email')
    count = 0
    deleted_keys = []

    sessions = Session.objects.filter(expire_date__gt=timezone.now())
    for s in sessions:
        try:
            decoded = base64.b64decode(s.session_data)
            sep = decoded.find(b':')
            if sep == -1:
                continue
            data = json.loads(decoded[sep + 1:].decode('utf-8'))
            if data.get('email') == email:
                deleted_keys.append(s.session_key)
                s.delete()
                count += 1
        except Exception:
            continue

    # tbl_device_info에서 삭제된 세션의 session_key도 정리
    if deleted_keys:
        try:
            from django.db import connections
            with connections['default'].cursor() as cur:
                ph = ','.join(['%s'] * len(deleted_keys))
                cur.execute(
                    f"UPDATE tbl_device_info SET session_key = NULL WHERE session_key IN ({ph})",
                    deleted_keys
                )
        except Exception:
            pass

    return JsonResponse({'result': 200, 'deleted': count})


# (2026-02-11)  Kill only WEB sessions for a user (sessions without device_info)
@allow_admin
def api_delete_web_sessions(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from django.db import connections
    import base64, json

    email = request.POST.get('email')
    now = timezone.now()
    count = 0

    # tbl_device_info에 있는 session_key 목록 (앱 세션)
    with connections['default'].cursor() as cur:
        cur.execute("SELECT DISTINCT session_key FROM tbl_device_info WHERE session_key IS NOT NULL")
        app_keys = {row[0] for row in cur.fetchall()}

    sessions = Session.objects.filter(expire_date__gt=now)
    for s in sessions:
        try:
            decoded = base64.b64decode(s.session_data)
            sep = decoded.find(b':')
            if sep == -1:
                continue
            data = json.loads(decoded[sep + 1:].decode('utf-8'))
            if data.get('email') == email and s.session_key not in app_keys:
                s.delete()
                count += 1
        except Exception:
            continue

    return JsonResponse({'result': 200, 'deleted': count})


# ===== 회원 관리 통합 조회 (서비스시간 + 세션 + 비번 + 활성 한번에) =====
@allow_admin
def api_read_user_manage_info(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id=user_id)
    email = user.email

    # 서비스 시간
    service_time = my_radius_time(email, 'str')

    # 세션
    try:
        session = Radcheck.objects.using('radius').get(username=email, attribute='Simultaneous-Use').value
    except Exception:
        session = '1'

    # 비밀번호
    try:
        password = Radcheck.objects.using('radius').get(username=email, attribute='Cleartext-Password').value
    except Exception:
        password = 'ERROR'

    # 활성 상태
    is_active = user.is_active

    return JsonResponse({
        'result': 200,
        'email': email,
        'service_time': service_time,
        'session': session,
        'password': password,
        'is_active': is_active,
    })


# ===== 사용자별 로그인 로그 (최근 50건) =====
@allow_admin
def api_read_user_login_logs(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id=user_id)
    email = user.email

    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT x.id, y.email, x.app_version, x.device_type, x.device_ip,
                   x.device_country, x.device_city, x.device_isp, x.login_time,
                   x.load_balancer, x.api_url
            FROM tbl_device_info x
            JOIN tbl_user y ON x.user_id = y.id
            WHERE y.email = %s
            ORDER BY x.login_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    logs = []
    for r in rows:
        logs.append({
            'id': r[0],
            'email': r[1],
            'app_version': r[2] or '',
            'device_type': r[3] or '',
            'device_ip': r[4] or '',
            'country': r[5] or '',
            'city': r[6] or '',
            'isp': r[7] or '',
            'login_time': str(r[8]) if r[8] else '',
            'load_balancer': r[9] or '',
            'api_url': r[10] or '',
        })
    return JsonResponse({'result': 200, 'logs': logs})


# ===== 기기/세션 접속금지 (2026-02-11) =====
@allow_admin
def api_ban_device(request):
    """각 차단 유형은 독립적으로 동작 (자동 복합 차단 없음)
    ban_type:
      - device  : 이 기기 UUID만 차단 (Android 확실, iOS는 재설치 시 우회 가능)
      - session : 이 계정만 로그인 차단 (다른 기기에서도 이 계정 사용 불가)
      - ip      : 이 IP에서 모든 로그인 차단 (같은 IP의 다른 사용자도 영향)
    """
    import datetime as dt

    session_key = request.POST.get('session_key', '').strip()
    email = request.POST.get('email', '').strip()
    ban_type = request.POST.get('ban_type', 'session')  # session / device / ip
    reason = request.POST.get('reason', '')
    banned_by = request.session.get('email', 'admin')

    if not email:
        return JsonResponse({'result': 400, 'msg': '이메일이 필요합니다'})

    # 유저 정보
    try:
        user = TblUser.objects.get(email=email)
    except TblUser.DoesNotExist:
        return JsonResponse({'result': 404, 'msg': '사용자를 찾을 수 없습니다'})

    # tbl_device_info에서 세션키 또는 최근 접속 기기 정보 가져오기
    device_uuid = ''
    device_ip = ''
    device_type = ''
    device_os = ''

    with connections['default'].cursor() as cur:
        if session_key:
            cur.execute("""
                SELECT device_uuid, device_ip, device_type, device_os
                FROM tbl_device_info
                WHERE session_key = %s
                ORDER BY login_time DESC LIMIT 1
            """, [session_key])
        else:
            cur.execute("""
                SELECT device_uuid, device_ip, device_type, device_os
                FROM tbl_device_info
                WHERE user_id = %s
                ORDER BY login_time DESC LIMIT 1
            """, [user.id])
        row = cur.fetchone()
        if row:
            device_uuid = row[0] or ''
            device_ip = row[1] or ''
            device_type = row[2] or ''
            device_os = row[3] or ''

    now = dt.datetime.now()

    # IP 차단 시 NAS 서버 IP인지 확인 — 서버 IP 차단 방지
    if ban_type == 'ip' and device_ip:
        with connections['default'].cursor() as cur:
            cur.execute(
                "SELECT name FROM tbl_agent3 WHERE hostip = %s AND is_active = 1 LIMIT 1",
                [device_ip]
            )
            nas_row = cur.fetchone()
            if nas_row:
                return JsonResponse({
                    'result': 403,
                    'msg': f'⚠️ 이 IP({device_ip})는 NAS 서버({nas_row[0]})의 IP입니다.\n'
                           f'서버 IP를 차단하면 해당 서버를 통해 접속하는 모든 유저가 차단됩니다.\n'
                           f'IP차단 대신 "계정차단" 또는 "기기차단"을 사용하세요.'
                })

    # 각 유형별 단일 차단 레코드 생성
    ban = TblBannedDevice(
        user_id=user.id,
        email=email if ban_type == 'session' else '',
        device_uuid=device_uuid if ban_type == 'device' else '',
        device_ip=device_ip if ban_type == 'ip' else '',
        device_type=device_type,
        device_os=device_os,
        session_key=session_key,
        reason=reason,
        ban_type=ban_type,
        ban_group=None,
        is_active=1,
        banned_by=banned_by,
        regist_date=now
    )
    ban.save()

    # 세션 즉시 삭제
    deleted_count = 0
    from django.contrib.sessions.models import Session
    if session_key:
        try:
            Session.objects.get(session_key=session_key).delete()
            deleted_count = 1
        except Session.DoesNotExist:
            pass
    else:
        # 세션키 지정 안 한 경우 해당 유저의 모든 세션 삭제
        from django.utils import timezone
        import base64, json as _json
        sessions = Session.objects.filter(expire_date__gt=timezone.now())
        for s in sessions:
            try:
                decoded = base64.b64decode(s.session_data)
                sep = decoded.find(b':')
                if sep == -1:
                    continue
                data = _json.loads(decoded[sep + 1:].decode('utf-8'))
                if data.get('email') == email:
                    s.delete()
                    deleted_count += 1
            except Exception:
                continue

    ban_type_txt = {'session': '계정 차단', 'device': '기기(UUID) 차단', 'ip': 'IP 차단'}.get(ban_type, ban_type)
    return JsonResponse({
        'result': 200,
        'msg': f'{ban_type_txt} 완료 (세션 {deleted_count}개 삭제)',
        'device_uuid': device_uuid,
        'device_ip': device_ip,
    })


# ===== 접속금지 해제 (2026-02-11) =====
@allow_admin
def api_unban_device(request):
    import datetime as dt
    ban_id = request.POST.get('ban_id')
    try:
        ban = TblBannedDevice.objects.get(id=ban_id)
        now = dt.datetime.now()
        # 그룹 차단이면 같은 그룹 전체 해제
        if ban.ban_group:
            group_bans = TblBannedDevice.objects.filter(ban_group=ban.ban_group, is_active=1)
            count = group_bans.update(is_active=0, modify_date=now)
            return JsonResponse({'result': 200, 'msg': f'그룹 차단 {count}건 해제 완료'})
        else:
            ban.is_active = 0
            ban.modify_date = now
            ban.save()
            return JsonResponse({'result': 200, 'msg': '차단 해제 완료'})
    except TblBannedDevice.DoesNotExist:
        return JsonResponse({'result': 404, 'msg': '차단 기록을 찾을 수 없습니다'})


# ===== 접속금지 목록 조회 (2026-02-11) =====
@allow_admin
def api_read_banned_devices(request):
    email = request.POST.get('email', '').strip()

    with connections['default'].cursor() as cur:
        if email:
            cur.execute("""
                SELECT id, user_id, email, device_uuid, device_ip, device_type,
                       device_os, session_key, reason, ban_type, is_active,
                       banned_by, regist_date, modify_date, ban_group
                FROM tbl_banned_device
                WHERE email = %s
                ORDER BY regist_date DESC
            """, [email])
        else:
            cur.execute("""
                SELECT id, user_id, email, device_uuid, device_ip, device_type,
                       device_os, session_key, reason, ban_type, is_active,
                       banned_by, regist_date, modify_date, ban_group
                FROM tbl_banned_device
                WHERE is_active = 1
                ORDER BY regist_date DESC
                LIMIT 100
            """)
        rows = cur.fetchall()

    result = []
    for r in rows:
        result.append({
            'id': r[0],
            'user_id': r[1],
            'email': r[2] or '',
            'device_uuid': r[3] or '',
            'device_ip': r[4] or '',
            'device_type': r[5] or '',
            'device_os': r[6] or '',
            'session_key': r[7] or '',
            'reason': r[8] or '',
            'ban_type': r[9] or '',
            'is_active': r[10],
            'banned_by': r[11] or '',
            'regist_date': str(r[12]) if r[12] else '',
            'modify_date': str(r[13]) if r[13] else '',
            'ban_group': r[14] or '',
        })

    return JsonResponse({'result': 200, 'bans': result})
@allow_admin
def api_read_user_fail_logs(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id=user_id)
    email = user.email

    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT id, username, platform, app_version, server_name,
                   server_protocol, user_ip, user_location, device_info, failed_time
            FROM tbl_agent_failed
            WHERE username = %s
            ORDER BY failed_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    logs = []
    for r in rows:
        logs.append({
            'id': r[0],
            'username': r[1] or '',
            'platform': r[2] or '',
            'app_version': r[3] or '',
            'server_name': r[4] or '',
            'protocol': r[5] or '',
            'ip': r[6] or '',
            'location': r[7] or '',
            'device': r[8] or '',
            'failed_time': str(r[9]) if r[9] else '',
        })
    return JsonResponse({'result': 200, 'logs': logs})


# ===== 사용자별 강제종료 로그 (최근 50건) =====
@allow_admin
def api_read_user_disconnect_logs(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id=user_id)
    email = user.email

    with connections['default'].cursor() as cur:
        cur.execute("""
            SELECT d.id, d.username, d.user_session, d.connected_count, d.protocol,
                   IFNULL(d.server_name, '') as server_name,
                   IFNULL(a.telecom, '') as telecom,
                   d.disconnected_time, d.old_ip, d.new_ip
            FROM tbl_disconnection d
            LEFT JOIN tbl_agent3 a ON a.name = d.server_name
            WHERE d.username = %s
            ORDER BY d.disconnected_time DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    logs = []
    for r in rows:
        logs.append({
            'id': r[0],
            'username': r[1] or '',
            'session': r[2],
            'connected_count': r[3],
            'protocol': r[4] or '',
            'server_name': r[5] or '',
            'telecom': r[6] or '',
            'disconnected_time': str(r[7]) if r[7] else '',
            'old_ip': r[8] or '',
            'new_ip': r[9] or '',
        })
    return JsonResponse({'result': 200, 'logs': logs})


# ===== 사용자별 서버접속 로그 (최근 50건) =====
@allow_admin
def api_read_user_connection_logs(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id=user_id)
    email = user.email

    with connections['radius'].cursor() as cur:
        cur.execute("""
            SELECT radacctid, username, nasipaddress, nasporttype,
                   acctstarttime, acctstoptime,
                   acctinputoctets, acctoutputoctets,
                   callingstationid, framedipaddress
            FROM radacct
            WHERE username = %s
            ORDER BY acctstarttime DESC
            LIMIT 50
        """, [email])
        rows = cur.fetchall()

    logs = []
    for r in rows:
        # callingstationid에서 순수 IP 추출
        csid = r[8] or ''
        idx = csid.find('=5B')
        client_ip = csid[:idx] if idx > 0 else csid

        logs.append({
            'id': r[0],
            'username': r[1] or '',
            'nas_ip': r[2] or '',
            'nas_type': r[3] or '',
            'start_time': str(r[4]) if r[4] else '',
            'stop_time': str(r[5]) if r[5] else '',
            'input_bytes': r[6] or 0,
            'output_bytes': r[7] or 0,
            'client_ip': client_ip,
            'private_ip': r[9] or '',
        })
    return JsonResponse({'result': 200, 'logs': logs})
