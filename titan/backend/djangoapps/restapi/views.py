import json
import datetime
import re
import uuid
import requests
import time
import ipaddress
import os
from dateutil.relativedelta import relativedelta
from django.shortcuts import render
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import connections
from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ObjectDoesNotExist
from pytz import timezone
from urllib.parse import quote
from urllib.parse import unquote
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.models import *
from backend.models_radius import *
from backend.djangoapps.common.views import *
from backend.djangoapps.common.smtp import send_email
from django.utils import translation
from django.conf import settings
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from distutils.version import LooseVersion, StrictVersion
import paramiko
import traceback
import socket
import random
import string
import threading

try:
    import geoip2.database
    from geoip2.errors import AddressNotFoundError
except ModuleNotFoundError:
    geoip2 = None
    AddressNotFoundError = Exception


GEOIP2_ASN_READER = None


def _get_geoip2_asn_reader():
    global GEOIP2_ASN_READER
    if geoip2 is None:
        return None
    if GEOIP2_ASN_READER is False:
        return None

    if GEOIP2_ASN_READER is None:
        db_path = getattr(settings, 'GEOIP2_ASN_DB_PATH', None)
        if not db_path or not os.path.exists(db_path):
            print('INFO -> GeoIP2 ASN DB missing or disabled, skip lookup')
            GEOIP2_ASN_READER = False
            return None
        try:
            GEOIP2_ASN_READER = geoip2.database.Reader(db_path)
        except Exception as err:
            # Downgrade to WARN and disable silently as requested
            print('WARN -> GeoIP2 ASN load fail (disabled): ', err)
            GEOIP2_ASN_READER = False
            return None

    return GEOIP2_ASN_READER


def _escape_sql_literal(value):
    return str(value).replace("'", "''")


DETECT_TELECOM_CACHE = {}
DETECT_TELECOM_CACHE_TTL = 300  # seconds

def _match_cn_telecom_hint(org_str):
    """ISP/org 문자열에서 중국 3대 통신사 힌트를 반환한다."""
    if not org_str:
        return None
    s = org_str.lower()
    if 'china telecom' in s:
        return 'ct'
    if 'china mobile' in s or 'cmcc' in s:
        return 'cm'
    if 'china unicom' in s or 'cucc' in s or 'china united network communications' in s:
        return 'cu'
    return None


def detect_cn_telecom(login_ip):
    """중국 통신사 힌트 탐지.
    1순위: GeoIP2 ASN 로컬 DB (네트워크 호출 없음, <1ms)
    2순위: ip-api.com HTTP (캐시 적용, timeout 0.8초)
    매핑: China Telecom -> ct, China Mobile|CMCC -> cm, China Unicom|CUCC -> cu
    """
    organization_raw = ''
    try:
        ip_obj = ipaddress.ip_address(login_ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast:
            return None, organization_raw
    except Exception:
        return None, organization_raw

    # Cache first
    try:
        now = time.time()
        cached = DETECT_TELECOM_CACHE.get(login_ip)
        if cached and cached[0] > now:
            return cached[1], cached[2]
    except Exception:
        pass

    # ---- 1순위: GeoIP2 ASN 로컬 DB (즉시 응답) ----
    reader = _get_geoip2_asn_reader()
    if reader:
        try:
            asn_resp = reader.asn(login_ip)
            organization_raw = asn_resp.autonomous_system_organization or ''
            hint = _match_cn_telecom_hint(organization_raw)
            try:
                DETECT_TELECOM_CACHE[login_ip] = (time.time() + DETECT_TELECOM_CACHE_TTL, hint, organization_raw)
            except Exception:
                pass
            return hint, organization_raw
        except Exception:
            pass  # GeoIP2 lookup 실패 시 fallback

    # ---- 2순위: ip-api.com HTTP (캐시 적용) ----
    try:
        resp = safe_ip_api_lookup(login_ip, timeout=0.8)
        isp = (resp.get('isp') or '')
        if isp:
            organization_raw = isp
            hint = _match_cn_telecom_hint(isp)
            if hint:
                try:
                    DETECT_TELECOM_CACHE[login_ip] = (time.time() + DETECT_TELECOM_CACHE_TTL, hint, organization_raw)
                except Exception:
                    pass
                return hint, organization_raw
    except Exception:
        pass

    # ---- 3순위: ip-api.com 확장 조회 (org/as) ----
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{login_ip}?fields=status,message,org,isp,as",
            timeout=1.0,
        )
        data = resp.json()
        if data.get('status') != 'success':
            return None, organization_raw
        organization_raw = data.get('org') or data.get('isp') or data.get('as') or ''
        hint = _match_cn_telecom_hint(organization_raw)
        try:
            DETECT_TELECOM_CACHE[login_ip] = (time.time() + DETECT_TELECOM_CACHE_TTL, hint, organization_raw)
        except Exception:
            pass
        return hint, organization_raw
    except Exception:
        return None, organization_raw


SAFE_IP_CACHE = {}
SAFE_IP_CACHE_TTL = 300  # seconds

# Server list cache (shared across all users, TTL 30s)
import copy as _copy
_SERVER_LIST_CACHE = {'rows': None, 'ts': 0}
_SERVER_LIST_CACHE_TTL = 30  # seconds

# Short-window de-duplication for telecom org logging to reduce noise
_TELECOM_ORG_LAST = {'org': None, 'ts': 0}

def _log_telecom_org_once(organization_raw, window_secs=3):
    try:
        if not organization_raw:
            return
        now = time.time()
        last_org = _TELECOM_ORG_LAST.get('org')
        last_ts = _TELECOM_ORG_LAST.get('ts', 0)
        if last_org == organization_raw and (now - last_ts) < window_secs:
            return
        print('INFO -> telecom org(raw) : ', organization_raw)
        _TELECOM_ORG_LAST['org'] = organization_raw
        _TELECOM_ORG_LAST['ts'] = now
    except Exception:
        # Fallback to direct print on any unexpected error
        try:
            print('INFO -> telecom org(raw) : ', organization_raw)
        except Exception:
            pass


def safe_ip_api_lookup(ip_addr, timeout=0.8):
    """Best-effort lookup of country/city/isp via ip-api.com.
    Returns dict with keys: country, city, isp (may be empty strings on failure).
    Swallows all exceptions and network / JSON errors.
    """
    # Cache check
    try:
        now = time.time()
        cached = SAFE_IP_CACHE.get(ip_addr)
        if cached and cached[0] > now:
            return cached[1]
    except Exception:
        pass

    base = f"http://ip-api.com/json/{ip_addr}?fields=status,message,country,city,isp"
    try:
        resp = requests.get(base, timeout=timeout)
        data = resp.json()
        if data.get('status') != 'success':
            return {'country': '', 'city': '', 'isp': ''}
        result = {
            'country': data.get('country') or '',
            'city': data.get('city') or '',
            'isp': data.get('isp') or ''
        }
        # Cache success only
        try:
            SAFE_IP_CACHE[ip_addr] = (time.time() + SAFE_IP_CACHE_TTL, result)
        except Exception:
            pass
        return result
    except Exception as err:
        # Keep logs lightweight to avoid flooding
        print('WARN -> safe_ip_api_lookup fail:', err)
        return {'country': '', 'city': '', 'isp': ''}


def _read_first_line_nonblock(stdout, timeout=0.7):
    """Read first line from Paramiko stdout with a channel timeout to avoid blocking."""
    try:
        try:
            stdout.channel.settimeout(timeout)
        except Exception:
            pass
        data = stdout.read().decode("utf-8")
        if not data:
            return ''
        return data.split('\n')[0]
    except Exception:
        return ''


def strongswan_down_nb_safely(ssh, user_identifier, max_total_wait=0.8):
    """Attempt to gracefully tear down a strongSwan SA; avoid long waits and duplicate calls unless needed.
    Flow:
    - statusall|grep {user} to get SA id (non-blocking read with short timeout)
    - run one down-nb
    - small sleep, re-check; only run a second down-nb if SA still present
    - never exceed max_total_wait seconds of sleeps/checks
    """
    try:
        # Find SA identifier first
        cmd = 'strongswan statusall | grep ' + user_identifier
        _stdin, _stdout, _stderr = ssh.exec_command(cmd)
        first = _read_first_line_nonblock(_stdout, timeout=min(0.7, max_total_wait))
        if not first:
            return
        sa = first.split(':')[0].strip()
        if not sa:
            return
        down_cmd = 'strongswan stroke down-nb ' + sa
        print('cmd => ', down_cmd)
        ssh.exec_command(down_cmd)
        # Re-check if still present, then optionally send second
        remaining = max_total_wait - 0.15
        if remaining <= 0:
            return
        time.sleep(0.15)
        cmd2 = 'strongswan statusall | grep ' + user_identifier
        _stdin2, _stdout2, _stderr2 = ssh.exec_command(cmd2)
        second = _read_first_line_nonblock(_stdout2, timeout=max(0.0, remaining))
        if second:
            # Still present, send one more down-nb
            ssh.exec_command(down_cmd)
    except Exception as _e:
        print('WARN -> strongswan_down_nb_safely fail:', _e)

