import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


# 안드로이드 다운로드 관리 페이지 렌더링 (2019.09.15 12:44 점검완료)
@allow_admin
def android(request):
    use_yn = TblMenuManage.objects.get(type='android').use_yn
    context = {}
    context['version'] = 'android'
    context['use_yn'] = use_yn
    return render(request, 'download/admin_android.html', context)


# IOS 다운로드 관리 페이지 렌더링 (2019.09.15 12:44 점검완료)
@allow_admin
def ios(request):
    use_yn = TblMenuManage.objects.get(type='ios').use_yn
    context = {}
    context['version'] = 'ios'
    context['use_yn'] = use_yn
    return render(request, 'download/admin_ios.html', context)


# 맥 다운로드 관리 페이지 렌더링 (2019.09.15 12:44 점검완료)
@allow_admin
def mac(request):
    use_yn = TblMenuManage.objects.get(type='mac').use_yn
    context = {}
    context['version'] = 'mac'
    context['use_yn'] = use_yn
    return render(request, 'download/admin_mac.html', context)


# 윈도우즈 다운로드 관리 페이지 렌더링 (2019.09.15 12:44 점검완료)
@allow_admin
def windows(request):
    use_yn = TblMenuManage.objects.get(type='windows').use_yn
    context = {}
    context['version'] = 'windows'
    context['use_yn'] = use_yn
    return render(request, 'download/admin_windows.html', context)


# 메뉴 활성화 API (2019.09.15 12:44 점검완료)
@allow_admin
def api_menuControl(request):
    flag = request.POST.get('flag')
    version = request.POST.get('version')
    tmm = TblMenuManage.objects.get(type=version)
    tmm.use_yn = flag
    tmm.save()
    return JsonResponse({'result': 200})


# 파일 업로드 API (2019.09.15 12:44 점검완료)
@allow_admin
def api_download(request):
    flag = request.POST.get('flag')
    if flag.find('link') != -1:
        upload_file = request.POST.get('upload_file')
        download_upload(upload_file, flag)
    if 'upload_file' in request.FILES:
        upload_file = request.FILES['upload_file']
        download_upload(upload_file, flag)
    return JsonResponse({'result':200})


# 렌더링 데이터 로드 API (2019.09.15 12:44 점검완료)
@allow_admin
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
