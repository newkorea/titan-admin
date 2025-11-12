import os
import socket
import paramiko
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections

DEFAULT_TIMEOUT = float(os.environ.get('AUDIT_SSH_TIMEOUT', '2.0'))
PUSH_ON_FAIL = os.environ.get('AUDIT_SSH_PUSH_ON_FAIL', '0') == '1'

class Command(BaseCommand):
    help = 'Audit SSH connectivity for all NAS entries in titan.tbl_agent3 (hostip + optional hostdomain).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None, help='Limit number of rows tested.')
        parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT, help='Per-host SSH connect timeout (seconds).')
        parser.add_argument('--push', action='store_true', help='Send PushPlus notification on failures.')
        parser.add_argument('--skip-domain', action='store_true', help='Skip hostdomain if present (use hostip only).')
        parser.add_argument('--only-active', action='store_true', help='Test only rows where is_active=\'Y\'.')

    def handle(self, *args, **opts):
        t0 = time.time()
        timeout = opts['timeout']
        push = opts['push'] or PUSH_ON_FAIL
        only_active = opts['only_active']
        limit = opts['limit']
        skip_domain = opts['skip_domain']

        with connections['default'].cursor() as cur:
            where = ''
            if only_active:
                # Support both char and numeric active flags
                where = "WHERE (is_active='Y' OR is_active='1' OR is_active=1)"
            cur.execute(f"SELECT id, hostip, hostdomain, username, password, protocol FROM titan.tbl_agent3 {where} ORDER BY id")
            rows = cur.fetchall()
        if limit:
            rows = rows[:limit]

        total = len(rows)
        ok = 0
        fail = []

        self.stdout.write(f"[audit] Testing {total} NAS entries (timeout={timeout}s, push_fail={push})")
        for r in rows:
            _id, hostip, hostdomain, user, pw, proto = r
            target = hostip
            if hostdomain and (not skip_domain):
                target = hostdomain
            label = f"id={_id} {target} ({proto})"
            if not hostip or not user or not pw:
                self.stdout.write(f"[skip] {label} missing credentials")
                fail.append((target, 'missing-cred'))
                continue
            res = self._try_ssh(target, user, pw, timeout)
            if res is True:
                ok += 1
                self.stdout.write(f"[ok]   {label}")
            else:
                self.stdout.write(f"[fail] {label} reason={res}")
                fail.append((target, res))

        self.stdout.write(f"[audit] Done: success={ok}/{total} fail={len(fail)} elapsed={time.time()-t0:.1f}s")
        if fail:
            self.stdout.write("[audit] Failed targets:")
            for tgt, reason in fail:
                self.stdout.write(f"    - {tgt}: {reason}")
            if push:
                self._push_fail(fail, total, ok)

    def _try_ssh(self, host, user, pw, timeout):
        try:
            # basic resolve check before SSH
            try:
                socket.gethostbyname(host)
            except Exception:
                return 'dns'
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(host, username=user, password=pw, timeout=timeout, banner_timeout=timeout)
            cli.close()
            return True
        except paramiko.AuthenticationException:
            return 'auth'
        except paramiko.SSHException as e:
            return f'ssh:{e.__class__.__name__}'
        except Exception as e:
            return f'other:{e.__class__.__name__}'

    def _push_fail(self, fail_list, total, ok):
        token = getattr(settings, 'PUSHPLUS_TOKEN', '') or os.environ.get('PUSHPLUS_TOKEN', '')
        if not token:
            return
        endpoint = getattr(settings, 'PUSHPLUS_ENDPOINT', 'https://www.pushplus.plus/send')
        sample = ', '.join([f"{h}:{r}" for h,r in fail_list[:5]])
        content = f"SSH AUDIT FAIL {len(fail_list)}/{total} (ok={ok}) sample=[{sample}]"
        try:
            import requests
            requests.post(endpoint, json={
                'token': token,
                'title': 'ssh audit Alert',
                'content': content,
                'template': 'txt'
            }, timeout=4)
        except Exception:
            pass
