import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'fj@9(_0ecerym9(a=lqv_-@6smmg92^lm3z=02kr@xl7d=4m7i'
ALLOWED_HOSTS = ['*']


# 글로벌 변수 관리 영역
DEBUG = True

SMTP_HOST = 'smtp.titanvpn.io'                          # SMTP 도메인
SMTP_PORT = 25                                          # SMTP 포트
SMTP_EMAIL = 'titanvpnsupport@titanvpn.io'              # SMTP 이메일
SMTP_ID = 'titanvpnsupport'                             # SMTP 아이디
SMTP_PW = 'xkdlxks12!@'                                 # SMTP 비밀번호

LOGIN_FAIL_ATTEMPT = 10                                 # 로그인 시도 가능 회수

UPLOAD_ROOT = BASE_DIR + '/upload'                      # 업로드 디렉토리

REPLACE_ABS_FROM = '/home/ubuntu/project/titan'  # 파일 서브 디렉토리 변경 (FROM)
REPLACE_ABS_TO = ''                                     # 파일 서브 디렉토리 변경 (TO)

# 페이레터 모드 설정 ('LIVE' or 'TEST')
PAYLETTER_MODE = 'TEST'

# 페이레터 국내 테스트 설정
PAYLETTER_KOR_TEST_ENDPOINT         = 'https://testpgapi.payletter.com/'
PAYLETTER_KOR_TEST_SHOPID           = 'pay_test'
PAYLETTER_KOR_TEST_APIKEY_PAYMENT   = 'MTFBNTAzNTEwNDAxQUIyMjlCQzgwNTg1MkU4MkZENDA='
PAYLETTER_KOR_TEST_APIKEY_SEARCH    = 'MUI3MjM0RUExQTgyRDA1ODZGRDUyOEM4OTY2QTVCN0Y='

# 페이레터 국내 라이브 설정
PAYLETTER_KOR_LIVE_ENDPOINT         = 'https://pgapi.payletter.com/'
PAYLETTER_KOR_LIVE_SHOPID           = 'titan'
PAYLETTER_KOR_LIVE_APIKEY_PAYMENT   = 'RjUxRTVEQURENjZBNDYzRkQ3NDJDMDU3REUwNkY1M0Q='
PAYLETTER_KOR_LIVE_APIKEY_SEARCH    = 'MEM1QzY0RkFCOEMyMDZBMjVGN0YwRTY5NjU4MzA2RDA='

# 페이레터 해외 테스트 설정
PAYLETTER_GLOBAL_TEST_ENDPOINT      = 'https://dev-gpgclient.payletter.com/'
PAYLETTER_GLOBAL_TEST_ENDPOINT_API  = 'https://dev-api.payletter.com/'
PAYLETTER_GLOBAL_TEST_STOREID       = 'titanvpn'
PAYLETTER_GLOBAL_TEST_STORE_HASHKEY = 'titanvpn_190613'

# 페이레터 해외 라이브 설정
PAYLETTER_GLOBAL_LIVE_ENDPOINT      = 'https://psp.payletter.com/'
PAYLETTER_GLOBAL_LIVE_ENDPOINT_API  = 'https://api.payletter.com/'
PAYLETTER_GLOBAL_LIVE_STOREID       = 'titanvpn'
PAYLETTER_GLOBAL_LIVE_STORE_HASHKEY = 'titanvpn_190905'

# 페이박스 위쳇페이 테스트 설정
PAYBOX_WECHATPAY_TEST_ENDPOINT      = 'http://devapi.paybox.store/'
PAYBOX_WECHATPAY_TEST_PARTNER_ID    = 'riv1mmx7zirp4l4mtnntwf6ii7i6no4z'
PAYBOX_WECHATPAY_TEST_PARTNER_KEY   = 'bTZnd3UzZjNhZnI2aXdrMngxY291NGlrM3k4bmp5anI='

# 페이박스 위쳇페이 라이브 설정
PAYBOX_WECHATPAY_LIVE_ENDPOINT      = 'http://api.paybox.store/'
PAYBOX_WECHATPAY_LIVE_PARTNER_ID    = 'riv1mmx7zirp4l4mtnntwf6ii7i6no4z'
PAYBOX_WECHATPAY_LIVE_PARTNER_KEY   = 'bTZnd3UzZjNhZnI2aXdrMngxY291NGlrM3k4bmp5anI='

# 데이터베이스 커넥션 관리
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
        'USER': 'scv',
        'PASSWORD': 'dhlwn12!@',
        'HOST': '1.234.70.54',
        'PORT': '3306',
    },
    'radius': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radius',
        'USER': 'scv',
        'PASSWORD': 'dhlwn12!@',
        'HOST': '1.234.70.54',
        'PORT': '3306',
    }
}


# 설치 앱 관리
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'backend',
     'django_extensions',
]


# 미들웨어 관리
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# 루트 URL 관리
ROOT_URLCONF = 'main.urls'


# 템플릿 관리
TEMPLATES = [
    {
        'BACKEND': 'djangomako.backends.MakoBackend',
        'NAME': 'mako',
        'DIRS': [
            BASE_DIR + '/backend/templates/',
        ],
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


WSGI_APPLICATION = 'main.wsgi.application'
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 기본 관리
DATABASAE_OPTIONS = {'charset':'utf8'}
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'

USE_I18N = True
USE_L10N = True


# 스태틱 관리
STATIC_ROOT = BASE_DIR + '/static/'
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR + '/backend/static/'
]
