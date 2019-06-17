import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


@login_check
def support(request):

    tcg = TblCodeGroup.objects.filter(memo='support')
    context = {}
    context['code_group'] = tcg
    return render(request, 'support/support.html', context)


@login_check
def api_support_getSubOption(request):

    group_code = request.POST.get('group_code')
    
    tcd = TblCodeDetail.objects.filter(group_code=group_code)

    rr = []
    for f in tcd:
        tmp = {}
        tmp['code'] = f.code
        tmp['name'] = f.memo
        rr.append(tmp)

    return JsonResponse({'result': rr})


# parameter : yyyy-mm-dd
def convertStrToDatetime(strTypedate):

    tmp = strTypedate.split('-')
    yyyy = int(tmp[0])
    mm = int(tmp[1])
    dd = int(tmp[2])
    return datetime.datetime(yyyy, mm, dd)


@login_check
def api_support_getContent(request):

    main_sel = request.POST.get('main_sel')
    sub_sel = request.POST.get('sub_sel')
    send_yn = request.POST.get('send_yn')
    target_date = request.POST.get('target_date')
    
    # life cycle bug fix
    if sub_sel == '':
        sub_sel = '0'

    print('----------------------------')
    print('main_sel -> ', main_sel)
    print('sub_sel -> ', sub_sel)
    print('sub_sel -> ', type(sub_sel))
    print('send_yn -> ', send_yn)
    print('target_date -> ', target_date)
    print('----------------------------')

    with connections['default'].cursor() as cur:
        if sub_sel == '0':
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and date(regist_date) = date('{target_date}')
                and send_yn='{send_yn}';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()
        else:
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and sub_type='{sub_sel}'
                and date(regist_date) = date('{target_date}')
                and send_yn='{send_yn}';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()   

    print('len(rows) -> ', len(rows))

    rr = []
    for row in rows:
        tmp = {}
        tmp['id'] = row[0]
        tmp['title'] = row[1]
        tmp['regist_date'] = row[2]
        rr.append(tmp)

    return JsonResponse({'result': rr})


@login_check
def api_support_getSelectContent(request):

    id = request.POST.get('id')

    ts = TblSupport.objects.get(id=id)

    tcg = TblCodeGroup.objects.get(
        code=ts.main_type
    )

    tcd = TblCodeDetail.objects.get(
        group_code=ts.main_type,
        code=ts.sub_type
    )

    tf = TblFile.objects.filter(
        gname=ts.main_type,
        gid=id
    )

    rr = {}
    rr['main_type'] = tcg.name
    rr['sub_type'] = tcd.memo
    rr['email'] = ts.email
    rr['title'] = ts.title
    rr['content'] = ts.content

    print('-----------------------')
    print('len(tf) -> ', len(tf))
    print('-----------------------')

    if len(tf) == 0:
        rr['file1'] = ''
        rr['file2'] = ''
    if len(tf) == 1 or len(tf) == 2:
        print('tf[0].save_path -> ', tf[0].save_path)
        rr['file1'] = tf[0].save_path
        rr['file2'] = ''
    if len(tf) == 2:
        print('tf[1].save_path -> ', tf[1].save_path)
        rr['file2'] = tf[1].save_path
    return JsonResponse({'result': rr})
