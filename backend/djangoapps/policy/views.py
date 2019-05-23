import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


def service(request):

    context = {}
    return render(request, 'policy/service.html', context)


def privacy(request):

    context = {}
    return render(request, 'policy/privacy.html', context)


def refund(request):

    context = {}
    return render(request, 'policy/refund.html', context)
