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
            from tbl_policy_manage
            where type = 'S';
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

    return render(request, 'company/about.html', context)
