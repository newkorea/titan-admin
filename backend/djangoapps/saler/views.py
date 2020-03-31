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
@allow_dealer
def saler_user(request):
    delete_list = TblCodeDetail.objects.filter(group_code='delete_yn')
    active_list = TblCodeDetail.objects.filter(group_code='is_active')
    staff_list = TblCodeDetail.objects.filter(group_code='is_staff')
    context = {
        'delete_list': delete_list,
        'active_list': active_list,
        'staff_list': staff_list
    }
    return render(request, 'saler/user.html', context)


# (2020-03-16)
@allow_dealer
def api_read_saler_user(request):

    # 본인 추천인코드
    rec = request.session['rec']

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

    # order by 컬럼
    column_name = ['id', 'email', 'username', 'delete_yn', 'is_active']

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
            and x.regist_rec = '{rec}'
            {wc}
        '''.format(wc=wc, rec=rec)
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
                and x.regist_rec = '{rec}'
                {wc}
                order by {orderby_col} {orderby_opt}
            	limit {start}, 10
            ) w
            JOIN ( SELECT @rnum := -1 ) AS r
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            rec=rec)
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