def _bg_ssh_kick(nasipaddress, ssh_user, ssh_pass, nasporttype, nasportid,
                 sessionid, user_id, protocol, simultaneous_use, connected_count,
                 nas_name, nas_telecom, login_ip, callingstationid):
    """Background thread: SSH kick + tbl_disconnection INSERT.
    radacct UPDATE is already done synchronously in the main thread."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(nasipaddress, username=ssh_user, password=ssh_pass, timeout=1)
            if nasporttype == 'ISDN':  # openvpn
                print('INFO -> [bg] Openvpn Server telnet login:' + user_id)
                channel = ssh.invoke_shell()
                channel.send("telnet 127.0.0.1 1199\n")
                time.sleep(0.5)
                channel.send("mykakao9898\n")
                time.sleep(0.2)
                channel.send('kill ' + user_id + '\n')
                time.sleep(0.2)
                channel.send("exit\n")
                time.sleep(0.2)
                channel.send("exit\n")
                time.sleep(0.2)
                output = channel.recv(65535).decode('utf-8')
                print(output)
            elif nasportid == '443':  # softether sstp
                print('INFO -> [bg] SSTP Force Stop:' + user_id)
                _sid = sessionid.replace('=5BSSTP=5D', '[SSTP]')
                command = ("/usr/local/vpnserver/vpncmd " + nasipaddress +
                           " /SERVER /HUB:" + settings.SOFTETHER_HUB +
                           " /PASSWORD:'" + settings.SOFTETHER_PASS +
                           "' /CMD SessionDisconnect " + _sid)
                print('cmd => ', command)
                ssh.exec_command(command)
            elif nasporttype == 'V2RAY':  # V2RAY
                pass  # No SSH action needed
            else:  # IKEV2
                print('INFO -> [bg] IKEV2 Force Stop:' + user_id)
                strongswan_down_nb_safely(ssh, user_id)
        except socket.timeout:
            print('INFO -> [bg] socket.timeout ' + user_id)
        except Exception as err:
            print('ERROR -> [bg] ssh kick err: ' + user_id, err)
        finally:
            try:
                ssh.close()
            except Exception:
                pass
        # INSERT tbl_disconnection using a fresh DB connection
        try:
            with connections['default'].cursor() as bg_cur:
                sql = '''
                    INSERT INTO tbl_disconnection (username, user_session, connected_count, protocol, server_name, telecom, disconnected_time, new_ip, old_ip)
                    VALUES('{id}', '{simultaneous_use}', '{connected_count}', '{protocol}', '{server_name}', '{telecom}', '{date}', '{login_ip}', '{callingstationid}');
                '''.format(date=datetime.datetime.now(), id=user_id, connected_count=connected_count,
                           protocol=protocol, server_name=nas_name, telecom=nas_telecom,
                           simultaneous_use=simultaneous_use, login_ip=login_ip,
                           callingstationid=callingstationid)
                bg_cur.execute(sql)
        except Exception as db_err:
            print('ERROR -> [bg] tbl_disconnection insert fail:', db_err)
    except Exception as e:
        print('ERROR -> [bg] _bg_ssh_kick outer:', e)
    finally:
        try:
            from django.db import close_old_connections
            close_old_connections()
        except Exception:
            pass


# 페이레터 해외 모바일 (2019.09.12 21:06 점검완료)
@csrf_exempt
def app_payletter_global(request):

    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')

    product_name = makeProductName(session, month_type)
    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> user_name : ', user_name)
    print('DEBUG -> pgcode : ', pgcode)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month_type : ', month_type)
    print('DEBUG -> product_name : ', product_name)

    price = getProductPirce(session, month_type, 'USD')
    print('DEBUG -> price : ', price)

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(user_id):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    gp = PayletterGlobal(settings.PAYLETTER_MODE)
    html = gp.payments_request(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email,
        'mobile'
    )

    print('DEBUG -> html : ', html)

    return JsonResponse({'result': html})


# 페이레터 국내 모바일 (2019.09.12 21:06 점검완료)
@csrf_exempt
def app_payletter_korea(request):

    user_id = request.session['id']
    user_name = request.session['username']
    pgcode = request.POST.get('pgcode')
    session = request.POST.get('session')
    month_type = request.POST.get('month_type')

    product_name = makeProductName(session, month_type)
    print('DEBUG -> user_id : ', user_id)
    print('DEBUG -> user_name : ', user_name)
    print('DEBUG -> pgcode : ', pgcode)
    print('DEBUG -> session : ', session)
    print('DEBUG -> month_type : ', month_type)
    print('DEBUG -> product_name : ', product_name)

    price = getProductPirce(session, month_type, 'KRW')
    print('DEBUG -> price : ', price)

    u1 = TblUser.objects.get(id=user_id)

    # 사용자 이중결제 방지
    if duplicatePaymentProtect(user_id):
        return JsonResponse({'result': 'fail'})

    # 상품번호 생성
    order_no = createOrderNumber(user_id)

    # 세션, 개월수를 넘겨주기 위한 커스텀 파라미터 생성
    custom_parameter = createCustomParameter(session, month_type)

    # 결제요청 API 호출
    p = Payletter(settings.PAYLETTER_MODE)
    res = p.payments_request(
        pgcode,
        user_id,
        user_name,
        int(price),
        product_name,
        order_no,
        custom_parameter,
        u1.email
    )
    res = json.loads(res)
    mobile_url = res['mobile_url']

    print('DEBUG -> mobile_url : ', mobile_url)

    return JsonResponse({'result': mobile_url})


# 안드로이드 버전 조회 API (2019.09.16 21:49)
@csrf_exempt
def app_android_version(request):
    # 200 : 업데이트 필요없음
    # 300 : 업데이트 필요함
    version_name = request.POST.get('version_name')
    version_code = request.POST.get('version_code')

    with connections['default'].cursor() as cur:
            sql = '''
                SELECT ver_name , ver_code
                FROM titan.tbl_android_version
                ORDER BY id desc limit 1 
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            ver_code = rows[0]['ver_code']
            ver_name = rows[0]['ver_name']
            
            if StrictVersion(ver_name) <= StrictVersion(version_name) :
                return JsonResponse({'result': 200,
                					 'version_code': version_code,
                					 'version_name': version_name})
            else :
                return JsonResponse({'result': 300,
                					 'version_code': ver_code,
                					 'version_name': ver_name})


# 윈도우즈 버전 조회 API (2019.09.16 21:49)
@csrf_exempt
def app_windows_version(request):
    version_code = request.POST.get('version_code')
    with connections['default'].cursor() as cur:
            sql = '''
                SELECT ver_code
                FROM titan.tbl_windows_version
                ORDER BY id desc limit 1 
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            ver_code = rows[0]['ver_code']
            new_ver_code = ver_code.split('.')[0] + "." + ver_code.split('.')[1] + "." + ver_code.split('.')[2]
            new_version_code = version_code.split('.')[0] + "." + version_code.split('.')[1] + "." + version_code.split('.')[2] 
            if StrictVersion(new_ver_code) <= StrictVersion(new_version_code) :
                return JsonResponse({'result': 200,
                					 'version_code': version_code})
            else :
                return JsonResponse({'result': 300,
                					 'version_code': ver_code})

    # try:
    #     twv = TblWindowsVersion.objects.get(ver_code=version_code)
    #     ret = {
    #         'ver_code': twv.ver_code,
    #         'remark': twv.remark
    #     }
    #     print("debug ver request ==>",version_code)
    #     print("debug ver request ==>",ret['ver_code'])
    #     return JsonResponse({'result': 200})
    # except BaseException as err:
    #     print('ERROR -> err : ', err)
    #     return JsonResponse({'result': 300})

# MAC OS 버전 조회 API (2020.02.18 12:44)
@csrf_exempt
def app_osx_version(request):

    version_code = request.POST.get('version_code')

    with connections['default'].cursor() as cur:
            sql = '''
                SELECT ver_code
                FROM titan.tbl_osx_version
                ORDER BY id desc limit 1 
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            ver_code = rows[0]['ver_code']

            if StrictVersion(ver_code) <= StrictVersion(version_code) :
                return JsonResponse({'result': 200,
                					 'version_code': version_code})
            else :
                return JsonResponse({'result': 300,
                					 'version_code': ver_code})


# 디비에 세션키 생성 후 반환 API (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_init_session(request):
    if settings.HTTPS == True:
        endpoint = 'https://'+ settings.MY_URL +''
    if settings.HTTPS == False:
        endpoint = 'http://'+ settings.MY_URL +''
    url = endpoint + '/login'
    session = requests.Session()
    attempts = 0
    csrftoken = None
    sessionid = None
    last_err = None
    while attempts < 3 and (csrftoken is None or sessionid is None):
        try:
            session.get(url, timeout=2)
            store = session.cookies.get_dict()
            csrftoken = store.get('csrftoken')
            sessionid = store.get('sessionid')
            if csrftoken and sessionid:
                break
        except Exception as err:
            last_err = err
        attempts += 1
        if attempts < 3:
            time.sleep(0.4 * attempts)  # exponential-ish backoff
    if csrftoken is None or sessionid is None:
        if last_err:
            print('ERROR -> init_session network fail:', last_err)
            return JsonResponse({'result': 500, 'error': 'session_init_failed'})
        print('ERROR -> init_session missing cookies after retries')
        return JsonResponse({'result': 501, 'error': 'missing_session_cookies'})
    print('INFO -> csrftoken : ', csrftoken)
    print('INFO -> sessionid : ', sessionid)
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT *
            FROM titan.tbl_china_app
        '''
        cur.execute(sql)
        rows = dictfetchall(cur)

        return JsonResponse({
            'csrftoken': csrftoken,
            'sessionid': sessionid,
            'data':rows
        })

# 세션 키 복호화 테스트 API (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_session_test(request):
    tmp = {
        'id': request.session['id'],
        'email': request.session['email'],
        'username': request.session['username'],
        'is_staff': request.session['is_staff'],
    }
    print('DEBUG -> tmp : ', tmp)
    return JsonResponse({'result': tmp})


# 세션키 체크 API (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_check_login(request):
    if 'id' in request.session:
        id = request.session['id']
        device_type = request.POST.get('device_type')
        device_os = request.headers['User-Agent']
        app_version = request.POST.get('app_version')
        device_uuid = request.POST.get('device_uuid')
        load_balancer = request.headers['Host']
        api_url = settings.MY_URL
        login_ip = get_client_ip(request)
        print('INFO -> START CHECK LOGIN')
        print('INFO -> ID : ', id)
        print('INFO -> device_type : ', device_type)
        print('INFO -> device_os : ', device_os)
        print('INFO -> app_version : ', app_version)
        print('INFO -> device_uuid : ', device_uuid)
        print('INFO -> load_balancer : ', load_balancer)
        print('INFO -> api_url : ', api_url)

        # ===== 기기/계정/IP 접속금지 체크 (2026-02-11) =====
        try:
            from django.db.models import Q
            login_email = request.session.get('email', '')
            ban_q = Q()
            if device_uuid:
                ban_q |= Q(device_uuid=device_uuid)
            if login_ip:
                ban_q |= Q(device_ip=login_ip)
            if login_email:
                ban_q |= Q(email=login_email)
            active_ban = TblBannedDevice.objects.filter(
                ban_q, is_active=1
            ).exclude(
                device_uuid='', device_ip='', email=''
            ).first()
            if active_ban:
                print(f'INFO -> CHECK_LOGIN BANNED email={login_email} ban_id={active_ban.id} '
                      f'type={active_ban.ban_type}')
                request.session.flush()
                return JsonResponse({'result': 710, 'msg': 'This device is banned'})
        except Exception as ban_err:
            print('WARN -> check_login ban check error:', ban_err)
	
        #if app_version == None:
        #    return JsonResponse({'result': 200,'id': id})
        response = safe_ip_api_lookup(login_ip)
        print('INFO -> device_country : ', (response.get('country') or ''))
        print('INFO -> device_city : ', (response.get('city') or ''))
        print('INFO -> login_time : ', datetime.datetime.now())
 
        # 같은 user_id + device_uuid: upsert (중복 있으면 최신 1개만 남기고 UPDATE)
        current_sk = request.session.session_key or ''
        if device_uuid:
            dupes = list(TblDeviceInfo.objects.filter(
                user_id=id, device_uuid=device_uuid
            ).order_by('-login_time'))
            if len(dupes) > 1:
                # 최신 1개 빼고 나머지 삭제
                keep = dupes[0]
                del_ids = [d.id for d in dupes[1:]]
                TblDeviceInfo.objects.filter(id__in=del_ids).delete()
                print(f'INFO -> check_login: dedup deleted {len(del_ids)} old device_info')
                existing = keep
            elif len(dupes) == 1:
                existing = dupes[0]
            else:
                existing = None
        else:
            existing = None

        if existing:
            existing.app_version = app_version
            existing.device_type = device_type
            existing.device_os = device_os.replace('\'', '')
            existing.device_ip = login_ip
            existing.device_country = (response.get('country') or '').replace('\'', '')
            existing.device_city = (response.get('city') or '').replace('\'', '')
            existing.device_isp = (response.get('isp') or '').replace('\'', '')
            existing.session_key = current_sk
            existing.api_url = api_url
            existing.load_balancer = load_balancer
            existing.login_time = datetime.datetime.now()
            existing.save()
            print(f'INFO -> check_login: UPDATED id={existing.id} sk={current_sk[:12]}')
        else:
            st = TblDeviceInfo(
                user_id = id,
                app_version = app_version,
                device_type = device_type,
                device_os = device_os.replace('\'', ''),
                device_uuid = device_uuid,
                device_ip = login_ip,
                device_country = (response.get('country') or '').replace('\'', ''),
                device_city = (response.get('city') or '').replace('\'', ''),
                device_isp = (response.get('isp') or '').replace('\'', ''),
                session_key = current_sk,
                api_url = api_url,
                load_balancer = load_balancer,
                login_time = datetime.datetime.now())
            st.save()
            print(f'INFO -> check_login: INSERTED id={st.id} sk={current_sk[:12]}')

        with connections['default'].cursor() as cur:
            sql = '''
                SELECT *
                FROM titan.tbl_china_app
            '''
            cur.execute(sql)
            rows = dictfetchall(cur)
            
            sql_all = '''
                SELECT id, content_zh, content_en, content_ko
                FROM tbl_notice
                WHERE (platform = "{device_type}"
                OR platform = "All") AND delete_yn = 'N' AND end_date > '{date}'
                ORDER BY id DESC
            '''.format(device_type=device_type, date = datetime.datetime.now())
            cur.execute(sql_all)
            common_rows = dictfetchall(cur)
                    
            sql_user = '''
                SELECT tn.id, tn.content_zh, tn.content_en, tn.content_ko
                FROM tbl_notice_user tu
                LEFT JOIN tbl_notice tn ON tu.notice_id = tn.id
                WHERE tu.user_id ={id} AND delete_yn = 'N' AND end_date > '{date}'
                ORDER BY tu.id DESC
            '''.format(id=id, date = datetime.datetime.now())
            cur.execute(sql_user)
            user_rows = dictfetchall(cur)
            
            return JsonResponse({'result': 200,'id': id, 'data':rows, 'common_notice': common_rows, 'user_notice': user_rows})
    else:
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT *
                FROM titan.tbl_china_app
            '''
            cur.execute(sql)
            rows = dictfetchall(cur)
            print('INFO -> Session is invalid')
            return JsonResponse({'result': 400, 'data':rows})


# 세션키 삭제 API - 로그아웃 (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_user_logout(request):
    if 'id' in request.session:
        del request.session['id']
    if 'email' in request.session:
        del request.session['email']
    if 'username' in request.session:
        del request.session['username']
    if 'is_staff' in request.session:
        del request.session['is_staff']
    print('INFO -> App Logout Processing Complete')
    return JsonResponse({'result': 200})


# 비밀번호 변경 API (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_change_password(request):
    if 'id' in request.session:
        id = request.session['id']

        user_privious_password = request.POST.get('user_privious_password')
        user_new_password = request.POST.get('user_new_password')
        hash_password = hashText(user_new_password)

        # 비밀번호 유효성 검증
        check_cnt = 0
        pattern1 = re.search('[0-9]', user_new_password)
        pattern2 = re.search('[a-zA-Z]', user_new_password)
        pattern3 = re.search('[~!@#$%^&*()_+|<>?:{}]', user_new_password)

        if len(user_new_password) < 8:
            print('ERROR -> Password validation fail')
            return JsonResponse({'result': 500})
        if len(user_new_password) > 16:
            print('ERROR -> Password validation fail')
            return JsonResponse({'result': 500})
        if pattern1 != None:
            print('INFO -> pattern1 match')
            check_cnt += 1
        if pattern2 != None:
            print('INFO -> pattern2 match')
            check_cnt += 1
        if pattern3 != None:
            print('INFO -> pattern3 match')
            check_cnt += 1
        print('INFO -> check_cnt : ', check_cnt)
        if check_cnt >= 2:
            print('INFO -> Password validation success')
            pass
        else:
            print('ERROR -> Password validation fail')
            return JsonResponse({'result': 500})

        # 현재 비밀번호 검증
        u1 = TblUser.objects.get(id = id)
        match_result = matchHashedText(u1.password, user_privious_password)
        if match_result == True:
            u1.password = hash_password
            u1.save()
            print('INFO -> Password change completed')
            return JsonResponse({'result': 200})
        else:
            print('INFO -> Password change failed')
            return JsonResponse({'result': 600})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 404})


# 사용자 정보 로드 API (2019.09.09 15:12 점검완료)
@csrf_exempt
def app_get_userinfo(request):
    if 'id' in request.session:
        id = request.session['id']

        with connections['default'].cursor() as cur:
            sql = '''
                select 	w.email,
                		ifnull(w.product_name, '') as product_name,
                        w.username,
                        ifnull(t.value, '') as value,
                        ifnull(w.rec, '') as rec,
                        ifnull(w.regist_rec, '') as regist_rec
                from (
                select email,
                		case
                        when a.regist_date > b.accept_date or b.accept_date is null
                        then a.product_name
                        else b.product_name
                        end as product_name,
                        username,
                        rec,
                        regist_rec
                from tbl_user x
                left join (
                	select *
                	from tbl_price_history
                	where refund_yn = 'N'
                	and user_id = '{id}'
                	order by regist_date desc
                	limit 1
                )a
                on x.id = a.user_id
                left join (
                	select *
                	from tbl_send_history
                	where status IN ('A','S')
                	and user_id = '{id}'
                	order by accept_date desc
                	limit 1
                ) b
                on x.id = b.user_id
                where x.id = '{id}'
                ) w
                join radius.radcheck t
                on w.email = t.username
                where t.attribute = 'Expiration';
            '''.format(id=id)
            cur.execute(sql)
            row = dictfetchall(cur)
            # FOR APPLE
            apple_sql = '''
                    select 
                    (select status from titan.tbl_apple_status where platform = 'iOS') as apple_status, 
                    (select status from titan.tbl_apple_status where platform = 'Mac') as mac_status;
            '''.format()
            cur.execute(apple_sql)
            apple_row = dictfetchall(cur)
            
            if len(row) != 0:
                res = row[0]
                res['info_value'] = dec_radius_time(res['value']).strftime("%Y-%m-%d %H:%M:%S")
                delta = datetime.datetime.strptime(res['info_value'], '%Y-%m-%d %H:%M:%S') - datetime.datetime.now()
                res['remain_days'] = delta.days
                if len(apple_row) != 0:
                    res['apple_status'] = apple_row[0]['apple_status']
                    res['mac_status'] = apple_row[0]['mac_status']
                else :
                    res['apple_status'] = 0
                    res['mac_status'] = 0
            else:
                sql = '''
                    select email, '' as product_name, username, '' as value, rec, regist_rec
                    from titan.tbl_user
                    where id = '{id}';
                '''.format(id=id)
                cur.execute(sql)
                row = dictfetchall(cur)
                res = row[0]
                res['info_value'] = ''
                res['remain_days'] = ''
                if len(apple_row) != 0:
                    res['apple_status'] = apple_row[0]['apple_status']
                    res['mac_status'] = apple_row[0]['mac_status']
                else :
                    res['apple_status'] = 0
                    res['mac_status'] = 0
        res['result'] = 200
        res['id'] = id
        # 서비스 만료 체크
        if datetime.datetime.strptime(res['info_value'], '%Y-%m-%d %H:%M:%S') < datetime.datetime.now() :
            res['is_expiration'] = True
        else :
            res['is_expiration'] = False
        return JsonResponse(res)
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})


# 그룹코드 목록 호출 API (2019.09.09 15:15 점검완료)
@csrf_exempt
def app_group_list(request):
    tcg = TblCodeGroup.objects.filter(
        delete_yn = 'N'
    )
    res = []
    for t in tcg:
        tmp = {}
        tmp['code'] = t.code
        tmp['name'] = t.name
        res.append(tmp)
    return JsonResponse({'result': res})


# 가격정보 호출 API (2019.09.09 15:15 점검완료)
@csrf_exempt
def app_get_price(request):
    tp = TblPrice.objects.all()
    res = []
    for t in tp:
        session = t.type_session
        month = t.type_month
        price = t.item_price
        item_price_usd = t.item_price_usd
        item_price_jpy = t.item_price_jpy
        item_price_cny = t.item_price_cny
        tmp = {
            'session': session,
            'month': month,
            'price': price,
            'item_price_usd': item_price_usd,
            'item_price_jpy': item_price_jpy,
            'item_price_cny': item_price_cny
        }
        res.append(tmp)
    return JsonResponse({'result': res})


# 그룹코드 요소 호출 API (2019.09.09 15:15 점검완료)
@csrf_exempt
def app_get_group(request):
    code = request.POST.get('code')
    tcg = TblCodeGroup.objects.get(
        code = code,
        delete_yn = 'N'
    )
    res = {
        'name': tcg.name,
        'memo': tcg.memo
    }
    return JsonResponse({'result':res})


# 코드 요소 호출 API (2019.09.09 15:15 점검완료)
@csrf_exempt
def app_get_detail(request):
    group_code = request.POST.get('group_code')
    tcd = TblCodeDetail.objects.filter(
        group_code = group_code,
        delete_yn = 'N'
    )
    res = []
    for t in tcd:
        tmp = {}
        tmp['code'] = t.code
        tmp['name'] = t.name
        tmp['memo'] = t.memo
        res.append(tmp)
    return JsonResponse({'result': res})


# 메세지 푸쉬 API (2019.09.09 15:15 점검완료)
@csrf_exempt
def app_push_message(request):
    to = request.POST.get('to')                      # "/topics/all"
    collapse_key = request.POST.get('collapse_key')  # "type_a"
    body = request.POST.get('body')                  # "world"
    title = request.POST.get('title')                # "hello"
    url = 'https://fcm.googleapis.com/fcm/send'
    headers = {
        "Authorization": "key=AAAAHkOoqDo:APA91bEv8Q51tDZQ5rMgDTWStGQK_s0W1jAkfB0a29aY0BTPamiYwxHGPAxue0UoJz8tZ_ERfSry-QvFBtDO5Akw2N6BI2myDUXDXUiZP6FCHj9-p0zp_oEOcNBx2IXcTA7zC8ChMJNy",
        "Content-Type": "application/json"
    }
    payload = {
        "to": to,
        "collapse_key": collapse_key,
        "data": {
            "title": title,
            "body": body
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print('DEBUG -> status_code : ', r.status_code)
        print('DEBUG -> text : ', r.text)
        print('INFO -> I sent you a normal Push message')
        return JsonResponse({'result': 200})
    except BaseException as err:
        print('ERROR -> err : ', err)
        return JsonResponse({'result': 500})


# 세션키 발급 API (2019.09.09 15:20 점검완료)
@csrf_exempt
def app_session_key(request):
    login_email = request.POST.get('login_email')
    login_password = request.POST.get('login_password')
    device_type = request.POST.get('device_type')
    device_os = request.headers['User-Agent']
    app_version = request.POST.get('app_version')
    device_uuid = request.POST.get('device_uuid')
    load_balancer = request.headers['Host']
    api_url = settings.MY_URL
    login_ip = get_client_ip(request)
    print('INFO -> START APP SESSION KEY')
    print('INFO -> login_email : ', login_email)
    # 비밀번호는 로그에 남기지 않고 마스킹 처리
    if login_password:
        print('INFO -> login_password : (masked {} chars)'.format(len(login_password)))
    else:
        print('INFO -> login_password : (empty)')
    print('INFO -> login_ip : ', login_ip)

    # 백엔드 유효성 체크
    if login_email == '':
        return JsonResponse({'result': 400})
    elif login_password == '':
        return JsonResponse({'result': 400})

    # 아이디 존재여부 체크
    try:
        u1 = TblUser.objects.get(email=login_email)
    except BaseException:
        return JsonResponse({'result': 600})

    user_password = u1.password
    user_id = u1.id

    # 활성화 여부 체크
    if u1.is_active == 0:
        return JsonResponse({'result': 700})

    # ===== 기기/계정/IP 접속금지 체크 (2026-02-11) =====
    try:
        from django.db.models import Q
        # 각 차단 유형별 해당 필드만 저장되므로 OR로 매칭
        ban_q = Q()
        if device_uuid:
            ban_q |= Q(device_uuid=device_uuid)
        if login_ip:
            ban_q |= Q(device_ip=login_ip)
        ban_q |= Q(email=login_email)
        # device_uuid='' 이거나 device_ip='' 인 빈값 매칭 방지
        active_ban = TblBannedDevice.objects.filter(
            ban_q, is_active=1
        ).exclude(
            device_uuid='', device_ip='', email=''
        ).first()
        if active_ban:
            print(f'INFO -> BANNED login_email={login_email} matched ban_id={active_ban.id} '
                  f'type={active_ban.ban_type} uuid={active_ban.device_uuid} ip={active_ban.device_ip} email={active_ban.email}')
            return JsonResponse({'result': 710, 'msg': 'This device is banned'})
    except Exception as ban_err:
        print('WARN -> ban check error:', ban_err)

    # 로그인 테이블 체크
    try:
        u2 = TblUserLogin.objects.get(user_id=user_id)
    except BaseException:
        return JsonResponse({'result': 500})

    user_attempt = u2.attempt

    print('INFO -> user_id : ', user_id)
    print('INFO -> user_attempt : ', user_attempt)

    # 로그인 시도 오버 시 계정 잠금
    if user_attempt >= 100:
        return JsonResponse({'result': 300})

    match_result = matchHashedText(user_password, login_password)
    if match_result == True:
        try:
            with transaction.atomic():
                u1.login_ip = login_ip
                u2.attempt = 0
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()

                # 세션키를 찾을 수 없는 경우
                if request.session.session_key == None:
                    return JsonResponse({'result': 444})

                # 로그인 성공
                request.session['id'] = u1.id
                request.session['email'] = u1.email
                request.session['username'] = u1.username
                request.session['is_staff'] = u1.is_staff
                
                #if app_version == None:
                #    return JsonResponse({'result': 200})
                response = safe_ip_api_lookup(login_ip)
                print('INFO -> user_id : ', user_id)
                print('INFO -> app_version : ', app_version)
                print('INFO -> device_type : ', device_type)
                print('INFO -> device_os : ', device_os)
                print('INFO -> device_uuid : ', device_uuid)
                print('INFO -> device_country: ', response.get('country'))
                print('INFO -> device_city : ', response.get('city'))
                print('INFO -> api_url : ', api_url)
                print('INFO -> load_balancer : ', load_balancer)
                print('INFO -> login_time : ', datetime.datetime.now())
                
                # 같은 user_id + device_uuid: upsert (중복 있으면 최신 1개만 남기고 UPDATE)
                current_sk = request.session.session_key or ''
                if device_uuid:
                    dupes = list(TblDeviceInfo.objects.filter(
                        user_id=u1.id, device_uuid=device_uuid
                    ).order_by('-login_time'))
                    if len(dupes) > 1:
                        keep = dupes[0]
                        del_ids = [d.id for d in dupes[1:]]
                        TblDeviceInfo.objects.filter(id__in=del_ids).delete()
                        print(f'INFO -> session_key login: dedup deleted {len(del_ids)} old device_info')
                        existing = keep
                    elif len(dupes) == 1:
                        existing = dupes[0]
                    else:
                        existing = None
                else:
                    existing = None

                if existing:
                    existing.app_version = app_version
                    existing.device_type = device_type
                    existing.device_os = device_os.replace('\'', '')
                    existing.device_ip = login_ip
                    existing.device_country = (response.get('country') or '').replace('\'', '')
                    existing.device_city = (response.get('city') or '').replace('\'', '')
                    existing.device_isp = (response.get('isp') or '').replace('\'', '')
                    existing.session_key = current_sk
                    existing.api_url = api_url
                    existing.load_balancer = load_balancer
                    existing.login_time = datetime.datetime.now()
                    existing.save()
                    print(f'INFO -> session_key login: UPDATED id={existing.id} sk={current_sk[:12]}')
                else:
                    st = TblDeviceInfo(
                        user_id = u1.id,
                        app_version = app_version,
                        device_type = device_type,
                        device_os = device_os.replace('\'', ''),
                        device_uuid = device_uuid,
                        device_ip = login_ip,
                        device_country = (response.get('country') or '').replace('\'', ''),
                        device_city = (response.get('city') or '').replace('\'', ''),
                        device_isp = (response.get('isp') or '').replace('\'', ''),
                        session_key = current_sk,
                        api_url = api_url,
                        load_balancer = load_balancer,
                        login_time = datetime.datetime.now())
                    st.save()
                    print(f'INFO -> session_key login: INSERTED id={st.id} sk={current_sk[:12]}')
                
                with connections['default'].cursor() as cur:
                    sql_all = '''
                        SELECT id, content_zh, content_en, content_ko
                        FROM tbl_notice
                        WHERE (platform = "{device_type}"
                        OR platform = "All") AND delete_yn = 'N' AND end_date > '{date}'
                        ORDER BY id DESC
                    '''.format(device_type=device_type, date = datetime.datetime.now())
                    cur.execute(sql_all)
                    common_rows = dictfetchall(cur)
                    
                    sql_user = '''
                        SELECT tn.id, tn.content_zh, tn.content_en, tn.content_ko
                        FROM tbl_notice_user tu
                        LEFT JOIN tbl_notice tn ON tu.notice_id = tn.id
                        WHERE tu.user_id ={id} AND delete_yn = 'N' AND end_date > '{date}'
                        ORDER BY tu.id DESC
                    '''.format(id=u1.id, date = datetime.datetime.now())
                    cur.execute(sql_user)
                    user_rows = dictfetchall(cur)
                    
                    return JsonResponse({'result': 200, 'common_notice': common_rows, 'user_notice': user_rows})
        except BaseException as err:
            print('ERROR -> err : ', err)
            return JsonResponse({'result': 500})
    else:
        try:
            with transaction.atomic():
                # 로그인 실패
                u1.login_ip = login_ip
                u2.attempt = u2.attempt + 1
                u2.login_date = datetime.datetime.now()
                u1.save()
                u2.save()
                return JsonResponse({'result': 600})
        except BaseException as err:
            print('ERROR -> err : ', err)
            return JsonResponse({'result': 500})


# VPN 시작 API (2019.09.09 15:23 점검완료)
@csrf_exempt
def app_start_vpn(request):
    if 'id' in request.session:
        id = request.session['email']

        client_type = request.META['HTTP_USER_AGENT'].split('/')[0]
        print('client_type -----> ',client_type)

        # VPN 클라이언트 매핑 저장 (기기 종류 추적용 — 매 VPN 시작마다 기록)
        try:
            vpn_client_ip = get_client_ip(request)
            ua_full = request.META.get('HTTP_USER_AGENT', '')
            # device_type 판별
            ua_lower = ua_full.lower()
            if 'android' in ua_lower or 'dalvik' in ua_lower:
                vpn_device_type = 'Android'
            elif 'ios' in ua_lower or 'iphone' in ua_lower or 'ipad' in ua_lower or 'titanvpn' in ua_lower:
                vpn_device_type = 'iOS'
            elif 'windows' in ua_lower or 'restsharp' in ua_lower:
                vpn_device_type = 'Windows'
            elif 'mac' in ua_lower:
                vpn_device_type = 'macOS'
            else:
                vpn_device_type = client_type
            # app_version 추출
            import re as _re
            _av_match = _re.search(r'/([\d.]+)', ua_full)
            vpn_app_version = _av_match.group(1) if _av_match else ''
            with connections['default'].cursor() as map_cur:
                map_cur.execute("""
                    INSERT INTO tbl_vpn_client_map
                        (email, device_type, device_os, app_version, client_ip, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, [id, vpn_device_type, ua_full[:500], vpn_app_version, vpn_client_ip])
        except Exception as e:
            print('WARN -> vpn_client_map save failed:', e)

        # get regist_rec
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT regist_rec 
                FROM   titan.tbl_user 
                WHERE  email = '{id}' 
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            for row in rows:
                regist_rec = row['regist_rec']


        # radius 기본정보 획득
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT username
                        ,attribute
                        ,op
                        ,value
                FROM   radius.radcheck
                WHERE  username = '{id}'
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            username = rows[0]['username']
            for row in rows:
                # VPN 세션 수
                if row["attribute"] == "Simultaneous-Use":
                    simultaneous_use = row["value"]

                # VPN 접속 비밀번호
                if row["attribute"] == "Cleartext-Password":
                    password = row["value"]

                # VPN 접속 만료기한
                if row["attribute"] == "Expiration":
                    expiration  = row["value"]

            # VPN 사용기한 확인
            try:
                date = datetime.datetime.strptime(expiration, "%d %b %Y %H:%M:%S %Z")
                now = datetime.datetime.now()
                if date < now:
                    print('INFO -> The period of use has expired')
                    return JsonResponse({'result': 300})
            except BaseException as err:
                print('ERROR -> err : ', err)
                return JsonResponse({'result': 300})

            # radius 사용자 수 체크
            sql = '''
                SELECT  radacctid,
                        acctsessionid, 
                        nasportid, 
                        nasipaddress,
			nasporttype
                FROM   radius.radacct 
                WHERE  acctstoptime IS NULL 
                AND username = '{id}'
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            print (simultaneous_use)
            
            if len(rows) >= int(simultaneous_use) :
                sessionid = rows[0]['acctsessionid']
                nasportid = rows[0]['nasportid']
                nasipaddress = rows[0]['nasipaddress']
                nasporttype = rows[0]['nasporttype']

                # 서버 접속정보 가져오기
                sql = '''
                    SELECT username,password FROM titan.tbl_agent WHERE hostip='{ip}';
                '''.format(ip=nasipaddress)
                cur.execute(sql)
                ssh_info_rows = dictfetchall(cur)

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    # timeout 1초
                    ssh.connect(nasipaddress,
                                username=ssh_info_rows[0]['username'],
                                password=ssh_info_rows[0]['password'],
                                timeout = 1)
	            
                    if nasporttype == 'ISDN' : # openvpn
                        channel = ssh.invoke_shell()
                        channel.send("telnet 127.0.0.1 1199\n")
                        time.sleep(1.0)
                        channel.send("mykakao9898\n")
                        time.sleep(0.5)
                        command = 'kill '+id+'\n'
                        channel.send(command)
                        time.sleep(0.5)
                        channel.send("exit\n")
                        time.sleep(0.5)
                        channel.send("exit\n")
                        time.sleep(0.5)
                        output = channel.recv(65535).decode("utf-8")
                        print(output)
                    elif nasportid == '443' : # softether sstp
                        sessionid = sessionid.replace('=5BSSTP=5D','[SSTP]')
                        command = "/usr/local/vpnserver/vpncmd "+nasipaddress+" /SERVER /HUB:"+settings.SOFTETHER_HUB+" /PASSWORD:'"+settings.SOFTETHER_PASS+"' /CMD SessionDisconnect "+sessionid
                        print('cmd => ',command)
                        ssh.exec_command(command)
                    else :
                        # IKEv2 (strongSwan) safe disconnect
                        strongswan_down_nb_safely(ssh, id)
                except socket.timeout:
                    #timeout 걸렸을때 radius 강제 업데이트
                    sql = '''
                        UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                        COMMIT;
                    '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                    cur.execute(sql)
                except BaseException as err:
                    print('ERROR -> err : ', err)
                    return JsonResponse({'result': 600})
                    
                finally:
                    ssh.close()
                    
            

            # VPN Agent 매칭
            sql = '''
                SELECT t2.count,
                       t1.hostdomain
                FROM   titan.tbl_agent t1,
                       (SELECT t1.hostip,
                               Count(t2.nasipaddress) AS count
                        FROM   titan.tbl_agent t1
                               LEFT JOIN (SELECT *
                                          FROM   radius.radacct
                                          WHERE  acctstoptime IS NULL
                                          ) t2
                                      ON t1.hostip = t2.nasipaddress
                        WHERE  is_active
                                OR is_active = 1
                                   AND is_status = 1
                        GROUP  BY t1.hostip)t2
                WHERE  t1.hostip = t2.hostip and t1.telecom = 'KT'
                ORDER  BY t2.count
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            if len(rows) == 0:
                print('INFO -> Agent does not exist')
                return JsonResponse({'result': 700})
            else:
                host_name = rows[0]['hostdomain']

                #if regist_rec.lower() == 'kok'.lower() :
                #    host_name = 'dt35.a301469t.com'

                res = {
                    'result' : 200,
                    'vpn_hostname' : host_name,
                    'vpn_username' : username,
                    'vpn_password' : password
                }
            return JsonResponse(res)
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_server_list(request):
    if 'id' in request.session:
        id = request.session['email']
        with connections['default'].cursor() as cur:
                sql = '''
                SELECT
                        name,
                        hostdomain,
                        hostip,
                        is_active,
                        is_status,
                        country,
                        pd_name,
                        telecom,
                        protocol
                    FROM titan.tbl_agent
                    order by is_active desc ,is_status desc, telecom, RAND();
                '''
                cur.execute(sql)
                rows = dictfetchall(cur)
                return JsonResponse({'result' : 200 , 'data' : rows})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})
        
@csrf_exempt
def app_new_server_list(request):
    if 'id' in request.session:
        id = request.session['email']
        with connections['default'].cursor() as cur:
                # Check subscription expiration first
                try:
                    cur.execute("SELECT value FROM radius.radcheck WHERE username = %s AND attribute = 'Expiration' LIMIT 1", [id])
                    _exp_row = cur.fetchone()
                    if _exp_row:
                        _exp_date = datetime.datetime.strptime(_exp_row[0], '%d %b %Y %H:%M:%S %Z')
                        if _exp_date < datetime.datetime.now():
                            print('INFO -> app_new_server_list: expired user blocked:', id)
                            return JsonResponse({'result': 300})
                    else:
                        print('INFO -> app_new_server_list: no expiration record:', id)
                        return JsonResponse({'result': 300})
                except Exception as _exp_err:
                    print('WARN -> app_new_server_list expiration check fail:', _exp_err)
                    return JsonResponse({'result': 300})

                # Server list cache (30s TTL) — DB query is shared across all users
                _now = time.time()
                if _SERVER_LIST_CACHE['rows'] is not None and (_now - _SERVER_LIST_CACHE['ts']) < _SERVER_LIST_CACHE_TTL:
                    rows = _copy.deepcopy(_SERVER_LIST_CACHE['rows'])
                else:
                    sql = '''                    
                        SELECT
                        	t1.id, 
                        	t1.name,
                            t1.hostdomain,
                            t1.hostip,
                            t1.v2_port,
                            t1.is_active,
                            t1.is_status,
                            t1.is_auto,
                            t1.country,
                            t1.pd_name,
                            t1.telecom,
                            t1.protocol,
                            t1.config,
                            t1.v2_config
                        FROM   titan.tbl_agent3 t1,
                            (SELECT t1.hostip,
                                    Count(t2.nasipaddress) AS count
                                FROM   titan.tbl_agent3 t1
                                    LEFT JOIN (SELECT *
                                                FROM   radius.radacct
                                                WHERE  acctstoptime IS NULL
                                                ) t2
                                            ON t1.hostip = t2.nasipaddress
                                WHERE  is_active
                                        OR is_active = 1
                                        AND is_status = 1
                                GROUP  BY t1.hostip)t2
                        WHERE t1.hostip = t2.hostip AND t1.is_active = 1
                        ORDER BY t1.country = 'KR' desc, t2.count, t1.is_auto desc
                    '''
                    cur.execute(sql)
                    rows = dictfetchall(cur)
                    _SERVER_LIST_CACHE['rows'] = _copy.deepcopy(rows)
                    _SERVER_LIST_CACHE['ts'] = _now

                # Per-user V2RAY UUID: use personal UUID only if deployed to servers
                # New users (v2ray_deployed=0) use tbl_agent3.v2_config (shared UUID)
                try:
                    cur.execute("SELECT v2ray_uuid, v2ray_deployed FROM tbl_user WHERE email = %s AND v2ray_uuid IS NOT NULL LIMIT 1", [id])
                    _uuid_row = cur.fetchone()
                    if _uuid_row and _uuid_row[0] and _uuid_row[1] == 1:
                        _user_v2uuid = _uuid_row[0]
                        for row in rows:
                            row['v2_config'] = _user_v2uuid
                    # else: v2ray_deployed=0, keep tbl_agent3.v2_config (shared UUID)
                except Exception as _uuid_err:
                    print('WARN -> v2ray_uuid lookup fail:', _uuid_err)

                return JsonResponse({'result' : 200 , 'data' : rows})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_check_server(request):
    if 'id' in request.session:
        id = request.session['email']
        server_name = request.POST.get('server_name')

        with connections['default'].cursor() as cur:
            # radius 기본정보 획득 만료일, 패스워드, 세션등
                sql = '''
                    SELECT username
                            ,attribute
                            ,op
                            ,value
                    FROM   radius.radcheck
                    WHERE  username = '{id}'
                '''.format(id=id)
                cur.execute(sql)
                rows = dictfetchall(cur)
                username = rows[0]['username']
                for row in rows:
                    # VPN 세션 수
                    if row["attribute"] == "Simultaneous-Use":
                        simultaneous_use = row["value"]

                    # VPN 접속 비밀번호
                    if row["attribute"] == "Cleartext-Password":
                        password = row["value"]

                    # VPN 접속 만료기한
                    if row["attribute"] == "Expiration":
                        expiration  = row["value"]

                # VPN 사용기한 확인
                try:
                    date = datetime.datetime.strptime(expiration, "%d %b %Y %H:%M:%S %Z")
                    now = datetime.datetime.now()
                    if date < now:
                        print('INFO -> The period of use has expired:' + id)
                        return JsonResponse({'result': 300})
                except BaseException as err:
                    print('ERROR -> err : ' + id, err)
                    return JsonResponse({'result': 300})

                # radius 사용자 수 체크(동접세션수)
                sql = '''
                    SELECT acctsessionid, 
                            nasportid, 
                            nasipaddress,
			    nasporttype
                    FROM   radius.radacct 
                    WHERE  acctstoptime IS NULL 
                    AND username = '{id}'
                '''.format(id=id)
                cur.execute(sql)
                rows = dictfetchall(cur)
                print('INFO old app ->' + id + ' 의' + 'NULL 줄수 :'+ str(len(rows)) + ' 동시접속 설정수 :' + simultaneous_use)
                if len(rows) >= int(simultaneous_use) :
                    sessionid = rows[0]['acctsessionid']
                    nasportid = rows[0]['nasportid']
                    nasipaddress = rows[0]['nasipaddress']
                    nasporttype = rows[0]['nasporttype']

                    # 서버 접속정보 가져오기
                    sql = '''
                        SELECT username,password FROM titan.tbl_agent3 WHERE hostip='{ip}';
                    '''.format(ip=nasipaddress)
                    cur.execute(sql)
                    ssh_info_rows = dictfetchall(cur)

                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    try:
                        # timeout 1초
                        ssh.connect(nasipaddress,
                                    username=ssh_info_rows[0]['username'],
                                    password=ssh_info_rows[0]['password'],
                                    timeout = 1)

                    
                        if nasporttype == 'ISDN' : # openvpn
                            channel = ssh.invoke_shell()
                            channel.send("telnet 127.0.0.1 1199\n")
                            time.sleep(0.5)
                            channel.send("mykakao9898\n")
                            time.sleep(0.2)
                            command = 'kill '+id+'\n'
                            channel.send(command)
                            time.sleep(0.2)
                            channel.send("exit\n")
                            time.sleep(0.2)
                            channel.send("exit\n")
                            time.sleep(0.2)
                            output = channel.recv(65535).decode("utf-8")
                            print(output)
                        elif nasportid == '443' : # softether sstp
                            sessionid = sessionid.replace('=5BSSTP=5D','[SSTP]')
                            command = "/usr/local/vpnserver/vpncmd "+nasipaddress+" /SERVER /HUB:"+settings.SOFTETHER_HUB+" /PASSWORD:'"+settings.SOFTETHER_PASS+"' /CMD SessionDisconnect "+sessionid
                            print('cmd => ',command)
                            ssh.exec_command(command)
                        else :
                            # IKEv2 (strongSwan) safe disconnect
                            strongswan_down_nb_safely(ssh, id)
                    except socket.timeout:
                        #timeout 걸렸을때 radius 강제 업데이트
                        sql = '''
                            UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                            COMMIT;
                        '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                        cur.execute(sql)
                    except BaseException as err:
                        sql = '''
                            UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                            COMMIT;
                        '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                        cur.execute(sql)
                        print('ERROR -> err : ' + id, err)
                    finally:
                        ssh.close()
                
                # VPN Agent 매칭
                sql = '''
                    SELECT t2.count,
                        t1.hostdomain,
                        t1.name,
                        t1.country
                    FROM   titan.tbl_agent t1,
                        (SELECT t1.hostip,
                                Count(t2.nasipaddress) AS count
                            FROM   titan.tbl_agent t1
                                LEFT JOIN (SELECT *
                                            FROM   radius.radacct
                                            WHERE  acctstoptime IS NULL
                                            ) t2
                                        ON t1.hostip = t2.nasipaddress
                            WHERE  is_active
                                    OR is_active = 1
                                    AND is_status = 1
                            GROUP  BY t1.hostip)t2
                    WHERE  t1.hostip = t2.hostip AND t1.telecom = 'KT'
                    ORDER  BY t2.count
                '''
                cur.execute(sql)
                rows = dictfetchall(cur)
                if len(rows) == 0:
                    print('INFO -> Agent does not exist:' + id)
                    return JsonResponse({'result': 700})
                else:
                    host_name = rows[0]['hostdomain']
                    vpn_server_name = rows[0]['name']
                    vpn_server_country = rows[0]['country']

                    sql = '''
                    SELECT
                            name,
                            hostdomain,
                            hostip,
                            is_active,
                            is_status,
                            country,
                            pd_name,
                            telecom,
			    protocol
                        FROM titan.tbl_agent
                        WHERE hostdomain = '{server_name}'
                        LIMIT 1;
                    '''.format(server_name = server_name)
                    cur.execute(sql)
                    rows = dictfetchall(cur)


                    if len(rows) <= 0 :
                        return JsonResponse({'result' : 200 , 
                                            'vpn_smart_match_hostname' : host_name,
                                            'vpn_smart_match_name' : vpn_server_name,
                                            'vpn_smart_match_country' : vpn_server_country,
                                            'vpn_username' : username,
                                            'vpn_password' : password})
                    
                    is_active = rows[0]['is_active']
                    is_status = rows[0]['is_status']

                    if is_active == 1 and is_status == 1 :
                        return JsonResponse({'result' : 1001 , 
                                            'vpn_smart_match_hostname' : rows[0]['hostdomain'],
                                            'vpn_smart_match_name' : rows[0]['name'],
                                            'vpn_smart_match_country' : rows[0]['country'],
                                            'vpn_username' : username,
                                            'vpn_password' : password}) # 정상
                    else :
                        return JsonResponse({'result' : 1002 ,
                                            'vpn_smart_match_hostname' : host_name,
                                            'vpn_smart_match_name' : vpn_server_name,
                                            'vpn_smart_match_country' : vpn_server_country,
                                            'vpn_username' : username,
                                            'vpn_password' : password})# 점검중

#2023-08-10 Fixed By Zhao
@csrf_exempt
def app_new_check_server(request):
    if 'id' in request.session:
        _t0 = time.monotonic()
        def _log_elapsed(stage):
            try:
                elapsed_ms = int((time.monotonic() - _t0) * 1000)
                print('INFO -> app_new_check_server elapsed(ms):', elapsed_ms, 'stage:', stage)
            except Exception:
                pass
        id = request.session['email']
        server_name = request.POST.get('server_name') # Server Domain
        # Prefer explicit server_protocol; fallback to generic 'protocol' if client uses that key
        server_protocol = request.POST.get('server_protocol') or request.POST.get('protocol')
        name = request.POST.get('name')               # Server Name
        failed_server = request.POST.get('failed_server_name')
        login_ip = get_client_ip(request)
        optimize_server = request.POST.get('optimize_server') # Deprecated: previously client ping result

        if server_protocol == None:
            server_protocol = ''
        if failed_server == None:
            failed_server = ''
        if name == None:
            name = ''
        # Deprecated: ignore optimize_server completely
        optimize_server = ''

        telecom_hint, telecom_org = detect_cn_telecom(login_ip)
        if telecom_org:
            _log_telecom_org_once(telecom_org)
        if telecom_hint:
            print('INFO -> telecom hint : ', telecom_hint)
        # Fallback: if GeoIP2 is unavailable or inconclusive, use last stored ISP from TblDeviceInfo
        if not telecom_hint:
            try:
                with connections['default'].cursor() as _cur2:
                    _sql_isp = '''
                        SELECT device_isp
                        FROM titan.tbl_device_info
                        WHERE device_ip = '{login_ip}'
                        ORDER BY login_time DESC
                        LIMIT 1
                    '''.format(login_ip=_escape_sql_literal(login_ip))
                    _cur2.execute(_sql_isp)
                    _rows_isp = dictfetchall(_cur2)
                    if _rows_isp:
                        _isp = _rows_isp[0]['device_isp'] or ''
                        telecom_hint = _match_cn_telecom_hint(_isp)
                        if telecom_hint:
                            print('INFO -> ISP fallback telecom hint : ', telecom_hint)
            except Exception as _isp_err:
                # Non-fatal: proceed without telecom hint
                pass
        # Per-user V2RAY UUID: fetch once at start (only if deployed to servers)
        _user_v2uuid = None
        try:
            with connections['default'].cursor() as _cur_uuid:
                _cur_uuid.execute("SELECT v2ray_uuid, v2ray_deployed FROM tbl_user WHERE email = %s AND v2ray_uuid IS NOT NULL LIMIT 1", [id])
                _uuid_row = _cur_uuid.fetchone()
                if _uuid_row and _uuid_row[0] and _uuid_row[1] == 1:
                    _user_v2uuid = _uuid_row[0]
                # else: v2ray_deployed=0, keep shared UUID from tbl_agent3
        except Exception as _uuid_err:
            print('WARN -> v2ray_uuid lookup fail:', _uuid_err)

        with connections['default'].cursor() as cur:
            # radius 기본정보 획득
                sql = '''
                    SELECT username
                            ,attribute
                            ,op
                            ,value
                    FROM   radius.radcheck
                    WHERE  username = '{id}'
                '''.format(id=id)
                cur.execute(sql)
                rows = dictfetchall(cur)
                username = rows[0]['username']
                for row in rows:
                    # VPN 세션 수
                    if row["attribute"] == "Simultaneous-Use":
                        simultaneous_use = row["value"]

                    # VPN 접속 비밀번호
                    if row["attribute"] == "Cleartext-Password":
                        password = row["value"]

                    # VPN 접속 만료기한
                    if row["attribute"] == "Expiration":
                        expiration  = row["value"]

                _log_elapsed('t1_radcheck')

                # VPN 사용기한 확인
                try:
                    date = datetime.datetime.strptime(expiration, "%d %b %Y %H:%M:%S %Z")
                    now = datetime.datetime.now()
                    if date < now:
                        print('INFO -> The period of use has expired:' + id)
                        return JsonResponse({'result': 300})
                except BaseException as err:
                    print('ERROR -> err : ' + id, err)
                    return JsonResponse({'result': 300})

                # radius 사용자 수 체크
                sql = '''
                    SELECT acctsessionid, 
                            nasportid, 
                            nasipaddress,
                            nasporttype,
                            radacctid,
                            callingstationid
                    FROM   radius.radacct 
                    WHERE  acctstoptime IS NULL 
                    AND username = '{id}'
                    ORDER BY radacctid
                '''.format(id=id)
                cur.execute(sql)
                rows = dictfetchall(cur)
                print('INFO ->' + id + ' 의' + 'NULL 줄수 :'+ str(len(rows)) + ' 동시접속 설정수 :' + simultaneous_use)
                _log_elapsed('t2_radacct')
                if len(rows) >= int(simultaneous_use) :
                    _forced_done = False
                    sessionid = rows[0]['acctsessionid']
                    nasportid = rows[0]['nasportid']
                    nasipaddress = rows[0]['nasipaddress']
                    nasporttype = rows[0]['nasporttype']
                    callingstationid = rows[0]['callingstationid'].split('=')[0]
                    print('INFO ->' + str(len(rows)) + ' 의 강제종료스타트 ' + simultaneous_use)
                    # 서버 접속정보 가져오기
                    sql = '''
                        SELECT username,password,name,telecom FROM titan.tbl_agent3 WHERE hostip='{ip}';
                    '''.format(ip=nasipaddress)
                    cur.execute(sql)
                    ssh_info_rows = dictfetchall(cur)
                    _nas_name = ssh_info_rows[0].get('name', '') if ssh_info_rows else ''
                    _nas_telecom = ssh_info_rows[0].get('telecom', '') if ssh_info_rows else ''
                    if not ssh_info_rows:
                        # Reverted to ERROR so monitor catches missing credentials (operationally important)
                        print('ERROR -> SSH credentials not found for hostip:', nasipaddress)
                        # radius 레코드 정리만 하고 종료
                        cleanup_sql = '''
                            UPDATE radius.radacct SET acctstoptime = '{date}' WHERE radacctid = {radacctid};
                            COMMIT;
                        '''.format(date = datetime.datetime.now(), radacctid = rows[0]['radacctid'])
                        cur.execute(cleanup_sql)
                        _forced_done = True
                        # 다음 단계 계속 (서버 선택 로직) 진행
                    else:
                        # Determine protocol
                        if nasporttype == 'ISDN':
                            _kick_protocol = 'OPENVPN'
                        elif nasportid == '443':
                            _kick_protocol = 'SSTP'
                        elif nasporttype == 'V2RAY':
                            _kick_protocol = 'V2RAY'
                        else:
                            _kick_protocol = 'IKEV2'

                        # Immediately update radacct (sync) — server selection sees correct conn count
                        sql = '''
                            UPDATE radius.radacct SET acctstoptime = '{date}' WHERE radacctid = {radacctid};
                            COMMIT;
                        '''.format(date=datetime.datetime.now(), radacctid=rows[0]['radacctid'])
                        cur.execute(sql)
                        _forced_done = True

                        # SSH kick + tbl_disconnection in background thread
                        print('INFO -> SSH kick dispatch [bg]: ' + id + ' proto=' + _kick_protocol)
                        threading.Thread(
                            target=_bg_ssh_kick,
                            kwargs={
                                'nasipaddress': nasipaddress,
                                'ssh_user': ssh_info_rows[0]['username'],
                                'ssh_pass': ssh_info_rows[0]['password'],
                                'nasporttype': nasporttype,
                                'nasportid': nasportid,
                                'sessionid': sessionid,
                                'user_id': id,
                                'protocol': _kick_protocol,
                                'simultaneous_use': simultaneous_use,
                                'connected_count': len(rows),
                                'nas_name': _nas_name,
                                'nas_telecom': _nas_telecom,
                                'login_ip': login_ip,
                                'callingstationid': callingstationid,
                            },
                            daemon=True
                        ).start()
                        _log_elapsed('t3_disconnect_done')
                
                # ── VPN Agent 매칭 (실측 ping 기반) ──
                # telecom_hint: ct/cm/cu/None (중국 통신사 감지 결과)
                # failed_server: 이전 연결 실패 서버명 (앱에서 전달)
                MAX_CONN_PER_SERVER = 50  # 서버당 최대 접속자 수 제한

                if server_protocol == '':
                    _protocol_clause = "(t1.protocol LIKE '%IKEV2%' OR t1.protocol LIKE '%OPENVPN%' OR t1.protocol LIKE '%V2RAY%')"
                    _failed_clause = ''
                else:
                    _esc_proto = _escape_sql_literal(server_protocol or '')
                    _protocol_clause = f"t1.protocol LIKE '%{_esc_proto}%'"
                    _esc_failed = _escape_sql_literal(failed_server or '')
                    _failed_clause = f" AND t1.name != '{_esc_failed}'" if failed_server else ''

                def _fetch_ping_ranked(extra_where=''):
                    """실측 ping + 접속자수 가중치로 서버 순위 조회.
                    ping_score = ping_avg * 0.7 + conn_count * 0.3
                    telecom_hint가 있으면 해당 통신사 ping, 없으면 3통신사 평균."""
                    if telecom_hint and telecom_hint in ('ct', 'cm', 'cu'):
                        _tc_inner = f"AND cn_telecom = '{telecom_hint}'"
                        _tc_outer = f"AND p.cn_telecom = '{telecom_hint}'"
                    else:
                        _tc_inner = ""
                        _tc_outer = ""

                    sql = f"""
                        SELECT
                            t1.id, t1.hostdomain, t1.hostip, t1.name,
                            t1.country, t1.config, t1.v2_config, t1.v2_port,
                            t1.telecom AS kr_telecom,
                            COALESCE(conn.count, 0) AS conn_count,
                            COALESCE(ping.ping_avg, 999) AS ping_avg,
                            (COALESCE(ping.ping_avg, 999) * 0.7 + COALESCE(conn.count, 0) * 0.3) AS score
                        FROM titan.tbl_agent3 t1
                        /* 최신 ping 측정값 (서버별 통신사별 최신 1건) */
                        LEFT JOIN (
                            SELECT p.server_ip, p.ping_avg
                            FROM titan.tbl_server_telecom_ping p
                            INNER JOIN (
                                SELECT server_ip, {f"cn_telecom," if telecom_hint in ('ct','cm','cu') else ""} MAX(check_time) AS max_ct
                                FROM titan.tbl_server_telecom_ping
                                WHERE check_time > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                                {_tc_inner}
                                GROUP BY server_ip {f", cn_telecom" if telecom_hint in ('ct','cm','cu') else ""}
                            ) latest ON p.server_ip = latest.server_ip AND p.check_time = latest.max_ct
                            {_tc_outer}
                        ) ping ON t1.hostip = ping.server_ip
                        /* 현재 접속자 수 */
                        LEFT JOIN (
                            SELECT nasipaddress, COUNT(*) AS count
                            FROM radius.radacct
                            WHERE acctstoptime IS NULL
                            GROUP BY nasipaddress
                        ) conn ON t1.hostip = conn.nasipaddress
                        WHERE t1.is_active = 1 AND t1.is_status = 1 AND t1.is_auto = 1
                          AND {_protocol_clause}
                          {_failed_clause}
                          {extra_where}
                        HAVING conn_count < {MAX_CONN_PER_SERVER}
                        ORDER BY score ASC, RAND()
                    """
                    try:
                        cur.execute(sql)
                        return dictfetchall(cur)
                    except Exception as _e:
                        print('ERROR -> ping-ranked query fail:', _e)
                        return []

                selected_rows = None
                selected_method = None

                # 1차: 실측 ping 기반 전체 서버 순위
                rows = _fetch_ping_ranked()
                if rows:
                    selected_rows = rows
                    selected_method = f'ping_ranked(telecom={telecom_hint or "all"})'

                # 2차: 실패 서버가 있을 때 → 다른 한국 ISP 서버 우선 배정
                if failed_server and selected_rows:
                    # 실패 서버의 한국 ISP 확인
                    _failed_kr_telecom = None
                    try:
                        cur.execute(f"SELECT telecom FROM titan.tbl_agent3 WHERE name = '{_escape_sql_literal(failed_server)}' LIMIT 1")
                        _ftc = dictfetchall(cur)
                        if _ftc:
                            _failed_kr_telecom = _ftc[0]['telecom']
                    except Exception:
                        pass

                    if _failed_kr_telecom:
                        # 다른 한국 ISP 서버 중 가장 빠른 서버 재조회
                        _diff_isp = _fetch_ping_ranked(
                            extra_where=f" AND t1.telecom != '{_escape_sql_literal(_failed_kr_telecom)}'"
                        )
                        if _diff_isp:
                            selected_rows = _diff_isp
                            selected_method = f'failover_diff_isp(failed={failed_server},exclude={_failed_kr_telecom})'
                            print(f'INFO -> Failover: exclude ISP {_failed_kr_telecom}, selected {_diff_isp[0]["name"]}')

                # 3차: ping 데이터 없을 때 → is_auto=1 서버 중 접속자 적은 순
                if not selected_rows:
                    _legacy_sql = f'''
                        SELECT t1.id, COALESCE(conn.count,0) AS count,
                               t1.hostdomain, t1.hostip, t1.name,
                               t1.country, t1.config, t1.v2_config, t1.v2_port, t1.telecom AS kr_telecom
                        FROM titan.tbl_agent3 t1
                        LEFT JOIN (SELECT nasipaddress, COUNT(*) AS count
                                   FROM radius.radacct WHERE acctstoptime IS NULL
                                   GROUP BY nasipaddress) conn ON t1.hostip = conn.nasipaddress
                        WHERE t1.is_active = 1 AND t1.is_status = 1 AND t1.is_auto = 1
                          AND {_protocol_clause}{_failed_clause}
                        HAVING count < {MAX_CONN_PER_SERVER}
                        ORDER BY count ASC, RAND()
                    '''
                    try:
                        cur.execute(_legacy_sql)
                        _legacy_rows = dictfetchall(cur)
                        if _legacy_rows:
                            selected_rows = _legacy_rows
                            selected_method = 'legacy_auto(is_auto=1)'
                    except Exception:
                        pass

                # 4차: 최종 fallback — 아무 활성 서버
                if not selected_rows:
                    try:
                        _any_sql = f"""
                            SELECT t1.id, COALESCE(conn.count,0) AS count,
                                   t1.hostdomain, t1.hostip, t1.name, t1.country,
                                   t1.config, t1.v2_config, t1.v2_port, t1.telecom AS kr_telecom
                            FROM titan.tbl_agent3 t1
                            LEFT JOIN (SELECT nasipaddress, COUNT(*) AS count
                                       FROM radius.radacct WHERE acctstoptime IS NULL
                                       GROUP BY nasipaddress) conn ON t1.hostip = conn.nasipaddress
                            WHERE t1.is_active = 1 AND t1.is_status = 1 AND t1.is_auto = 1
                              AND {_protocol_clause}
                            HAVING count < {MAX_CONN_PER_SERVER}
                            ORDER BY count ASC, RAND()
                            LIMIT 1
                        """
                        cur.execute(_any_sql)
                        _any_rows = dictfetchall(cur)
                        if _any_rows:
                            selected_rows = _any_rows
                            selected_method = 'any_active_fallback'
                            print('INFO -> Final fallback any-active server for', id)
                        else:
                            print('INFO -> No server available for', id)
                            _log_elapsed('no_agent')
                            return JsonResponse({'result': 700})
                    except Exception as _any_err:
                        print('ERROR -> any-active fallback fail:', _any_err)
                        _log_elapsed('no_agent')
                        return JsonResponse({'result': 700})

                _log_elapsed('t4_auto_select')
                print(f'INFO -> Server selected: method={selected_method}, server={selected_rows[0].get("name","?")}, '
                      f'ping={selected_rows[0].get("ping_avg","?")}, conn={selected_rows[0].get("conn_count", selected_rows[0].get("count","?"))}')
                rows = selected_rows
                host_name = rows[0]['hostdomain']
                host_ip = rows[0]['hostip']
                vpn_server_name = rows[0]['name']
                vpn_server_country = rows[0]['country']
                vpn_server_config = rows[0]['config']
                vpn_server_v2config = rows[0]['v2_config']
                vpn_server_v2port = rows[0]['v2_port']
                vpn_server_id = rows[0]['id']

                # Per-user V2RAY UUID override
                if _user_v2uuid:
                    vpn_server_v2config = _user_v2uuid

                # Build check SQL only for explicit server selection from client (legacy <2.2.0 case)
                if name == '': # Under 2.2.0 version
                    sql = '''
                        SELECT
                            id,
                            name,
                            hostdomain,
                            hostip,
                            v2_port,
                            is_active,
                            is_status,
                            country,
                            pd_name,
                            telecom,
                            protocol,
                            config,
                            v2_config
                        FROM titan.tbl_agent3
                        WHERE hostdomain = '{server_name}'
                        LIMIT 1;
                    '''.format(server_name = server_name)
                else:
                    sql = '''
                        SELECT
                            id,
                            name,
                            hostdomain,
                            hostip,
                            v2_port,
                            is_active,
                            is_status,
                            country,
                            pd_name,
                            telecom,
                            protocol,
                            config,
                            v2_config
                        FROM titan.tbl_agent3
                        WHERE hostdomain = '{server_name}' AND name = '{name}'
                        LIMIT 1;
                    '''.format(server_name = server_name, name = name)
                cur.execute(sql)
                rows = dictfetchall(cur)

                # If explicit server lookup failed, treat smart match as active instead of fallback
                if len(rows) <= 0 :
                    _log_elapsed('active_smart')
                    return JsonResponse({'result' : 200 , 
                                         'vpn_smart_match_id' : vpn_server_id,
                                         'vpn_smart_match_hostname' : host_name,
                                         'vpn_smart_match_name' : vpn_server_name,
                                         'vpn_smart_match_ip' : host_ip,
                                         'vpn_smart_match_country' : vpn_server_country,
                                         'vpn_smart_match_config' : vpn_server_config,
                                         'vpn_smart_match_v2config' : vpn_server_v2config,
                                         'vpn_smart_match_v2port' : vpn_server_v2port,
                                         'vpn_username' : username,
                                         'vpn_password' : password})
                
                is_active = rows[0]['is_active']
                is_status = rows[0]['is_status']

                if is_active == 1 and is_status == 1 :
                    _log_elapsed('active')
                    return JsonResponse({'result' : 1001 , 
                                        'vpn_smart_match_id' : rows[0]['id'],
                                        'vpn_smart_match_hostname' : rows[0]['hostdomain'],
                                        'vpn_smart_match_ip' : rows[0]['hostip'],
                                        'vpn_smart_match_name' : rows[0]['name'],
                                        'vpn_smart_match_country' : rows[0]['country'],
                                        'vpn_smart_match_config' : rows[0]['config'],
                                        'vpn_smart_match_v2config' : _user_v2uuid or rows[0]['v2_config'],
                                        'vpn_smart_match_v2port' : rows[0]['v2_port'],
                                        'vpn_username' : username,
                                        'vpn_password' : password}) # 정상
                else :
                    _log_elapsed('inactive')
                    return JsonResponse({'result' : 1002 ,
                                        'vpn_smart_match_id' : rows[0]['id'],
                                        'vpn_smart_match_hostname' : host_name,
                                        'vpn_smart_match_ip' : host_ip,
                                        'vpn_smart_match_name' : vpn_server_name,
                                        'vpn_smart_match_country' : vpn_server_country,
                                        'vpn_smart_match_config' : vpn_server_config,
                                        'vpn_smart_match_v2config' : vpn_server_v2config,
                                        'vpn_smart_match_v2port' : vpn_server_v2port,
                                        'vpn_username' : username,
                                        'vpn_password' : password})# 점검중
    else :
         print('ERROR -> err : NO ID')
         return JsonResponse({'result': 500})

#2023-03-02 Added By Zhao
#2023-05-04 Fixed By Zhao
#2023-07-19 Fixed By Zhao
@csrf_exempt
def app_stable_server(request):
    if 'id' in request.session:
        _t0 = time.monotonic()
        def _elapsed(stage):
            try:
                print('INFO -> app_stable_server elapsed(ms):', int((time.monotonic() - _t0)*1000), 'stage:', stage)
            except Exception:
                pass
        print("===Called Stable Server Function===")
        email = request.session['email']

        # Per-user V2RAY UUID: fetch once (only if deployed to servers)
        _user_v2uuid = None
        try:
            with connections['default'].cursor() as _cur_uuid:
                _cur_uuid.execute("SELECT v2ray_uuid, v2ray_deployed FROM tbl_user WHERE email = %s AND v2ray_uuid IS NOT NULL LIMIT 1", [email])
                _uuid_row = _cur_uuid.fetchone()
                if _uuid_row and _uuid_row[0] and _uuid_row[1] == 1:
                    _user_v2uuid = _uuid_row[0]
                # else: v2ray_deployed=0, keep shared UUID from tbl_agent3
        except Exception:
            pass

        telecom = request.POST.get('telecom')
        server_name = request.POST.get('server_name')
        server_ip = request.POST.get('server_ip')
        protocol = request.POST.get('protocol')
        app_version = request.POST.get('app_version')
        platform = request.POST.get('platform')
        device = request.POST.get('device')
        
        login_ip = get_client_ip(request)

        # Hardened IP lookup (safe, non-fatal)
        response = safe_ip_api_lookup(login_ip)

        # Fetch user's allowed simultaneous sessions to record in disconnection logs
        simultaneous_use = '1'
        try:
            with connections['default'].cursor() as _cur_sim:
                _sql_sim = '''
                    SELECT value
                    FROM radius.radcheck
                    WHERE username = '{email}' AND attribute = 'Simultaneous-Use'
                    LIMIT 1
                '''.format(email=email)
                _cur_sim.execute(_sql_sim)
                _rows_sim = dictfetchall(_cur_sim)
                if _rows_sim:
                    simultaneous_use = str(_rows_sim[0]['value'])
        except Exception as _sim_err:
            print('WARN -> fetch Simultaneous-Use fail:', _sim_err)
        
        with connections['default'].cursor() as cur:
            # radius 기본정보 획득
                sql = '''
                    SELECT acctsessionid, 
                            nasportid, 
                            nasipaddress,
                            nasporttype,
                            radacctid,
                            callingstationid
                    FROM   radius.radacct 
                    WHERE  acctstoptime IS NULL 
                    AND ABS(TIMESTAMPDIFF(SECOND, acctstarttime, NOW())) <= 20
                    AND username = '{email}'
                    ORDER BY radacctid DESC
                '''.format(email=email)
                cur.execute(sql)
                rows = dictfetchall(cur)
                print('len:' + str(len(rows)))
                if len(rows) > 0 :
                    print('INFO -> called here>>>>>: ')
                    sessionid = rows[0]['acctsessionid']
                    nasportid = rows[0]['nasportid']
                    nasipaddress = rows[0]['nasipaddress']
                    nasporttype = rows[0]['nasporttype']
                    callingstationid = rows[0]['callingstationid'].split('=')[0]
                    print('INFO -> sessionid: ' + sessionid)
                    
                    # 서버 접속정보 가져오기
                    sql = '''
                        SELECT username,password,name,telecom FROM titan.tbl_agent3 WHERE hostip='{ip}';
                    '''.format(ip=nasipaddress)
                    cur.execute(sql)
                    ssh_info_rows = dictfetchall(cur)
                    _nas_name = ssh_info_rows[0].get('name', '') if ssh_info_rows else ''
                    _nas_telecom = ssh_info_rows[0].get('telecom', '') if ssh_info_rows else ''

                    if not ssh_info_rows:
                        print('ERROR -> SSH credentials not found for hostip:', nasipaddress)
                        # 아무 동작 없이 넘어감 (선택 로직만 계속)
                    else:
                        ssh = paramiko.SSHClient()
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        print('INFO -> SSH Open: ' + email)
                        try:
                            protocol = ''
                            # timeout 1초
                            ssh.connect(nasipaddress,
                                        username=ssh_info_rows[0]['username'],
                                        password=ssh_info_rows[0]['password'],
                                        timeout = 1)
                        			
                            if nasporttype == 'ISDN' : # openvpn
                                protocol = 'OPENVPN'
                                print('INFO -> Openvpn Server telnet login:' + email)
                                channel = ssh.invoke_shell()
                                channel.send("telnet 127.0.0.1 1199\n")
                                time.sleep(0.5)
                                channel.send("mykakao9898\n")
                                time.sleep(0.2)
                                command = 'kill '+email+'\n'
                                channel.send(command)
                                time.sleep(0.2)
                                channel.send("exit\n")
                                time.sleep(0.2)
                                channel.send("exit\n")
                                time.sleep(0.2)
                                output = channel.recv(65535).decode("utf-8")
                                print(output)
                            elif nasportid == '443' : # softether sstp
                                protocol = 'SSTP'
                                print('INFO -> SSTP Force Stop:' + email)
                                sessionid = sessionid.replace('=5BSSTP=5D','[SSTP]')
                                command = "/usr/local/vpnserver/vpncmd "+nasipaddress+" /SERVER /HUB:"+settings.SOFTETHER_HUB+" /PASSWORD:'"+settings.SOFTETHER_PASS+"' /CMD SessionDisconnect "+sessionid
                                print('cmd => ',command)
                                ssh.exec_command(command)
                            elif nasporttype == 'V2RAY' : # V2RAY
                                protocol = 'V2RAY'
                                print("No Action")
                            else :
                                protocol = 'IKEV2'
                                print('INFO -> IKEV2 Force Stop:' + email)
                                strongswan_down_nb_safely(ssh, email)

                            # 강제 종료 후 레코드 업데이트/로그 적재
                            sql = '''
                                UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                                COMMIT;
                            '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                            cur.execute(sql)
                            
                            sql = '''
                                INSERT INTO tbl_disconnection (username, user_session, connected_count, protocol, server_name, telecom, disconnected_time, new_ip, old_ip) 
                                VALUES('{email}', '{simultaneous_use}', '{connected_count}', '{protocol}', '{server_name}', '{telecom}', '{date}', '{login_ip}', '{callingstationid}');
                            '''.format(date = datetime.datetime.now() , email=email, connected_count = len(rows),protocol=protocol,server_name=_nas_name,telecom=_nas_telecom,simultaneous_use=simultaneous_use, login_ip=login_ip, callingstationid=callingstationid)
                            cur.execute(sql)
                        except socket.timeout:
                            #timeout 걸렸을때 radius 강제 업데이트
                            print('INFO -> socket.timeout' + email)
                            sql = '''
                            UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                            COMMIT;
                        '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                            cur.execute(sql)
                            
                            sql = '''
                            INSERT INTO tbl_disconnection (username, user_session, connected_count, protocol, server_name, telecom, disconnected_time, new_ip, old_ip) 
                            VALUES('{email}', '{simultaneous_use}', '{connected_count}', '{protocol}', '{server_name}', '{telecom}', '{date}', '{login_ip}', '{callingstationid}');
                        '''.format(date = datetime.datetime.now() , email=email, connected_count = len(rows),protocol=protocol,server_name=_nas_name,telecom=_nas_telecom,simultaneous_use=simultaneous_use, login_ip=login_ip, callingstationid=callingstationid)
                            cur.execute(sql)

                        except BaseException as err:
                            print('ERROR -> err : ' + email, err)
                            sql = '''
                                UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                                COMMIT;
                            '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                            cur.execute(sql)
                            
                            sql = '''
                                INSERT INTO tbl_disconnection (username, user_session, connected_count, protocol, server_name, telecom, disconnected_time, new_ip, old_ip) 
                                VALUES('{email}', '{simultaneous_use}', '{connected_count}', '{protocol}', '{server_name}', '{telecom}', '{date}', '{login_ip}', '{callingstationid}');
                            '''.format(date = datetime.datetime.now() , email=email, connected_count = len(rows),protocol=protocol,server_name=_nas_name,telecom=_nas_telecom,simultaneous_use=simultaneous_use, login_ip=login_ip, callingstationid=callingstationid)
                            cur.execute(sql)
                        finally:
                            try:
                                ssh.close()
                            except Exception:
                                pass
                        _elapsed('forced_disconnect_done')
        
        
        if platform != None:
            device_info = ''
            if device != None:
                device_info = device
            st = TblAgentFailed(
                username = email,
                server_name = server_name,
                server_domain = server_ip,
                server_protocol = protocol,
                platform = platform,
                app_version = app_version,
                user_ip = login_ip,
                user_location = (response.get('country') or '').replace('\'', '') + " " + (response.get('city') or '').replace('\'', ''),
                device_info = device_info,
                failed_time = datetime.datetime.now())
            st.save()
        
        # ── Smart Failover: 프로토콜 우선순위 기반 대체 서버 배정 ──
        # 실패 프로토콜에 따라 다음 프로토콜로 폴백:
        #   IKEV2 실패 → OPENVPN 서버 (ping 2순위)
        #   OPENVPN 실패 → V2RAY 서버
        #   V2RAY 실패 → 연결 불가
        _failed_proto = (protocol or '').upper().strip()
        if _failed_proto in ('IKEV2', 'SSTP', ''):
            _fallback_protos = ['OPENVPN', 'V2RAY']
        elif _failed_proto == 'OPENVPN':
            _fallback_protos = ['V2RAY']
        else:  # V2RAY or unknown
            _fallback_protos = []

        _exclude_server = _escape_sql_literal(server_name or '')
        _exclude_clause = f"AND t1.name != '{_exclude_server}'" if server_name else ''

        with connections['default'].cursor() as cur:
            for _fb_proto in _fallback_protos:
                _proto_clause = f"t1.protocol LIKE '%{_fb_proto}%'"

                _sql = f"""
                    SELECT
                        t1.id, t1.name, t1.hostdomain, t1.hostip,
                        t1.is_active, t1.is_status, t1.country, t1.pd_name,
                        t1.telecom, t1.protocol, t1.config,
                        t1.v2_config, t1.v2_port,
                        COALESCE(conn.cnt, 0) AS conn_count,
                        COALESCE(ping.ping_avg, 999) AS ping_avg
                    FROM titan.tbl_agent3 t1
                    LEFT JOIN (
                        SELECT p.server_ip, p.ping_avg
                        FROM titan.tbl_server_telecom_ping p
                        INNER JOIN (
                            SELECT server_ip, MAX(check_time) AS max_ct
                            FROM titan.tbl_server_telecom_ping
                            WHERE check_time > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                            GROUP BY server_ip
                        ) latest ON p.server_ip = latest.server_ip
                                AND p.check_time = latest.max_ct
                    ) ping ON t1.hostip = ping.server_ip
                    LEFT JOIN (
                        SELECT nasipaddress, COUNT(*) AS cnt
                        FROM radius.radacct
                        WHERE acctstoptime IS NULL
                        GROUP BY nasipaddress
                    ) conn ON t1.hostip = conn.nasipaddress
                    WHERE t1.is_active = 1 AND t1.is_status = 1 AND t1.is_auto = 1
                      AND {_proto_clause}
                      {_exclude_clause}
                    HAVING conn_count < 50
                    ORDER BY (COALESCE(ping.ping_avg, 999) * 0.7
                            + COALESCE(conn.cnt, 0) * 0.3) ASC
                    LIMIT 5
                """
                try:
                    cur.execute(_sql)
                    rows = dictfetchall(cur)
                    if rows:
                        _elapsed(f'fallback_{_fb_proto}')
                        print(f'INFO -> stable_server fallback: failed_proto={_failed_proto}, '
                              f'try={_fb_proto}, server={rows[0]["name"]}, '
                              f'ping={rows[0].get("ping_avg","?")}, '
                              f'conn={rows[0].get("conn_count","?")}')
                        # Per-user V2RAY UUID override
                        if _user_v2uuid:
                            for _r in rows:
                                _r['v2_config'] = _user_v2uuid
                        return JsonResponse({'result': 200, 'data': rows})
                except Exception as _e:
                    print(f'ERROR -> stable_server fallback query fail ({_fb_proto}):', _e)

            # 모든 폴백 실패
            _elapsed('no_fallback')
            print(f'INFO -> stable_server: no fallback available. failed_proto={_failed_proto}, user={email}')
            return JsonResponse({'result': 300})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

