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
@allow_cs
def service(request):

    context = {
    }
    return render(request, 'service/admin_service.html', context)



@allow_cs
def api_service_read(request):
    seq = int(request.POST.get('user_seq'))
    u1 = TblUser.objects.get(id = seq)
    ue1 = u1.email
    service_time = my_radius_time(ue1, 'str')


    return JsonResponse({'service_time':service_time})

@allow_cs
def api_service_update(request):
    mody_time = request.POST.get('mody_time')
    seq = int(request.POST.get('user_seq'))
    u1 = TblUser.objects.get(id = seq)
    ue1 = u1.email

    try:
        after = datetime.datetime.strptime(mody_time, '%Y-%m-%d %H:%M:%S')
        after_rad= enc_radius_time(after)
    except BaseException:
        return JsonResponse({'result': '300'}) # 시간 형식 안맞음

    try:
        with transaction.atomic():
            rce = Radcheck.objects.using('radius').get(
                username = ue1,
                attribute = 'Expiration'
            )
            prev_rad = rce.value
            prev = dec_radius_time(prev_rad)
            time_dif = after - prev
            time_diff = round((time_dif).total_seconds()/60)
            st1 = TblServiceTime(
                user_id = seq,
                prev_time = prev,
                prev_time_rad = prev_rad,
                after_time = after,
                after_time_rad = after_rad,
                diff = time_diff,
                regist_date = datetime.datetime.now()
                )
            rce.value = after_rad
            rce.save(using='radius')
            st1.save()

        return JsonResponse({'result': '200'})
    except BaseException as p:
        print(p)
        return JsonResponse({'result': '500'})


@allow_cs
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
        sql += " and prev_time >= '" + regist_date_start + "'"
    if regist_date_end != '':
        sql += " and prev_time <= '" + regist_date_end + "'"
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
                    select id, email, prev_time, prev_time_rad, after_time, after_time_rad, diff, DATE_FORMAT(regist_date, '%Y-%m-%d %H:%i') as regist_date
                    from (
                        select x.*
                        from (
                                select a.id, b.email, prev_time, prev_time_rad, after_time, after_time_rad, diff, a.regist_date
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
            sql = sql
        )
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
