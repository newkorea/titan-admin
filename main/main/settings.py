import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'fj@9(_0ecerym9(a=lqv_-@6smmg92^lm3z=02kr@xl7d=4m7i'
ALLOWED_HOSTS = ['*']


# 글로벌 변수 관리 영역
DEBUG = True
SESSION_COOKIE_AGE = 24 * 60 * 60                       # 세션 타임아웃 (sec)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True                  # 브라우저 닫을 시 세션 만료 (크롬 적용 불가)
APPEND_SLASH = False
# settings.py
#USE_TZ = True  # 시간을 시간대가 고려된 datetime으로 처리
#TIME_ZONE = 'Asia/Seoul'  # 서울 시간대 (한국 표준시)


SMTP_HOST = 'smtp.naver.com'                            # SMTP 도메인
SMTP_PORT = 465                                         # SMTP 포트
SMTP_EMAIL = 'kakaovpn@naver.com'                     # SMTP 이메일
SMTP_ID = 'kakaovpn'                        # SMTP 아이디
SMTP_PW = 'myboss1357'                         # SMTP 비밀번호
#SMTP_HOST = 'smtp-relay.gmail.com'                      # SMTP 도메인
#SMTP_PORT = 25                                          # SMTP 포트
#SMTP_EMAIL = 'master@titanvpn.io'                       # SMTP 이메일
#SMTP_ID = 'titanvpnsupport'                            # SMTP 아이디
#SMTP_PW = 'xkdlxks12!@'                                # SMTP 비밀번호

# API Key 설정 (강력한 키로 변경하세요!)
API_SECRET_KEY = "MyJohnFCandy670312!@bemyslave"        #원격연장승인API용 비밀번호

LOGIN_FAIL_ATTEMPT = 10                                 # 로그인 시도 가능 회수

UPLOAD_ROOT = BASE_DIR + '/upload'                      # 업로드 디렉토리

REPLACE_ABS_FROM = '/home/ubuntu/project/titan'         # 파일 서브 디렉토리 변경 (FROM)
REPLACE_ABS_TO = ''                                     # 파일 서브 디렉토리 변경 (TO)

# 상품 이름 관리
SESSION_MONTH_1_1   = 'TITAN NETWORKS 세션1 (1개월)'
SESSION_MONTH_1_2   = 'TITAN NETWORKS 세션1 (2개월)'
SESSION_MONTH_1_3   = 'TITAN NETWORKS 세션1 (3개월)'
SESSION_MONTH_1_6   = 'TITAN NETWORKS 세션1 (6개월)'
SESSION_MONTH_1_12  = 'TITAN NETWORKS 세션1 (12개월)'
SESSION_MONTH_2_1   = 'TITAN NETWORKS 세션2 (1개월)'
SESSION_MONTH_2_2   = 'TITAN NETWORKS 세션2 (2개월)'
SESSION_MONTH_2_3   = 'TITAN NETWORKS 세션2 (3개월)'
SESSION_MONTH_2_6   = 'TITAN NETWORKS 세션2 (6개월)'
SESSION_MONTH_2_12  = 'TITAN NETWORKS 세션2 (12개월)'
SESSION_MONTH_3_1   = 'TITAN NETWORKS 세션3 (1개월)'
SESSION_MONTH_3_2   = 'TITAN NETWORKS 세션3 (2개월)'
SESSION_MONTH_3_3   = 'TITAN NETWORKS 세션3 (3개월)'
SESSION_MONTH_3_6   = 'TITAN NETWORKS 세션3 (6개월)'
SESSION_MONTH_3_12  = 'TITAN NETWORKS 세션3 (12개월)'
SESSION_MONTH_4_1   = 'TITAN NETWORKS 세션4 (1개월)'
SESSION_MONTH_4_2   = 'TITAN NETWORKS 세션4 (2개월)'
SESSION_MONTH_4_3   = 'TITAN NETWORKS 세션4 (3개월)'
SESSION_MONTH_4_6   = 'TITAN NETWORKS 세션4 (6개월)'
SESSION_MONTH_4_12  = 'TITAN NETWORKS 세션4 (12개월)'
SESSION_MONTH_5_1   = 'TITAN NETWORKS 세션5 (1개월)'
SESSION_MONTH_5_2   = 'TITAN NETWORKS 세션5 (2개월)'
SESSION_MONTH_5_3   = 'TITAN NETWORKS 세션5 (3개월)'
SESSION_MONTH_5_6   = 'TITAN NETWORKS 세션5 (6개월)'
SESSION_MONTH_5_12  = 'TITAN NETWORKS 세션5 (12개월)'
SESSION_MONTH_6_1   = 'TITAN NETWORKS 세션6 (1개월)'
SESSION_MONTH_6_2   = 'TITAN NETWORKS 세션6 (2개월)'
SESSION_MONTH_6_3   = 'TITAN NETWORKS 세션6 (3개월)'
SESSION_MONTH_6_6   = 'TITAN NETWORKS 세션6 (6개월)'
SESSION_MONTH_6_12  = 'TITAN NETWORKS 세션6 (12개월)'

