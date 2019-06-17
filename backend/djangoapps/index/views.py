import json
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections

from backend.models import *
from backend.djangoapps.common.views import *

@login_check
def index(request):
    
    return redirect('/dashboard')
