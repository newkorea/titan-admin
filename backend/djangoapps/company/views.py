import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def about(request):

    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_company_manage
            where type = 'M';
        '''
        cur.execute(query)
        row = cur.fetchall()
        print(row)
        en = row[0][0]
        ko = row[0][1]
        ja = row[0][2]
        zh = row[0][3]
        kind = 'M'
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh,
            'kind': kind
        }

    return render(request, 'company/admin_about.html', context)


def api_company_edit(request):
    sum = request.POST.get('sum')
    kind = request.POST.get('kind')
    lang = request.POST.get('lang')

    t1 = TblCompanyManage.objects.get(type=kind)

    if lang == 'en':
        t1.en = sum
        t1.save()
    elif lang == 'ko':
        t1.ko = sum
        t1.save()
    elif lang == 'ja':
        t1.ja = sum
        t1.save()
    elif lang == 'zh':
        t1.zh = sum
        t1.save()
    return JsonResponse({'result': '200'})

def api_company_load(request):
    kind = request.POST.get('kind')

    rows = TblCompanyManage.objects.filter(type=kind)

    list = []
    for t in rows:
        print(t)
        sd = {}
        sd['en'] = t.en
        sd['ko'] = t.ko
        sd['ja'] = t.ja
        sd['zh'] = t.zh
        list.append(sd)

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_company_manage
            set zh = '{zhSum}', zh_modify_date = now()
            where type = 'M';
            )
        '''.format(
            zhSum = zhSum
        )
        cur.execute(query)

    print(list)
    return JsonResponse({'result': list})
