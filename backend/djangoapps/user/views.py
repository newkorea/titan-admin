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

    # where 조건 동적 연산
    wc = ""
    if id != '':
        wc += " and x.id = '" + id + "'"
    if email != '':
        wc += " and x.email like '%" + email + "%'"
    if username != '':
        wc += " and x.username like '%" + username + "%'"
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
            			c.name as is_staff,
            			a.name as delete_yn
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


# (2020-03-17)
@allow_admin
def api_read_user_detail(request):
    user_id = request.POST.get('user_id')
    user = TblUser.objects.get(id = user_id)
    ret = {
        'id': user.id,
        'email': user.email,
        'rec': user.rec,
        'regist_rec': user.regist_rec,
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

    if change_session == '1' or change_session == '2':
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
                diff = '세션변경',
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
