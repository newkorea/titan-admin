import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from django.db import transaction


# 회원관리 페이지 렌더링 (2020-03-16)
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


# 회원정보 로드 APi (2020-03-16)
@allow_admin
def api_user_read(request):
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



















# 회원관리 상세 페이지 렌더링 (2019.09.15 12:04 점검완료)
@allow_cs
def api_user_detail(request):
    seq = int(request.POST.get('seq'))
    u1 = TblUser.objects.get(id = seq)
    ul1 = TblUserLogin.objects.get(user_id = seq)
    p_code = u1.phone_country
    p_number = u1.phone
    phone = '+' + p_code + ' ' + p_number
    s_code = u1.sns_code
    s_name = u1.sns_name
    if s_code == None and s_name == None:
        sns = ''
    else:
        sns = '({snsName}) {snsContent}'.format(
            snsName=TblCodeDetail.objects.get(group_code='message', code=s_code).name,
            snsContent=s_name)
    list = []
    sd = {}
    sd['id'] = u1.id
    sd['email'] = u1.email
    sd['username'] = u1.username
    sd['phone'] = phone
    sd['gender'] = u1.gender
    sd['birth_date'] = u1.birth_date
    sd['sns'] = sns
    sd['rec'] = u1.rec
    sd['regist_rec'] = u1.regist_rec
    sd['regist_ip'] = u1.regist_ip
    sd['regist_date'] = u1.regist_date
    sd['modify_date'] = u1.modify_date
    sd['is_active'] = u1.is_active
    sd['is_staff'] = u1.is_staff
    sd['delete_yn'] = u1.delete_yn
    sd['black_yn'] = u1.black_yn
    sd['attempt'] = ul1.attempt
    sd['login_ip'] = ul1.login_ip
    sd['login_date'] = ul1.login_date
    list.append(sd)
    return JsonResponse({'result': list})


# 회원정보 수정 APi (2019.09.15 12:05 점검완료)
@allow_cs
def api_user_edit(request):
    active = request.POST.get('active')
    delete_yn = request.POST.get('delete_yn')
    staff = request.POST.get('staff')
    black = request.POST.get('black')
    id = request.POST.get('id')
    u1 = TblUser.objects.get(id = id)
    u1.is_active = active
    u1.delete_yn = delete_yn
    u1.is_staff = staff
    u1.black_yn = black
    u1.save()
    return JsonResponse({'result': 200})
