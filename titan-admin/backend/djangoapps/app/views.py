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


# (2023-05-10)
@allow_admin
def app(request):
    context = {}
    return render(request, 'admin/app.html', context)

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


# (2022-08-08)
@allow_admin
def api_read_app_datatables(request):

    # datatables 기본 파라미터
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')
    
    # order by 리스트
    column_name = [
        'id',
        'app_name',
        'package_name',
        'created_at',
        'id',
        'id'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_china_app
        '''
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
            		app_name,
            		package_name,
            		created_at
            from tbl_china_app
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2023-05-11) Added By Zhao
@allow_admin
def api_create_app(request):
    app_name = request.POST.get('app_name')
    package_name = request.POST.get('package_name')
    # 존재여부 체크
    try:
        u1 = TblChinaApp.objects.get(package_name=package_name)
        return JsonResponse({'result': 400})
    except BaseException:
        sh = TblChinaApp(
            app_name = app_name,
            package_name = package_name,
            created_at = datetime.datetime.now())
        sh.save()
        return JsonResponse({'result': 200})

# (2023-05-11) Added By Zhao
@allow_admin
def api_read_app_detail(request):
    app_id = request.POST.get('app_id')
    # 존재여부 체크
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT app_name, package_name
                FROM tbl_china_app WHERE id = {app_id};
        '''.format(
            app_id = app_id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        return JsonResponse({'result' : 200 , 'data' : rows[0]})


# (2023-05-11) Added by Zhao
@allow_admin
def api_update_app(request):
    id = request.POST.get('app_id')
    app_name = request.POST.get('app_name')
    package_name = request.POST.get('package_name')
    
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT app_name, package_name
                FROM tbl_china_app WHERE id != {id} AND package_name = '{package_name}';
        '''.format(
            id = id,
            package_name = package_name
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        if len(rows) == 0 :
            try:
                chinaapp = TblChinaApp.objects.get(id=id)
                chinaapp.app_name = app_name
                chinaapp.package_name = package_name
                chinaapp.save()

                title, text = get_swal('SUCCESS_COMMON')
                return JsonResponse({'result': 200, 'title': title, 'text': text})
            except BaseException as err:
                title, text = get_swal('UNKNOWN_ERROR')
                return JsonResponse({'result': 500, 'title': title, 'text': text})
        else :
            return JsonResponse({'result': 400})

# (2023-05-11) Added by Zhao
@allow_admin
def api_delete_app(request):
    id = request.POST.get('app_id')
    with connections['default'].cursor() as cur:
        sql = '''
            Delete 
                FROM tbl_china_app WHERE id = {id};
        '''.format(
            id = id
        )
        print(sql)
        cur.execute(sql)
        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})