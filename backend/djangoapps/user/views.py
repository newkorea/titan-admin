import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from django.db import transaction


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
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

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
    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

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
            select w.*
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
            JOIN ( SELECT @rnum := -1 ) AS r
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start)
        # print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = dictfetchall(cur)

    returnData = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(returnData)


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
        deleted_user = rows[0][0]/3
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
                })
        except Exception:
            continue

    # 만료 임박한 순으로 정렬(선택)
    result.sort(key=lambda x: x['expire_unix'])

    return JsonResponse({'sessions': result})


# (2025-05-02)  Kill user session from django_session for User App kill after changing user password
@allow_admin
def api_delete_session(request):
    from django.contrib.sessions.models import Session

    session_key = request.POST.get('session_key')
    try:
        Session.objects.get(session_key=session_key).delete()
        return JsonResponse({'result': 200})
    except Session.DoesNotExist:
        return JsonResponse({'result': 404})

# (2025-08-24)  Kill ALL sessions for a user
@allow_admin
def api_delete_all_sessions(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    import base64, json

    email = request.POST.get('email')
    count = 0

    sessions = Session.objects.filter(expire_date__gt=timezone.now())
    for s in sessions:
        try:
            decoded = base64.b64decode(s.session_data)
            sep = decoded.find(b':')
            if sep == -1:
                continue
            data = json.loads(decoded[sep + 1:].decode('utf-8'))
            if data.get('email') == email:
                s.delete()
                count += 1
        except Exception:
            continue

    return JsonResponse({'result': 200, 'deleted': count})
