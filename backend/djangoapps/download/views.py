import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def android(request):

    ko_win_clt = TblDownloadManage.objects.get(type='windows', language='ko').client_name
    en_win_clt = TblDownloadManage.objects.get(type='windows', language='en').client_name
    zh_win_clt = TblDownloadManage.objects.get(type='windows', language='zh').client_name
    ja_win_clt = TblDownloadManage.objects.get(type='windows', language='ja').client_name

    ko_win_img = TblDownloadManage.objects.get(type='windows', language='ko').image_name
    en_win_img = TblDownloadManage.objects.get(type='windows', language='en').image_name
    zh_win_img = TblDownloadManage.objects.get(type='windows', language='zh').image_name
    ja_win_img = TblDownloadManage.objects.get(type='windows', language='ja').image_name

    context = {}
    context['ko_win_clt'] = ko_win_clt
    context['en_win_clt'] = en_win_clt
    context['zh_win_clt'] = zh_win_clt
    context['ja_win_clt'] = ja_win_clt

    context['ko_win_img'] = ko_win_img
    context['en_win_img'] = en_win_img
    context['zh_win_img'] = zh_win_img
    context['ja_win_img'] = ja_win_img
    return render(request, 'download/android.html', context)


def ios(request):

    ko_win_clt = TblDownloadManage.objects.get(type='windows', language='ko').client_name
    en_win_clt = TblDownloadManage.objects.get(type='windows', language='en').client_name
    zh_win_clt = TblDownloadManage.objects.get(type='windows', language='zh').client_name
    ja_win_clt = TblDownloadManage.objects.get(type='windows', language='ja').client_name

    ko_win_img = TblDownloadManage.objects.get(type='windows', language='ko').image_name
    en_win_img = TblDownloadManage.objects.get(type='windows', language='en').image_name
    zh_win_img = TblDownloadManage.objects.get(type='windows', language='zh').image_name
    ja_win_img = TblDownloadManage.objects.get(type='windows', language='ja').image_name

    context = {}
    context['ko_win_clt'] = ko_win_clt
    context['en_win_clt'] = en_win_clt
    context['zh_win_clt'] = zh_win_clt
    context['ja_win_clt'] = ja_win_clt

    context['ko_win_img'] = ko_win_img
    context['en_win_img'] = en_win_img
    context['zh_win_img'] = zh_win_img
    context['ja_win_img'] = ja_win_img
    return render(request, 'download/ios.html', context)


def mac(request):

    ko_mac_clt = TblDownloadManage.objects.get(type='mac', language='ko').client_name
    en_mac_clt = TblDownloadManage.objects.get(type='mac', language='en').client_name
    zh_mac_clt = TblDownloadManage.objects.get(type='mac', language='zh').client_name
    ja_mac_clt = TblDownloadManage.objects.get(type='mac', language='ja').client_name

    ko_mac_img = TblDownloadManage.objects.get(type='mac', language='ko').image_name
    en_mac_img = TblDownloadManage.objects.get(type='mac', language='en').image_name
    zh_mac_img = TblDownloadManage.objects.get(type='mac', language='zh').image_name
    ja_mac_img = TblDownloadManage.objects.get(type='mac', language='ja').image_name

    context = {}
    context['ko_mac_clt'] = ko_mac_clt
    context['en_mac_clt'] = en_mac_clt
    context['zh_mac_clt'] = zh_mac_clt
    context['ja_mac_clt'] = ja_mac_clt

    context['ko_mac_img'] = ko_mac_img
    context['en_mac_img'] = en_mac_img
    context['zh_mac_img'] = zh_mac_img
    context['ja_mac_img'] = ja_mac_img
    return render(request, 'download/mac.html', context)


def windows(request):

    ko_win_clt = TblDownloadManage.objects.get(type='windows', language='ko').client_name
    en_win_clt = TblDownloadManage.objects.get(type='windows', language='en').client_name
    zh_win_clt = TblDownloadManage.objects.get(type='windows', language='zh').client_name
    ja_win_clt = TblDownloadManage.objects.get(type='windows', language='ja').client_name

    ko_win_img = TblDownloadManage.objects.get(type='windows', language='ko').image_name
    en_win_img = TblDownloadManage.objects.get(type='windows', language='en').image_name
    zh_win_img = TblDownloadManage.objects.get(type='windows', language='zh').image_name
    ja_win_img = TblDownloadManage.objects.get(type='windows', language='ja').image_name

    context = {}
    context['ko_win_clt'] = ko_win_clt
    context['en_win_clt'] = en_win_clt
    context['zh_win_clt'] = zh_win_clt
    context['ja_win_clt'] = ja_win_clt

    context['ko_win_img'] = ko_win_img
    context['en_win_img'] = en_win_img
    context['zh_win_img'] = zh_win_img
    context['ja_win_img'] = ja_win_img
    return render(request, 'download/windows.html', context)


def api_download(request):

    flag = request.POST.get('flag')
    print('flag -> ', flag)

    if 'upload_file' in request.FILES:
        upload_file = request.FILES['upload_file']
        print('upload_file -> ', upload_file)
        download_upload(upload_file, flag)

    return JsonResponse({'result':200})
