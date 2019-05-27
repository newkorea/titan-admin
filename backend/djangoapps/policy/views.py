import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def service(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'S';
        '''
        cur.execute(query)
        row = cur.fetchall()
        #print(row)
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
    return render(request, 'policy/service.html', context)

def api_service_edit1(request):
    enSum = request.POST.get('enSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set en = '{enSum}', en_modify_date = now()
            where type = 'S';
            )
        '''.format(
            enSum = enSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_service_edit2(request):
    koSum = request.POST.get('koSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ko = '{koSum}', ko_modify_date = now()
            where type = 'S';
            )
        '''.format(
            koSum = koSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_service_edit3(request):
    jaSum = request.POST.get('jaSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ja = '{jaSum}', ja_modify_date = now()
            where type = 'S';
            )
        '''.format(
            jaSum = jaSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_service_edit4(request):
    zhSum = request.POST.get('zhSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set zh = '{zhSum}', zh_modify_date = now()
            where type = 'S';
            )
        '''.format(
            zhSum = zhSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def privacy(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'P';
        '''
        cur.execute(query)
        row = cur.fetchall()
        #print(row)
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

    return render(request, 'policy/privacy.html', context)

def api_privacy_edit1(request):
    enSum = request.POST.get('enSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set en = '{enSum}', en_modify_date = now()
            where type = 'P';
            )
        '''.format(
            enSum = enSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_privacy_edit2(request):
    koSum = request.POST.get('koSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ko = '{koSum}', ko_modify_date = now()
            where type = 'P';
            )
        '''.format(
            koSum = koSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_privacy_edit3(request):
    jaSum = request.POST.get('jaSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ja = '{jaSum}', ja_modify_date = now()
            where type = 'P';
            )
        '''.format(
            jaSum = jaSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_privacy_edit4(request):
    zhSum = request.POST.get('zhSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set zh = '{zhSum}', zh_modify_date = now()
            where type = 'P';
            )
        '''.format(
            zhSum = zhSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def refund(request):
    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_policy_manage
            where type = 'R';
        '''
        cur.execute(query)
        row = cur.fetchall()
        #print(row)
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
    return render(request, 'policy/refund.html', context)

def api_refund_edit1(request):
    enSum = request.POST.get('enSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set en = '{enSum}', en_modify_date = now()
            where type = 'R';
            )
        '''.format(
            enSum = enSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_refund_edit2(request):
    koSum = request.POST.get('koSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ko = '{koSum}', ko_modify_date = now()
            where type = 'R';
            )
        '''.format(
            koSum = koSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_refund_edit3(request):
    jaSum = request.POST.get('jaSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set ja = '{jaSum}', ja_modify_date = now()
            where type = 'R';
            )
        '''.format(
            jaSum = jaSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})

def api_refund_edit4(request):
    zhSum = request.POST.get('zhSum')

    with connections['default'].cursor() as cur:
        query = '''
            update tbl_policy_manage
            set zh = '{zhSum}', zh_modify_date = now()
            where type = 'R';
            )
        '''.format(
            zhSum = zhSum
        )
        cur.execute(query)
    return JsonResponse({'result': '200'})
