import os
import sys

# ✅ Django 프로젝트 루트 경로 추가
sys.path.append('/www/wwwroot/tiadmintansk1.titanvpn.kr/backend')  # `backend/`를 추가해야 함

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = get_wsgi_application()
