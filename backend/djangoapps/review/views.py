import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


@login_check
def review(request):

    context = {}
    return render(request, 'review/admin_review.html', context)


@login_check
def api_review_read(request):
    language = request.POST.get('language')
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


@login_check
def api_review_save(request):

    seq = request.POST.get('seq')
    starbox = request.POST.get('starbox')
    username = request.POST.get('username')
    content = request.POST.get('content')
    language = request.POST.get('language')

    print('seq -> ', seq)
    print('starbox -> ', starbox)
    print('username -> ', username)
    print('content -> ', content)
    print('language -> ', language)

    if seq == '0':
        print('insert')
        tr = TblReview(
            language=language,
            star=starbox,
            username=username,
            content=content,
            regist_date=datetime.now(),
            regist_id='999',
            delete_yn='N'
        )
        tr.save()
    else:
        print('update')
        tr = TblReview.objects.get(id=seq)
        tr.language = language
        tr.star = starbox
        tr.content = content
        tr.username = username
        tr.modify_date = datetime.now()
        tr.modify_id = '999'
        tr.save()

    return JsonResponse({'result': 200})


@login_check
def api_review_del(request):

    seq = request.POST.get('seq')

    tr = TblReview.objects.get(id=seq)
    tr.delete_yn = 'Y'
    tr.delete_date = datetime.now()
    tr.save()

    return JsonResponse({'result': 200})
