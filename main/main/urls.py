from django.contrib import admin
from django.urls import path
from django.urls import re_path, include

urlpatterns = [
    path('', include('backend.urls')),
]
