import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


@login_check
def user(request):

    context = {}
    return render(request, 'user/admin_user.html', context)

@login_check
def api_user_read(request):
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    column_name = ['id', 'email', 'username', 'gender', 'birth_date', 'sns', 'phone', 'delete_yn', 'black_yn', 'is_active','is_staff']

    # search

    print('start -> ', start)
    print('length -> ', length)
    print('draw -> ', draw)
    print('orderby_col -> ', orderby_col)
    print('orderby_opt -> ', orderby_opt)

    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from (
            	select @rnum := @rnum + 1 AS rnum, x.*
            	from (
                    select id, email, username, gender, birth_date, concat("(", sns_code, ")", sns_name) as sns, concat("+", phone_country, " ", phone) as phone, delete_yn, black_yn, is_active, is_staff
                    from tbl_user
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format()

        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]

    print('---------------------------------')
    print("total -> ", total)
    print('---------------------------------')


    with connections['default'].cursor() as cur:
        query = '''
                select id, email, username, gender, birth_date, sns, phone, delete_yn, black_yn, is_active, is_staff
                from (
                    select @rnum := @rnum + 1 AS rnum, x.*
                    from (
                    select id, email, username, gender, birth_date, concat("(", sns_code, ")", sns_name) as sns, concat("+", phone_country, " ", phone) as phone, delete_yn, black_yn, is_active, is_staff
                    from tbl_user
                    order by {orderby_col} {orderby_opt}
                    ) x
                    JOIN ( SELECT @rnum := -1 ) AS r
                ) t1
                where t1.rnum BETWEEN {start} AND {end};
        '''.format(
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start,
            end=start+length-1
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    print('---------------------------------')
    for r in rows:
        print(r)
    print('---------------------------------')

    test = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

    return JsonResponse(test)