#2023-06-16 Fixed By Zhao
@csrf_exempt
def app_report_failed_server(request):
    if 'id' in request.session:
        email = request.session['email']
        telecom = request.POST.get('telecom')
        server_name = request.POST.get('server_name')
        server_ip = request.POST.get('server_ip')
        protocol = request.POST.get('protocol')
        app_version = request.POST.get('app_version')
        platform = request.POST.get('platform')
        device = request.POST.get('device')
        login_ip = get_client_ip(request)
        response = safe_ip_api_lookup(login_ip)
        device_info = ''
        if device != None:
            device_info = device
        st = TblAgentFailed(
            username = email,
            server_name = server_name,
            server_domain = server_ip,
            server_protocol = protocol,
            platform = platform,
            app_version = app_version,
            user_ip = login_ip,
            user_location = (response.get('country') or '').replace('\'', '') + " " + (response.get('city') or '').replace('\'', ''),
            device_info = device_info,
            failed_time = datetime.datetime.now())
        st.save()
        return JsonResponse({'result' : 200 }) # 정상
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})
        
@csrf_exempt
def app_disconnect(request):
    if 'id' in request.session:
        id = request.session['email']
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT  radacctid,
                        acctsessionid, 
                        nasportid, 
                        nasipaddress
                FROM   radius.radacct 
                WHERE nasporttype = 'ISDN' AND acctstoptime IS NULL 
                AND username = '{id}' ORDER BY radacctid DESC
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            
            if len(rows) > 0 :
                sql = '''
                    UPDATE radius.radacct set acctstoptime = '{date}' where radacctid = {radacctid};
                    COMMIT;
                '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                cur.execute(sql)
                return JsonResponse({'result': 200})
            else :
                return JsonResponse({'result': 200})
                
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_check_connection(request):
    if 'id' in request.session:
        print('INFO -> Check V2ray Connection')
        id = request.session['email']
        acctuniqueid = request.POST.get('acctuniqueid')
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT  radacctid,
                        acctsessionid, 
                        nasportid, 
                        nasipaddress
                FROM   radius.radacct 
                WHERE nasporttype = 'V2RAY' AND acctstoptime IS NULL 
                AND username = '{id}' AND acctuniqueid = '{acctuniqueid}'
            '''.format(id=id, acctuniqueid = acctuniqueid)
            cur.execute(sql)
            rows = dictfetchall(cur)
            if len(rows) > 0 :
                return JsonResponse({'result': 200})
            else :
                return JsonResponse({'result': 300})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_add_connection(request):
    if 'id' in request.session:
        print('INFO -> Add V2ray Connection')
        id = request.session['email']
        login_ip = get_client_ip(request)
        server_ip = request.POST.get('server_ip')
        uniqueid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        with connections['default'].cursor() as cur:
            # V2RAY device count check: count active V2RAY sessions for this user
            cur.execute('''
                SELECT COUNT(*) AS cnt FROM radius.radacct
                WHERE nasporttype = 'V2RAY' AND acctstoptime IS NULL AND username = %s
            ''', [id])
            _v2_count = cur.fetchone()[0] or 0

            # Get allowed simultaneous sessions
            _max_sessions = 1
            try:
                cur.execute('''
                    SELECT value FROM radius.radcheck
                    WHERE username = %s AND attribute = 'Simultaneous-Use' LIMIT 1
                ''', [id])
                _sim_row = cur.fetchone()
                if _sim_row:
                    _max_sessions = int(_sim_row[0])
            except Exception:
                pass

            if _v2_count >= _max_sessions:
                print(f'INFO -> V2RAY device limit reached: {id} has {_v2_count}/{_max_sessions} active sessions')
                return JsonResponse({'result': 600, 'message': 'Device limit reached'})

            sql = '''
                INSERT INTO radius.radacct (acctuniqueid, username, nasporttype, acctstarttime, nasipaddress, callingstationid, calledstationid) 
                VALUES('{uniqueid}', '{id}', 'V2RAY', '{date}', '{server_ip}', '{login_ip}', '{server_ip}');
            '''.format(date = datetime.datetime.now() , id=id, uniqueid = uniqueid,server_ip=server_ip,login_ip=login_ip)
            cur.execute(sql)
            return JsonResponse({'result': 200, 'acctuniqueid':uniqueid})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_disconnect_v2ray(request):
    if 'id' in request.session:
        id = request.session['email']
        acctuniqueid = request.POST.get('acctuniqueid')
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT  radacctid
                FROM   radius.radacct 
                WHERE nasporttype = 'V2RAY' AND acctstoptime IS NULL 
                AND username = '{id}' ORDER BY radacctid DESC
            '''.format(id=id)
            cur.execute(sql)
            rows = dictfetchall(cur)
            if acctuniqueid == None:
                if len(rows) > 0 :
                    sql = '''
                        UPDATE radius.radacct set acctstoptime = '{date}',
                        acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, '{date}')
                        where radacctid = {radacctid};
                        COMMIT;
                    '''.format(date = datetime.datetime.now() , radacctid = rows[0]['radacctid'])
                    cur.execute(sql)
                    return JsonResponse({'result': 200})
                else :
                    return JsonResponse({'result': 300})
            else :
                sql = '''
                    UPDATE radius.radacct set acctstoptime = '{date}',
                    acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, '{date}')
                    where acctuniqueid = '{acctuniqueid}';
                    COMMIT;
                '''.format(date = datetime.datetime.now() , acctuniqueid = acctuniqueid)
                cur.execute(sql)
                return JsonResponse({'result': 200})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})
        
@csrf_exempt
def app_delete_user(request):
    if 'id' in request.session:
        change_reason = 'iOS'
        user_id = request.session['id']
        user = TblUser.objects.get(id = user_id)
        # 이메일
        email = request.session['email']
        # 이메일(삭제)
        delete_email = 'delete__' + user.email + '#' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # racheck 처리
        Radcheck.objects.using('radius').filter(username=email).update(username=delete_email)
        # tbl_user 처리
        user.email = delete_email
        user.delete_yn = 'Y'
        user.save()
        # 내역 기록
        st = TblServiceTime(
            user_id = user_id,
            prev_time = '',
            prev_time_rad = '',
            after_time = '',
            after_time_rad = '',
            diff = '회원탈퇴',
            reason = change_reason,
            regist_date = datetime.datetime.now())
        st.save()
        return JsonResponse({'result': 200})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

@csrf_exempt
def app_purchase_product(request):
    # 유저객체 획득
    if 'id' in request.session:
        user_id = request.session['id']
        session = request.POST.get('session')
        price = request.POST.get('price')
        tid = request.POST.get('transaction')
        month_type = request.POST.get('month_type')
        if "-" in tid:
            return JsonResponse({'result': 300})
        # check double records
        with connections['default'].cursor() as cur:
            sql = '''
                SELECT  tid,
                        user_id
                FROM  tbl_price_history
                WHERE tid = '{tid}' AND session = '{session}' AND month_type = '{month_type}' AND pgcode= 'apple'
                AND user_id = '{id}'
            '''.format(id=user_id, tid=tid, month_type=month_type, session=session)
            print(sql)
            cur.execute(sql)
            rows = dictfetchall(cur)
            
            if len(rows) > 0 :
                return JsonResponse({'result': 300})
                
        # 요금 충전
        giveServiceTime(user_id, session, month_type)
        
        product_name = makeProductName(session, month_type)
        # 결제 내역 데이터베이스 기록 (해외)
        tph = TblPriceHistory(
            tid = tid,
            user_id = user_id,
            pgcode = 'apple',
            product_name = product_name,
            session = session,
            month_type = month_type,
            krw = None,
            usd = price,
            jpy = None,
            cny = None,
            taxfree_amount = None,
            tax_amount = None,
            autopay_flag = 'N',
            billkey = None,
            refund_yn = 'N',
            regist_date = datetime.datetime.now(),
            refund_date = None,
            auto_end_date = None
        )
        tph.save()
        
        u1 = TblUser.objects.get(id = user_id)
        email = u1.email
        rce = Radcheck.objects.using('radius').filter(
            username = email,
            attribute = 'Expiration'
        )
        
        radius_time = ''
        if len(rce) != 0:
            rceu = rce.first()
            radius_time = rceu.value
                
        return JsonResponse({'result': 200, 'expire_date': dec_radius_time(radius_time)})
    else:
        print('INFO -> Session is invalid')
        return JsonResponse({'result': 400})

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


@csrf_exempt
def app_health(request):
    """간단한 헬스체크: GeoIP2 로더 상태, 캐시 크기, 시간 반환"""
    reader_ok = GEOIP2_ASN_READER not in (None, False)
    return JsonResponse({
        'result': 200,
        'time': datetime.datetime.utcnow().isoformat() + 'Z',
        'geoip2_loaded': reader_ok,
        'ip_cache_size': len(SAFE_IP_CACHE),
    })


# ===== 유저 이슈 자동 통지 API (앱용) =====

@csrf_exempt
def app_get_notifications(request):
    """앱에서 유저에게 발송된 통지 목록 조회"""
    if 'id' not in request.session:
        return JsonResponse({'result': 401})
    email = request.session.get('email', '')
    if not email:
        return JsonResponse({'result': 401})
    
    try:
        with connections['default'].cursor() as cur:
            cur.execute("""
                SELECT id, noti_type, severity, title, message, recommendation,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i') as created_at,
                       DATE_FORMAT(sent_at, '%%Y-%%m-%%d %%H:%%i') as sent_at,
                       CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END as is_read
                FROM tbl_notification
                WHERE username = %s AND status = 'sent'
                ORDER BY sent_at DESC
                LIMIT 20
            """, [email])
            columns = [col[0] for col in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            # 미읽은 수
            cur.execute("""
                SELECT COUNT(*) FROM tbl_notification
                WHERE username = %s AND status = 'sent' AND read_at IS NULL
            """, [email])
            unread = cur.fetchone()[0]
            
        return JsonResponse({'result': 200, 'notifications': rows, 'unread': unread})
    except Exception as e:
        print('ERROR -> app_get_notifications:', e)
        return JsonResponse({'result': 500})


@csrf_exempt
def app_read_notification(request):
    """앱에서 통지 읽음 처리"""
    if 'id' not in request.session:
        return JsonResponse({'result': 401})
    email = request.session.get('email', '')
    noti_id = request.POST.get('noti_id')
    if not email or not noti_id:
        return JsonResponse({'result': 400})
    
    try:
        with connections['default'].cursor() as cur:
            cur.execute("""
                UPDATE tbl_notification SET status='read', read_at=NOW()
                WHERE id = %s AND username = %s AND status = 'sent'
            """, [noti_id, email])
        return JsonResponse({'result': 200})
    except Exception as e:
        print('ERROR -> app_read_notification:', e)
        return JsonResponse({'result': 500})


@csrf_exempt
def app_unread_notification_count(request):
    """앱에서 미읽은 통지 수 조회 (배지용)"""
    if 'id' not in request.session:
        return JsonResponse({'result': 401})
    email = request.session.get('email', '')
    if not email:
        return JsonResponse({'result': 401})
    
    try:
        with connections['default'].cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM tbl_notification
                WHERE username = %s AND status = 'sent' AND read_at IS NULL
            """, [email])
            unread = cur.fetchone()[0]
        return JsonResponse({'result': 200, 'unread': unread})
    except Exception as e:
        print('ERROR -> app_unread_notification_count:', e)
        return JsonResponse({'result': 500})


# 상품 가격 획득 함수 (안전판) - 기존 버전 대체
def getProductPirce(session, month_type, type):
    """Return product price string for given session/month/currency.
    Uses filter().first() to avoid DoesNotExist; logs and sends PushPlus alert once per (session,month_type) pair if missing.
    """
    qs = TblPrice.objects.filter(type_session=session, type_month=month_type)
    obj = qs.first()
    if not obj:
        key = f'{session}:{month_type}'
        _missing_price_alert(key, type)
        return None
    if type == 'KRW':
        return obj.item_price
    elif type == 'USD':
        return obj.item_price_usd
    elif type == 'CNY':
        return obj.item_price_cny
    return None

_MISSING_PRICE_CACHE = {}

def _missing_price_alert(key, currency):
    now = time.time()
    last = _MISSING_PRICE_CACHE.get(key)
    # 30분 내 중복 알림 억제
    if last and (now - last) < 1800:
        return
    _MISSING_PRICE_CACHE[key] = now
    msg = f'PRICE_MISSING session={key.split(":")[0]} month={key.split(":")[1]} currency={currency}'
    print('[price-missing]', msg)
    try:
        token = getattr(settings, 'PUSHPLUS_TOKEN', '') or os.environ.get('PUSHPLUS_TOKEN', '')
        if token:
            endpoint = getattr(settings, 'PUSHPLUS_ENDPOINT', 'https://www.pushplus.plus/send')
            payload = {
                'token': token,
                'title': 'Titan Missing Price',
                'content': msg,
                'template': 'txt'
            }
            requests.post(endpoint, json=payload, timeout=3)
    except Exception as e:
        print('[price-missing] pushplus failed:', e)


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
            return settings.SESSION_MONTH_1_1
        elif month_type == '2':
            return settings.SESSION_MONTH_2_2
        elif month_type == '3':
            return settings.SESSION_MONTH_2_3
        elif month_type == '6':
            return settings.SESSION_MONTH_2_6
        elif month_type == '12':
            return settings.SESSION_MONTH_2_12


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
