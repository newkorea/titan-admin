# main/settings.py
import os
from django.utils.translation import ugettext_lazy as _

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 보안/기본 ---
# 운영에선 settings_local.py에서 실제 값으로 덮어쓰기
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
DEBUG = True
ALLOWED_HOSTS = ['*']
HTTPS = True

# GeoIP2 ASN database path (for telecom-aware auto-selection)
# Place GeoLite2-ASN.mmdb at this path; can be overridden in settings_local.py
GEOIP2_ASN_DB_PATH = os.path.join(BASE_DIR, 'data', 'GeoLite2-ASN.mmdb')

# --- 세션 ---
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --- 서비스 전역 상수(민감 아님) ---
ACTIVE_AES_KEY = ''  # 로컬에서 덮어쓰기
FULL_URL  = 'titan.jobjapan.com'
FULL_URL2 = 'titanvpn.kr'
FULL_URL3 = 'tl.jobjapan.net'
MY_URL    = 'aws14.titanvpn.kr'

FREE_SESSION = 1
FREE_DAY = 0
FREE_FIX_DAY = None

# --- Agent / SoftEther (비밀번호는 로컬에서) ---
AGENT_USER = 'root'
AGENT_PASS = ''           # settings_local.py에서 세팅
SOFTETHER_HUB  = 'TITAN'
SOFTETHER_PASS = ''       # settings_local.py에서 세팅

# --- SMTP (비밀번호 등은 로컬에서) ---
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 465
SMTP_EMAIL = ''           # settings_local.py에서 세팅
SMTP_ID = ''              # settings_local.py에서 세팅
SMTP_PW = ''              # settings_local.py에서 세팅

# --- 결제/외부 연동: 엔드포인트/ID(비밀 아님) ---
PAYLETTER_MODE = 'LIVE'
PAYBOX_MODE    = 'LIVE'
EXIMBAY_MODE   = 'LIVE'

# Payletter (국내)
PAYLETTER_KOR_TEST_ENDPOINT = 'https://testpgapi.payletter.com/'
PAYLETTER_KOR_TEST_SHOPID = 'pay_test'
PAYLETTER_KOR_LIVE_ENDPOINT = 'https://pgapi.payletter.com/'
PAYLETTER_KOR_LIVE_SHOPID = 'utocom'
# 키/해시는 settings_local.py에서:
PAYLETTER_KOR_TEST_APIKEY_PAYMENT = ''
PAYLETTER_KOR_TEST_APIKEY_SEARCH  = ''
PAYLETTER_KOR_LIVE_APIKEY_PAYMENT = ''
PAYLETTER_KOR_LIVE_APIKEY_SEARCH  = ''

# Payletter (해외)
PAYLETTER_GLOBAL_TEST_ENDPOINT = 'https://dev-gpgclient.payletter.com/'
PAYLETTER_GLOBAL_TEST_ENDPOINT_API = 'https://dev-api.payletter.com/'
PAYLETTER_GLOBAL_TEST_STOREID = 'utocom_test'
PAYLETTER_GLOBAL_LIVE_ENDPOINT = 'https://psp.payletter.com/'
PAYLETTER_GLOBAL_LIVE_ENDPOINT_API = 'https://api.payletter.com/'
PAYLETTER_GLOBAL_LIVE_STOREID = 'shanghai'
# 해시 키는 로컬에서:
PAYLETTER_GLOBAL_TEST_STORE_HASHKEY = ''
PAYLETTER_GLOBAL_LIVE_STORE_HASHKEY = ''

# Paybox WeChatPay
PAYBOX_WECHATPAY_TEST_ENDPOINT = 'http://devapi.paybox.store/'
PAYBOX_WECHATPAY_TEST_PARTNER_ID = 'riv1mmx7zirp4l4mtnntwf6ii7i6no4z'
PAYBOX_WECHATPAY_LIVE_ENDPOINT = 'https://api.paybox.store/'
PAYBOX_WECHATPAY_LIVE_PARTNER_ID = 'nmlqpm5reoubrvtkypkl29q9hse1gj4l'
# 파트너 키는 로컬에서:
PAYBOX_WECHATPAY_TEST_PARTNER_KEY = ''
PAYBOX_WECHATPAY_LIVE_PARTNER_KEY = ''

# Eximbay
EXIMBAY_TEST_ENDPOINT = 'https://secureapi.test.eximbay.com/Gateway/BasicProcessor.krp'
EXIMBAY_TEST_MID = '1849705C64'
EXIMBAY_LIVE_ENDPOINT = 'https://secureapi.eximbay.com/Gateway/BasicProcessor.krp'
EXIMBAY_LIVE_MID = '113F89FEE5'
# 시크릿 키는 로컬에서:
EXIMBAY_TEST_SECRET_KEY = ''
EXIMBAY_LIVE_SECRET_KEY = ''

# --- 업로드/로그 경로 ---
UPLOAD_ROOT = os.path.join(BASE_DIR, 'upload')
PAYMENT_KOREA_ROOT   = os.path.join(BASE_DIR, 'payment_korea')
PAYMENT_GLOBAL_ROOT  = os.path.join(BASE_DIR, 'payment_global')
PAYMENT_PAYBOX_ROOT  = os.path.join(BASE_DIR, 'payment_paybox')
PAYMENT_EXIMBAY_ROOT = os.path.join(BASE_DIR, 'payment_eximbay')

