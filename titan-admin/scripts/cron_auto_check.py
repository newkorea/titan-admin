#!/usr/bin/env python3
"""
매일 아침 7시(KST) 자동 실행 — Gemini/ChatGPT 가용성 체크 후 is_auto 갱신
- Gemini 차단(cn/hk/ru) 또는 ChatGPT 실패(!=200) → is_auto=0 후보
- 단, is_auto=1 서버가 최소 MIN_AUTO_SERVERS개 이상 유지되도록 보장
- 결과를 이메일로 발송
"""
import os, sys, logging, datetime, time, concurrent.futures, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

from django.conf import settings as djsettings
from django.db import connections
from backend.djangoapps.common.views import dictfetchall
import paramiko

# ─── 설정 ───
MIN_AUTO_SERVERS = 15          # is_auto=1 최소 유지 개수
SSH_USER = 'root'
SSH_PASS = 'ss135690'
SSH_TIMEOUT = 5
CMD_TIMEOUT = 35
MAX_WORKERS = 12
SSH_RETRIES = 3                # SSH 실패시 재시도 횟수
SSH_RETRY_DELAY = 3            # 재시도 간격(초)
GEMINI_BLOCKED_GEOS = {'cn', 'hk', 'ru'}
MAIL_TO = 'softcan@naver.com'

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'auto_check.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('auto_check')

# ─── SSH 스크립트 (어드민 페이지와 동일 로직) ───
SSH_SCRIPT = r'''
UA="Mozilla/5.0 Chrome/131"
if ip link show eth1 >/dev/null 2>&1; then
  HAS=Y
  iptables -t mangle -I OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
  GEO=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 12 "https://gemini.google.com" 2>/dev/null | grep -oP '"[a-z]{2}"' | head -1 | tr -d '"')
  iptables -t mangle -D OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
else
  HAS=N
  GEO=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 12 "https://gemini.google.com" 2>/dev/null | grep -oP '"[a-z]{2}"' | head -1 | tr -d '"')
fi
[ -z "$GEO" ] && GEO=EMPTY
CGP=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 10 -o /dev/null -w "%{http_code}" "https://chatgpt.com" 2>/dev/null)
echo "ETH1=$HAS|GEO=$GEO|CHATGPT=$CGP"
'''


