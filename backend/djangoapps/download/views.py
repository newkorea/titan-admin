import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def android(request):

    context = {}
    context['version'] = 'android'
    return render(request, 'download/android.html', context)


def ios(request):

    context = {}
    context['version'] = 'ios'
    return render(request, 'download/ios.html', context)


def mac(request):

    context = {}
    context['version'] = 'mac'
    return render(request, 'download/mac.html', context)


def windows(request):

    context = {}
    context['version'] = 'windows'
    return render(request, 'download/windows.html', context)


def api_download(request):

    flag = request.POST.get('flag')
    print('flag -> ', flag)
    if flag.find('link') != -1:
        upload_file = request.POST.get('upload_file')
        download_upload(upload_file, flag)

    if 'upload_file' in request.FILES:
        upload_file = request.FILES['upload_file']
        print('upload_file -> ', upload_file)
        download_upload(upload_file, flag)

    return JsonResponse({'result':200})


def api_load_download_data(request):

    version = request.POST.get('version')
    tdm = TblDownloadManage.objects.filter(type=version)

    sdl = []
    for t in tdm:
        sd = {}
        sd['language'] = t.language
        sd['client_name'] = t.client_name
        sd['image_name'] = t.image_name
        sdl.append(sd)

    return JsonResponse({'result':sdl})
