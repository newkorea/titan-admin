import os
import json
import uuid
import hashlib
import base64
import re
import datetime
from pytz import timezone
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from Crypto import Random
from Crypto.Cipher import AES
from backend.models import *
try:
    from html.parser import HTMLParser
except:
    from HTMLParser import HTMLParser
from backend.models_radius import Radcheck

# 공통 테스트 함수 (2019.09.15 12:26 점검완료)
def common_sample():
    print("hello world")


# 요금 초기화 함수 (2019.11.14 14.33)
def initServiceTime(user_id):

    # 유저객체 획득
    u1 = TblUser.objects.get(id = user_id)
    email = u1.email

    # Radcheck의 Cleartext-Password가 없을 경우 생성
    rr = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Cleartext-Password')
    if len(rr) == 0:
        r1 = Radcheck(
            username=email,
            attribute='Cleartext-Password',
            op=':=',
            value=str(uuid.uuid4()).replace('-', '')
        )
        r1.save(using='radius')

    # Radcheck의 session 변경 (merge 로직)
    rc = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Simultaneous-Use'
    )
    if len(rc) == 0:
        rci = Radcheck(
            username = email,
            attribute = 'Simultaneous-Use',
            op = ':=',
            value = int(1)
        )
        rci.save(using='radius')
    else:
        rcu = rc.first()
        rcu.value = int(1)
        rcu.save(using='radius')

    # Radcheck의 time 변경 (merge 로직)
    rce = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Expiration'
    )
    if len(rce) == 0:
        rcei = Radcheck(
            username = email,
            attribute = 'Expiration',
            op = ':=',
            value = '01 Jan 2010 00:00:00 KST'
        )
        rcei.save(using='radius')
    else:
        rceu = rce.first()
        rceu.value = '01 Jan 2010 00:00:00 KST'
        rceu.save(using='radius')


# 요금 충전 공통함수 (2019.09.21 12:57 점검완료)
def giveServiceTime(user_id, session, month_type):

    # 유저객체 획득
    u1 = TblUser.objects.get(id = user_id)
    email = u1.email

    # Radcheck의 Cleartext-Password가 없을 경우 생성
    rr = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Cleartext-Password')
    if len(rr) == 0:
        r1 = Radcheck(
            username=email,
            attribute='Cleartext-Password',
            op=':=',
            value=str(uuid.uuid4()).replace('-', '')
        )
        r1.save(using='radius')

    # Radcheck의 session 변경 (merge 로직)
    rc = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Simultaneous-Use'
    )
    if len(rc) == 0:
        rci = Radcheck(
            username = email,
            attribute = 'Simultaneous-Use',
            op = ':=',
            value = int(session)
        )
        rci.save(using='radius')
    else:
        rcu = rc.first()
        rcu.value = int(session)
        rcu.save(using='radius')

    # Radcheck의 time 변경 (merge 로직)
    if month_type == '1':
        add_time = datetime.datetime.now(timezone('Asia/Seoul')) + datetime.timedelta(30)
    if month_type == '6':
        add_time = datetime.datetime.now(timezone('Asia/Seoul')) + datetime.timedelta(180)
    if month_type == '12':
        add_time = datetime.datetime.now(timezone('Asia/Seoul')) + datetime.timedelta(360)
    radius_time = enc_radius_time(add_time)
    rce = Radcheck.objects.using('radius').filter(
        username = email,
        attribute = 'Expiration'
    )
    if len(rce) == 0:
        rcei = Radcheck(
            username = email,
            attribute = 'Expiration',
            op = ':=',
            value = radius_time
        )
        rcei.save(using='radius')
    else:
        rceu = rce.first()
        rceu.value = radius_time
        rceu.save(using='radius')


# python datetime 자료형을 radius 자료형으로 변경하는 함수 (2019.09.09 12:53 점검완료)
def enc_radius_time(obj):
    print('DEBUG -> enc_radius_time / obj : ', obj)
    radius_time = obj.strftime('%d') + ' ' + \
                  obj.strftime('%B')[:3] + ' ' + \
                  obj.strftime('%Y') + ' ' + \
                  obj.strftime('%H') + ':' + \
                  obj.strftime('%M') + ':' + \
                  obj.strftime('%S') + ' KST'
    print('DEBUG -> enc_radius_time / radius_time : ', radius_time)
    return radius_time


