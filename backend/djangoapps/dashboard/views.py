import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from datetime import datetime, timedelta


# 대쉬보드 렌더링 (2020-03-16)
@allow_admin
def dashboard(request):
    context = {}
    return render(request, 'admin/dashboard.html', context)
