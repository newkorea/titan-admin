#!/usr/bin/env python3
"""
UTO NAS 서버 상태 자동 점검 (1시간마다 cron 실행)
결과는 /tmp/uto_nas_check/results.json에 저장
uto-admin UTO NAS 현황 페이지에서 이 파일을 읽어 표시

crontab:
  0 * * * * /home/newkorea/project/uto-admin/.venv38/bin/python3 /home/newkorea/project/scripts/uto_nas_check_cron.py >> /home/newkorea/project/scripts/uto_nas_check.log 2>&1
"""
import os
import sys
import json
import time

# Django setup
sys.path.insert(0, '/home/newkorea/project/uto-admin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from backend.djangoapps.uto.views import _run_uto_check_all, _is_uto_check_running, _set_uto_check_running

LOCK_FILE = '/tmp/uto_nas_check_cron.lock'


def main():
    # Prevent concurrent runs
    running, elapsed = _is_uto_check_running()
    if running:
        print(f'[SKIP] Already running ({elapsed:.0f}s elapsed)')
        return

    print(f'[START] UTO NAS check at {time.strftime("%Y-%m-%d %H:%M:%S")}')
    start = time.time()

    try:
        _run_uto_check_all()
        elapsed = round(time.time() - start, 1)
        print(f'[DONE] Completed in {elapsed}s')

        # Verify results
        results_path = '/tmp/uto_nas_check/results.json'
        if os.path.exists(results_path):
            with open(results_path) as f:
                data = json.load(f)
            vpn = len(data.get('servers', []))
            infra = len(data.get('infra_servers', []))
            ok = data.get('ok', 0)
            warn = data.get('warning', 0)
            crit = data.get('critical', 0)
            print(f'  VPN: {vpn}, Infra: {infra} | OK: {ok}, Warn: {warn}, Crit: {crit}')
        else:
            print('  [WARN] results.json not found after check')
    except Exception as e:
        print(f'[ERROR] {e}')
        import traceback
        traceback.print_exc()
        _set_uto_check_running(False)


if __name__ == '__main__':
    main()
