import os

from django.core.wsgi import get_wsgi_application

# Use only this repo's codebase; avoid injecting legacy paths.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = get_wsgi_application()
