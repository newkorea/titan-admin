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
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh
        }

    return render(request, 'company/admin_about.html', context)


def api_company_edit1(request):
    enSum = request.POST.get('enSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_company_manage
            set en = '{enSum}', en_modify_date = now()
            where type = 'M';
            )
        '''.format(
            enSum = enSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_company_edit2(request):
    koSum = request.POST.get('koSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_company_manage
            set ko = '{koSum}', ko_modify_date = now()
            where type = 'M';
            )
        '''.format(
            koSum = koSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_company_edit3(request):
    jaSum = request.POST.get('jaSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_company_manage
            set ja = '{jaSum}', ja_modify_date = now()
            where type = 'M';
            )
        '''.format(
            jaSum = jaSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_company_edit4(request):
    zhSum = request.POST.get('zhSum')

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
    return JsonResponse({'result': '200'})
