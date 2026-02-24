#!/usr/bin/env python3
"""
NAS 일일 점검 스크립트 (매일 저녁 7시 실행)
- nas_monitor.py (서버 상태 점검 + 자동수리)
- nas_service_check.py (VPN 서비스 점검)
- 결과를 tbl_nas_monitor_log에 저장

Usage:
    python3 scripts/nas_daily_check.py
"""

import sys
import os
import json
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import MySQLdb

DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

PYTHON = os.path.join(BASE_DIR, '.venv310', 'bin', 'python3')


def save_to_db(check_type, report_data):
    """점검 결과를 DB에 저장"""
    db = MySQLdb.connect(**DB_CONFIG)
    c = db.cursor()
    c.execute('''INSERT INTO tbl_nas_monitor_log 
                 (check_time, check_type, total_servers, ok_count, warning_count, critical_count, report_json)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)''',
              (datetime.now(), check_type,
               report_data.get('total', 0),
               report_data.get('ok', 0),
               report_data.get('warning', 0),
               report_data.get('critical', 0),
               json.dumps(report_data, ensure_ascii=True, default=str)))
    db.commit()
    db.close()


def run_health_check():
    """서버 상태 점검 (디스크, 메모리, CPU, 로그) + 자동수리"""
    print(f'[{datetime.now()}] === 서버 상태 점검 시작 (--fix) ===')
    result = subprocess.run(
        [PYTHON, 'scripts/nas_monitor.py', '--fix', '--json'],
        capture_output=True, text=True, encoding='utf-8', timeout=300
    )
    if result.returncode in (0, 1, 2) and result.stdout.strip():
        # JSON 출력 파싱
        try:
            data = json.loads(result.stdout)
            save_to_db('health', data)
            print(f'  결과: 전체 {data["total"]}대 | 정상 {data["ok"]} | 경고 {data["warning"]} | 위험 {data["critical"]}')
            return data
        except json.JSONDecodeError:
            print(f'  JSON 파싱 실패: {result.stdout[:200]}')
            return None
    else:
        print(f'  실행 실패: exit={result.returncode}, stderr={result.stderr[:200]}')
        return None


def run_service_check():
    """VPN 서비스 점검 (IKEv2, SSTP, OpenVPN, V2Ray)"""
    print(f'[{datetime.now()}] === VPN 서비스 점검 시작 ===')
    result = subprocess.run(
        [PYTHON, 'scripts/nas_service_check.py', '--json'],
        capture_output=True, text=True, encoding='utf-8', timeout=300
    )
    if result.returncode in (0, 1, 2) and result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            save_to_db('service', data)
            print(f'  결과: 전체 {data["total"]}대 | 정상 {data["ok"]} | 경고 {data["warning"]} | 위험 {data["critical"]}')
            return data
        except json.JSONDecodeError:
            print(f'  JSON 파싱 실패: {result.stdout[:200]}')
            return None
    else:
        print(f'  실행 실패: exit={result.returncode}, stderr={result.stderr[:200]}')
        return None


def run_alert_check():
    """WARNING/CRITICAL 이슈가 있으면 이메일 알림 발송 (중복 방지: 2시간 쿨다운)"""
    print(f'[{datetime.now()}] === 이슈 알림 체크 ===')
    result = subprocess.run(
        [PYTHON, 'scripts/nas_status_alert.py'],
        capture_output=True, text=True, encoding='utf-8', timeout=60
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(f'  알림 오류: {result.stderr[:200]}')


def main():
    print(f'[{datetime.now()}] NAS 일일 점검 시작')
    print('=' * 60)

    health = run_health_check()
    print()
    service = run_service_check()

    # 점검 후 이슈 알림 발송
    print()
    run_alert_check()

    print()
    print('=' * 60)
    print(f'[{datetime.now()}] NAS 일일 점검 완료')

    if health:
        print(f'  서버상태: 정상 {health["ok"]}/{health["total"]}')
    if service:
        print(f'  VPN서비스: 정상 {service["ok"]}/{service["total"]}')


if __name__ == '__main__':
    main()
