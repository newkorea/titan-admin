#!/usr/bin/env python3
"""
nas_status_alert.py  –  NAS 서버 상태 이메일 알림
====================================================
tbl_nas_monitor_log에서 최신 health/service 체크 결과를 읽어
WARNING 또는 CRITICAL 이슈가 있으면 이메일로 전송.

사용법:
  python3 scripts/nas_status_alert.py              # 이슈 있으면 이메일 발송
  python3 scripts/nas_status_alert.py --test       # 테스트 이메일 발송
  python3 scripts/nas_status_alert.py --dry-run    # 이메일 안 보내고 내용만 출력

cron 예시 (30분마다):
  */30 * * * * cd /home/newkorea/project/titan && .venv310/bin/python3 scripts/nas_status_alert.py >> logs/nas_status_alert.log 2>&1
"""

import os
import sys
import json
import time
import smtplib
import argparse
import hashlib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import MySQLdb

# ── DB 설정 ──
DB_CONFIG = {
    'host': '218.158.57.48',
    'user': 'titan',
    'passwd': 'xkdlxks12!@',
    'db': 'titan',
    'charset': 'utf8mb4',
}

# ── 이메일 설정 (settings_local.py 에서 읽어옴) ──
EMAIL_TO = 'softcan@naver.com'
_SETTINGS_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'main', 'settings_local.py')
SMTP_HOST = 'smtp.naver.com'
SMTP_PORT = 465
SMTP_EMAIL = ''
SMTP_USER = ''
SMTP_PASS = ''
try:
    _ns = {}
    with open(_SETTINGS_LOCAL) as _f:
        exec(_f.read(), _ns)
    SMTP_HOST = _ns.get('SMTP_HOST', SMTP_HOST)
    SMTP_PORT = _ns.get('SMTP_PORT', SMTP_PORT)
    SMTP_EMAIL = _ns.get('SMTP_EMAIL', '')
    SMTP_USER = _ns.get('SMTP_ID', '')
    SMTP_PASS = _ns.get('SMTP_PW', '')
except Exception as _e:
    print(f'WARN: settings_local.py 로드 실패: {_e}')

# ── PushPlus (백업 알림) ──
PUSHPLUS_TOKEN = '71441d4026b84b068f3e7522b173299f'
PUSHPLUS_ENDPOINT = 'https://www.pushplus.plus/send'

# ── 중복 알림 방지 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, '..', 'logs', 'nas_status_alert_state.json')
# 같은 이슈에 대해 최소 2시간 간격으로만 알림
ALERT_COOLDOWN = 7200  # seconds


def get_db():
    conn = MySQLdb.connect(**DB_CONFIG)
    return conn


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_latest_status():
    """DB에서 최신 health + service 체크 결과를 가져온다."""
    conn = get_db()
    cur = conn.cursor()

    # 최신 health 체크
    cur.execute("""
        SELECT check_time, check_type, total_servers, ok_count, warning_count,
               critical_count, report_json
        FROM tbl_nas_monitor_log
        WHERE check_type = 'health'
        ORDER BY check_time DESC
        LIMIT 1
    """)
    health_rows = dictfetchall(cur)

    # 최신 service 체크
    cur.execute("""
        SELECT check_time, check_type, total_servers, ok_count, warning_count,
               critical_count, report_json
        FROM tbl_nas_monitor_log
        WHERE check_type = 'service'
        ORDER BY check_time DESC
        LIMIT 1
    """)
    service_rows = dictfetchall(cur)

    cur.close()
    conn.close()

    return health_rows[0] if health_rows else None, service_rows[0] if service_rows else None


def parse_issues(row):
    """체크 결과에서 WARNING/CRITICAL 서버 목록을 추출한다."""
    if not row or not row.get('report_json'):
        return [], []

    try:
        report = json.loads(row['report_json'])
    except json.JSONDecodeError:
        return [], []

    servers = report.get('servers', [])
    warnings = []
    criticals = []

    for s in servers:
        name = s.get('name', '?')
        ip = s.get('ip', '?')

        # criticals 리스트
        crit_list = s.get('criticals', [])
        if crit_list:
            criticals.append({
                'name': name,
                'ip': ip,
                'issues': crit_list,
                'disk_pct': s.get('disk_pct', 0),
                'mem_pct': s.get('mem_pct', 0),
                'load_1m': s.get('load_1m', 0),
                'strongswan_running': s.get('strongswan_running', False),
                'strongswan_conns': s.get('strongswan_conns', 0),
                'cert_status': s.get('cert_status', ''),
                'cert_days_left': s.get('cert_days_left', -999),
                'actions_taken': s.get('actions_taken', []),
            })

        # warnings 리스트
        warn_list = s.get('warnings', [])
        if warn_list and not crit_list:  # criticals에 이미 포함된 서버는 제외
            warnings.append({
                'name': name,
                'ip': ip,
                'issues': warn_list,
                'disk_pct': s.get('disk_pct', 0),
                'mem_pct': s.get('mem_pct', 0),
                'load_1m': s.get('load_1m', 0),
                'strongswan_running': s.get('strongswan_running', False),
                'strongswan_conns': s.get('strongswan_conns', 0),
                'cert_status': s.get('cert_status', ''),
                'cert_days_left': s.get('cert_days_left', -999),
                'actions_taken': s.get('actions_taken', []),
            })

    return warnings, criticals


