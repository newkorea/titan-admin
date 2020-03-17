import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from backend.models_radius import *
import datetime
from django.db import transaction


# 서비스 시간 페이지 렌더링
@allow_admin
def service(request):
    context = {}
    return render(request, 'admin/service.html', context)


# 서비스 시간 데이터테이블즈
@allow_admin
def api_service_time_read(request):
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')
    id = request.POST.get('id')
    regist_date_start = request.POST.get('regist_date_start')
    regist_date_end = request.POST.get('regist_date_end')

    # where 조건 동적 연산
    sql = "where 1=1"
    if id != '':
        sql += " and b.email = '" + id + "'"
    if regist_date_start != '':
        sql += " and a.regist_date >= '" + regist_date_start + "'"
    if regist_date_end != '':
        sql += " and a.regist_date <= '" + regist_date_end + "'"
    #if id != '':
    #    sql += " and id = '" + id + "'"

    # order by 컬럼 생성
    column_name = ['id', 'user_id', 'prev_time', 'prev_time_rad', 'after_time', 'after_time_rad', 'diff', 'regist_date']

    # 디버그 로깅
    print('DEBUG -> start : ', start)
    print('DEBUG -> length : ', length)
    print('DEBUG -> draw : ', draw)
    print('DEBUG -> orderby_col : ', orderby_col)
    print('DEBUG -> orderby_opt : ', orderby_opt)

    # 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
                select count(*)
                from (
                	select @rnum := @rnum + 1 AS rnum, x.*
                	from (
                        select a.id, b.email, prev_time, prev_time_rad, after_time, after_time_rad, diff, a.regist_date
                        from tbl_service_time a
                        join tbl_user b
                        on a.user_id = b.id
                        {sql}
                	) x
                	JOIN ( SELECT @rnum := -1 ) AS r
                ) t1;
            '''.format(
            sql=sql
        )
        print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
    print('DEBUG -> total : ', total)


    # 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
                    email,
                    prev_time,
                    prev_time_rad,
                    after_time,
                    after_time_rad,
                    diff,
                    reason,
                    DATE_FORMAT(regist_date, '%Y-%m-%d %H:%i') as regist_date
            from (
                select x.*
                from (
                    select a.id, b.email, prev_time, prev_time_rad, after_time, after_time_rad, diff, a.regist_date, a.reason
                    from tbl_service_time a
                    join tbl_user b
                    on a.user_id = b.id
                    {sql}
                    order by {orderby_col} {orderby_opt}
                    limit {start}, 10
                ) x
                JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format(
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            sql = sql)
        print('DEBUG -> query : ', query)
        cur.execute(query)
        rows = dictfetchall(cur)

    returnData = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(returnData)