# 페이레터 모드 설정 ('LIVE' or 'TEST')
PAYLETTER_MODE  = 'LIVE'
PAYBOX_MODE     = 'LIVE'

# 페이레터 국내 테스트 설정
PAYLETTER_KOR_TEST_ENDPOINT         = 'https://testpgapi.payletter.com/'
PAYLETTER_KOR_TEST_SHOPID           = 'pay_test'
PAYLETTER_KOR_TEST_APIKEY_PAYMENT   = 'MTFBNTAzNTEwNDAxQUIyMjlCQzgwNTg1MkU4MkZENDA='
PAYLETTER_KOR_TEST_APIKEY_SEARCH    = 'MUI3MjM0RUExQTgyRDA1ODZGRDUyOEM4OTY2QTVCN0Y='

# 페이레터 국내 라이브 설정
PAYLETTER_KOR_LIVE_ENDPOINT         = 'https://pgapi.payletter.com/'
PAYLETTER_KOR_LIVE_SHOPID           = 'utocom'
PAYLETTER_KOR_LIVE_APIKEY_PAYMENT   = 'MDdGQkZBQkNDNUM5N0QwNDFCMEMyRTkxRENBRkJBMEY='
PAYLETTER_KOR_LIVE_APIKEY_SEARCH    = 'QjYxNTlFMjMwQTY2MEQzRjVGRkMyQzA1Mjg1MjJCMTg='

# 페이레터 해외 테스트 설정
PAYLETTER_GLOBAL_TEST_ENDPOINT      = 'https://dev-gpgclient.payletter.com/'
PAYLETTER_GLOBAL_TEST_ENDPOINT_API  = 'https://dev-api.payletter.com/'
PAYLETTER_GLOBAL_TEST_STOREID       = 'utocom_test'
PAYLETTER_GLOBAL_TEST_STORE_HASHKEY = 'utocom_test_210908'

# 페이레터 해외 라이브 설정
PAYLETTER_GLOBAL_LIVE_ENDPOINT      = 'https://psp.payletter.com/'
PAYLETTER_GLOBAL_LIVE_ENDPOINT_API  = 'https://api.payletter.com/'
PAYLETTER_GLOBAL_LIVE_STOREID       = 'shanghai'
PAYLETTER_GLOBAL_LIVE_STORE_HASHKEY = 'shanghai_220315'

# 페이박스 위쳇페이 테스트 설정
PAYBOX_WECHATPAY_TEST_ENDPOINT      = 'http://devapi.paybox.store/'
PAYBOX_WECHATPAY_TEST_PARTNER_ID    = 'riv1mmx7zirp4l4mtnntwf6ii7i6no4z'
PAYBOX_WECHATPAY_TEST_PARTNER_KEY   = 'bTZnd3UzZjNhZnI2aXdrMngxY291NGlrM3k4bmp5anI='

# 페이박스 위쳇페이 라이브 설정
PAYBOX_WECHATPAY_LIVE_ENDPOINT      = 'https://api.paybox.store/'
PAYBOX_WECHATPAY_LIVE_PARTNER_ID    = 'nmlqpm5reoubrvtkypkl29q9hse1gj4l'
PAYBOX_WECHATPAY_LIVE_PARTNER_KEY   = 'dHQzbnBlMmZwbHcxcXRibDN1YjNqbjEzNmphMmRoeWY='


# 데이터베이스 커넥션 관리
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
#        'HOST': '15.165.156.213',
        'HOST': '218.158.57.48',
        'PORT': '3306',
    },
    'radius': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radius',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
#        'HOST': '15.165.156.213',
        'HOST': '218.158.57.48',
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
    'backend.djangoapps.price',  # ✅ `backend.`를 앞에 추가해야 함
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
