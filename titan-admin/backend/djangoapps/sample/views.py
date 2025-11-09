import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


@login_check
def sample(request):

    """
    with connections['default'].cursor() as cur:
        query = '''
            select *
            FROM table
            where sample = '{page}'
        '''.format(page=page)
        cur.execute(query)
        rows = cur.fetchall()
    """

    context = {}
    context['sample_key'] = 'sample_val'

    print("-------------------------> DEBUG [s]")
    print(settings.TIME_ZONE)
    print("-------------------------> DEBUG [e]")

    return render(request, 'sample/admin_sample.html', context)
    #return JsonResponse({'a':'b'})
