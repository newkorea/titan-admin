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