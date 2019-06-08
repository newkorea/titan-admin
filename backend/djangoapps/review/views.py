import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from datetime import datetime

def review(request):


    return render(request, 'review/admin_review.html', {})


def api_review_read(request):
    language = request.POST.get('language')
    print('call api_review_read')
    rows = TblReview.objects.filter(language=language, delete_yn='N')

    res = []
    idx = 1
    for t in rows:
        print(t)
        sd = {}
        sd['idx'] = idx
        sd['id'] = t.id
        sd['star'] = t.star
        sd['username'] = t.username
        sd['content'] = t.content
        res.append(sd)
        idx += 1

    return JsonResponse({'result': res})


def api_review_save(request):
    print("api_review_save call")
    seq = request.POST.get('seq')
    starbox = request.POST.get('starbox')
    username = request.POST.get('username')
    content = request.POST.get('content')
    language = request.POST.get('language')

    tbl = TblReview.objects.filter(id=seq, language=language)

    if tbl:
        print('true')
        tr1 = TblReview.objects.get(id=seq, language=language)
        tr1.language = language
        tr1.star = starbox
        tr1.content = content
        tr1.username = username
        tr1.modify_date = datetime.now()
        tr1.save()
    else:
        print('false')
        TblReview.objects.create(language=language, star=starbox, content=content, username=username, regist_date=datetime.now(), delete_yn='N')

    return JsonResponse({'result': 200})


def api_review_add(request):
    language = request.POST.get('language')
    TblReview.objects.create(language=language, star = 5, delete_yn='N')

    return JsonResponse({'result': 200})


def api_review_del(request):
    print('call api_review_del')
    seq = request.POST.get('seq')

    tbl = TblReview.objects.get(id=seq)
    tbl.delete_yn = 'Y'
    tbl.save()

    return JsonResponse({'result': 200})
