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


# 데이터베이스 커넥션 관리
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
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