def _issue_fingerprint(warnings, criticals, check_type):
    """이슈의 지문(해시) 생성 — 같은 이슈 반복 알림 방지"""
    parts = []
    for s in criticals:
        parts.append(f"C:{s['name']}:{','.join(s['issues'])}")
    for s in warnings:
        parts.append(f"W:{s['name']}:{','.join(s['issues'])}")
    raw = f"{check_type}|{'|'.join(sorted(parts))}"
    return hashlib.md5(raw.encode()).hexdigest()


def load_state():
    """중복 알림 방지 상태 파일 로드"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_state(state):
    """상태 파일 저장"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f'WARN: 상태 파일 저장 실패: {e}')


def should_alert(fingerprint, state):
    """해당 이슈에 대해 알림을 보내야 하는지 확인"""
    now = time.time()
    last = state.get(fingerprint, {}).get('last_alert', 0)
    return (now - last) > ALERT_COOLDOWN


def build_email_body(health_row, service_row,
                     health_warnings, health_criticals,
                     service_warnings, service_criticals):
    """이메일 본문(HTML) 생성"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Malgun Gothic', Arial, sans-serif; margin: 20px; background: #f5f5f5;">
<div style="max-width: 700px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden;">

<div style="background: #dc3545; color: #fff; padding: 20px 24px;">
  <h2 style="margin: 0;">⚠ TitanVPN NAS 서버 알림</h2>
  <p style="margin: 5px 0 0; opacity: 0.9;">발생 시각: {now}</p>
</div>

<div style="padding: 24px;">
"""

    # 요약
    total_crit = len(health_criticals) + len(service_criticals)
    total_warn = len(health_warnings) + len(service_warnings)

    html += f"""
<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 12px 16px; margin-bottom: 20px;">
  <strong>요약:</strong> CRITICAL {total_crit}건 / WARNING {total_warn}건
</div>
"""

    # Health 체크
    if health_row:
        check_time = health_row['check_time']
        if hasattr(check_time, 'strftime'):
            check_time = check_time.strftime('%Y-%m-%d %H:%M:%S')

        html += f"""
<h3 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 8px;">
  🖥 서버 상태 (Health) — {check_time}
</h3>
<p>전체 {health_row['total_servers']}대 | 정상 {health_row['ok_count']} | 경고 {health_row['warning_count']} | 위험 {health_row['critical_count']}</p>
"""

        if health_criticals:
            html += _build_server_table(health_criticals, 'CRITICAL', '#dc3545')
        if health_warnings:
            html += _build_server_table(health_warnings, 'WARNING', '#ffc107')

    # Service 체크
    if service_row:
        check_time = service_row['check_time']
        if hasattr(check_time, 'strftime'):
            check_time = check_time.strftime('%Y-%m-%d %H:%M:%S')

        if service_criticals or service_warnings:
            html += f"""
<h3 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 8px;">
  🔌 VPN 서비스 (Service) — {check_time}
</h3>
<p>전체 {service_row['total_servers']}대 | 정상 {service_row['ok_count']} | 경고 {service_row['warning_count']} | 위험 {service_row['critical_count']}</p>
"""
            if service_criticals:
                html += _build_server_table(service_criticals, 'CRITICAL', '#dc3545')
            if service_warnings:
                html += _build_server_table(service_warnings, 'WARNING', '#ffc107')

    html += """
<div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; color: #888; font-size: 12px;">
  <p>이 메일은 TitanVPN NAS 모니터링 시스템에서 자동 발송되었습니다.</p>
  <p>관리페이지: <a href="https://tiadmintan14.titanvpn.kr/nas_status">https://tiadmintan14.titanvpn.kr/nas_status</a></p>
</div>

</div></div></body></html>"""

    return html


