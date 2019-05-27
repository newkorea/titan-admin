import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def main(request):

    # windows
    try:
        windows_top = TblFile.objects.filter(gname='windows_top').order_by('-regist_date')[0].real_name
    except BaseException:
        windows_top = '등록안됨'
    try:
        windows_bot = TblFile.objects.filter(gname='windows_bot').order_by('-regist_date')[0].real_name
    except BaseException:
        windows_bot = '등록안됨'

    # macOS
    try:
        mac_top = TblFile.objects.filter(gname='mac_top').order_by('-regist_date')[0].real_name
    except BaseException:
        mac_top = '등록안됨'
    try:
        mac_bot = TblFile.objects.filter(gname='mac_bot').order_by('-regist_date')[0].real_name
    except BaseException:
        mac_bot = '등록안됨'

    # android
    try:
        android_top = TblDownloadManage.objects.get(type='android').link
        if android_top == '':
            android_top = '등록안됨'
    except BaseException:
        android_top = '등록안됨'
    try:
        android_bot = TblFile.objects.filter(gname='android_bot').order_by('-regist_date')[0].real_name
    except BaseException:
        android_bot = '등록안됨'

    # ios
    try:
        ios_top = TblDownloadManage.objects.get(type='ios').link
        if ios_top == '':
            ios_top = '등록안됨'
    except BaseException:
        ios_top = '등록안됨'
    try:
        ios_bot = TblFile.objects.filter(gname='ios_bot').order_by('-regist_date')[0].real_name
    except BaseException:
        ios_bot = '등록안됨'

    context = {}
    context['windows_top'] = windows_top
    context['windows_bot'] = windows_bot
    context['mac_top'] = mac_top
    context['mac_bot'] = mac_bot
    context['android_top'] = android_top
    context['android_bot'] = android_bot
    context['ios_top'] = ios_top
    context['ios_bot'] = ios_bot
    return render(request, 'download/main.html', context)


def api_download(request):

    if 'w_top' in request.FILES:
        w_top = request.FILES['w_top']
        print('w_top -> ', w_top)
        file_upload(w_top, 'windows_top', None)
    if 'w_bot' in request.FILES:
        w_bot = request.FILES['w_bot']
        print('w_bot -> ', w_bot)
        file_upload(w_bot, 'windows_bot', None)

    if 'm_top' in request.FILES:
        m_top = request.FILES['m_top']
        print('m_top -> ', m_top)
        file_upload(m_top, 'mac_top', None)
    if 'm_bot' in request.FILES:
        m_bot = request.FILES['m_bot']
        print('m_bot -> ', m_bot)
        file_upload(m_bot, 'mac_bot', None)

    if 'a_top' in request.POST:
        a_top = request.POST.get('a_top')
        if a_top != '':
            t1 = TblDownloadManage.objects.get(type='android')
            t1.link = a_top
            t1.modify_date = datetime.datetime.now()
            t1.save()
    if 'a_bot' in request.FILES:
        a_bot = request.FILES['a_bot']
        print('a_bot -> ', a_bot)
        file_upload(a_bot, 'android_bot', None)

    if 'i_top' in request.POST:
        i_top = request.POST.get('i_top')
        if i_top != '':
            t1 = TblDownloadManage.objects.get(type='ios')
            t1.link = i_top
            t1.modify_date = datetime.datetime.now()
            t1.save()
    if 'i_bot' in request.FILES:
        i_bot = request.FILES['i_bot']
        print('i_bot -> ', i_bot)
        file_upload(i_bot, 'ios_bot', None)

    return JsonResponse({'result':200})
