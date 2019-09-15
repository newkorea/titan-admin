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
    return redirect('/dashboard')