def _build_server_table(servers, level, color):
    """서버 목록 HTML 테이블 생성"""
    bg = '#fff5f5' if level == 'CRITICAL' else '#fffdf0'
    html = f"""
<table style="width: 100%; border-collapse: collapse; margin: 10px 0 20px;">
  <tr style="background: {color}; color: {'#fff' if level == 'CRITICAL' else '#333'};">
    <td colspan="6" style="padding: 8px 12px; font-weight: bold;">
      {'🔴' if level == 'CRITICAL' else '🟡'} {level} ({len(servers)}대)
    </td>
  </tr>
  <tr style="background: #f8f9fa; font-size: 13px;">
    <th style="padding: 6px 8px; text-align: left; border: 1px solid #ddd;">서버명</th>
    <th style="padding: 6px 8px; text-align: left; border: 1px solid #ddd;">IP</th>
    <th style="padding: 6px 8px; text-align: center; border: 1px solid #ddd;">디스크</th>
    <th style="padding: 6px 8px; text-align: center; border: 1px solid #ddd;">메모리</th>
    <th style="padding: 6px 8px; text-align: center; border: 1px solid #ddd;">인증서</th>
    <th style="padding: 6px 8px; text-align: left; border: 1px solid #ddd;">이슈</th>
  </tr>
"""

    for s in servers:
        issues_html = '<br>'.join(s['issues'])
        cert_display = s.get('cert_status', '')
        if s.get('cert_days_left', -999) >= 0:
            cert_display += f" ({s['cert_days_left']}일)"

        # 자동 복구 조치
        actions = s.get('actions_taken', [])
        if actions:
            issues_html += '<br><span style="color: #28a745; font-size: 11px;">✔ ' + \
                           ', '.join(actions) + '</span>'

        html += f"""
  <tr style="background: {bg};">
    <td style="padding: 6px 8px; border: 1px solid #ddd; font-weight: bold;">{s['name']}</td>
    <td style="padding: 6px 8px; border: 1px solid #ddd;">{s['ip']}</td>
    <td style="padding: 6px 8px; border: 1px solid #ddd; text-align: center;">{s['disk_pct']}%</td>
    <td style="padding: 6px 8px; border: 1px solid #ddd; text-align: center;">{s['mem_pct']}%</td>
    <td style="padding: 6px 8px; border: 1px solid #ddd; text-align: center;">{cert_display}</td>
    <td style="padding: 6px 8px; border: 1px solid #ddd; font-size: 12px;">{issues_html}</td>
  </tr>"""

    html += "</table>"
    return html


def build_text_summary(health_warnings, health_criticals,
                       service_warnings, service_criticals):
    """PushPlus / 콘솔용 텍스트 요약"""
    lines = []
    for s in health_criticals + service_criticals:
        short = s['name'].replace('KOREA-', '')
        lines.append(f'🔴{short}: {", ".join(s["issues"])}')
    for s in health_warnings + service_warnings:
        short = s['name'].replace('KOREA-', '')
        lines.append(f'🟡{short}: {", ".join(s["issues"])}')
    return '\n'.join(lines)


def send_email_alert(subject, html_body):
    """SMTP로 이메일 전송"""
    if not SMTP_PASS:
        print(f'WARN: SMTP_PASS 미설정 — 이메일 전송 건너뜀')
        print(f'  제목: {subject}')
        return False

    from_addr = SMTP_EMAIL or f'{SMTP_USER}@naver.com'

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = from_addr
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        if SMTP_PORT == 465:
            # SSL (naver 기본)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            # STARTTLS
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

        print(f'  ✅ 이메일 발송 완료 → {EMAIL_TO}')
        return True
    except Exception as e:
        print(f'  ❌ 이메일 발송 실패: {e}')
        return False


def send_pushplus_alert(title, body):
    """PushPlus 알림 전송 (백업)"""
    try:
        import requests
        resp = requests.post(PUSHPLUS_ENDPOINT, json={
            'token': PUSHPLUS_TOKEN,
            'title': title,
            'content': body,
            'template': 'txt',
        }, timeout=10)
        print(f'  PushPlus: {resp.status_code}')
    except Exception as e:
        print(f'  PushPlus 실패: {e}')


