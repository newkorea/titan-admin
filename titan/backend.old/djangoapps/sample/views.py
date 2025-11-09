import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from django.utils import translation
from backend.models import *
from backend.models_radius import *


def index(request):
    context = {}
    return render(request, 'new/index.html', context)


def signin(request):
    context = {}
    return render(request, 'new/login.html', context)


def signup(request):
    context = {}
    return render(request, 'new/sign-up.html', context)


def change_password(request):
    context = {}
    return render(request, 'new/change-password.html', context)


def reset_password(request):
    context = {}
    return render(request, 'new/password-reset.html', context)


def blog_left_sidebar(request):
    context = {}
    return render(request, 'new/blog-left-sidebar.html', context)


def team(request):
    context = {}
    return render(request, 'new/team.html', context)


def download(request):
    context = {}
    return render(request, 'new/download.html', context)


def faq(request):
    context = {}
    return render(request, 'new/faq.html', context)
