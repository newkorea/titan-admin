import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from backend.models_radius import *
import datetime
from django.db import transaction


# 서비스 시간 페이지 렌더링 (2020-03-18)
@allow_admin
def service(request):
    context = {}
    return render(request, 'admin/service.html', context)


# (2020-03-18)
@allow_admin
def api_read_change_history(request):
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    id = request.POST.get('id')
    regist_date_start = request.POST.get('regist_date_start')
    regist_date_end = request.POST.get('regist_date_end')
    type = request.POST.get('type')

    # where 조건 동적 연산
    wc = "where 1=1"
    if id != '':
        wc += " and b.email like '%" + id + "%'"
    if regist_date_start != '':
        wc += " and a.regist_date >= '" + regist_date_start + "'"
    if regist_date_end != '':
        wc += " and a.regist_date < '" + regist_date_end + "'"
    if type != '':
        if type == 'session':
            wc += " and a.diff like '%세션 변경%' "
        elif type == 'password':
            wc += " and a.diff = '비밀번호 변경' "
        elif type == 'refund':
            wc += " and a.diff = '환불' "
        elif type == 'active':
            wc += " and a.diff = '활성화 변경' "
        elif type == 'delete':
            wc += " and a.diff = '회원탈퇴' "
        elif type == 'service':
            wc += " and a.diff not in ('세션 변경', '환불', '비밀번호 변경', '활성화 변경', '회원탈퇴') "

    # order by 컬럼 생성
    column_name = ['id', 'email', 'prev_time', 'prev_time_rad', 'after_time', 'after_time_rad', 'diff', 'regist_date']

    # 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_service_time a
            join tbl_user b
            on a.user_id = b.id
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
                select x.*
                from (
                    select  a.id,
                            b.email,
                            a.prev_time,
                            a.prev_time_rad,
                            a.after_time,
                            a.after_time_rad,
                            a.diff,
                            DATE_FORMAT(a.regist_date, '%Y-%m-%d %H:%i') as regist_date,
                            a.reason
                    from tbl_service_time a
                    join tbl_user b
                    on a.user_id = b.id
                    {wc}
                    order by {orderby_col} {orderby_opt}
                    limit {start}, 10
                ) x
                JOIN ( SELECT @rnum := -1 ) AS r
        '''.format(
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            wc = wc)
        #print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = dictfetchall(cur)

    returnData = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(returnData)