def main():
    parser = argparse.ArgumentParser(description='NAS 서버 상태 이메일 알림')
    parser.add_argument('--test', action='store_true', help='테스트 이메일 발송')
    parser.add_argument('--dry-run', action='store_true', help='이메일 안 보내고 내용만 출력')
    parser.add_argument('--force', action='store_true', help='쿨다운 무시하고 강제 발송')
    args = parser.parse_args()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{now}] NAS 상태 알림 체크 시작')

    # ── 테스트 모드 ──
    if args.test:
        subject = '[TitanVPN] NAS 알림 테스트'
        html = f"""<html><body>
        <h2>테스트 이메일</h2>
        <p>발송 시각: {now}</p>
        <p>NAS 서버 상태 알림 시스템이 정상 작동 중입니다.</p>
        <p><a href="https://tiadmintan14.titanvpn.kr/nas_status">관리 페이지</a></p>
        </body></html>"""
        if args.dry_run:
            print(f'  [DRY-RUN] 제목: {subject}')
            print(f'  내용: 테스트 이메일')
        else:
            send_email_alert(subject, html)
            send_pushplus_alert('NAS알림테스트', f'NAS 알림 시스템 테스트 — {now}')
        return

    # ── 최신 데이터 조회 ──
    health_row, service_row = fetch_latest_status()

    if not health_row and not service_row:
        print('  데이터 없음 — 점검 결과가 DB에 없습니다.')
        return

    # ── 이슈 파싱 ──
    health_warnings, health_criticals = parse_issues(health_row)
    service_warnings, service_criticals = parse_issues(service_row)

    total_issues = (len(health_warnings) + len(health_criticals) +
                    len(service_warnings) + len(service_criticals))

    if total_issues == 0:
        print(f'  ✅ 이슈 없음 (Health: {health_row["ok_count"] if health_row else 0}대 정상, '
              f'Service: {service_row["ok_count"] if service_row else 0}대 정상)')
        # 이슈 해소 시 상태 초기화
        save_state({})
        return

    total_crit = len(health_criticals) + len(service_criticals)
    total_warn = len(health_warnings) + len(service_warnings)
    print(f'  ⚠ 이슈 발견: CRITICAL {total_crit}건, WARNING {total_warn}건')

    # ── 텍스트 요약 ──
    text_summary = build_text_summary(health_warnings, health_criticals,
                                      service_warnings, service_criticals)
    print(text_summary)

    # ── 중복 알림 체크 ──
    fp_health = _issue_fingerprint(health_warnings, health_criticals, 'health')
    fp_service = _issue_fingerprint(service_warnings, service_criticals, 'service')
    fp_combined = hashlib.md5(f'{fp_health}:{fp_service}'.encode()).hexdigest()

    state = load_state()
    if not args.force and not should_alert(fp_combined, state):
        elapsed = time.time() - state.get(fp_combined, {}).get('last_alert', 0)
        remaining = ALERT_COOLDOWN - elapsed
        print(f'  ⏳ 쿨다운 중 (같은 이슈, {remaining:.0f}초 후 재알림 가능)')
        return

    # ── 이메일 발송 ──
    level = 'CRITICAL' if total_crit > 0 else 'WARNING'
    subject = f'[TitanVPN] NAS {level}: {total_crit}건 위험, {total_warn}건 경고'
    html_body = build_email_body(health_row, service_row,
                                 health_warnings, health_criticals,
                                 service_warnings, service_criticals)

    if args.dry_run:
        print(f'\n  [DRY-RUN] 제목: {subject}')
        print(f'  HTML body: {len(html_body)} chars')
        # 간단한 텍스트 미리보기
        for s in health_criticals + service_criticals:
            print(f'    🔴 {s["name"]} ({s["ip"]}): {", ".join(s["issues"])}')
        for s in health_warnings + service_warnings:
            print(f'    🟡 {s["name"]} ({s["ip"]}): {", ".join(s["issues"])}')
        return

    # 이메일 발송
    email_ok = send_email_alert(subject, html_body)

    # PushPlus 발송 (백업)
    pushplus_title = f'타이탄NAS_{level}_{total_crit + total_warn}건'
    send_pushplus_alert(pushplus_title, text_summary)

    # 상태 업데이트
    state[fp_combined] = {
        'last_alert': time.time(),
        'subject': subject,
        'email_sent': email_ok,
    }
    # 기존 오래된 항목 정리
    cutoff = time.time() - 86400  # 24시간 이상 된 항목 제거
    state = {k: v for k, v in state.items() if v.get('last_alert', 0) > cutoff}
    save_state(state)

    print(f'  완료: 이메일 {"✅" if email_ok else "❌"}, PushPlus ✅')


if __name__ == '__main__':
    main()
