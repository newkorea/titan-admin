import os
import json
import uuid
import hashlib
import datetime
import base64
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from Crypto import Random
from Crypto.Cipher import AES

from backend.models import *


def common_sample():
    print("hello world")


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def sizeof_fmt(num, suffix='b'):
    for unit in ['', 'k', 'm', 'g', 't', 'p', 'e', 'z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def file_upload(file, gname, gid):

    upload_root = settings.UPLOAD_ROOT
    real_name = file.name
    save_name = str(uuid.uuid4()).replace('-', '')
    ext = file.name.split('.')[-1]
    real_size = file.size
    save_size = sizeof_fmt(file.size)
    save_path = upload_root + save_name

    print('upload_root -> ', upload_root)
    print('save_name -> ', save_name)
    print('ext -> ', ext)
    print('real_size -> ', real_size)
    print('save_size -> ', save_size)

    if not os.path.exists(upload_root):
        os.makedirs(upload_root)

    fs = FileSystemStorage()
    filename = fs.save(save_path, file)

    file = TblFile(
        gname       = gname,
        gid         = gid,
        real_name   = real_name,
        save_name   = save_name,
        ext         = ext,
        real_size   = real_size,
        save_size   = save_size,
        save_path   = save_path,
        regist_id   = None,
        regist_date = datetime.datetime.now(),
        delete_yn   = 'N',
        delete_date = None
    )
    file.save()
