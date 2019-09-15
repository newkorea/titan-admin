import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


# 서비스이용약관 렌더링 (2019.09.15 11:49 점검완료)
@login_check
def service(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'S';
        '''
        cur.execute(query)
        row = cur.fetchall()
        en = row[0][0]
        ko = row[0][1]
        ja = row[0][2]
        zh = row[0][3]
        kind = 'S'
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh,
            'kind': kind
        }
    return render(request, 'policy/admin_service.html', context)


# 개인정보보호정책 렌더링 (2019.09.15 11:49 점검완료)
@login_check
def privacy(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'P';
        '''
        cur.execute(query)
        row = cur.fetchall()
        en = row[0][0]
        ko = row[0][1]
        ja = row[0][2]
        zh = row[0][3]
        kind = 'P'
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh,
            'kind': kind
        }

    return render(request, 'policy/admin_privacy.html', context)


# 환불정책 렌더링 (2019.09.15 11:49 점검완료)
@login_check
def refund(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'R';
        '''
        cur.execute(query)
        row = cur.fetchall()
        en = row[0][0]
        ko = row[0][1]
        ja = row[0][2]
        zh = row[0][3]
        kind = 'R'
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh,
            'kind': kind
        }
    return render(request, 'policy/admin_refund.html', context)


# 약관 공통 편집 API (2019.09.15 11:49 점검완료)
@login_check
def api_policy_edit(request):
    sum = request.POST.get('sum')
    kind = request.POST.get('kind')
    lang = request.POST.get('lang')

    t1 = TblPolicyManage.objects.get(type=kind)

    if lang == 'en':
        t1.en = sum
        t1.en_modify_date = datetime.now()
        t1.save()
    elif lang == 'ko':
        t1.ko = sum
        t1.ko_modify_date = datetime.now()
        t1.save()
    elif lang == 'ja':
        t1.ja = sum
        t1.ja_modify_date = datetime.now()
        t1.save()
    elif lang == 'zh':
        t1.zh = sum
        t1.zh_modify_date = datetime.now()
        t1.save()

    return JsonResponse({'result': '200'})


# 약관 공통 로드 API (2019.09.15 11:49 점검완료)
@login_check
def api_policy_load(request):
    kind = request.POST.get('kind')

    rows = TblPolicyManage.objects.filter(type=kind)

    list = []
    for t in rows:
        sd = {}
        sd['en'] = t.en
        sd['ko'] = t.ko
        sd['ja'] = t.ja
        sd['zh'] = t.zh
        list.append(sd)

    return JsonResponse({'result': list})
