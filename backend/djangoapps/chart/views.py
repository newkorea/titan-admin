import json
import datetime
import smtplib
from django.shortcuts import render
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ObjectDoesNotExist
from pytz import timezone
from urllib.parse import quote
from urllib.parse import unquote
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.models import *
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from django.utils import translation
from django.conf import settings

# 일일 통계 (가입계정 및 활성계정) (2020-03-27)
def dd_user(request):
    return render(request, 'chart/dd_user.html')

# 월별 통계 (가입계정 및 활성계정) (2020-03-27)
def mm_user(request):
    return render(request, 'chart/mm_user.html')