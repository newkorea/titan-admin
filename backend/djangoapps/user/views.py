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

    gender_list = TblCodeDetail.objects.filter(group_code = 'gender')
    delete_list = TblCodeDetail.objects.filter(group_code='delete_yn')
    black_list = TblCodeDetail.objects.filter(group_code='black_yn')
    active_list = TblCodeDetail.objects.filter(group_code='is_active')
    staff_list = TblCodeDetail.objects.filter(group_code='is_staff')

    context = {
        'gender_list': gender_list,
        'delete_list': delete_list,
        'black_list': black_list,
        'active_list': active_list,
        'staff_list': staff_list
    }
    return render(request, 'user/admin_user.html', context)

@login_check
def api_user_detail(request):
    seq = int(request.POST.get('seq'))

    u1 = TblUser.objects.get(id = seq)
    ul1 = TblUserLogin.objects.get(user_id = seq)
    p_code = u1.phone_country
    p_number = u1.phone
    phone = '+' + p_code + ' ' + p_number

    s_code = u1.sns_code
    s_name = u1.sns_name
    print(s_code, s_name)
    if s_code == None and s_name == None:
        sns = ''
    else:
        sns = '(' + s_code + ')' + s_name

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

    print(list)

    return JsonResponse({'result': list})

@login_check
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

@login_check
def api_user_read(request):
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')

    id = request.POST.get('id')
    email = request.POST.get('email')
    username = request.POST.get('username')
    gender = request.POST.get('gender')
    delete = request.POST.get('delete')
    black = request.POST.get('black')
    active = request.POST.get('active')
    staff = request.POST.get('staff')
    sql = "where 1=1"

    if id != '':
        sql += " and id = '" + id + "'"

    if email != '':
        sql += " and email = '" + email + "'"

    if username != '':
        sql += " and username = '" + username + "'"

    if gender != '':
        sql += " and gender = '" + gender + "'"

    if delete != '':
        sql += " and delete_yn = '" + delete + "'"

    if black != '':
        sql += " and black_yn = '" + black + "'"

    if active != '':
        sql += " and is_active = '" + active + "'"

    if staff != '':
        sql += " and is_staff = '" + staff + "'"

    print(sql)

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
                    select a.id, a.email, a.username, a.gender, a.birth_date, concat("(", a.sns_code, ")", a.sns_name) as sns, concat("+", phone_country, " ", phone) as phone, delete_yn, black_yn, is_active, is_staff
                    from tbl_user a
                    {sql}
            	) x
            	JOIN ( SELECT @rnum := -1 ) AS r
            ) t1;
        '''.format(
            sql=sql
        )

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
                    select a.id, a.email, a.username, b.name as gender, a.birth_date, concat("(", a.sns_code, ")", a.sns_name) as sns, concat("+", a.phone_country, " ", a.phone) as phone, c.name as delete_yn, d.name as black_yn, e.name as is_active, f.name as is_staff
                    from tbl_user a
                    join tbl_code_detail b
                    on a.gender = b.code
					join tbl_code_detail c
                    on a.delete_yn = c.code
                    join tbl_code_detail d
                    on a.black_yn = d.code
                    join tbl_code_detail e
                    on a.is_active = e.code
                    join tbl_code_detail f
                    on a.is_staff = f.code
                    {sql}
                    and c.group_code = 'delete_yn'
                    and d.group_code = 'black_yn'
                    and e.group_code = 'is_active'
                    and f.group_code = 'is_staff'
                    order by {orderby_col} {orderby_opt}
                    ) x
                    JOIN ( SELECT @rnum := -1 ) AS r
                ) t1
                where t1.rnum BETWEEN {start} AND {end};
        '''.format(
            sql=sql,
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
