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

# (2023-05-25) Added by Zhao
@allow_admin
def notification(request):
    context = {}
    return render(request, 'admin/notification.html', context)

# (2023-05-25) Added by Zhao
@allow_admin
def api_delete_notification(request):
    notification_id = request.POST.get('notification_id')
    try:
        tb = TblNotice.objects.get(id=notification_id)
        tb.delete_yn = 'Y'
        tb.delete_date = datetime.datetime.now()
        tb.save()
        title, text = get_swal('SUCCESS_REGIST_BAN_DEL')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        print('err => ', err)
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2023-05-25) Added by Zhao
@allow_admin
def get_notifications(request):

    # datatables 기본 파라미터
    platform = request.POST.get('platform')
    start_at = request.POST.get('start_at')
    end_at = request.POST.get('end_at')
    
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')
    
    wc = ' where 1=1 '
    if platform != 'All':
        wc += " and platform = '{platform}' ".format(platform=platform)
    if start_at != '':
        wc += '''
            and end_date >= '{start_at}'
        '''.format(start_at=start_at)
    if end_at != '':
        wc += '''
            and end_date < '{end_at}'
        '''.format(end_at=end_at)
    
    # order by 리스트
    column_name = [
        'id'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_notice
            {wc} and delete_yn = 'N'
        '''.format(wc=wc)
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
            		content_ko,
            		content_en,
            		content_zh,
            		platform,
            		concat(platform, '@', id) as user,
                    end_date,
            		regist_date
            from tbl_notice
            {wc} and delete_yn = 'N'
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
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


# (2023-05-25) Added By Zhao
@allow_admin
def api_create_notification(request):
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    platform = request.POST.get('platform')
    end_date = request.POST.get('end_date')
    # 존재여부 체크
    sh = TblNotice(
        content_ko = content_ko,
        content_en = content_en,
        content_zh = content_zh,
        platform = platform,
        end_date = end_date,
        delete_yn = 'N',
        regist_date = datetime.datetime.now())
    sh.save()
    return JsonResponse({'result': 200})

# (2023-05-25) Added By Zhao
@allow_admin
def api_read_notification_detail(request):
    notification_id = request.POST.get('notification_id')
    # 존재여부 체크
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT content_en, content_ko, content_zh, platform, end_date
                FROM tbl_notice WHERE id = {notification_id};
        '''.format(
            notification_id = notification_id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        return JsonResponse({'result' : 200 , 'data' : rows[0]})


# (2023-05-25) Added by Zhao
@allow_admin
def api_update_notification(request):
    id = request.POST.get('notification_id')
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    platform = request.POST.get('platform')
    end_date = request.POST.get('end_date')
    
    try:
        notification = TblNotice.objects.get(id=id)
        notification.content_ko = content_ko
        notification.content_en = content_en
        notification.content_zh = content_zh
        notification.platform = platform
        notification.end_date = end_date
        notification.save()
        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
     
# (2023-05-26) Added by Zhao
@allow_admin
def api_add_user(request):
    email = request.POST.get('email')
    notice_id = request.POST.get('notification_id')
    
    try:
        u1 = TblUser.objects.get(email=email)
    except BaseException:
        return JsonResponse({'result': 600})
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT *
                FROM tbl_notice_user WHERE notice_id = {notice_id} and user_id = {user_id};
        '''.format(
            notice_id = notice_id,
            user_id = u1.id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        if len(rows) != 0:
            return JsonResponse({'result' : 400})
    try:
        sh = TblNoticeUser(
            user_id = u1.id,
            notice_id = notice_id,
            regist_date = datetime.datetime.now())
        sh.save()
        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

# (2023-05-26) Added by Zhao
@allow_admin
def api_get_user(request):
    notice_id = request.POST.get('notification_id')
    
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT tu.email FROM tbl_notice_user tn
            JOIN tbl_user tu ON tn.user_id = tu.id
            WHERE tn.notice_id= {notice_id}
            ORDER BY tu.email;
        '''.format(
            notice_id = notice_id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        return JsonResponse({'result' : 200, 'data': rows})