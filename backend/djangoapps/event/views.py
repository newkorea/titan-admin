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


# (2020-04-07)
@allow_admin
def event_code(request):
    with connections['default'].cursor() as cur:
        query = '''
            select  event_code, 
                    start, 
                    end, 
                    free_day, 
                    case
                    when start < now() and now() < end
                    then '적용중'
                    else '미적용'
                    end as status,
                    regist_date, 
                    ifnull(delete_date, '') as delete_date, 
                    case 
                    when delete_yn = 'N'
                    then '정상'
                    else '삭제'
                    end as delete_yn
            from tbl_event_code
        '''.format()
        print(query)
        cur.execute(query)
        rows = dictfetchall(cur)
    
    context = {}
    context['rows'] = rows
    return render(request, 'admin/event_code.html', context)


# (2020-04-07)
@allow_admin
def event_all(request):
    context = {}
    return render(request, 'admin/event_all.html', context)


# (2020-04-07)
@allow_admin
def api_delete_event_code(request):
    event_code = request.POST.get('event_code')

    try:
        event = TblEventCode.objects.get(event_code=event_code)
        event.delete_yn = 'Y'
        event.save()
        title, text = get_swal('SUCCESS_EVENT_CODE_DEL')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

# (2020-04-07)
@allow_admin
def api_create_event_code(request):

    event_code = request.POST.get('event_code')
    event_start = request.POST.get('event_start')
    event_end = request.POST.get('event_end')
    event_free_day = request.POST.get('event_free_day')

    print('event_code = ', event_code)
    print('event_start = ', event_start)
    print('event_end = ', event_end)
    print('event_free_day = ', event_free_day)

    # 1. 이벤트 코드 유효성 체크
    user = TblUser.objects.filter(rec=event_code).count()
    if user > 0:
        title, text = get_swal('EXIST_EVENT_CODE_USER')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    event_cnt = TblEventCode.objects.filter(event_code=event_code).count()
    if event_cnt > 0:
        title, text = get_swal('EXIST_EVENT_CODE')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 2. 적용 시작일시 유효성 체크
    try:
        event_start = datetime.datetime.strptime(event_start, '%Y-%m-%d %H:%M:%S')
    except BaseException:
        title, text = get_swal('FAIL_TIME_FORMAT')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
    print('event_start = ', event_start)
    print('event_start = ', type(event_start))

    # 3. 적용 종료일시 유효성 체크
    try:
        event_end = datetime.datetime.strptime(event_end, '%Y-%m-%d %H:%M:%S')
    except BaseException:
        title, text = get_swal('FAIL_TIME_FORMAT')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 4. 무료체험일 유효성 체크
    try:
        event_free_day = int(event_free_day)
        if event_free_day > 0:
            pass
        else:
            raise
    except BaseException:
        title, text = get_swal('FAIL_FREE_DAY')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 5. 적용일시 유효성체크
    if event_start > event_end:
        title, text = get_swal('FAIL_START_END')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    # 6. 적용일시 유효성체크
    if datetime.datetime.now() > event_start:
        title, text = get_swal('FAIL_CURRENT')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

    event = TblEventCode(
        event_code=event_code,
        start=event_start,
        end=event_end,
        free_day=event_free_day,
        regist_date=datetime.datetime.now(),
        delete_date=None,
        delete_yn='N'
    )
    event.save()

    title, text = get_swal('SUCCESS_EVENT_CODE')
    return JsonResponse({'result': 200, 'title': title, 'text': text})