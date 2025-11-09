import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from django.utils import translation


# 서비스이용약관 렌더링 (2020-03-09)
def policy_service(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/policy/policy_service_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/policy/policy_service_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/policy/policy_service_zh.html', {})
    else:
        return render(request, 'new/policy/policy_service_ko.html', {})


# 개인정보보호정책 렌더링 (2020-03-09)
def policy_privacy(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/policy/policy_privacy_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/policy/policy_privacy_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/policy/policy_privacy_zh.html', {})
    else:
        return render(request, 'new/policy/policy_privacy_ko.html', {})


# 환불정책 렌더링 (2020-03-09)
def policy_refund(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/policy/policy_refund_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/policy/policy_refund_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/policy/policy_refund_zh.html', {})
    else:
        return render(request, 'new/policy/policy_refund_ko.html', {})


# 서비스이용약관 렌더링 - 웹뷰 (2020-03-12)
def webview_policy_service(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/webview/policy_service_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/webview/policy_service_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/webview/policy_service_zh.html', {})
    else:
        return render(request, 'new/webview/policy_service_ko.html', {})


# 개인정보보호정책 렌더링 - 웹뷰 (2020-03-12)
def webview_policy_privacy(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/webview/policy_privacy_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/webview/policy_privacy_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/webview/policy_privacy_zh.html', {})
    else:
        return render(request, 'new/webview/policy_privacy_ko.html', {})


# 환불정책 렌더링 - 웹뷰 (2020-03-12)
def webview_policy_refund(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    if LANGUAGE_CODE == 'ko':
        return render(request, 'new/webview/policy_refund_ko.html', {})
    elif LANGUAGE_CODE == 'en':
        return render(request, 'new/webview/policy_refund_en.html', {})
    elif LANGUAGE_CODE == 'zh':
        return render(request, 'new/webview/policy_refund_zh.html', {})
    else:
        return render(request, 'new/webview/policy_refund_ko.html', {})
