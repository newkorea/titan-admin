import os
import json
import uuid
import hashlib
import base64
import re
import datetime
from pytz import timezone
from dateutil.relativedelta import relativedelta
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


# 활성화 값을 텍스트로 반환 (2020-03-18)
def get_active_txt(status):
    if status == '1':
        return '활성화'
    else:
        return '비활성화'


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

#(2022-08-10)
def change_date_style(old_date):
    try:
        return old_date.strftime("%Y-%m-%d %H:%M:%S")
    except BaseException:
        return None
def change_date(old_date):
    try:
        return old_date.strftime("%d %b %Y %H:%M:%S") + " KST"
    except BaseException:
        return None

# 요금 충전 공통함수 (2019.09.21 12:57 점검완료)
def giveServiceTime(user_id, session, month_type):
    # 유저객체 획득
    print("============= User Subscription ============", "")
    u1 = TblUser.objects.get(id = user_id)
    email = u1.email
    update_session = False
    old_session = 1
    print("User Email=> ", email)
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
        if rcu.value != session :
            update_session = True
            old_session = int(rcu.value)
        rcu.value = int(session)
        rcu.save(using='radius')

    my_time = my_radius_time(email, 'datetime')
    
    print("Old Time        => ", my_time)
    if my_time != None and my_time > datetime.datetime.now():
        if update_session :
            print("Update Session => ", update_session)
            diff = my_time - datetime.datetime.now()
            new_days = 0
            print("Time Diff => ", diff.days + 1)
            if int(session) == 1:
                if old_session == 2 :
                    new_days = int(diff.days * 140 / 83)
                elif old_session == 3:
                    new_days = int(diff.days * 220 / 83)
                elif old_session == 4:
                    new_days = int(diff.days * 280 / 83)
                elif old_session == 5:
                    new_days = int(diff.days * 350 / 83)
                elif old_session == 6:
                    new_days = int(diff.days * 433 / 83)
            elif int(session) == 2:
                if old_session == 1 :
                    new_days = int(diff.days * 83 / 140)
                elif old_session == 3:
                    new_days = int(diff.days * 220 / 140)
                elif old_session == 4:
                    new_days = int(diff.days * 280 / 140)
                elif old_session == 5:
                    new_days = int(diff.days * 350 / 140)
                elif old_session == 6:
                    new_days = int(diff.days * 433 / 140)
            elif int(session) == 3:
                if old_session == 1 :
                    new_days = int(diff.days * 83 / 220)
                elif old_session == 2:
                    new_days = int(diff.days * 140 / 220)
                elif old_session == 4:
                    new_days = int(diff.days * 280 / 220)
                elif old_session == 5:
                    new_days = int(diff.days * 350 / 220)
                elif old_session == 6:
                    new_days = int(diff.days * 433 / 220)
            elif int(session) == 4:
                if old_session == 1 :
                    new_days = int(diff.days * 83 / 280)
                elif old_session == 2:
                    new_days = int(diff.days * 140 / 280)
                elif old_session == 3:
                    new_days = int(diff.days * 220 / 280)
                elif old_session == 5:
                    new_days = int(diff.days * 350 / 280)
                elif old_session == 6:
                    new_days = int(diff.days * 433 / 280)
            elif int(session) == 5:
                if old_session == 1 :
                    new_days = int(diff.days * 83 / 350)
                elif old_session == 2:
                    new_days = int(diff.days * 140 / 350)
                elif old_session == 3:
                    new_days = int(diff.days * 220 / 350)
                elif old_session == 4:
                    new_days = int(diff.days * 280 / 350)
                elif old_session == 6:
                    new_days = int(diff.days * 280 / 433)
            elif int(session) == 6:
                if old_session == 1 :
                    new_days = int(diff.days * 83 / 433)
                elif old_session == 2:
                    new_days = int(diff.days * 140 / 433)
                elif old_session == 3:
                    new_days = int(diff.days * 220 / 433)
                elif old_session == 4:
                    new_days = int(diff.days * 280 / 433)
                elif old_session == 5:
                    new_days = int(diff.days * 350 / 433)
            # Calculate Correct Time
            print("Time Diff(Converted) => ", new_days)
            print("Old Session => ", old_session)
            print("New Session => ", session)
            print("New Months  => ", month_type)
            add_time = get_add_time(datetime.datetime.now(timezone('Asia/Seoul')), month_type, new_days)
        else:
            print("New Months  => ", month_type)
            add_time = get_add_time(my_time, month_type, 0)
    else:
        print("New Months  => ", month_type)
        add_time = get_add_time(datetime.datetime.now(timezone('Asia/Seoul')), month_type, 0)

    radius_time = enc_radius_time(add_time)
    
    if update_session:
        rcu = rc.first()
        rcu.value = int(session)
        rcu.save(using='radius')
        
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
        prev_time_rad = ''
        prev_time = ''
    else:
        rceu = rce.first()        
        prev_time_rad = rceu.value
        prev_time = dec_radius_time(rceu.value)
        rceu.value = radius_time
        rceu.save(using='radius')
    time_diff = dec_radius_time(radius_time) - prev_time
    time_diff = round((time_diff).total_seconds()/60)
    
    print("New Time        => ", add_time)
    print("Radius New Time => ", radius_time)
    reason = "구매"
    if update_session :
        reason = "구매 + 세션 변경(" + str(old_session) + "->" + session + ")"
    else :
    	reason = time_diff
    st = TblServiceTime(
        user_id = user_id,
        prev_time = prev_time,
        prev_time_rad = prev_time_rad,
        after_time = dec_radius_time(radius_time),
        after_time_rad = radius_time,
        diff = reason,
        reason = '',
        regist_date = datetime.datetime.now())
    st.save()
    
    print("============ User Subscription END =========", "")
    # Reward Time Calculate
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT tu.*, te.* FROM tbl_user tu 
            JOIN tbl_event_code te ON tu.rec = te.event_code
            WHERE  te.event_code = '{event_code}' 
        '''.format(event_code=u1.regist_rec)
        cur.execute(sql)
        rows = dictfetchall(cur)
        referrer_email = ""
        referrer_code = ""
        rewarder_id = 0
        if len(rows) == 0 :
            reward_percent = get_reward_percent()
            if reward_percent != 0 :
                sql = '''
                    SELECT * FROM tbl_user 
                    WHERE  rec = '{rec}' 
                '''.format(rec=u1.regist_rec)
                cur.execute(sql)
                rows = dictfetchall(cur)
                if len(rows) != 0 :
                    referrer_email = rows[0]['email']
                    rewarder_id = rows[0]['id']
                    referrer_code = rows[0]['rec']
        else :
            reward_percent =  get_reward_percent()
            if datetime.datetime.now() > rows[0]['start'] and datetime.datetime.now() < rows[0]['end']:
                reward_percent =  rows[0]['reward_percent']
            
            if reward_percent != 0 :
                referrer_email = rows[0]['email']
                rewarder_id = rows[0]['id']
                referrer_code = rows[0]['rec']
        if referrer_email != "" :
            print("================== Rewarder ================", "")
            referrer_session = 0
            referrer_time = my_radius_time(referrer_email, 'datetime')
            rc = Radcheck.objects.using('radius').filter(
                username = referrer_email,
                attribute = 'Simultaneous-Use'
            )
            if len(rc) != 0:
                rcu = rc.first()
                referrer_session = int(rcu.value)
            
            print("Rewarder Old Date====> ", referrer_time)
            reward_times = 0
            if referrer_time != None and referrer_time > datetime.datetime.now():
                print("No Expired===========> ", "True")
                reward_times = round(int(month_type) * 30 * 24 * 60* reward_percent * int(session) / (100 * referrer_session))
                print("Reward Minutes=======> ", month_type + "*30*" + str(reward_percent) + "*" + session +"/(100 * " + str(referrer_session) + ")")
                print("Reward Minutes=======> ", reward_times)
                add_referrer_time = get_referrer_time(referrer_time, month_type, reward_times)
            else :
                print("Expired===========> ", "True")
                reward_times = round(int(month_type) * 30 * 24 * 60* reward_percent * int(session) /(100 * referrer_session))
                print("Reward Minutes:======> ", month_type + "*30*" + str(reward_percent) +  "*" + session + "/(100 * " + str(referrer_session) + ")")
                print("Reward Minutes:======> ",reward_times)
                add_referrer_time = get_referrer_time(datetime.datetime.now(timezone('Asia/Seoul')), month_type, reward_times)
            
            referrer_radius_time = enc_radius_time(add_referrer_time)
            print("Referrer New Date====> ", referrer_radius_time)
            rce = Radcheck.objects.using('radius').filter(
                username = referrer_email,
                attribute = 'Expiration'
            )
            
            referrer_time_rad = ''
            if len(rce) == 0:
                rcei = Radcheck(
                    username = email,
                    attribute = 'Expiration',
                    op = ':=',
                    value = referrer_radius_time
                )
                rcei.save(using='radius')
            else:
                rceu = rce.first()
                referrer_time_rad = rceu.value
                rceu.value = referrer_radius_time
                rceu.save(using='radius')
            
            print("Rewarder Email:=======> ", referrer_email)
            print("Rewarder ID===========> ", rewarder_id)
            print("Register ID===========> ",  user_id)
            print("Reward Times:=========> ", reward_times)
            sql = '''
                INSERT INTO tbl_reward_log (rewarder_id, registrant_id, reward_days, type, event_code, register_date)
                VALUES ({rewarder_id}, {user_id}, {reward_days}, 1, '{event_code}', '{date}')
            '''.format(rewarder_id=rewarder_id, user_id=user_id, reward_days=reward_times, event_code=referrer_code, date = datetime.datetime.now())
            cur.execute(sql)
            st = TblServiceTime(
                user_id = rewarder_id,
                prev_time = referrer_time,
                prev_time_rad = referrer_time_rad,
                after_time = add_referrer_time,
                after_time_rad = referrer_radius_time,
                diff = reward_times,
                reason = '추천보상',
                regist_date = datetime.datetime.now())
            st.save()
            print("=============== Rewarder END ===============", "")
    
def get_old_time(old_time, month_type):
    add_time = old_time - relativedelta(months=int(month_type))
    return add_time
def get_time_other_session(old_time, new_days):
    add_time = old_time - datetime.timedelta(int(new_days))
    return add_time
    
def get_referrer_time(old_time, month_type, reward_times):
    referrer_add_time = old_time + datetime.timedelta(minutes=reward_times)
    return referrer_add_time

def get_add_time(old_time, month_type, new_days):
    add_time = old_time + relativedelta(months=int(month_type)) + datetime.timedelta(new_days)
    return add_time

def get_reward_percent():
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT * FROM tbl_reward_setting 
        '''.format()
        cur.execute(sql)
        rows = dictfetchall(cur)
        if len(rows) == 0 :
            return 0
        else :
            return rows[0]['percent']

