#!/usr/bin/env python3
import os, sys
# ensure project root is on sys.path so `main` package can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()
from django.test import Client
from backend.models import TblUser

c = Client()

# allow optional email argument: python test_api_create_payment.py user@example.com
email_arg = sys.argv[1] if len(sys.argv) > 1 else None
bypass_arg = sys.argv[2] if len(sys.argv) > 2 else None
if email_arg:
    u = TblUser.objects.filter(email=email_arg).first()
    if not u:
        print('NO_USER_FOUND_FOR_EMAIL', email_arg)
        sys.exit(2)
else:
    u = TblUser.objects.first()
    if not u:
        print('NO_USER_IN_DB')
        sys.exit(1)

print('Using user id:', u.id, 'username:', getattr(u, 'username', ''), 'email:', getattr(u, 'email', ''))
# prepare session like web login uses
s = c.session
s['id'] = u.id
s['username'] = getattr(u, 'username', '')
s['email'] = getattr(u, 'email', '')
s.save()

# Make the POST to api_create_payment
resp = c.post('/api_create_payment', {
    'pgcode': 'ALIPAY_IV',
    'session': '1',
    'month_type': '1',
    'type': 'A',
    'create_type': 'F'
}, follow=False)
if bypass_arg == 'bypass':
    # resend with bypass flag
    resp = c.post('/api_create_payment', {
        'pgcode': 'ALIPAY_IV',
        'session': '1',
        'month_type': '1',
        'type': 'A',
        'create_type': 'F',
        'bypass_recent': '1'
    })
print('HTTP_STATUS:', resp.status_code)
print('RESPONSE:', resp.content.decode('utf-8'))