# radius 자료형을 python datetime 자료형으로 변경하는 함수 (2019.09.09 12:53 점검완료)
def dec_radius_time(radius_time):
    radius_time = radius_time.replace(' KST', '')
    radius_time = radius_time.replace('Jan', 'January')
    radius_time = radius_time.replace('Feb', 'February')
    radius_time = radius_time.replace('Mar', 'March')
    radius_time = radius_time.replace('Apr', 'April')
    radius_time = radius_time.replace('May', 'May')
    radius_time = radius_time.replace('Jun', 'June')
    radius_time = radius_time.replace('Jul', 'July')
    radius_time = radius_time.replace('Aug', 'August')
    radius_time = radius_time.replace('Sep', 'September')
    radius_time = radius_time.replace('Oct', 'October')
    radius_time = radius_time.replace('Nov', 'November')
    radius_time = radius_time.replace('Dec', 'December')
    radius_time = datetime.datetime.strptime(radius_time, '%d %B %Y %H:%M:%S')
    return radius_time


# 상품 가격 획득 함수 (2019.09.10 11:31 점검완료)
def getProductPirce(session, month_type, type):
    if type == 'KRW':
        price = TblPrice.objects.get(
            type_session = session,
            type_month = month_type,
        ).item_price
    elif type == 'USD':
        price = TblPrice.objects.get(
            type_session = session,
            type_month = month_type,
        ).item_price_usd
    elif type == 'CNY':
        price = TblPrice.objects.get(
            type_session = session,
            type_month = month_type,
        ).item_price_cny
    return price


# 해당 이메일의 세션 수를 반환하는 함수 (2019.09.09 12:53 점검완료)
def my_radius_session(email):
    try:
        r = Radcheck.objects.using('radius').get(
            username=email,
            attribute='Simultaneous-Use'
        )
        my_session = r.value
        return my_session
    except BaseException:
        return None


# 해당 이메일의 radius 자료형을 반환하는 함수 (2019.09.09 12:53 점검완료)
def my_radius_time(email, return_type):
    try:
        r = Radcheck.objects.using('radius').get(
            username=email,
            attribute='Expiration'
        )
        expire_time = r.value
        expire_time = dec_radius_time(expire_time)
        if return_type == 'datetime':
            return expire_time
        elif return_type == 'str':
            return expire_time.strftime("%Y-%m-%d %H:%M:%S")
    except BaseException:
        return None


# xss 해킹 방어 함수 (2019.09.15 12:26 점검완료)
def xssProtect(text):
    if '<'  in text:
        text = text.replace('<', '&lt')
    if '>' in text:
        text = text.replace('>', '&gt')
    if '&ltbr&gt' in text:
        text = text.replace('&ltbr&gt', '<br>')
    return text


# AES 공통 클래스 (2019.09.15 12:26 점검완료)
class AESCipher(object):

    def __init__(self):
        key = settings.ACTIVE_AES_KEY
        self.bs = 32
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


# 쿼리 결과 dict 형 반환 함수 (2019.09.15 12:26 점검완료)
def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


# 미들웨어 - 로그인 여부 확인 (2019.09.15 12:26 점검완료)
def login_check(func):
    def wrapper(request, *args, **kwargs):

        if 'id' in request.session:
            pass
        else:
            return redirect('/login')

        result = func(request, *args, **kwargs)
        return result

    return wrapper


# 미들웨어 - 로그인 여부 확인 (2019.09.15 12:26 점검완료)
def allow_admin(func):
    def wrapper(request, *args, **kwargs):

        if 'is_staff' in request.session:
            if request.session['is_staff'] in [1]:
                pass
            else:
                return redirect('/login')
        else:
            return redirect('/login')

        result = func(request, *args, **kwargs)
        return result

    return wrapper


# 미들웨어 - 로그인 여부 확인 (2019.09.15 12:26 점검완료)
def allow_cs(func):
    def wrapper(request, *args, **kwargs):

        if 'is_staff' in request.session:
            if request.session['is_staff'] in [1, 2]:
                pass
            else:
                return redirect('/login')
        else:
            return redirect('/login')

        result = func(request, *args, **kwargs)
        return result

    return wrapper


# 미들웨어 - 로그인 여부 확인 (2019.09.15 12:26 점검완료)
def allow_dealer(func):
    def wrapper(request, *args, **kwargs):

        if 'is_staff' in request.session:
            if request.session['is_staff'] in [1, 3]:
                pass
            else:
                return redirect('/login')
        else:
            return redirect('/login')

        result = func(request, *args, **kwargs)
        return result

    return wrapper


# 리퀘스트에 들어온 아이피를 얻는 함수 (2019.09.15 12:26 점검완료)
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# 평문을 sha256으로 반환하는 함수 (2019.09.15 12:26 점검완료)
def hashText(text):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + text.encode()).hexdigest() + ':' + salt