# python datetime 자료형을 radius 자료형으로 변경하는 함수 (2019.09.09 12:53 점검완료)
def enc_radius_time(obj):
    #print('DEBUG -> enc_radius_time / obj : ', obj)
    radius_time = obj.strftime('%d') + ' ' + \
                  obj.strftime('%B')[:3] + ' ' + \
                  obj.strftime('%Y') + ' ' + \
                  obj.strftime('%H') + ':' + \
                  obj.strftime('%M') + ':' + \
                  obj.strftime('%S') + ' KST'
    #print('DEBUG -> enc_radius_time / radius_time : ', radius_time)
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


# 세션과 개월을 입력받아 상품명 생성 (2019.09.10 09:44 점검완료)
def makeProductName(session, month_type):
    if session == '1':
        if month_type == '1':
            return settings.SESSION_MONTH_1_1
        elif month_type == '2':
            return settings.SESSION_MONTH_1_2
        elif month_type == '3':
            return settings.SESSION_MONTH_1_3
        elif month_type == '6':
            return settings.SESSION_MONTH_1_6
        elif month_type == '12':
            return settings.SESSION_MONTH_1_12
    elif session == '2':
        if month_type == '1':
            return settings.SESSION_MONTH_2_1
        elif month_type == '2':
            return settings.SESSION_MONTH_2_2
        elif month_type == '3':
            return settings.SESSION_MONTH_2_3
        elif month_type == '6':
            return settings.SESSION_MONTH_2_6
        elif month_type == '12':
            return settings.SESSION_MONTH_2_12
    elif session == '3':
        if month_type == '1':
            return settings.SESSION_MONTH_3_1
        elif month_type == '2':
            return settings.SESSION_MONTH_3_2
        elif month_type == '3':
            return settings.SESSION_MONTH_3_3
        elif month_type == '6':
            return settings.SESSION_MONTH_3_6
        elif month_type == '12':
            return settings.SESSION_MONTH_3_12
    elif session == '4':
        if month_type == '1':
            return settings.SESSION_MONTH_4_1
        elif month_type == '2':
            return settings.SESSION_MONTH_4_2
        elif month_type == '3':
            return settings.SESSION_MONTH_4_3
        elif month_type == '6':
            return settings.SESSION_MONTH_4_6
        elif month_type == '12':
            return settings.SESSION_MONTH_4_12
    elif session == '5':
        if month_type == '1':
            return settings.SESSION_MONTH_5_1
        elif month_type == '2':
            return settings.SESSION_MONTH_5_2
        elif month_type == '3':
            return settings.SESSION_MONTH_5_3
        elif month_type == '6':
            return settings.SESSION_MONTH_5_6
        elif month_type == '12':
            return settings.SESSION_MONTH_5_12
    elif session == '6':
        if month_type == '1':
            return settings.SESSION_MONTH_6_1
        elif month_type == '2':
            return settings.SESSION_MONTH_6_2
        elif month_type == '3':
            return settings.SESSION_MONTH_6_3
        elif month_type == '6':
            return settings.SESSION_MONTH_6_6
        elif month_type == '12':
            return settings.SESSION_MONTH_6_12

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