# --- 파일 경로 치환 ---
REPLACE_ABS_FROM = '/home/ubuntu/project/titan-admin'
REPLACE_ABS_TO = ''

# --- 상품명 상수 (민감 아님) ---
SESSION_MONTH_1_1  = 'TITAN NETWORKS 세션1 (1개월)'
SESSION_MONTH_1_2  = 'TITAN NETWORKS 세션1 (2개월)'
SESSION_MONTH_1_3  = 'TITAN NETWORKS 세션1 (3개월)'
SESSION_MONTH_1_6  = 'TITAN NETWORKS 세션1 (6개월)'
SESSION_MONTH_1_12 = 'TITAN NETWORKS 세션1 (12개월)'
SESSION_MONTH_2_1  = 'TITAN NETWORKS 세션2 (1개월)'
SESSION_MONTH_2_2  = 'TITAN NETWORKS 세션2 (2개월)'
SESSION_MONTH_2_3  = 'TITAN NETWORKS 세션2 (3개월)'
SESSION_MONTH_2_6  = 'TITAN NETWORKS 세션2 (6개월)'
SESSION_MONTH_2_12 = 'TITAN NETWORKS 세션2 (12개월)'
SESSION_MONTH_3_1  = 'TITAN NETWORKS 세션3 (1개월)'
SESSION_MONTH_3_2  = 'TITAN NETWORKS 세션3 (2개월)'
SESSION_MONTH_3_3  = 'TITAN NETWORKS 세션3 (3개월)'
SESSION_MONTH_3_6  = 'TITAN NETWORKS 세션3 (6개월)'
SESSION_MONTH_3_12 = 'TITAN NETWORKS 세션3 (12개월)'
SESSION_MONTH_4_1  = 'TITAN NETWORKS 세션4 (1개월)'
SESSION_MONTH_4_2  = 'TITAN NETWORKS 세션4 (2개월)'
SESSION_MONTH_4_3  = 'TITAN NETWORKS 세션4 (3개월)'
SESSION_MONTH_4_6  = 'TITAN NETWORKS 세션4 (6개월)'
SESSION_MONTH_4_12 = 'TITAN NETWORKS 세션4 (12개월)'
SESSION_MONTH_5_1  = 'TITAN NETWORKS 세션5 (1개월)'
SESSION_MONTH_5_2  = 'TITAN NETWORKS 세션5 (2개월)'
SESSION_MONTH_5_3  = 'TITAN NETWORKS 세션5 (3개월)'
SESSION_MONTH_5_6  = 'TITAN NETWORKS 세션5 (6개월)'
SESSION_MONTH_5_12 = 'TITAN NETWORKS 세션5 (12개월)'
SESSION_MONTH_6_1  = 'TITAN NETWORKS 세션6 (1개월)'
SESSION_MONTH_6_2  = 'TITAN NETWORKS 세션6 (2개월)'
SESSION_MONTH_6_3  = 'TITAN NETWORKS 세션6 (3개월)'
SESSION_MONTH_6_6  = 'TITAN NETWORKS 세션6 (6개월)'
SESSION_MONTH_6_12 = 'TITAN NETWORKS 세션6 (12개월)'

# --- DB (비밀번호는 로컬에서) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
        'USER': 'titan',
        'PASSWORD': '',  # settings_local.py에서 덮어쓰기
        'HOST': '218.158.57.48',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': 'SET NAMES utf8mb4',
        },
    },
    'radius': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radius',
        'USER': 'titan',
        'PASSWORD': '',  # settings_local.py에서 덮어쓰기
        'HOST': '218.158.57.48',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': 'SET NAMES utf8mb4',
        },
    },
}

# PushPlus notification token (set real token via environment or settings_local)
# Legacy default token preserved for backward-compatibility; override via env or settings_local.py
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN', '71441d4026b84b068f3e7522b173299f')
# Endpoint override allowed via environment
PUSHPLUS_ENDPOINT = os.environ.get('PUSHPLUS_ENDPOINT', 'https://www.pushplus.plus/send')

# --- 앱/미들웨어 ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'backend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'main.urls'
WSGI_APPLICATION = 'main.wsgi.application'

# --- 템플릿 (Mako + Django) ---
TEMPLATES = [
    {
        'BACKEND': 'djangomako.backends.MakoBackend',
        'NAME': 'mako',
        'DIRS': [os.path.join(BASE_DIR, 'backend', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'NAME': 'django',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# --- 인증 비번 정책(기본값) ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- 국제화 ---
LANGUAGES = [
    ('ko', _('Korean')),
    ('zh', _('Chinese')),
    ('en', _('English')),
]
LOCALE_PATHS = (os.path.join(BASE_DIR, 'locale'),)

# 원문 그대로(오타 포함) 유지
DATABASAE_OPTIONS = {'charset': 'utf8'}  # sic
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_L10N = True
USE_TZ = False

# --- 정적파일 ---
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'backend', 'static')]

# --- 로컬 비밀설정 덮어쓰기 ---
try:
    from .settings_local import *
    DATABASES['default']['PASSWORD'] = DB_PASSWORD_DEFAULT
    DATABASES['radius']['PASSWORD'] = DB_PASSWORD_RADIUS
except ImportError:
    pass
except NameError:
    pass