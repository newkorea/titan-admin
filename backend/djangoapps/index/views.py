import json
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from backend.models import *
from backend.djangoapps.common.views import *


# 인덱스 페이지 리다이렉트 설정 (2019.09.15 11:46 점검완료)
@login_check
def index(request):
    # 시스템 관리자 리다이렉트 설정
    return redirect('/dashboard')
    """
    if request.session['is_staff'] == 1:
        return redirect('/dashboard')
    # CS 관리자 리다이렉트 설정
    elif request.session['is_staff'] == 2:
        return redirect('/dashboard')
    # 총판 리다이렉트 설정
    elif request.session['is_staff'] == 3:
        return redirect('/dashboard')
    """