# 해쉬와 평문이 일치하는지 확인하는 함수 (2019.09.15 12:26 점검완료)
def matchHashedText(hashedText, providedText):
    _hashedText, salt = hashedText.split(':')
    return _hashedText == hashlib.sha256(salt.encode() + providedText.encode()).hexdigest()


# 파일 사이즈 연산 함수 (2019.09.15 12:26 점검완료)
def sizeof_fmt(num, suffix='b'):
    for unit in ['', 'k', 'm', 'g', 't', 'p', 'e', 'z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


# 파일 업로드 공통 함수 (2019.09.15 12:26 점검완료)
def file_upload(file, gname, gid):
    upload_root = settings.UPLOAD_ROOT
    real_name = file.name
    save_name = str(uuid.uuid4()).replace('-', '')
    ext = file.name.split('.')[-1]
    real_size = file.size
    save_size = sizeof_fmt(file.size)
    save_path = upload_root + save_name
    lock = 0

    print('DEBUG -> upload_root : ', upload_root)
    print('DEBUG -> save_name -> ', save_name)
    print('DEBUG -> ext -> ', ext)
    print('DEBUG -> real_size -> ', real_size)
    print('DEBUG -> save_size -> ', save_size)

    if real_name.endswith('.png'):
        print('INFO -> File is a png extension')
    else:
        print('INFO -> File is not a png extension')
        lock = 1

    if not os.path.exists(upload_root):
        print('INFO -> Create upload directory because it does not exist')
        os.makedirs(upload_root)

    if lock == 0:
        fs = FileSystemStorage()
        filename = fs.save(save_path, file)
        print('INFO -> File saved in directory')

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
        print('INFO -> File saved in database')


# 파일관리 공통 함수 (2019.09.15 12:26 점검완료)
def download_upload(file, flag):

    if flag.find('link') != -1:
        real_name = file
        real_size = 0
        save_size = ''
        save_path = ''

        print('DEBUG -> real_name : ', real_name)
        print('DEBUG -> real_size : ', real_size)
        print('DEBUG -> save_size : ', save_size)
        print('DEBUG -> save_path : ', save_path)
    else:
        upload_root = settings.UPLOAD_ROOT + '/download/'
        real_name = file.name
        real_size = file.size
        save_size = sizeof_fmt(file.size)
        save_path = upload_root + real_name

        print('DEBUG -> upload_root : ', upload_root)
        print('DEBUG -> real_name : ', real_name)
        print('DEBUG -> real_size : ', real_size)
        print('DEBUG -> save_size : ', save_size)
        print('DEBUG -> save_path : ', save_path)

        if not os.path.exists(upload_root):
            os.makedirs(upload_root)

        fs = FileSystemStorage()
        filename = fs.save(save_path, file)

    if flag == 'ko_win_clt' or flag == 'ko_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='ko')
    if flag == 'en_win_clt' or flag == 'en_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='en')
    if flag == 'zh_win_clt' or flag == 'zh_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='zh')
    if flag == 'ja_win_clt' or flag == 'ja_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='ja')

    if flag == 'ko_mac_clt' or flag == 'ko_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='ko')
    if flag == 'en_mac_clt' or flag == 'en_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='en')
    if flag == 'zh_mac_clt' or flag == 'zh_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='zh')
    if flag == 'ja_mac_clt' or flag == 'ja_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='ja')

    if flag == 'ko_and_link' or flag == 'ko_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='ko')
    if flag == 'en_and_link' or flag == 'en_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='en')
    if flag == 'zh_and_link' or flag == 'zh_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='zh')
    if flag == 'ja_and_link' or flag == 'ja_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='ja')

    if flag == 'ko_ios_link' or flag == 'ko_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='ko')
    if flag == 'en_ios_link' or flag == 'en_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='en')
    if flag == 'zh_ios_link' or flag == 'zh_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='zh')
    if flag == 'ja_ios_link' or flag == 'ja_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='ja')

    if flag.find('clt') != -1 or flag.find('link') != -1:
        tdm.client_name = real_name
        tdm.client_real_size = real_size
        tdm.client_save_size = save_size
        tdm.client_save_path = save_path
        tdm.client_modify_date = datetime.datetime.now()
        tdm.save()
        print('INFO -> client save success')

    if flag.find('img') != -1:
        tdm.image_name = real_name
        tdm.image_real_size = real_size
        tdm.image_save_size = save_size
        tdm.image_save_path = save_path
        tdm.image_modify_date = datetime.datetime.now()
        tdm.save()
        print('INFO -> image save success')
