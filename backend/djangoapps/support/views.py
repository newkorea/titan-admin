import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def support(request):

    tcg = TblCodeGroup.objects.filter(memo='support')
    context = {}
    context['code_group'] = tcg
    return render(request, 'support/support.html', context)


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


def api_support_getContent(request):

    main_sel = request.POST.get('main_sel')
    sub_sel = request.POST.get('sub_sel')
    send_yn = request.POST.get('send_yn')
    target_date = request.POST.get('target_date')

    print('main_sel -> ', main_sel)
    print('sub_sel -> ', sub_sel)
    print('send_yn -> ', send_yn)
    print('target_date -> ', target_date)

    ts = TblSupport.objects.filter(
        main_type=main_sel
    )

    rr = []
    for t in ts:
        tmp = {}
        tmp['id'] = t.id
        tmp['title'] = t.title
        tmp['regist_date'] = t.regist_date.strftime("%Y-%m-%d %H:%M")
        rr.append(tmp)

    return JsonResponse({'result': rr})


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