def check_server(name, ip):
    """SSH로 서버에 접속하여 Gemini GEO + ChatGPT 상태 체크 (최대 3회 재시도)
    SSH 실패뿐 아니라 체크 결과가 FAIL이어도 재시도하여 일시적 오류를 걸러냄"""
    last_result = None
    last_err = None

    for attempt in range(1, SSH_RETRIES + 1):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=SSH_USER, password=SSH_PASS,
                           timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
            stdin, stdout, stderr = client.exec_command(SSH_SCRIPT, timeout=CMD_TIMEOUT)
            output = stdout.read().decode().strip()
            client.close()

            parts = {}
            for p in output.split('|'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    parts[k] = v.strip()

            geo = parts.get('GEO', 'EMPTY')
            chatgpt = parts.get('CHATGPT', '000')

            gemini_ok = geo.lower() not in GEMINI_BLOCKED_GEOS and geo not in ('EMPTY', 'UNKNOWN', '')
            chatgpt_ok = chatgpt == '200' or chatgpt == '302'
            both_ok = gemini_ok and chatgpt_ok

            last_result = {
                'name': name, 'ip': ip,
                'geo': geo, 'chatgpt': chatgpt,
                'gemini_ok': gemini_ok, 'chatgpt_ok': chatgpt_ok,
                'both_ok': both_ok,
                'error': None,
            }
            last_err = None

            # 성공(both OK) → 즉시 반환, 재시도 불필요
            if both_ok:
                if attempt > 1:
                    log.info(f"  {name} ({ip}): OK on attempt {attempt}")
                return last_result

            # FAIL이지만 아직 재시도 가능 → 다시 시도
            if attempt < SSH_RETRIES:
                reasons = []
                if not gemini_ok:
                    reasons.append(f"Gemini:{geo}")
                if not chatgpt_ok:
                    reasons.append(f"ChatGPT:{chatgpt}")
                log.warning(f"  {name} ({ip}): attempt {attempt}/{SSH_RETRIES} FAIL ({', '.join(reasons)}), retrying in {SSH_RETRY_DELAY}s")
                time.sleep(SSH_RETRY_DELAY)
            else:
                # 최종 시도도 FAIL → 그 결과를 반환
                log.info(f"  {name} ({ip}): FAIL confirmed after {SSH_RETRIES} attempts (Gemini:{geo}, ChatGPT:{chatgpt})")

        except Exception as e:
            last_err = str(e)[:80]
            last_result = None
            if attempt < SSH_RETRIES:
                log.warning(f"  {name} ({ip}): attempt {attempt}/{SSH_RETRIES} SSH error — {last_err}, retrying in {SSH_RETRY_DELAY}s")
                time.sleep(SSH_RETRY_DELAY)
            else:
                log.error(f"  {name} ({ip}): all {SSH_RETRIES} attempts failed — {last_err}")

    # 마지막 시도 결과 반환 (FAIL 또는 ERROR)
    if last_result:
        return last_result
    return {
        'name': name, 'ip': ip,
        'geo': 'ERROR', 'chatgpt': 'ERROR',
        'gemini_ok': False, 'chatgpt_ok': False,
        'both_ok': False,
        'error': f'{last_err} ({SSH_RETRIES}x)',
    }


def main():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log.info(f"{'='*60}")
    log.info(f"Auto-check started at {now}")

    cursor = connections['default'].cursor()

    # 1) 활성 서버 목록 조회
    cursor.execute("SELECT id, hostip, name, is_auto FROM tbl_agent3 WHERE is_active=1 ORDER BY name")
    servers = dictfetchall(cursor)
    log.info(f"Active servers: {len(servers)}")

    # 2) 병렬 체크
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(check_server, s['name'], s['hostip']): s
            for s in servers
        }
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda x: x['name'])

    # 3) 결과 로깅
    ok_servers = [r for r in results if r['both_ok']]
    fail_servers = [r for r in results if not r['both_ok']]

    log.info(f"Check results: OK={len(ok_servers)}, FAIL={len(fail_servers)}")
    for r in results:
        status = 'OK' if r['both_ok'] else 'FAIL'
        reason = ''
        if r['error']:
            reason = f" (ERROR: {r['error']})"
        elif not r['gemini_ok']:
            reason += f" (Gemini:{r['geo']})"
        if not r['chatgpt_ok'] and not r['error']:
            reason += f" (ChatGPT:{r['chatgpt']})"
        log.info(f"  {r['name']:<20} {r['ip']:<18} {status}{reason}")

    # 4) is_auto 결정
    #    - 체크 OK → is_auto=1 후보
    #    - 체크 FAIL → is_auto=0 후보
    #    - 단, 에러(SSH 실패 등)인 서버는 기존 상태 유지 (건드리지 않음)
    server_map = {s['hostip']: s for s in servers}

    # OK 서버 → is_auto=1로 설정
    auto_on_ips = [r['ip'] for r in ok_servers]
    # FAIL 서버 (에러 제외) → is_auto=0 후보
    auto_off_candidates = [r for r in fail_servers if r['error'] is None]
    # 에러 서버 → 기존 상태 유지
    error_servers = [r for r in fail_servers if r['error'] is not None]

    # 현재 is_auto=1인 에러 서버 수 (유지됨)
    error_auto_count = sum(
        1 for r in error_servers
        if server_map.get(r['ip'], {}).get('is_auto') == 1
    )

    total_auto_if_all_applied = len(auto_on_ips) + error_auto_count

    log.info(f"Plan: auto_on={len(auto_on_ips)}, auto_off_candidates={len(auto_off_candidates)}, "
             f"error_keep={len(error_servers)} (auto1={error_auto_count})")

    # 5) 최소 보장 체크
    if total_auto_if_all_applied < MIN_AUTO_SERVERS:
        # FAIL 서버 중 일부를 is_auto=1로 유지해야 함
        need = MIN_AUTO_SERVERS - total_auto_if_all_applied
        log.info(f"MIN guarantee: need {need} more from fail servers")

        # 기존에 is_auto=1이었던 FAIL 서버를 우선 유지 (기존 운영 중이던 서버)
        existing_auto1_fails = [
            r for r in auto_off_candidates
            if server_map.get(r['ip'], {}).get('is_auto') == 1
        ]
        # Gemini만 실패(ChatGPT는 OK)인 서버를 우선 유지
        gemini_only_fail = [r for r in existing_auto1_fails if r['chatgpt_ok']]
        chatgpt_only_fail = [r for r in existing_auto1_fails if r['gemini_ok']]
        both_fail = [r for r in existing_auto1_fails if not r['gemini_ok'] and not r['chatgpt_ok']]

        # 우선순위: ChatGPT만 실패 > Gemini만 실패 > 둘 다 실패
        keep_pool = chatgpt_only_fail + gemini_only_fail + both_fail
        keep_ips = set()
        for r in keep_pool:
            if len(keep_ips) >= need:
                break
            keep_ips.add(r['ip'])
            log.info(f"  Keeping {r['name']} ({r['ip']}) as auto=1 for MIN guarantee")

        # 유지 대상은 auto_off에서 제외, auto_on에 추가
        auto_off_candidates = [r for r in auto_off_candidates if r['ip'] not in keep_ips]
        auto_on_ips.extend(keep_ips)

    auto_off_ips = [r['ip'] for r in auto_off_candidates]

    # 6) DB 업데이트
    updated_on = 0
    updated_off = 0

    if auto_on_ips:
        ph = ','.join(['%s'] * len(auto_on_ips))
        cursor.execute(
            f"UPDATE tbl_agent3 SET is_auto=1 WHERE hostip IN ({ph}) AND is_auto=0 AND is_active=1",
            auto_on_ips
        )
        updated_on = cursor.rowcount

    if auto_off_ips:
        ph = ','.join(['%s'] * len(auto_off_ips))
        cursor.execute(
            f"UPDATE tbl_agent3 SET is_auto=0 WHERE hostip IN ({ph}) AND is_auto=1 AND is_active=1",
            auto_off_ips
        )
        updated_off = cursor.rowcount

    # 7) 최종 상태 확인
    cursor.execute("SELECT COUNT(*) as cnt FROM tbl_agent3 WHERE is_active=1 AND is_auto=1")
    final_auto = dictfetchall(cursor)[0]['cnt']

    log.info(f"DB updated: +auto_on={updated_on}, -auto_off={updated_off}")
    log.info(f"Final is_auto=1 count: {final_auto}")

    if final_auto < MIN_AUTO_SERVERS:
        log.warning(f"WARNING: is_auto=1 count ({final_auto}) < MIN ({MIN_AUTO_SERVERS})!")

    log.info(f"Auto-check completed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"{'='*60}")

    # stdout 요약 (cron 메일 또는 수동 실행시)
    summary = (f"[{now}] Checked {len(servers)} servers. "
               f"OK={len(ok_servers)} FAIL={len(fail_servers)} "
               f"Updated: on={updated_on} off={updated_off} "
               f"Final auto={final_auto}")
    print(summary)

    # 8) 이메일 발송
    try:
        send_report_email(now, results, ok_servers, fail_servers,
                          updated_on, updated_off, final_auto, server_map)
        log.info("Email sent successfully")
    except Exception as e:
        log.error(f"Email send failed: {e}")
        print(f"Email error: {e}")


def send_report_email(now, results, ok_servers, fail_servers,
                      updated_on, updated_off, final_auto, server_map):
    """HTML 이메일 결과 리포트 발송"""
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    subject = f'[TitanVPN] 서버 자동점검 결과 — {date_str} (auto={final_auto})'

    # 서버별 HTML 행 생성
    rows_html = ''
    for r in results:
        prev_auto = server_map.get(r['ip'], {}).get('is_auto', '?')

        if r['error']:
            geo_cell = f'<td style="color:#999">ERROR</td>'
            cgp_cell = f'<td style="color:#999">ERROR</td>'
        else:
            geo = r['geo']
            if geo.lower() in GEMINI_BLOCKED_GEOS:
                geo_cell = f'<td style="color:#e74c3c;font-weight:bold">🚫 {geo}</td>'
            elif geo == 'EMPTY':
                geo_cell = f'<td style="color:#f39c12">⚠ {geo}</td>'
            else:
                geo_cell = f'<td style="color:#27ae60">✅ {geo}</td>'

            cgp = r['chatgpt']
            if cgp in ('200', '302'):
                cgp_cell = f'<td style="color:#27ae60">✅ {cgp}</td>'
            else:
                cgp_cell = f'<td style="color:#e74c3c;font-weight:bold">❌ {cgp}</td>'

        if r['both_ok']:
            status = '<span style="color:#27ae60;font-weight:bold">OK</span>'
            new_auto = 1
        elif r['error']:
            status = '<span style="color:#999">ERROR</span>'
            new_auto = prev_auto  # 유지
        else:
            status = '<span style="color:#e74c3c;font-weight:bold">FAIL</span>'
            new_auto = 0

        # 변경 표시
        if prev_auto != new_auto and prev_auto != '?':
            change = f' → <b>{new_auto}</b>' if new_auto == 1 else f' → <b style="color:#e74c3c">{new_auto}</b>'
            auto_cell = f'<td>{prev_auto}{change}</td>'
        else:
            auto_cell = f'<td>{prev_auto}</td>'

        rows_html += f'''<tr>
            <td>{r['name']}</td><td>{r['ip']}</td>
            {geo_cell}{cgp_cell}
            <td>{status}</td>{auto_cell}
        </tr>\n'''

    html = f'''
    <html><body style="font-family:Arial,sans-serif;font-size:13px;color:#333">
    <h2 style="color:#2c3e50">🔍 TitanVPN 서버 자동점검 리포트</h2>
    <p style="color:#7f8c8d">{now}</p>

    <table style="border:1px solid #ddd;padding:8px;margin-bottom:15px">
      <tr><td style="padding:4px 12px"><b>총 서버</b></td><td>{len(results)}</td></tr>
      <tr><td style="padding:4px 12px"><b>Gemini+ChatGPT OK</b></td>
          <td style="color:#27ae60;font-weight:bold">{len(ok_servers)}</td></tr>
      <tr><td style="padding:4px 12px"><b>FAIL</b></td>
          <td style="color:#e74c3c;font-weight:bold">{len(fail_servers)}</td></tr>
      <tr><td style="padding:4px 12px"><b>is_auto ON 변경</b></td><td>+{updated_on}</td></tr>
      <tr><td style="padding:4px 12px"><b>is_auto OFF 변경</b></td><td>-{updated_off}</td></tr>
      <tr><td style="padding:4px 12px"><b>최종 is_auto=1</b></td>
          <td style="font-weight:bold;font-size:15px">{final_auto}</td></tr>
    </table>

    <table style="border-collapse:collapse;width:100%">
      <thead>
        <tr style="background:#34495e;color:white">
          <th style="padding:6px 8px;text-align:left">서버</th>
          <th style="padding:6px 8px;text-align:left">IP</th>
          <th style="padding:6px 8px">Gemini</th>
          <th style="padding:6px 8px">ChatGPT</th>
          <th style="padding:6px 8px">결과</th>
          <th style="padding:6px 8px">is_auto</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <p style="color:#95a5a6;font-size:11px;margin-top:15px">
      최소 유지: {MIN_AUTO_SERVERS}개 | 차단기준: Gemini GEO ∈ {'{'}cn, hk, ru{'}'} 또는 ChatGPT ≠ 200/302
    </p>
    </body></html>
    '''

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = djsettings.SMTP_EMAIL
    msg['To'] = MAIL_TO
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    with smtplib.SMTP_SSL(djsettings.SMTP_HOST, djsettings.SMTP_PORT) as smtp:
        smtp.login(djsettings.SMTP_ID, djsettings.SMTP_PW)
        smtp.sendmail(djsettings.SMTP_EMAIL, [MAIL_TO], msg.as_string())

    log.info(f"Report email sent to {MAIL_TO}")


if __name__ == '__main__':
    main()
