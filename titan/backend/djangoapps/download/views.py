import json
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


# 다운로드 페이지 렌더링 (2020-03-10)
def download(request, type):

    if type == 'android':
        pass
    elif type == 'ios':
        pass
    elif type == 'mac':
        pass
    elif type == 'windows':
        pass
    else:
        type = 'android'

    LANGUAGE_CODE = request.LANGUAGE_CODE
    image_save_path, client_save_path = get_download_resource(LANGUAGE_CODE, type)

    print('DEBUG -> type : ', type)
    print('DEBUG -> image_save_path : ', image_save_path)
    print('DEBUG -> client_save_path : ', client_save_path)

    context = {}
    context['type'] = type
    context['client_save_path'] = client_save_path
    context['image_save_path'] = image_save_path
    return render(request, 'new/download.html', context)
