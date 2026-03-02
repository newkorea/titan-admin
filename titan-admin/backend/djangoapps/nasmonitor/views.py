# NAS 모니터링 — NAS 장비 상태 모니터링, 알림
import json
import os
import socket
import subprocess
import threading
import time
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from backend.djangoapps.common.views import allow_admin, dictfetchall

# 인증서 갱신 진행 상태 추적 (서버명 → 상태)
_cert_renew_status = {}
_cert_renew_lock = threading.Lock()

# 수동 NAS 점검 진행 상태
_nas_check_status = {'running': False, 'result': None, 'started': None}
_nas_check_lock = threading.Lock()

# Cron 관리 진행 상태
_cron_task_status = {'running': False, 'result': None, 'started': None, 'task': None}
_cron_task_lock = threading.Lock()

# DNS 해석 캐시 (호스트명 → IP) — V2RAY가 nasipaddress에 호스트명을 보내는 문제 대응
_dns_cache = {}


def _calc_session_time(sess_time, nasporttype, start_time, stop_time):
    """V2RAY는 acctsessiontime이 항상 NULL이므로 TIMESTAMPDIFF로 계산.
    다른 프로토콜은 기존 acctsessiontime 사용."""
    if nasporttype == 'V2RAY' or (nasporttype or '') == 'V2RAY':
        if start_time and stop_time:
            diff = (stop_time - start_time).total_seconds()
            return int(diff)
        elif start_time and not stop_time:
            # 현재 활성 세션 — 시작시간부터 현재까지
            from datetime import datetime
            diff = (datetime.now() - start_time).total_seconds()
            return int(diff)
        return 0
    return sess_time or 0

def _resolve_nas(nasip, nas_map):
    """nasipaddress를 서버명으로 변환. 호스트명이면 DNS 조회 후 nas_map 재검색."""
    if nasip in nas_map:
        return nas_map[nasip]
    # 이미 캐시에 있으면 사용
    if nasip in _dns_cache:
        return nas_map.get(_dns_cache[nasip], nasip)
    # IP 형식이 아니면 (호스트명) DNS 조회 시도
    if not all(c.isdigit() or c == '.' for c in nasip):
        try:
            resolved = socket.gethostbyname(nasip)
            _dns_cache[nasip] = resolved
            return nas_map.get(resolved, nasip)
        except Exception:
            _dns_cache[nasip] = nasip
    return nasip


# ===== PAGE: NAS 서버 현황 =====
@allow_admin
def nas_status(request):
    """NAS 서버 모니터링 현황 페이지"""
    return render(request, 'admin/nas_status.html', {})


# ===== API: 최신 모니터링 데이터 =====
@allow_admin
def api_read_nas_status(request):
    """최신 health + service 체크 결과 반환"""
    cursor = connections['default'].cursor()

    # 최신 health 체크
    cursor.execute("""
        SELECT id, check_time, check_type, total_servers, ok_count, warning_count, critical_count, report_json
        FROM tbl_nas_monitor_log
        WHERE check_type = 'health'
        ORDER BY check_time DESC
        LIMIT 1
    """)
    health_rows = dictfetchall(cursor)

    # 최신 service 체크
    cursor.execute("""
        SELECT id, check_time, check_type, total_servers, ok_count, warning_count, critical_count, report_json
        FROM tbl_nas_monitor_log
        WHERE check_type = 'service'
        ORDER BY check_time DESC
        LIMIT 1
    """)
    service_rows = dictfetchall(cursor)

    health = None
    if health_rows:
        h = health_rows[0]
        health = {
            'check_time': h['check_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'total': h['total_servers'],
            'ok': h['ok_count'],
            'warning': h['warning_count'],
            'critical': h['critical_count'],
            'servers': json.loads(h['report_json']).get('servers', []) if h['report_json'] else [],
        }

    service = None
    if service_rows:
        s = service_rows[0]
        service = {
            'check_time': s['check_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'total': s['total_servers'],
            'ok': s['ok_count'],
            'warning': s['warning_count'],
            'critical': s['critical_count'],
            'servers': json.loads(s['report_json']).get('servers', []) if s['report_json'] else [],
        }

    # ESXi 호스트 매핑 (IP → esxi_host)
    cursor.execute("SELECT hostip, esxi_host FROM tbl_agent3 WHERE is_active=1 AND esxi_host IS NOT NULL AND esxi_host != ''")
    esxi_map = {row['hostip']: row['esxi_host'] for row in dictfetchall(cursor)}

    return JsonResponse({'result': 200, 'health': health, 'service': service, 'esxi_map': esxi_map})


# ===== API: NAS 서버 이슈 건수 (메뉴 뱃지용) =====
@allow_admin
def api_read_nas_issue_count(request):
    """최신 health/service 체크에서 WARNING/CRITICAL 건수 반환"""
    cursor = connections['default'].cursor()
    warning = 0
    critical = 0
    for check_type in ('health', 'service'):
        cursor.execute("""
            SELECT warning_count, critical_count
            FROM tbl_nas_monitor_log
            WHERE check_type = %s
            ORDER BY check_time DESC LIMIT 1
        """, [check_type])
        row = cursor.fetchone()
        if row:
            warning += row[0] or 0
            critical += row[1] or 0
    return JsonResponse({
        'result': 200,
        'warning': warning,
        'critical': critical,
        'total_issues': warning + critical,
    })


# ===== API: 이력 데이터 =====
@allow_admin
def api_read_nas_history(request):
    """최근 30일 체크 이력 (요약만, 서버 상세 제외)"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT id, check_time, check_type, total_servers, ok_count, warning_count, critical_count
        FROM tbl_nas_monitor_log
        WHERE check_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY check_time ASC
    """)
    rows = dictfetchall(cursor)
    data = []
    for r in rows:
        data.append({
            'id': r['id'],
            'check_time': r['check_time'].strftime('%Y-%m-%d %H:%M'),
            'check_type': r['check_type'],
            'total': r['total_servers'],
            'ok': r['ok_count'],
            'warning': r['warning_count'],
            'critical': r['critical_count'],
        })
    return JsonResponse({'result': 200, 'data': data})


# ===== PAGE: 서버 배정 현황 =====
@allow_admin
def nas_assignment(request):
    """중국 통신사별 NAS 서버 배정 현황 페이지"""
    return render(request, 'admin/nas_assignment.html', {})


# ===== API: 서버 배정 현황 데이터 =====
@allow_admin
def api_read_nas_assignment(request):
    """중국 3대 통신사별 ping 순위 + 접속자수 기반 서버 배정 현황"""
    cursor = connections['default'].cursor()

    MAX_CONN = 50
    telecoms = [
        ('ct', 'China Telecom', '#e74c3c'),
        ('cm', 'China Mobile', '#3498db'),
        ('cu', 'China Unicom', '#2ecc71'),
    ]
    result = {}

    for tc_code, tc_name, tc_color in telecoms:
        cursor.execute("""
            SELECT
                t1.name, t1.hostip, t1.telecom AS kr_isp,
                t1.is_auto,
                t1.protocol,
                COALESCE(ping.ping_avg, NULL) AS ping_avg,
                COALESCE(ping.ping_min, NULL) AS ping_min,
                COALESCE(ping.ping_max, NULL) AS ping_max,
                COALESCE(conn.cnt, 0) AS conn_count,
                CASE WHEN ping.ping_avg IS NOT NULL
                     THEN ROUND(ping.ping_avg * 0.7 + COALESCE(conn.cnt, 0) * 0.3, 1)
                     ELSE NULL END AS score,
                ping.check_time
            FROM titan.tbl_agent3 t1
            LEFT JOIN (
                SELECT p.server_ip, p.ping_avg, p.ping_min, p.ping_max, p.check_time
                FROM titan.tbl_server_telecom_ping p
                INNER JOIN (
                    SELECT server_ip, cn_telecom, MAX(check_time) AS max_ct, MAX(id) AS max_id
                    FROM titan.tbl_server_telecom_ping
                    WHERE check_time > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    AND cn_telecom = %s
                    GROUP BY server_ip, cn_telecom
                ) latest ON p.server_ip = latest.server_ip AND p.id = latest.max_id
                    AND p.cn_telecom = %s
            ) ping ON t1.hostip = ping.server_ip
            LEFT JOIN (
                SELECT nasipaddress, COUNT(*) AS cnt
                FROM radius.radacct WHERE acctstoptime IS NULL
                GROUP BY nasipaddress
            ) conn ON t1.hostip = conn.nasipaddress
            WHERE t1.is_active = 1 AND t1.is_status = 1
            ORDER BY
                t1.is_auto DESC,
                CASE WHEN ping.ping_avg IS NOT NULL
                     THEN ping.ping_avg * 0.7 + COALESCE(conn.cnt, 0) * 0.3
                     ELSE 99999 END ASC
        """, [tc_code, tc_code])
        rows = dictfetchall(cursor)

        servers = []
        rank = 0
        for r in rows:
            is_assignable = (r['is_auto'] == 1 and r['ping_avg'] is not None
                             and r['conn_count'] < MAX_CONN)
            if is_assignable:
                rank += 1
                display_rank = rank
            else:
                display_rank = None

            servers.append({
                'rank': display_rank,
                'name': r['name'],
                'ip': r['hostip'],
                'protocol': r['protocol'],
                'kr_isp': r['kr_isp'],
                'is_auto': r['is_auto'],
                'ping_avg': float(r['ping_avg']) if r['ping_avg'] is not None else None,
                'ping_min': float(r['ping_min']) if r['ping_min'] is not None else None,
                'ping_max': float(r['ping_max']) if r['ping_max'] is not None else None,
                'conn_count': r['conn_count'],
                'score': float(r['score']) if r['score'] is not None else None,
                'is_assignable': is_assignable,
                'check_time': r['check_time'].strftime('%Y-%m-%d %H:%M:%S') if r['check_time'] else None,
            })

        # 배정 1위 서버
        top = next((s for s in servers if s['rank'] == 1), None)

        result[tc_code] = {
            'name': tc_name,
            'color': tc_color,
            'servers': servers,
            'top_server': top,
            'assignable_count': sum(1 for s in servers if s['is_assignable']),
            'total_count': len(servers),
        }

    # 마지막 측정 시간
    cursor.execute("""
        SELECT MAX(check_time) AS last_check FROM titan.tbl_server_telecom_ping
    """)
    lc = dictfetchall(cursor)
    last_check = lc[0]['last_check'].strftime('%Y-%m-%d %H:%M:%S') if lc and lc[0]['last_check'] else None

    return JsonResponse({
        'result': 200,
        'telecoms': result,
        'last_check': last_check,
        'max_conn': MAX_CONN,
    })


# ===== API: is_auto 토글 =====
@allow_admin
def api_toggle_is_auto(request):
    """tbl_agent3.is_auto 값 토글 (1→0 / 0→1)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})
    server_name = request.POST.get('name', '')
    if not server_name:
        return JsonResponse({'result': 400, 'msg': 'name required'})
    cursor = connections['default'].cursor()
    cursor.execute(
        "UPDATE titan.tbl_agent3 SET is_auto = IF(is_auto=1, 0, 1) WHERE name = %s",
        [server_name]
    )
    if cursor.rowcount == 0:
        return JsonResponse({'result': 404, 'msg': 'server not found'})
    cursor.execute("SELECT is_auto FROM titan.tbl_agent3 WHERE name = %s", [server_name])
    row = cursor.fetchone()
    new_is_auto = row[0]

    # is_auto가 1(ON)로 변경되면 → 해당 서버 ping 측정 트리거 (aws13에서 비동기 실행)
    ping_triggered = False
    if new_is_auto == 1:
        try:
            subprocess.Popen(
                'ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan/scripts && '
                '/home/newkorea/project/titan/.venv310/bin/python3 cn_telecom_ping.py '
                f'--server {server_name}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ping_triggered = True
        except Exception:
            ping_triggered = False

    return JsonResponse({
        'result': 200, 'name': server_name,
        'is_auto': new_is_auto, 'ping_triggered': ping_triggered,
    })


# ===== API: 수동 NAS 점검 트리거 =====
@allow_admin
def api_nas_manual_check(request):
    """수동으로 NAS 서버 점검 실행 (aws13에서 nas_daily_check.py 실행)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    import time
    with _nas_check_lock:
        if _nas_check_status['running']:
            return JsonResponse({'result': 409, 'msg': '이미 점검이 진행 중입니다.'})
        _nas_check_status['running'] = True
        _nas_check_status['result'] = None
        _nas_check_status['started'] = time.time()

    def run_check():
        import time as _time
        try:
            cmd = (
                'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan && '
                '.venv310/bin/python3 scripts/nas_daily_check.py"'
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=600
            )
            with _nas_check_lock:
                _nas_check_status['running'] = False
                _nas_check_status['result'] = {
                    'success': result.returncode == 0,
                    'message': result.stdout[-500:] if result.stdout else result.stderr[-500:],
                    'elapsed': round(_time.time() - _nas_check_status['started'], 1),
                }
        except subprocess.TimeoutExpired:
            with _nas_check_lock:
                _nas_check_status['running'] = False
                _nas_check_status['result'] = {'success': False, 'message': '타임아웃 (600초)'}
        except Exception as e:
            with _nas_check_lock:
                _nas_check_status['running'] = False
                _nas_check_status['result'] = {'success': False, 'message': str(e)}

    t = threading.Thread(target=run_check, daemon=True)
    t.start()

    return JsonResponse({'result': 200, 'msg': 'NAS 서버 점검을 시작했습니다.'})


# ===== API: 수동 NAS 점검 상태 확인 =====
@allow_admin
def api_nas_manual_check_status(request):
    """수동 NAS 점검 진행 상태 조회"""
    import time
    with _nas_check_lock:
        running = _nas_check_status['running']
        result = _nas_check_status.get('result')
        started = _nas_check_status.get('started')

    elapsed = round(time.time() - started, 1) if started and running else None

    return JsonResponse({
        'result': 200,
        'running': running,
        'elapsed': elapsed,
        'data': result,
    })


# ===== API: 인증서 수동 갱신 =====
@allow_admin
def api_cert_renew(request):
    """단일 서버 인증서 수동 갱신 트리거 (aws13에서 실행)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    server_name = request.POST.get('name', '')
    if not server_name:
        return JsonResponse({'result': 400, 'msg': 'name required'})

    # 이미 갱신 중인지 확인
    with _cert_renew_lock:
        status = _cert_renew_status.get(server_name, {})
        if status.get('running'):
            return JsonResponse({
                'result': 409, 'msg': f'{server_name} 갱신이 이미 진행 중입니다.',
                'name': server_name,
            })
        _cert_renew_status[server_name] = {'running': True, 'result': None}

    def run_renewal():
        try:
            cmd = (
                'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan/scripts && '
                '/home/newkorea/project/titan/.venv310/bin/python3 cert_auto_renew.py '
                f'--server {server_name}"'
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            import json as _json
            try:
                data = _json.loads(result.stdout.strip().split('\n')[-1])
            except Exception:
                data = {
                    'success': False,
                    'message': result.stdout[-500:] if result.stdout else result.stderr[-500:],
                }
            with _cert_renew_lock:
                _cert_renew_status[server_name] = {'running': False, 'result': data}
        except subprocess.TimeoutExpired:
            with _cert_renew_lock:
                _cert_renew_status[server_name] = {
                    'running': False,
                    'result': {'success': False, 'message': '타임아웃 (300초)'}
                }
        except Exception as e:
            with _cert_renew_lock:
                _cert_renew_status[server_name] = {
                    'running': False,
                    'result': {'success': False, 'message': str(e)}
                }

    # 백그라운드 스레드로 실행 (HTTP 응답은 즉시 반환)
    t = threading.Thread(target=run_renewal, daemon=True)
    t.start()

    return JsonResponse({
        'result': 200,
        'msg': f'{server_name} 인증서 갱신을 시작했습니다.',
        'name': server_name,
    })


# ===== API: 인증서 갱신 상태 확인 =====
@allow_admin
def api_cert_renew_status(request):
    """인증서 갱신 진행 상태 조회"""
    server_name = request.GET.get('name', '')
    if not server_name:
        return JsonResponse({'result': 400, 'msg': 'name required'})

    with _cert_renew_lock:
        status = _cert_renew_status.get(server_name)

    if not status:
        return JsonResponse({'result': 404, 'msg': '갱신 기록 없음', 'name': server_name})

    return JsonResponse({
        'result': 200,
        'name': server_name,
        'running': status['running'],
        'data': status.get('result'),
    })


# ===== PAGE: NAS Cron 관리 =====
@allow_admin
def nas_cron(request):
    """NAS 중앙 Cron 관리 페이지"""
    return render(request, 'admin/nas_cron.html', {})


# ===== API: Cron 실행 이력 조회 =====
@allow_admin
def api_read_cron_logs(request):
    """최근 cron 실행 이력 반환"""
    task_type = request.GET.get('task_type', '')
    days = int(request.GET.get('days', 30))
    cursor = connections['default'].cursor()

    if task_type:
        cursor.execute("""
            SELECT id, run_time, task_type, total_servers, success_count,
                   fail_count, skip_count, report_json, elapsed_sec
            FROM tbl_nas_cron_log
            WHERE task_type = %s AND run_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY run_time DESC
            LIMIT 100
        """, [task_type, days])
    else:
        cursor.execute("""
            SELECT id, run_time, task_type, total_servers, success_count,
                   fail_count, skip_count, report_json, elapsed_sec
            FROM tbl_nas_cron_log
            WHERE run_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY run_time DESC
            LIMIT 100
        """, [days])

    rows = dictfetchall(cursor)
    data = []
    for r in rows:
        item = {
            'id': r['id'],
            'run_time': r['run_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'task_type': r['task_type'],
            'total': r['total_servers'],
            'success': r['success_count'],
            'fail': r['fail_count'],
            'skip': r['skip_count'],
            'elapsed': r['elapsed_sec'],
        }
        data.append(item)
    return JsonResponse({'result': 200, 'data': data})


# ===== API: Cron 실행 상세 조회 =====
@allow_admin
def api_read_cron_detail(request):
    """특정 cron 실행 상세 (서버별 리포트) 반환"""
    log_id = request.GET.get('id', '')
    if not log_id:
        return JsonResponse({'result': 400, 'msg': 'id required'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT id, run_time, task_type, total_servers, success_count,
               fail_count, skip_count, report_json, elapsed_sec
        FROM tbl_nas_cron_log WHERE id = %s
    """, [log_id])
    rows = dictfetchall(cursor)
    if not rows:
        return JsonResponse({'result': 404, 'msg': 'Not found'})

    r = rows[0]
    report = json.loads(r['report_json']) if r['report_json'] else {}

    return JsonResponse({
        'result': 200,
        'data': {
            'id': r['id'],
            'run_time': r['run_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'task_type': r['task_type'],
            'total': r['total_servers'],
            'success': r['success_count'],
            'fail': r['fail_count'],
            'skip': r['skip_count'],
            'elapsed': r['elapsed_sec'],
            'report': report,
        }
    })


# ===== API: 최신 작업별 결과 요약 =====
@allow_admin
def api_read_cron_latest(request):
    """각 task_type별 최신 실행 결과 반환"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT t1.id, t1.run_time, t1.task_type, t1.total_servers,
               t1.success_count, t1.fail_count, t1.skip_count,
               t1.report_json, t1.elapsed_sec
        FROM tbl_nas_cron_log t1
        INNER JOIN (
            SELECT task_type, MAX(run_time) AS max_time
            FROM tbl_nas_cron_log
            GROUP BY task_type
        ) t2 ON t1.task_type = t2.task_type AND t1.run_time = t2.max_time
        ORDER BY t1.task_type
    """)
    rows = dictfetchall(cursor)
    data = {}
    for r in rows:
        report = json.loads(r['report_json']) if r['report_json'] else {}
        data[r['task_type']] = {
            'id': r['id'],
            'run_time': r['run_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'total': r['total_servers'],
            'success': r['success_count'],
            'fail': r['fail_count'],
            'skip': r['skip_count'],
            'elapsed': r['elapsed_sec'],
            'servers': report.get('servers', []),
        }
    return JsonResponse({'result': 200, 'data': data})


# ===== API: Cron 이슈 건수 (메뉴 뱃지용) =====
@allow_admin
def api_read_cron_issue_count(request):
    """최신 cron_audit에서 WARNING/CRITICAL 건수 반환 (메뉴 뱃지용)"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT report_json FROM tbl_nas_cron_log
        WHERE task_type = 'cron_audit'
        ORDER BY run_time DESC LIMIT 1
    """)
    row = cursor.fetchone()
    warning = 0
    critical = 0
    if row and row[0]:
        try:
            report = json.loads(row[0])
            for s in report.get('servers', []):
                st = s.get('status', '')
                if st == 'warning':
                    warning += 1
                elif st in ('critical', 'fail'):
                    critical += 1
        except:
            pass
    return JsonResponse({
        'result': 200,
        'warning': warning,
        'critical': critical,
        'total_issues': warning + critical,
    })


# ===== API: Cron 작업 실행 트리거 =====
@allow_admin
def api_run_cron_task(request):
    """수동으로 cron 관리 작업 실행 (aws13에서 nas_cron_manager.py)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    task_name = request.POST.get('task', 'all_maintenance')
    valid_tasks = ['log_cleanup', 'journal_vacuum', 'packet_log_cleanup',
                   'cron_audit', 'cron_standardize', 'all_maintenance']
    if task_name not in valid_tasks:
        return JsonResponse({'result': 400, 'msg': f'Invalid task: {task_name}'})

    with _cron_task_lock:
        if _cron_task_status['running']:
            return JsonResponse({
                'result': 409,
                'msg': f"이미 '{_cron_task_status['task']}' 작업이 진행 중입니다."
            })
        _cron_task_status['running'] = True
        _cron_task_status['result'] = None
        _cron_task_status['started'] = time.time()
        _cron_task_status['task'] = task_name

    def run_cron():
        try:
            cmd = (
                'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan && '
                f'.venv310/bin/python3 scripts/nas_cron_manager.py --task {task_name} --json"'
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=600
            )
            with _cron_task_lock:
                _cron_task_status['running'] = False
                _cron_task_status['result'] = {
                    'success': result.returncode == 0,
                    'task': task_name,
                    'message': result.stdout[-1000:] if result.stdout else result.stderr[-500:],
                    'elapsed': round(time.time() - _cron_task_status['started'], 1),
                }
        except subprocess.TimeoutExpired:
            with _cron_task_lock:
                _cron_task_status['running'] = False
                _cron_task_status['result'] = {
                    'success': False, 'task': task_name,
                    'message': '타임아웃 (600초)'
                }
        except Exception as e:
            with _cron_task_lock:
                _cron_task_status['running'] = False
                _cron_task_status['result'] = {
                    'success': False, 'task': task_name,
                    'message': str(e)
                }

    t = threading.Thread(target=run_cron, daemon=True)
    t.start()

    return JsonResponse({
        'result': 200,
        'msg': f"'{task_name}' 작업을 시작했습니다.",
        'task': task_name,
    })


# ===== API: Cron 작업 진행 상태 =====
@allow_admin
def api_cron_task_status(request):
    """cron 작업 진행 상태 조회"""
    with _cron_task_lock:
        running = _cron_task_status['running']
        result = _cron_task_status.get('result')
        started = _cron_task_status.get('started')
        task = _cron_task_status.get('task')

    elapsed = round(time.time() - started, 1) if started and running else None

    return JsonResponse({
        'result': 200,
        'running': running,
        'task': task,
        'elapsed': elapsed,
        'data': result,
    })


# ===== API: 서버별 프로토콜별 접속 실패 건수 (최근 1시간) =====
@allow_admin
def api_read_server_failures(request):
    """최근 1시간 tbl_agent_failed 에서 서버별/프로토콜별 실패 건수 반환"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT server_name,
               SUM(CASE WHEN server_protocol='IKEV2' THEN 1 ELSE 0 END) AS fail_ikev2,
               SUM(CASE WHEN server_protocol='OPENVPN' THEN 1 ELSE 0 END) AS fail_openvpn,
               SUM(CASE WHEN server_protocol='V2RAY' THEN 1 ELSE 0 END) AS fail_v2ray,
               SUM(CASE WHEN server_protocol='SSTP' THEN 1 ELSE 0 END) AS fail_sstp,
               COUNT(*) AS fail_total
        FROM tbl_agent_failed
        WHERE failed_time >= NOW() - INTERVAL 1 HOUR
          AND IFNULL(server_name, '') <> ''
        GROUP BY server_name
    """)
    rows = dictfetchall(cursor)
    # {server_name: {ikev2: N, openvpn: N, ...}}
    data = {}
    for r in rows:
        data[r['server_name']] = {
            'ikev2': int(r['fail_ikev2']),
            'openvpn': int(r['fail_openvpn']),
            'v2ray': int(r['fail_v2ray']),
            'sstp': int(r['fail_sstp']),
            'total': int(r['fail_total']),
        }
    return JsonResponse({'result': 200, 'data': data})


# ===== API: 특정 서버+프로토콜 실패 로그 상세 =====
@allow_admin
def api_read_server_fail_logs(request):
    """특정 서버+프로토콜의 최근 1시간 실패 로그 반환"""
    server_name = request.GET.get('server', '')
    protocol = request.GET.get('protocol', '')
    if not server_name:
        return JsonResponse({'result': 400, 'msg': 'server required'})

    cursor = connections['default'].cursor()
    if protocol:
        cursor.execute("""
            SELECT f.username, f.server_name, f.server_protocol, f.platform,
                   f.app_version, f.user_ip, f.user_location, f.device_info, f.failed_time,
                   IFNULL(a.telecom, '') AS telecom
            FROM tbl_agent_failed f
            LEFT JOIN tbl_agent3 a ON a.name = f.server_name
            WHERE f.failed_time >= NOW() - INTERVAL 1 HOUR
              AND f.server_name = %s AND f.server_protocol = %s
            ORDER BY f.failed_time DESC
            LIMIT 100
        """, [server_name, protocol])
    else:
        cursor.execute("""
            SELECT f.username, f.server_name, f.server_protocol, f.platform,
                   f.app_version, f.user_ip, f.user_location, f.device_info, f.failed_time,
                   IFNULL(a.telecom, '') AS telecom
            FROM tbl_agent_failed f
            LEFT JOIN tbl_agent3 a ON a.name = f.server_name
            WHERE f.failed_time >= NOW() - INTERVAL 1 HOUR
              AND f.server_name = %s
            ORDER BY f.failed_time DESC
            LIMIT 100
        """, [server_name])
    rows = dictfetchall(cursor)
    logs = []
    for r in rows:
        logs.append({
            'username': r['username'],
            'protocol': r['server_protocol'],
            'platform': r['platform'],
            'version': r['app_version'] or '',
            'ip': r['user_ip'] or '',
            'location': r['user_location'] or '',
            'device': r['device_info'] or '',
            'telecom': r['telecom'] or '',
            'time': r['failed_time'].strftime('%H:%M:%S') if r['failed_time'] else '',
        })
    return JsonResponse({'result': 200, 'server': server_name, 'protocol': protocol, 'logs': logs})


# ===== API: NAS 서버 SSH 접속 정보 =====
@allow_admin
def api_read_nas_ssh_info(request):
    """서버 IP로 tbl_agent3에서 SSH 접속 정보(username, password) 조회"""
    ip = request.GET.get('ip', '').strip()
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP가 필요합니다.'})

    cursor = connections['default'].cursor()
    cursor.execute(
        "SELECT username, password, hostip, name FROM tbl_agent3 WHERE hostip = %s LIMIT 1",
        [ip]
    )
    rows = dictfetchall(cursor)
    if not rows:
        return JsonResponse({'result': 404, 'msg': '해당 IP의 서버 정보를 찾을 수 없습니다.'})

    row = rows[0]
    return JsonResponse({
        'result': 200,
        'data': {
            'ip': row['hostip'],
            'username': row['username'] or 'root',
            'password': row['password'] or '',
            'name': row['name'] or '',
        }
    })


# ===== API: 서비스 복구 (재시작) =====
@allow_admin
def api_restart_service(request):
    """실패한 VPN 서비스를 SSH로 재시작"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    ip = request.POST.get('ip', '').strip()
    service = request.POST.get('service', '').strip().upper()

    if not ip or not service:
        return JsonResponse({'result': 400, 'msg': 'IP와 서비스명이 필요합니다.'})

    # 서비스별 재시작 명령어 매핑
    SERVICE_MAP = {
        'IKEV2': {
            'restart': 'systemctl restart strongswan',
            'verify': 'systemctl is-active strongswan',
            'label': 'IKEv2 (StrongSwan)',
        },
        'OPENVPN': {
            'restart': 'systemctl stop openvpn-server@test2; sleep 1; kill -9 $(pgrep -f "openvpn.*test2") 2>/dev/null; sleep 1; systemctl start openvpn-server@test2',
            'verify': 'ss -ulnp | grep -q openvpn && echo active || echo inactive',
            'label': 'OpenVPN',
        },
        'SSTP': {
            'restart': 'systemctl restart vpnserver',
            'verify': 'systemctl is-active vpnserver',
            'label': 'SSTP (SoftEther)',
        },
        'V2RAY': {
            'restart': 'systemctl restart xray',
            'verify': 'systemctl is-active xray',
            'label': 'V2Ray (Xray)',
        },
    }

    if service not in SERVICE_MAP:
        return JsonResponse({'result': 400, 'msg': f'알 수 없는 서비스: {service}'})

    svc = SERVICE_MAP[service]

    # 서버 이름 조회
    cursor = connections['default'].cursor()
    cursor.execute("SELECT name FROM tbl_agent3 WHERE hostip = %s LIMIT 1", [ip])
    row = cursor.fetchone()
    srv_name = row[0] if row else ip

    import paramiko
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username='root', key_filename='/root/.ssh/id_rsa', timeout=15, banner_timeout=20)
        except Exception:
            ssh.connect(ip, username='root', timeout=15, banner_timeout=20)

        # 1) 재시작
        stdin, stdout, stderr = ssh.exec_command(svc['restart'], timeout=30)
        stdout.channel.recv_exit_status()

        # 2) 잠시 대기 후 확인
        import time
        time.sleep(2)
        stdin2, stdout2, stderr2 = ssh.exec_command(svc['verify'], timeout=10)
        result = stdout2.read().decode().strip()
        ssh.close()

        if result == 'active':
            return JsonResponse({
                'result': 200,
                'msg': f'{srv_name} — {svc["label"]} 재시작 성공!'
            })
        else:
            return JsonResponse({
                'result': 500,
                'msg': f'{srv_name} — {svc["label"]} 재시작했으나 상태: {result}'
            })
    except Exception as e:
        return JsonResponse({'result': 500, 'msg': f'SSH 연결 실패: {str(e)[:100]}'})


# ===== API: 서버 재부팅 =====
@allow_admin
def api_reboot_server(request):
    """서버 재부팅 (관리자 로그인 상태만 확인, SSH key 우선 사용)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    ip = request.POST.get('ip', '').strip()

    if not ip:
        return JsonResponse({'result': 400, 'msg': 'IP를 입력해주세요.'})

    # SSH 접속 정보 조회
    cursor = connections['default'].cursor()
    cursor.execute("SELECT username, password, name FROM tbl_agent3 WHERE hostip = %s LIMIT 1", [ip])
    srv = cursor.fetchone()
    if not srv:
        return JsonResponse({'result': 404, 'msg': '서버를 찾을 수 없습니다.'})

    srv_user = srv[0] or 'root'
    srv_pass = srv[1] or ''
    srv_name = srv[2] or ip

    # SSH로 reboot 실행 (key 우선, password fallback)
    import paramiko
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # SSH key 먼저 시도
        try:
            ssh.connect(ip, username='root', key_filename='/root/.ssh/id_rsa', timeout=15, banner_timeout=20)
        except Exception:
            # key 실패 시 password로 재시도
            ssh.connect(ip, username=srv_user, password=srv_pass, timeout=15, banner_timeout=20)
        ssh.exec_command('nohup bash -c "sleep 3 && reboot" &')
        ssh.close()
        return JsonResponse({
            'result': 200,
            'msg': f'{srv_name} ({ip}) 재부팅 명령을 전송했습니다. 약 1~2분 후 복구됩니다.'
        })
    except Exception as e:
        return JsonResponse({'result': 500, 'msg': f'SSH 연결 실패: {str(e)[:100]}'})


# ===== 단일 NAS 서버 재점검 상태 (파일 기반 — uWSGI 워커 간 공유) =====
import tempfile
SINGLE_CHECK_DIR = os.path.join(tempfile.gettempdir(), 'nas_single_check')
os.makedirs(SINGLE_CHECK_DIR, exist_ok=True)


def _single_check_file(ip):
    return os.path.join(SINGLE_CHECK_DIR, ip.replace('.', '_') + '.json')


def _read_single_check(ip):
    fpath = _single_check_file(ip)
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def _write_single_check(ip, data):
    fpath = _single_check_file(ip)
    with open(fpath, 'w') as f:
        json.dump(data, f, ensure_ascii=False)


def _update_db_report(check_type, ip, new_server_data):
    """tbl_nas_monitor_log 최신 레코드에서 해당 IP 서버 데이터 교체"""
    try:
        cursor = connections['default'].cursor()
        cursor.execute("""
            SELECT id, report_json FROM tbl_nas_monitor_log
            WHERE check_type = %s ORDER BY check_time DESC LIMIT 1
        """, [check_type])
        rows = dictfetchall(cursor)
        if not rows or not rows[0]['report_json']:
            return
        report = json.loads(rows[0]['report_json'])
        servers = report.get('servers', [])

        # 해당 IP 서버 찾아서 교체
        updated = False
        for i, sv in enumerate(servers):
            if sv.get('ip') == ip:
                servers[i] = new_server_data
                updated = True
                break
        if not updated:
            return

        # 카운트 재계산
        ok = sum(1 for s in servers if not s.get('criticals') and not s.get('warnings'))
        warning = sum(1 for s in servers if s.get('warnings') and not s.get('criticals'))
        critical = sum(1 for s in servers if s.get('criticals'))

        report['servers'] = servers
        cursor.execute("""
            UPDATE tbl_nas_monitor_log
            SET report_json = %s, ok_count = %s, warning_count = %s, critical_count = %s
            WHERE id = %s
        """, [json.dumps(report, ensure_ascii=True, default=str), ok, warning, critical, rows[0]['id']])
    except Exception as e:
        import logging
        logging.getLogger('nasmonitor').error(f"DB 업데이트 실패: {e}")


# ===== API: 단일 NAS 서버 재점검 트리거 =====
@allow_admin
def api_nas_single_check(request):
    """단일 NAS 서버를 재점검 (aws13에서 nas_monitor.py --server IP --json 실행)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    ip = request.POST.get('ip', '').strip()
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'ip required'})

    import time as _time
    status = _read_single_check(ip)
    if status.get('running'):
        # 이미 30초 이상 진행 중이면 이전 작업 무시 (좀비 방지)
        if _time.time() - status.get('started', 0) < 30:
            return JsonResponse({'result': 409, 'msg': f'{ip} 점검이 이미 진행 중입니다.'})

    _write_single_check(ip, {'running': True, 'result': None, 'started': _time.time()})

    def run_single_check():
        import time as _t
        started = _t.time()
        try:
            # health 점검
            cmd_health = (
                'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan && '
                f'.venv310/bin/python3 scripts/nas_monitor.py --server {ip} --json"'
            )
            result_h = subprocess.run(cmd_health, shell=True, capture_output=True, text=True, timeout=120)

            health_data = None
            if result_h.returncode in (0, 1, 2) and result_h.stdout.strip():
                try:
                    health_data = json.loads(result_h.stdout)
                except json.JSONDecodeError:
                    pass

            # service 점검
            cmd_service = (
                'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no '
                'aws13.titanvpn.kr '
                '"cd /home/newkorea/project/titan && '
                f'.venv310/bin/python3 scripts/nas_service_check.py --server {ip} --json"'
            )
            result_s = subprocess.run(cmd_service, shell=True, capture_output=True, text=True, timeout=120)

            service_data = None
            if result_s.returncode in (0, 1, 2) and result_s.stdout.strip():
                try:
                    service_data = json.loads(result_s.stdout)
                except json.JSONDecodeError:
                    pass

            elapsed = round(_t.time() - started, 1)

            # DB 업데이트 — 최신 health/service 레코드에 반영
            if health_data and health_data.get('servers'):
                _update_db_report('health', ip, health_data['servers'][0])
            if service_data and service_data.get('servers'):
                _update_db_report('service', ip, service_data['servers'][0])

            _write_single_check(ip, {
                'running': False,
                'result': {
                    'success': health_data is not None or service_data is not None,
                    'health': health_data,
                    'service': service_data,
                    'elapsed': elapsed,
                },
                'started': started,
            })
        except subprocess.TimeoutExpired:
            _write_single_check(ip, {
                'running': False,
                'result': {'success': False, 'message': '타임아웃 (120초)'},
                'started': started,
            })
        except Exception as e:
            _write_single_check(ip, {
                'running': False,
                'result': {'success': False, 'message': str(e)},
                'started': started,
            })

    t = threading.Thread(target=run_single_check, daemon=True)
    t.start()

    return JsonResponse({'result': 200, 'msg': f'{ip} 서버 점검을 시작했습니다.'})


# ===== API: 단일 NAS 서버 재점검 상태 확인 =====
@allow_admin
def api_nas_single_check_status(request):
    """단일 NAS 서버 재점검 진행 상태 조회"""
    ip = request.GET.get('ip', '').strip()
    if not ip:
        return JsonResponse({'result': 400, 'msg': 'ip required'})

    import time as _time
    status = _read_single_check(ip)

    running = status.get('running', False)
    started = status.get('started')
    elapsed = round(_time.time() - started, 1) if started and running else None

    return JsonResponse({
        'result': 200,
        'running': running,
        'elapsed': elapsed,
        'data': status.get('result'),
    })


# ===== API: 서버 분석 알림 카운트 (메뉴 뱃지용, 경량) =====
@allow_admin
def api_read_server_alert_count(request):
    """최근 24시간 서버 알림 카운트 (critical/warning) — problem_servers와 동일 기준"""
    cursor = connections['default'].cursor()
    cursor2 = connections['radius'].cursor()

    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1")
    nas_map = {r[0]: r[1] for r in cursor.fetchall()}

    def _classify_isp(isp_str):
        if not isp_str: return 'Other'
        s = isp_str.lower()
        if 'mobile' in s or 'cmnet' in s or 'tietong' in s: return 'ChinaMobile'
        if 'unicom' in s or 'cnc' in s or 'china169' in s: return 'ChinaUnicom'
        if 'telecom' in s or 'chinanet' in s: return 'ChinaTelecom'
        return 'Other'

    # China users + ISP 분류 (problem_servers와 동일)
    cursor.execute("""
        SELECT u.email, d.device_isp FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.login_time >= NOW() - INTERVAL 24 HOUR AND d.device_country = 'China'
    """)
    china_user_isp = {}
    for r in cursor.fetchall():
        isp = _classify_isp(r[1])
        if isp != 'Other':
            china_user_isp[r[0]] = isp

    # Sessions — problem_servers와 동일한 any-success per-user 로직
    cursor2.execute("""
        SELECT username, nasipaddress, acctsessiontime, nasporttype, acctstarttime, acctstoptime
        FROM radacct WHERE acctstarttime >= NOW() - INTERVAL 24 HOUR
    """)
    # server -> user -> has_success (bool)
    server_user_success = {}
    for r in cursor2.fetchall():
        if r[0] not in china_user_isp:
            continue
        sname = _resolve_nas(r[1], nas_map)
        if sname not in server_user_success:
            server_user_success[sname] = {}
        sess_time = _calc_session_time(r[2], r[3], r[4], r[5])
        if r[0] not in server_user_success[sname]:
            server_user_success[sname][r[0]] = False
        if sess_time > 10:
            server_user_success[sname][r[0]] = True

    critical = 0
    warning = 0
    for sname, users in server_user_success.items():
        total = len(users)
        if total < 5:
            continue
        success = sum(1 for v in users.values() if v)
        rate = success / total * 100
        if rate < 50:
            critical += 1
        elif rate < 70:
            warning += 1

    return JsonResponse({
        'result': 200,
        'critical': critical,
        'warning': warning,
        'total_issues': critical + warning,
    })


# ===== API: 문제 서버 상세 분석 + 정상화 제안 =====
@allow_admin
def api_read_problem_servers(request):
    """성공률 70% 미만 서버의 상세 분석 + 정상화 제안"""
    cursor = connections['default'].cursor()
    cursor2 = connections['radius'].cursor()

    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1")
    nas_map = {r[0]: r[1] for r in cursor.fetchall()}

    def classify_isp(isp_str):
        if not isp_str: return 'Other'
        s = isp_str.lower()
        if 'mobile' in s or 'cmnet' in s or 'tietong' in s: return 'ChinaMobile'
        if 'unicom' in s or 'cnc' in s or 'china169' in s: return 'ChinaUnicom'
        if 'telecom' in s or 'chinanet' in s: return 'ChinaTelecom'
        return 'Other'

    def classify_os(dt):
        if not dt: return 'Unknown'
        s = dt.lower()
        if 'iphone' in s or 'ipad' in s: return 'iOS'
        if 'mac' in s: return 'MacOS'
        if 'windows' in s: return 'Windows'
        if 'android' in s: return 'Android'
        return 'Unknown'

    def classify_protocol(npt):
        if npt == 'Virtual': return 'IKEv2'
        if npt == 'ISDN': return 'OpenVPN'
        if npt == '61': return 'SSTP'
        if npt == 'V2RAY': return 'V2RAY'
        return 'Other'

    # China users (24h)
    cursor.execute("""
        SELECT u.email, d.device_type, d.device_isp, d.device_city
        FROM tbl_device_info d JOIN tbl_user u ON d.user_id = u.id
        WHERE d.login_time >= NOW() - INTERVAL 24 HOUR AND d.device_country = 'China'
    """)
    user_info = {}
    for r in cursor.fetchall():
        user_info[r[0]] = {'isp': classify_isp(r[2]), 'os': classify_os(r[1]), 'city': r[3] or 'Unknown'}

    # VPN sessions (24h)
    cursor2.execute("""
        SELECT username, nasipaddress, acctsessiontime, nasporttype, acctstarttime, acctstoptime
        FROM radacct WHERE acctstarttime >= NOW() - INTERVAL 24 HOUR
    """)

    # server -> {user -> {isp, os, city, sessions: [{proto, success, sess_time}]}}
    server_data = {}
    for r in cursor2.fetchall():
        uname, nasip, raw_sess, npt = r[0], r[1], r[2], r[3] or ''
        if uname not in user_info:
            continue
        info = user_info[uname]
        if info['isp'] == 'Other':
            continue
        sname = _resolve_nas(nasip, nas_map)
        proto = classify_protocol(npt)
        sess_time = _calc_session_time(raw_sess, npt, r[4], r[5])
        is_success = sess_time > 10
        if sname not in server_data:
            server_data[sname] = {}
        if uname not in server_data[sname]:
            server_data[sname][uname] = {'isp': info['isp'], 'os': info['os'], 'city': info['city'], 'sessions': []}
        server_data[sname][uname]['sessions'].append({'proto': proto, 'success': is_success, 'sess_time': sess_time})

    # Build problem servers
    problem_servers = []
    for sname, users in server_data.items():
        total_users = len(users)
        success_users = sum(1 for u in users.values() if any(s['success'] for s in u['sessions']))
        if total_users < 5:
            continue
        rate = round(success_users / total_users * 100, 1)
        if rate >= 70:
            continue
        severity = 'critical' if rate < 50 else 'warning'
        fail_users = total_users - success_users

        # ISP breakdown (user-level)
        isp_st = {}
        for ud in users.values():
            isp = ud['isp']
            if isp not in isp_st:
                isp_st[isp] = {'s': 0, 'f': 0}
            if any(s['success'] for s in ud['sessions']):
                isp_st[isp]['s'] += 1
            else:
                isp_st[isp]['f'] += 1
        isp_breakdown = sorted([
            {'isp': k, 'success': v['s'], 'fail': v['f'], 'total': v['s'] + v['f'],
             'rate': round(v['s'] / (v['s'] + v['f']) * 100, 1) if v['s'] + v['f'] > 0 else 0}
            for k, v in isp_st.items()
        ], key=lambda x: x['rate'])

        # Protocol breakdown (session-level)
        proto_st = {}
        for ud in users.values():
            for sess in ud['sessions']:
                p = sess['proto']
                if p not in proto_st:
                    proto_st[p] = {'s': 0, 'f': 0}
                if sess['success']:
                    proto_st[p]['s'] += 1
                else:
                    proto_st[p]['f'] += 1
        proto_breakdown = sorted([
            {'protocol': k, 'success': v['s'], 'fail': v['f'], 'total': v['s'] + v['f'],
             'rate': round(v['s'] / (v['s'] + v['f']) * 100, 1) if v['s'] + v['f'] > 0 else 0}
            for k, v in proto_st.items()
        ], key=lambda x: x['rate'])

        # OS breakdown (user-level)
        os_st = {}
        for ud in users.values():
            o = ud['os']
            if o not in os_st:
                os_st[o] = {'s': 0, 'f': 0}
            if any(s['success'] for s in ud['sessions']):
                os_st[o]['s'] += 1
            else:
                os_st[o]['f'] += 1
        os_breakdown = sorted([
            {'os': k, 'success': v['s'], 'fail': v['f'], 'total': v['s'] + v['f'],
             'rate': round(v['s'] / (v['s'] + v['f']) * 100, 1) if v['s'] + v['f'] > 0 else 0}
            for k, v in os_st.items()
        ], key=lambda x: x['rate'])

        # City breakdown (user-level, top 8)
        city_st = {}
        for ud in users.values():
            c = ud['city']
            if c not in city_st:
                city_st[c] = {'s': 0, 'f': 0}
            if any(s['success'] for s in ud['sessions']):
                city_st[c]['s'] += 1
            else:
                city_st[c]['f'] += 1
        city_breakdown = sorted([
            {'city': k, 'success': v['s'], 'fail': v['f'], 'total': v['s'] + v['f'],
             'rate': round(v['s'] / (v['s'] + v['f']) * 100, 1) if v['s'] + v['f'] > 0 else 0}
            for k, v in city_st.items() if v['s'] + v['f'] >= 2
        ], key=lambda x: x['rate'])[:8]

        # Session-level rate
        all_sess = [s for ud in users.values() for s in ud['sessions']]
        total_sess = len(all_sess)
        succ_sess = sum(1 for s in all_sess if s['success'])
        sess_rate = round(succ_sess / total_sess * 100, 1) if total_sess > 0 else 0

        # ===== Generate recommendations =====
        recs = []

        # 1. GFW 완전 차단
        if rate < 20:
            recs.append({
                'icon': 'fa-ban', 'severity': 'critical',
                'title': 'GFW IP 차단 의심',
                'text': '전체 성공률 {}%로 매우 낮음. IP가 중국 방화벽(GFW)에 의해 완전 차단되었을 가능성이 높습니다.'.format(rate),
                'action': '서버 IP 교체 또는 서버 비활성화 권장. 자동 할당에서 즉시 제외하세요.'
            })
        elif rate < 50:
            # ISP 편차 분석
            if len(isp_breakdown) >= 2 and isp_breakdown[-1]['rate'] - isp_breakdown[0]['rate'] > 30 and isp_breakdown[0]['total'] >= 3:
                worst = isp_breakdown[0]
                best = isp_breakdown[-1]
                recs.append({
                    'icon': 'fa-filter', 'severity': 'critical',
                    'title': 'ISP별 차단 편차 감지',
                    'text': '{}: {}% vs {}: {}%. 특정 ISP에서 더 심하게 차단됩니다.'.format(worst['isp'], worst['rate'], best['isp'], best['rate']),
                    'action': '{} 유저에게 이 서버 자동 할당 중지 권장.'.format(worst['isp'])
                })
            else:
                recs.append({
                    'icon': 'fa-exclamation-triangle', 'severity': 'critical',
                    'title': '전체적 접속 불안정',
                    'text': '모든 ISP에서 성공률이 낮음 ({}%). 부분적 GFW 차단 또는 서버 문제입니다.'.format(rate),
                    'action': '서버 상태 확인 후 IP 교체 또는 자동 할당에서 제외.'
                })

        # 2. ISP별 차단
        for idata in isp_breakdown:
            if idata['total'] >= 3 and idata['rate'] < 30:
                recs.append({
                    'icon': 'fa-building', 'severity': 'critical',
                    'title': '{} 차단'.format(idata['isp']),
                    'text': '{}에서 성공률 {}% ({}/{}명). 해당 ISP의 패킷 검열에 의한 차단 가능성.'.format(idata['isp'], idata['rate'], idata['success'], idata['total']),
                    'action': '{} 유저에게 이 서버 할당 중지.'.format(idata['isp'])
                })
            elif idata['total'] >= 3 and 30 <= idata['rate'] < 50:
                recs.append({
                    'icon': 'fa-building', 'severity': 'warning',
                    'title': '{} 불안정'.format(idata['isp']),
                    'text': '{}에서 성공률 {}% ({}/{}명). 간헐적 차단 또는 라우팅 문제.'.format(idata['isp'], idata['rate'], idata['success'], idata['total']),
                    'action': '{} 유저에 대한 이 서버 우선순위 낮추기.'.format(idata['isp'])
                })

        # 3. 프로토콜별 문제
        for pdata in proto_breakdown:
            if pdata['total'] >= 3 and pdata['rate'] < 30:
                recs.append({
                    'icon': 'fa-lock', 'severity': 'critical',
                    'title': '{} 프로토콜 차단'.format(pdata['protocol']),
                    'text': '{} 세션 성공률 {}% ({}/{}건). 해당 프로토콜이 감지/차단되고 있습니다.'.format(pdata['protocol'], pdata['rate'], pdata['success'], pdata['total']),
                    'action': '이 서버에서 {} 비활성화하거나, 난독화(obfuscation) 적용 검토.'.format(pdata['protocol'])
                })
            elif pdata['total'] >= 3 and 30 <= pdata['rate'] < 50:
                recs.append({
                    'icon': 'fa-lock', 'severity': 'warning',
                    'title': '{} 프로토콜 불안정'.format(pdata['protocol']),
                    'text': '{} 세션 성공률 {}% ({}/{}건).'.format(pdata['protocol'], pdata['rate'], pdata['success'], pdata['total']),
                    'action': '해당 프로토콜 대신 다른 프로토콜로 전환 유도.'.format(pdata['protocol'])
                })

        # 4. OS별 편차
        if len(os_breakdown) >= 2 and os_breakdown[0]['total'] >= 3:
            worst_os = os_breakdown[0]
            best_os = os_breakdown[-1]
            if best_os['rate'] - worst_os['rate'] > 30:
                recs.append({
                    'icon': 'fa-desktop', 'severity': 'warning',
                    'title': '{}에서 낮은 성공률'.format(worst_os['os']),
                    'text': '{}: {}% vs {}: {}%. 특정 OS에서 접속 문제가 더 심합니다.'.format(worst_os['os'], worst_os['rate'], best_os['os'], best_os['rate']),
                    'action': '{} 클라이언트 버전 확인 및 프로토콜/설정 점검.'.format(worst_os['os'])
                })

        # 5. 세션 vs 유저 성공률 차이
        if abs(sess_rate - rate) > 15:
            if sess_rate > rate:
                recs.append({
                    'icon': 'fa-users', 'severity': 'warning',
                    'title': '소수 유저 반복 실패',
                    'text': '세션 성공률({}%) > 유저 성공률({}%). 일부 유저가 반복적으로 실패합니다.'.format(sess_rate, rate),
                    'action': '실패 유저의 ISP/디바이스/위치 확인 → "유저 실패 분석" 페이지 참조.'
                })
            else:
                recs.append({
                    'icon': 'fa-refresh', 'severity': 'warning',
                    'title': '재시도 성공 패턴',
                    'text': '세션 성공률({}%) < 유저 성공률({}%). 실패 후 재시도하면 성공하는 패턴.'.format(sess_rate, rate),
                    'action': '클라이언트측 자동 재연결 설정 확인. 초기 연결 지연이 원인일 수 있음.'
                })

        # 6. Warning 수준 일반
        if 50 <= rate < 70 and len(recs) == 0:
            recs.append({
                'icon': 'fa-eye', 'severity': 'warning',
                'title': '접속 불안정 — 모니터링 필요',
                'text': '성공률 {}%로 정상 범위(70%+)에 미달. 상황이 악화될 수 있습니다.'.format(rate),
                'action': '서버 상태 주시. 50% 이하로 떨어지면 즉시 자동 할당 제외.'
            })

        # 7. Critical 서버 즉시 조치
        if severity == 'critical':
            recs.append({
                'icon': 'fa-wrench', 'severity': 'critical',
                'title': '즉시 조치 필요',
                'text': '성공률 {}% 서버를 계속 할당하면 고객 불만과 이탈이 발생합니다.'.format(rate),
                'action': '① 자동 할당 제외 ② IP 변경 검토 ③ 프로토콜 변경 ④ 서버 교체'
            })

        # ===== Build per-user lists (fail / success) =====
        fail_users_list = []
        success_users_list = []
        for uname, ud in users.items():
            total_u_sess = len(ud['sessions'])
            succ_u_sess = sum(1 for s in ud['sessions'] if s['success'])
            fail_u_sess = total_u_sess - succ_u_sess
            u_rate = round(succ_u_sess / total_u_sess * 100, 1) if total_u_sess > 0 else 0
            # Protocol used by this user on this server
            u_protos = list(set(s['proto'] for s in ud['sessions']))
            u_entry = {
                'email': uname,
                'os': ud['os'],
                'city': ud['city'],
                'isp': ud['isp'],
                'total': total_u_sess,
                'success': succ_u_sess,
                'fail': fail_u_sess,
                'rate': u_rate,
                'protos': u_protos,
            }
            if any(s['success'] for s in ud['sessions']):
                success_users_list.append(u_entry)
            else:
                fail_users_list.append(u_entry)
        # Sort: fail users by fail count desc, success users by rate asc
        fail_users_list.sort(key=lambda x: (-x['fail'], x['rate']))
        success_users_list.sort(key=lambda x: (x['rate'], -x['success']))

        problem_servers.append({
            'name': sname,
            'rate': rate,
            'success': success_users,
            'fail': fail_users,
            'total': total_users,
            'severity': severity,
            'sess_rate': sess_rate,
            'total_sessions': total_sess,
            'isp_breakdown': isp_breakdown,
            'proto_breakdown': proto_breakdown,
            'os_breakdown': os_breakdown,
            'city_breakdown': city_breakdown,
            'recommendations': recs,
            'fail_users': fail_users_list[:50],
            'success_users': success_users_list[:50],
        })

    problem_servers.sort(key=lambda x: x['rate'])

    return JsonResponse({
        'result': 200,
        'critical_count': sum(1 for s in problem_servers if s['severity'] == 'critical'),
        'warning_count': sum(1 for s in problem_servers if s['severity'] == 'warning'),
        'servers': problem_servers,
    })


# ===== PAGE: 서버 분석 =====
@allow_admin
def server_analysis(request):
    """중국 사용자 VPN 서버 성공률 분석 페이지"""
    return render(request, 'admin/server_analysis.html', {})


# ===== API: 서버 분석 데이터 =====
@allow_admin
def api_read_server_analysis(request):
    """최근 24시간 중국 사용자 기준 서버별 성공률 분석 (Per-User Dedup)"""
    cursor = connections['default'].cursor()
    cursor2 = connections['radius'].cursor()

    # NAS IP → Name, protocol mapping
    cursor.execute("SELECT hostip, name, protocol FROM tbl_agent3 WHERE is_active=1")
    nas_map = {}
    nas_protocol = {}
    for r in cursor.fetchall():
        nas_map[r[0]] = r[1]
        nas_protocol[r[0]] = r[2] or ''

    def classify_isp(isp_str):
        if not isp_str: return 'Other'
        s = isp_str.lower()
        if 'mobile' in s or 'cmnet' in s or 'tietong' in s: return 'ChinaMobile'
        if 'unicom' in s or 'cnc' in s or 'china169' in s: return 'ChinaUnicom'
        if 'telecom' in s or 'chinanet' in s: return 'ChinaTelecom'
        return 'Other'

    def classify_os(dt):
        if not dt: return 'Unknown'
        s = dt.lower()
        if 'iphone' in s or 'ipad' in s: return 'iOS'
        if 'mac' in s: return 'MacOS'
        if 'windows' in s: return 'Windows'
        if 'android' in s: return 'Android'
        return 'Unknown'

    def classify_protocol(npt):
        if npt == 'Virtual': return 'IKEv2'
        if npt == 'ISDN': return 'OpenVPN'
        if npt == '61': return 'SSTP'
        if npt == 'V2RAY': return 'V2RAY'
        return 'Other'

    # China users in last 24h
    cursor.execute("""
        SELECT u.email, d.device_type, d.device_isp, d.device_city
        FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.login_time >= NOW() - INTERVAL 24 HOUR
          AND d.device_country = 'China'
    """)
    user_info = {}
    for r in cursor.fetchall():
        email = r[0]
        user_info[email] = {
            'isp': classify_isp(r[2]),
            'os': classify_os(r[1]),
            'city': r[3] or 'Unknown',
        }

    # VPN sessions in last 24h
    cursor2.execute("""
        SELECT username, nasipaddress, acctsessiontime, nasporttype, acctstarttime, acctstoptime
        FROM radacct
        WHERE acctstarttime >= NOW() - INTERVAL 24 HOUR
    """)

    # Per-user dedup: user_server_proto[email][nasip][proto] = {s, f}
    user_server_proto = {}
    total_sessions = 0
    china_sessions = 0
    for r in cursor2.fetchall():
        uname, nasip, raw_sess, npt = r[0], r[1], r[2], r[3] or ''
        total_sessions += 1
        if uname not in user_info:
            continue
        china_sessions += 1
        proto = classify_protocol(npt)
        sess_time = _calc_session_time(raw_sess, npt, r[4], r[5])
        if uname not in user_server_proto:
            user_server_proto[uname] = {}
        if nasip not in user_server_proto[uname]:
            user_server_proto[uname][nasip] = {}
        if proto not in user_server_proto[uname][nasip]:
            user_server_proto[uname][nasip][proto] = {'s': 0, 'f': 0}
        if sess_time > 10:
            user_server_proto[uname][nasip][proto]['s'] += 1
        else:
            user_server_proto[uname][nasip][proto]['f'] += 1

    # Build analysis structures
    # 1. Overall per server
    global_server = {}  # server -> {s: set, f: set}
    # 2. Per ISP
    isp_server = {}  # (isp, server) -> {s: set, f: set}
    # 3. Per protocol
    proto_server = {}  # (proto, server) -> {s: set, f: set}
    # 4. Per ISP×Protocol
    isp_proto_server = {}  # (isp, proto, server) -> {s: set, f: set}
    # 5. Per OS
    os_server = {}  # (os, server) -> {s: set, f: set}
    # 6. Per ISP×City
    city_server = {}  # (isp, city, server) -> {s: set, f: set}
    # 7. Session-level (for comparison)
    sess_level = {}  # server -> {s: int, f: int}
    # 8. Protocol distribution
    proto_dist = {}  # proto -> {s: int, f: int}

    for uname, servers in user_server_proto.items():
        info = user_info[uname]
        isp = info['isp']
        ostype = info['os']
        city = info['city']
        if isp == 'Other':
            continue

        for nasip, protos in servers.items():
            sname = _resolve_nas(nasip, nas_map)

            for proto, counts in protos.items():
                is_success = counts['s'] > 0

                # Session level
                if sname not in sess_level:
                    sess_level[sname] = {'s': 0, 'f': 0}
                sess_level[sname]['s'] += counts['s']
                sess_level[sname]['f'] += counts['f']

                # Proto distribution
                if proto not in proto_dist:
                    proto_dist[proto] = {'s': 0, 'f': 0}
                proto_dist[proto]['s'] += counts['s']
                proto_dist[proto]['f'] += counts['f']

                # Global server
                if sname not in global_server:
                    global_server[sname] = {'s': set(), 'f': set()}
                if is_success:
                    global_server[sname]['s'].add(uname)
                else:
                    global_server[sname]['f'].add(uname)

                # ISP server
                k = (isp, sname)
                if k not in isp_server:
                    isp_server[k] = {'s': set(), 'f': set()}
                if is_success:
                    isp_server[k]['s'].add(uname)
                else:
                    isp_server[k]['f'].add(uname)

                # Protocol server
                k = (proto, sname)
                if k not in proto_server:
                    proto_server[k] = {'s': set(), 'f': set()}
                if is_success:
                    proto_server[k]['s'].add(uname)
                else:
                    proto_server[k]['f'].add(uname)

                # ISP × Protocol × server
                k = (isp, proto, sname)
                if k not in isp_proto_server:
                    isp_proto_server[k] = {'s': set(), 'f': set()}
                if is_success:
                    isp_proto_server[k]['s'].add(uname)
                else:
                    isp_proto_server[k]['f'].add(uname)

                # OS server
                k = (ostype, sname)
                if k not in os_server:
                    os_server[k] = {'s': set(), 'f': set()}
                if is_success:
                    os_server[k]['s'].add(uname)
                else:
                    os_server[k]['f'].add(uname)

                # City server
                k = (isp, city, sname)
                if k not in city_server:
                    city_server[k] = {'s': set(), 'f': set()}
                if is_success:
                    city_server[k]['s'].add(uname)
                else:
                    city_server[k]['f'].add(uname)

    def _build_ranking(data_dict, min_users=5, key_fields=1):
        """Generic ranking builder from {key: {s: set, f: set}}"""
        results = []
        for k, v in data_dict.items():
            total = len(v['s']) + len(v['f'])
            if total < min_users:
                continue
            rate = round(len(v['s']) / total * 100, 1)
            tier = 'S' if rate >= 95 else 'A' if rate >= 85 else 'B' if rate >= 75 else 'C' if rate >= 60 else 'F'
            if key_fields == 1:
                results.append({'name': k, 'success': len(v['s']), 'total': total, 'rate': rate, 'tier': tier})
            elif key_fields == 2:
                results.append({'key1': k[0], 'name': k[1], 'success': len(v['s']), 'total': total, 'rate': rate, 'tier': tier})
            elif key_fields == 3:
                results.append({'key1': k[0], 'key2': k[1], 'name': k[2], 'success': len(v['s']), 'total': total, 'rate': rate, 'tier': tier})
        results.sort(key=lambda x: -x['rate'])
        return results

    # Build all rankings
    overall_ranking = _build_ranking(global_server, min_users=10)
    isp_ranking = _build_ranking(isp_server, min_users=5, key_fields=2)
    proto_ranking = _build_ranking(proto_server, min_users=3, key_fields=2)
    isp_proto_ranking = _build_ranking(isp_proto_server, min_users=3, key_fields=3)
    os_ranking = _build_ranking(os_server, min_users=5, key_fields=2)
    city_ranking = _build_ranking(city_server, min_users=5, key_fields=3)

    # Session vs User comparison
    comparison = []
    for sname, gs in global_server.items():
        total_users = len(gs['s']) + len(gs['f'])
        if total_users < 10:
            continue
        user_rate = round(len(gs['s']) / total_users * 100, 1)
        if sname in sess_level:
            sl = sess_level[sname]
            total_sess = sl['s'] + sl['f']
            sess_rate = round(sl['s'] / total_sess * 100, 1) if total_sess > 0 else 0
            diff = round(user_rate - sess_rate, 1)
            comparison.append({
                'name': sname,
                'sess_rate': sess_rate,
                'user_rate': user_rate,
                'diff': diff,
                'sess_count': total_sess,
                'user_count': total_users,
            })
    comparison.sort(key=lambda x: -abs(x['diff']))

    # Session time (V2RAY는 acctsessiontime이 NULL이므로 TIMESTAMPDIFF 사용)
    cursor2.execute("""
        SELECT nasipaddress,
               AVG(CASE WHEN nasporttype='V2RAY' THEN TIMESTAMPDIFF(SECOND, acctstarttime, acctstoptime)
                        ELSE acctsessiontime END) as avg_sess,
               COUNT(*)
        FROM radacct
        WHERE acctstarttime >= NOW() - INTERVAL 24 HOUR
          AND (
            (nasporttype != 'V2RAY' AND acctsessiontime > 10)
            OR
            (nasporttype = 'V2RAY' AND acctstoptime IS NOT NULL AND TIMESTAMPDIFF(SECOND, acctstarttime, acctstoptime) > 10)
          )
        GROUP BY nasipaddress
        ORDER BY avg_sess DESC
    """)
    session_times = []
    for r in cursor2.fetchall():
        sname = _resolve_nas(r[0], nas_map)
        session_times.append({
            'name': sname,
            'avg_hours': round(float(r[1]) / 3600, 1),
            'count': r[2],
        })

    # Blocklist
    blocklist_global = [x for x in _build_ranking(global_server, min_users=2) if x['rate'] < 30]
    blocklist_isp = [x for x in _build_ranking(isp_server, min_users=3, key_fields=2) if x['rate'] < 50]
    blocklist_proto = [x for x in _build_ranking(proto_server, min_users=3, key_fields=2) if x['rate'] < 50]

    # Alerts: critical (실패율 > 50%), warning (실패율 > 30%)
    alerts_critical = [x for x in _build_ranking(global_server, min_users=5) if x['rate'] < 50]
    alerts_warning = [x for x in _build_ranking(global_server, min_users=5) if 50 <= x['rate'] < 70]
    alerts_critical.sort(key=lambda x: x['rate'])
    alerts_warning.sort(key=lambda x: x['rate'])

    # Protocol distribution summary
    proto_summary = []
    for proto, d in proto_dist.items():
        total = d['s'] + d['f']
        rate = round(d['s'] / total * 100, 1) if total > 0 else 0
        proto_summary.append({'protocol': proto, 'success': d['s'], 'fail': d['f'], 'total': total, 'rate': rate})
    proto_summary.sort(key=lambda x: -x['total'])

    return JsonResponse({
        'result': 200,
        'summary': {
            'total_china_users': len(user_info),
            'matched_users': len(user_server_proto),
            'total_sessions': total_sessions,
            'china_sessions': china_sessions,
        },
        'proto_summary': proto_summary,
        'overall_ranking': overall_ranking,
        'isp_ranking': isp_ranking,
        'proto_ranking': proto_ranking,
        'isp_proto_ranking': isp_proto_ranking,
        'os_ranking': os_ranking,
        'city_ranking': city_ranking,
        'session_times': session_times[:25],
        'comparison': comparison[:15],
        'blocklist_global': blocklist_global,
        'blocklist_isp': blocklist_isp,
        'blocklist_proto': blocklist_proto,
        'alerts_critical': alerts_critical,
        'alerts_warning': alerts_warning,
        'alert_counts': {
            'critical': len(alerts_critical),
            'warning': len(alerts_warning),
            'total': len(alerts_critical) + len(alerts_warning),
        },
    })


# ===== PAGE: 유저 실패 분석 =====
@allow_admin
def user_fail_analysis(request):
    """유저별 VPN 접속 실패 분석 페이지"""
    return render(request, 'admin/user_fail_analysis.html', {})


# ===== API: 유저 실패 분석 데이터 =====
@allow_admin
def api_read_user_fail_analysis(request):
    """중국 사용자 기준 유저별 실패 분석 (시간범위 파라미터 지원)"""
    hours = int(request.GET.get('hours', 24))
    if hours not in (1, 3, 6, 12, 24):
        hours = 24
    cursor = connections['default'].cursor()
    cursor2 = connections['radius'].cursor()

    # NAS IP → Name mapping
    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1")
    nas_map = {r[0]: r[1] for r in cursor.fetchall()}

    def classify_isp(isp_str):
        if not isp_str: return 'Other'
        s = isp_str.lower()
        if 'mobile' in s or 'cmnet' in s or 'tietong' in s: return 'ChinaMobile'
        if 'unicom' in s or 'cnc' in s or 'china169' in s: return 'ChinaUnicom'
        if 'telecom' in s or 'chinanet' in s: return 'ChinaTelecom'
        return 'Other'

    def classify_os(dt):
        if not dt: return 'Unknown'
        s = dt.lower()
        if 'iphone' in s or 'ipad' in s: return 'iOS'
        if 'mac' in s: return 'MacOS'
        if 'windows' in s: return 'Windows'
        if 'android' in s: return 'Android'
        return 'Unknown'

    def classify_protocol(npt):
        if npt == 'Virtual': return 'IKEv2'
        if npt == 'ISDN': return 'OpenVPN'
        if npt == '61': return 'SSTP'
        if npt == 'V2RAY': return 'V2RAY'
        return 'Other'

    # China user info
    cursor.execute("""
        SELECT u.email, u.username, u.id, d.device_type, d.device_isp, d.device_city
        FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.login_time >= NOW() - INTERVAL %s HOUR
          AND d.device_country = 'China'
    """, [hours])
    user_info = {}
    for r in cursor.fetchall():
        email = r[0]
        user_info[email] = {
            'username': r[1] or '',
            'user_id': r[2],
            'os': classify_os(r[3]),
            'device_raw': r[3] or '',
            'isp': classify_isp(r[4]),
            'isp_raw': r[4] or '',
            'city': r[5] or 'Unknown',
        }

    # VPN sessions
    cursor2.execute("""
        SELECT username, nasipaddress, acctsessiontime, nasporttype, acctstarttime, acctstoptime, acctterminatecause
        FROM radacct
        WHERE acctstarttime >= NOW() - INTERVAL %s HOUR
    """, [hours])

    # Per-user session data
    user_sessions = {}  # email -> list of sessions
    for r in cursor2.fetchall():
        uname, nasip, raw_sess, npt, start_time, stop_time, term_cause = r[0], r[1], r[2], r[3] or '', r[4], r[5], r[6] or ''
        if uname not in user_info:
            continue
        sname = _resolve_nas(nasip, nas_map)
        proto = classify_protocol(npt)
        sess_time = _calc_session_time(raw_sess, npt, start_time, stop_time)
        is_success = sess_time > 10
        # 로테이션 판별: 10초 이하 + User-Request = 앱이 자동 서버 전환한 정상 동작
        is_rotation = (not is_success) and (term_cause == 'User-Request')

        if uname not in user_sessions:
            user_sessions[uname] = []
        user_sessions[uname].append({
            'server': sname,
            'server_ip': nasip,
            'proto': proto,
            'session_time': sess_time,
            'success': is_success,
            'rotation': is_rotation,
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else '',
        })

    # Build user ranking
    user_ranking = []
    for email, sessions in user_sessions.items():
        info = user_info[email]
        total = len(sessions)
        success = sum(1 for s in sessions if s['success'])
        rotation = sum(1 for s in sessions if s.get('rotation'))
        fail_raw = total - success  # 전체 실패 (로테이션 포함)
        fail = fail_raw - rotation  # 진짜 실패 (로테이션 제외)
        if total < 2:
            continue
        rate = round(success / total * 100, 1)
        # 로테이션 제외 성공률 (진짜 실패 기준)
        real_total = total - rotation
        real_rate = round(success / real_total * 100, 1) if real_total > 0 else 100.0

        # Per-server breakdown
        server_stats = {}
        proto_stats = {}
        for s in sessions:
            # Server stats
            if s['server'] not in server_stats:
                server_stats[s['server']] = {'s': 0, 'f': 0, 'r': 0}
            if s['success']:
                server_stats[s['server']]['s'] += 1
            elif s.get('rotation'):
                server_stats[s['server']]['r'] += 1
            else:
                server_stats[s['server']]['f'] += 1
            # Protocol stats
            if s['proto'] not in proto_stats:
                proto_stats[s['proto']] = {'s': 0, 'f': 0, 'r': 0}
            if s['success']:
                proto_stats[s['proto']]['s'] += 1
            elif s.get('rotation'):
                proto_stats[s['proto']]['r'] += 1
            else:
                proto_stats[s['proto']]['f'] += 1

        # Server breakdown list
        servers = []
        for sname, v in sorted(server_stats.items(), key=lambda x: -(x[1]['s'] + x[1]['f'] + x[1]['r'])):
            st = v['s'] + v['f'] + v['r']
            sr = round(v['s'] / st * 100, 1) if st > 0 else 0
            # 로테이션 제외 성공률
            real_st = v['s'] + v['f']
            real_sr = round(v['s'] / real_st * 100, 1) if real_st > 0 else 100.0
            servers.append({'name': sname, 'success': v['s'], 'fail': v['f'], 'rotation': v['r'], 'total': st, 'rate': sr, 'real_rate': real_sr})

        # Protocol breakdown
        protos = []
        for pname, v in sorted(proto_stats.items(), key=lambda x: -(x[1]['s'] + x[1]['f'] + x[1]['r'])):
            pt = v['s'] + v['f'] + v['r']
            pr = round(v['s'] / pt * 100, 1) if pt > 0 else 0
            real_pt = v['s'] + v['f']
            real_pr = round(v['s'] / real_pt * 100, 1) if real_pt > 0 else 100.0
            protos.append({'name': pname, 'success': v['s'], 'fail': v['f'], 'rotation': v['r'], 'total': pt, 'rate': pr, 'real_rate': real_pr})

        # Time range
        times = sorted([s['start_time'] for s in sessions if s['start_time']])
        first_seen = times[0] if times else ''
        last_seen = times[-1] if times else ''

        # Severity (로테이션 포함 기준)
        if rate < 30:
            severity = 'critical'
        elif rate < 60:
            severity = 'warning'
        else:
            severity = 'normal'

        # Real severity (로테이션 제외 기준)
        if real_rate < 30:
            real_severity = 'critical'
        elif real_rate < 60:
            real_severity = 'warning'
        else:
            real_severity = 'normal'

        user_ranking.append({
            'email': email,
            'username': info['username'],
            'user_id': info['user_id'],
            'isp': info['isp'],
            'isp_raw': info['isp_raw'],
            'os': info['os'],
            'device_raw': info['device_raw'],
            'city': info['city'],
            'total': total,
            'success': success,
            'fail': fail,
            'fail_raw': fail_raw,
            'rotation': rotation,
            'rate': rate,
            'real_rate': real_rate,
            'severity': severity,
            'real_severity': real_severity,
            'servers_tried': len(server_stats),
            'protos_used': len(proto_stats),
            'first_seen': first_seen,
            'last_seen': last_seen,
            'servers': servers[:10],
            'protos': protos,
        })

    # Sort by fail count desc
    user_ranking.sort(key=lambda x: (-x['fail'], x['rate']))

    # Summary
    total_users = len(user_ranking)
    critical_users = sum(1 for u in user_ranking if u['severity'] == 'critical')
    warning_users = sum(1 for u in user_ranking if u['severity'] == 'warning')
    zero_success = sum(1 for u in user_ranking if u['success'] == 0)
    real_critical = sum(1 for u in user_ranking if u['real_severity'] == 'critical')
    real_warning = sum(1 for u in user_ranking if u['real_severity'] == 'warning')
    total_rotation = sum(u['rotation'] for u in user_ranking)

    # ISP distribution of failing users (rate < 60%)
    isp_fail_dist = {}
    for u in user_ranking:
        if u['real_rate'] >= 60:
            continue
        isp = u['isp']
        if isp not in isp_fail_dist:
            isp_fail_dist[isp] = 0
        isp_fail_dist[isp] += 1
    isp_fail_summary = [{'isp': k, 'count': v} for k, v in sorted(isp_fail_dist.items(), key=lambda x: -x[1])]

    # OS distribution of failing users
    os_fail_dist = {}
    for u in user_ranking:
        if u['real_rate'] >= 60:
            continue
        ostype = u['os']
        if ostype not in os_fail_dist:
            os_fail_dist[ostype] = 0
        os_fail_dist[ostype] += 1
    os_fail_summary = [{'os': k, 'count': v} for k, v in sorted(os_fail_dist.items(), key=lambda x: -x[1])]

    # City distribution of failing users
    city_fail_dist = {}
    for u in user_ranking:
        if u['real_rate'] >= 60:
            continue
        city = u['city']
        if city not in city_fail_dist:
            city_fail_dist[city] = 0
        city_fail_dist[city] += 1
    city_fail_summary = [{'city': k, 'count': v} for k, v in sorted(city_fail_dist.items(), key=lambda x: -x[1])][:15]

    return JsonResponse({
        'result': 200,
        'hours': hours,
        'summary': {
            'total_users': total_users,
            'critical_users': critical_users,
            'warning_users': warning_users,
            'real_critical': real_critical,
            'real_warning': real_warning,
            'zero_success': zero_success,
            'total_china_users': len(user_info),
            'total_rotation': total_rotation,
        },
        'isp_fail_summary': isp_fail_summary,
        'os_fail_summary': os_fail_summary,
        'city_fail_summary': city_fail_summary,
        'users': user_ranking[:100],
    })


# ===== API: 강제종료 로그 =====
@allow_admin
def api_read_disconnect_logs(request):
    """강제종료 로그 — 시간범위 지원"""
    hours = int(request.GET.get('hours', 24))
    if hours not in (1, 3, 6, 12, 24):
        hours = 24
    cursor = connections['default'].cursor()

    cursor.execute("""
        SELECT d.id, d.username, d.user_session, d.connected_count, d.protocol,
               IFNULL(d.server_name, '') as server_name,
               d.disconnected_time, d.old_ip, d.new_ip,
               IFNULL(u.username, '') as display_name
        FROM tbl_disconnection d
        LEFT JOIN tbl_user u ON u.email = d.username
        WHERE d.disconnected_time >= NOW() - INTERVAL %s HOUR
        ORDER BY d.disconnected_time DESC
        LIMIT 500
    """, [hours])
    rows = cursor.fetchall()

    logs = []
    # 유저별 집계
    user_counts = {}
    server_counts = {}
    proto_counts = {}
    for r in rows:
        uname = r[1] or ''
        sname = r[5] or ''
        proto = r[4] or ''
        user_counts[uname] = user_counts.get(uname, 0) + 1
        server_counts[sname] = server_counts.get(sname, 0) + 1
        proto_counts[proto] = proto_counts.get(proto, 0) + 1
        logs.append({
            'id': r[0],
            'username': uname,
            'display_name': r[9] or '',
            'session': r[2],
            'connected_count': r[3],
            'protocol': proto,
            'server_name': sname,
            'disconnected_time': r[6].strftime('%Y-%m-%d %H:%M:%S') if r[6] else '',
            'old_ip': r[7] or '',
            'new_ip': r[8] or '',
        })

    # Top users / servers / protocols
    top_users = sorted(user_counts.items(), key=lambda x: -x[1])[:20]
    top_servers = sorted(server_counts.items(), key=lambda x: -x[1])[:15]
    top_protos = sorted(proto_counts.items(), key=lambda x: -x[1])

    return JsonResponse({
        'result': 200,
        'hours': hours,
        'total': len(logs),
        'logs': logs,
        'top_users': [{'email': k, 'count': v} for k, v in top_users],
        'top_servers': [{'server': k, 'count': v} for k, v in top_servers],
        'top_protos': [{'proto': k, 'count': v} for k, v in top_protos],
    })


# ===== API: 유저 심층분석 =====
@allow_admin
def api_read_user_deep_analysis(request):
    """특정 유저의 VPN 접속 심층분석"""
    email = request.GET.get('email', '')
    hours = int(request.GET.get('hours', 48))
    if hours not in (1, 3, 6, 12, 24, 48, 72, 168):
        hours = 48
    if not email:
        return JsonResponse({'result': 400, 'msg': 'email required'})

    cursor = connections['default'].cursor()
    cursor2 = connections['radius'].cursor()

    # NAS IP → Name mapping
    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1")
    nas_map = {r[0]: r[1] for r in cursor.fetchall()}

    # User info
    cursor.execute("""
        SELECT u.id, u.email, u.username, u.regist_date,
               IFNULL(d.device_type, '') as device_type,
               IFNULL(d.device_isp, '') as device_isp,
               IFNULL(d.device_city, '') as device_city,
               IFNULL(d.device_country, '') as device_country,
               u.v2ray_uuid, u.v2ray_deployed
        FROM tbl_user u
        LEFT JOIN tbl_device_info d ON d.user_id = u.id
        WHERE u.email = %s
        ORDER BY d.login_time DESC LIMIT 1
    """, [email])
    user_rows = cursor.fetchall()
    if not user_rows:
        return JsonResponse({'result': 404, 'msg': 'user not found'})
    ur = user_rows[0]

    # Subscription info
    cursor2.execute("""
        SELECT value FROM radcheck
        WHERE username = %s AND attribute = 'Expiration'
        LIMIT 1
    """, [email])
    exp_rows = cursor2.fetchall()
    expiration = exp_rows[0][0] if exp_rows else ''

    cursor2.execute("""
        SELECT value FROM radcheck
        WHERE username = %s AND attribute = 'Simultaneous-Use'
        LIMIT 1
    """, [email])
    sim_rows = cursor2.fetchall()
    sim_use = sim_rows[0][0] if sim_rows else ''

    user_profile = {
        'user_id': ur[0],
        'email': ur[1],
        'username': ur[2] or '',
        'regist_date': ur[3].strftime('%Y-%m-%d') if ur[3] else '',
        'device_type': ur[4],
        'isp': ur[5],
        'city': ur[6],
        'country': ur[7],
        'v2ray_deployed': ur[9],
        'expiration': expiration,
        'simultaneous_use': sim_use,
    }

    def classify_protocol(npt):
        if npt == 'Virtual': return 'IKEv2'
        if npt == 'ISDN': return 'OpenVPN'
        if npt == '61': return 'SSTP'
        if npt == 'V2RAY': return 'V2RAY'
        return 'Other'

    # Sessions
    cursor2.execute("""
        SELECT nasipaddress, nasporttype, acctsessiontime, acctstarttime, acctstoptime,
               acctterminatecause, callingstationid, framedipaddress
        FROM radacct
        WHERE username = %s AND acctstarttime >= NOW() - INTERVAL %s HOUR
        ORDER BY acctstarttime DESC
    """, [email, hours])
    sessions_raw = cursor2.fetchall()

    sessions = []
    server_stats = {}
    proto_stats = {}
    hour_stats = {}
    total_s = 0
    total_f = 0
    total_r = 0
    dur_buckets = {'0-10s': 0, '11-60s': 0, '1-5min': 0, '5-30min': 0, '30m-2h': 0, '2h+': 0}
    fail_causes = {}
    long_sessions = []

    for r in sessions_raw:
        nasip, npt, raw_sess, start_t, stop_t, term_cause, csid, framed = r
        npt = npt or ''
        proto = classify_protocol(npt)
        sess_time = _calc_session_time(raw_sess, npt, start_t, stop_t)
        sname = _resolve_nas(nasip or '', nas_map)
        is_success = sess_time > 10
        is_rotation = (not is_success) and ((term_cause or '') == 'User-Request')

        # Client IP from calledstationid
        client_ip = ''
        if csid:
            idx = csid.find('=5B')
            client_ip = csid[:idx] if idx > 0 else csid

        if is_success:
            total_s += 1
        elif is_rotation:
            total_r += 1
        else:
            total_f += 1

        # Duration buckets
        if sess_time <= 10:
            dur_buckets['0-10s'] += 1
        elif sess_time <= 60:
            dur_buckets['11-60s'] += 1
        elif sess_time <= 300:
            dur_buckets['1-5min'] += 1
        elif sess_time <= 1800:
            dur_buckets['5-30min'] += 1
        elif sess_time <= 7200:
            dur_buckets['30m-2h'] += 1
        else:
            dur_buckets['2h+'] += 1

        # Long sessions (> 5min)
        if sess_time > 300:
            long_sessions.append({
                'server': sname,
                'proto': proto,
                'duration': sess_time,
                'start': start_t.strftime('%m-%d %H:%M') if start_t else '',
            })

        # Fail causes
        if not is_success and not is_rotation:
            cause = term_cause or '(응답없음)'
            fail_causes[cause] = fail_causes.get(cause, 0) + 1

        # Hour stats
        if start_t:
            hr = start_t.hour
            if hr not in hour_stats:
                hour_stats[hr] = {'s': 0, 'f': 0, 'r': 0}
            if is_success:
                hour_stats[hr]['s'] += 1
            elif is_rotation:
                hour_stats[hr]['r'] += 1
            else:
                hour_stats[hr]['f'] += 1

        # Server stats
        if sname not in server_stats:
            server_stats[sname] = {'s': 0, 'f': 0, 'r': 0, 'max_dur': 0}
        if is_success:
            server_stats[sname]['s'] += 1
            if sess_time > server_stats[sname]['max_dur']:
                server_stats[sname]['max_dur'] = sess_time
        elif is_rotation:
            server_stats[sname]['r'] += 1
        else:
            server_stats[sname]['f'] += 1

        # Proto stats
        if proto not in proto_stats:
            proto_stats[proto] = {'s': 0, 'f': 0, 'r': 0}
        if is_success:
            proto_stats[proto]['s'] += 1
        elif is_rotation:
            proto_stats[proto]['r'] += 1
        else:
            proto_stats[proto]['f'] += 1

        sessions.append({
            'server': sname,
            'proto': proto,
            'duration': sess_time,
            'success': is_success,
            'rotation': is_rotation,
            'start': start_t.strftime('%m-%d %H:%M:%S') if start_t else '',
            'cause': term_cause or '',
            'client_ip': client_ip,
        })

    # Build server ranking
    server_ranking = []
    for sn, v in sorted(server_stats.items(), key=lambda x: -(x[1]['s'])):
        t = v['s'] + v['f'] + v['r']
        real_t = v['s'] + v['f']
        rate = round(v['s'] / real_t * 100, 1) if real_t > 0 else 100.0
        dur_str = ''
        if v['max_dur'] > 3600:
            dur_str = f"{v['max_dur'] // 3600}h{(v['max_dur'] % 3600) // 60}m"
        elif v['max_dur'] > 60:
            dur_str = f"{v['max_dur'] // 60}m"
        elif v['max_dur'] > 0:
            dur_str = f"{v['max_dur']}s"
        server_ranking.append({
            'name': sn, 'success': v['s'], 'fail': v['f'], 'rotation': v['r'],
            'total': t, 'rate': rate, 'max_dur': dur_str
        })

    # Build proto ranking
    proto_ranking = []
    for pn, v in sorted(proto_stats.items(), key=lambda x: -(x[1]['s'])):
        real_t = v['s'] + v['f']
        rate = round(v['s'] / real_t * 100, 1) if real_t > 0 else 100.0
        proto_ranking.append({
            'name': pn, 'success': v['s'], 'fail': v['f'], 'rotation': v['r'],
            'total': v['s'] + v['f'] + v['r'], 'rate': rate
        })

    # Hour distribution
    hour_dist = []
    for hr in sorted(hour_stats.keys()):
        v = hour_stats[hr]
        hour_dist.append({'hour': hr, 's': v['s'], 'f': v['f'], 'r': v['r']})

    total = total_s + total_f + total_r
    raw_rate = round(total_s / total * 100, 1) if total > 0 else 0
    real_total = total_s + total_f
    real_rate = round(total_s / real_total * 100, 1) if real_total > 0 else 100.0

    # Disconnect logs for this user
    cursor.execute("""
        SELECT server_name, protocol, disconnected_time, connected_count
        FROM tbl_disconnection
        WHERE username = %s AND disconnected_time >= NOW() - INTERVAL %s HOUR
        ORDER BY disconnected_time DESC LIMIT 50
    """, [email, hours])
    disconnects = []
    for dr in cursor.fetchall():
        disconnects.append({
            'server': dr[0] or '',
            'proto': dr[1] or '',
            'time': dr[2].strftime('%m-%d %H:%M:%S') if dr[2] else '',
            'count': dr[3],
        })

    # Diagnosis
    diagnosis = []
    if total_f == 0 and total_r > 5:
        diagnosis.append({'type': 'info', 'msg': '실제 실패 0건 — 모든 실패가 앱 서버 로테이션입니다. 정상 사용자.'})
    elif total_f <= 2 and total_s > 5:
        diagnosis.append({'type': 'info', 'msg': f'실질 실패 {total_f}건으로 매우 적음. 정상 사용자.'})
    if total_r > 20:
        diagnosis.append({'type': 'warning', 'msg': f'로테이션 {total_r}건 — 앱이 많은 서버를 시도 중. 연결 가능 서버가 제한적일 수 있음.'})
    if total_f > 10:
        diagnosis.append({'type': 'critical', 'msg': f'실제 실패 {total_f}건 — DPI 차단 또는 서버 문제 가능성.'})
    best_server = server_ranking[0] if server_ranking else None
    if best_server and best_server['success'] > 3 and best_server['max_dur']:
        diagnosis.append({'type': 'info', 'msg': f"최적 서버: {best_server['name']} (성공 {best_server['success']}건, 최대 {best_server['max_dur']})"})
    if len(long_sessions) >= 3:
        avg_dur = sum(s['duration'] for s in long_sessions) / len(long_sessions)
        diagnosis.append({'type': 'info', 'msg': f'장시간 연결 {len(long_sessions)}건, 평균 {avg_dur / 60:.0f}분 — 연결 유지력 양호.'})
    if len(disconnects) > 5:
        diagnosis.append({'type': 'warning', 'msg': f'강제종료 {len(disconnects)}건 — 동시접속 초과 발생 중.'})

    return JsonResponse({
        'result': 200,
        'hours': hours,
        'user': user_profile,
        'summary': {
            'total': total,
            'success': total_s,
            'fail': total_f,
            'rotation': total_r,
            'raw_rate': raw_rate,
            'real_rate': real_rate,
        },
        'servers': server_ranking,
        'protos': proto_ranking,
        'hour_dist': hour_dist,
        'dur_buckets': dur_buckets,
        'fail_causes': [{'cause': k, 'count': v} for k, v in sorted(fail_causes.items(), key=lambda x: -x[1])],
        'long_sessions': long_sessions[:20],
        'disconnects': disconnects,
        'sessions': sessions[:100],
        'diagnosis': diagnosis,
    })


# =====================================================================
#  목표사이트 점검 (Target Site Check)
# =====================================================================
SITE_CHECK_DIR = os.path.join(tempfile.gettempdir(), 'nas_site_check')
os.makedirs(SITE_CHECK_DIR, exist_ok=True)

SITES_TO_CHECK = [
    ('gemini',    'Google Gemini',   'https://gemini.google.com'),
    ('youtube',   'YouTube',         'https://www.youtube.com'),
    ('facebook',  'Facebook',        'https://www.facebook.com'),
    ('instagram', 'Instagram',       'https://www.instagram.com'),
    ('tiktok',    'TikTok',          'https://www.tiktok.com'),
    ('netflix',   'Netflix',         'https://www.netflix.com'),
]


def _site_check_file():
    return os.path.join(SITE_CHECK_DIR, 'results.json')


def _read_site_check_data():
    fpath = _site_check_file()
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_site_check_data(data):
    fpath = _site_check_file()
    tmp = fpath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, fpath)


def _check_single_server_sites(ip, server_name):
    """SSH into a VPN server and check target sites + exit IP via fwmark
    실패한 사이트는 최대 2회 재시도 (총 3회 시도)"""
    urls = ' '.join(f'"{s[2]}"' for s in SITES_TO_CHECK)
    script = f'''UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0"
# 1차 시도
RETRY_URLS=""
for url in {urls}; do
  code=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 10 -o /dev/null -w "%{{http_code}}" "$url" 2>/dev/null)
  echo "SITE|$url|$code"
  case "$code" in
    2*|3*) ;;
    *) RETRY_URLS="$RETRY_URLS $url" ;;
  esac
done
# 2차 재시도 (실패한 URL만, 3초 대기 후)
if [ -n "$RETRY_URLS" ]; then
  sleep 3
  RETRY2_URLS=""
  for url in $RETRY_URLS; do
    code=$(curl -4 -s -A "$UA" --connect-timeout 7 --max-time 12 -o /dev/null -w "%{{http_code}}" "$url" 2>/dev/null)
    echo "RETRY|$url|$code"
    case "$code" in
      2*|3*) ;;
      *) RETRY2_URLS="$RETRY2_URLS $url" ;;
    esac
  done
  # 3차 재시도 (여전히 실패한 URL만, 5초 대기 후)
  if [ -n "$RETRY2_URLS" ]; then
    sleep 5
    for url in $RETRY2_URLS; do
      code=$(curl -4 -s -A "$UA" --connect-timeout 10 --max-time 15 -o /dev/null -w "%{{http_code}}" "$url" 2>/dev/null)
      echo "RETRY|$url|$code"
    done
  fi
fi
# Gemini geo check — HTML body에서 첫 번째 2글자 국가코드 추출 (en=정상, cn=차단)
# fwmark로 Passwall(eth1) 경유하여 Google 국가 분류 확인
if ip link show eth1 >/dev/null 2>&1; then
  iptables -t mangle -I OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
  gemini_geo=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 15 "https://gemini.google.com" 2>/dev/null | grep -oP '"[a-z]{{2}}"' | head -1 | tr -d '"')
  iptables -t mangle -D OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
else
  gemini_geo=$(curl -4 -s -A "$UA" --connect-timeout 5 --max-time 15 "https://gemini.google.com" 2>/dev/null | grep -oP '"[a-z]{{2}}"' | head -1 | tr -d '"')
fi
[ -z "$gemini_geo" ] && gemini_geo="UNKNOWN"
echo "GEMINI_GEO|$gemini_geo"
# 출구IP 확인 (여러 서비스 fallback)
get_exit_ip() {{
  local ip
  ip=$(curl -4 -s --connect-timeout 4 --max-time 8 "https://ifconfig.me" 2>/dev/null | head -1)
  [ -n "$ip" ] && echo "$ip" && return
  ip=$(curl -4 -s --connect-timeout 4 --max-time 8 "https://api.ipify.org" 2>/dev/null | head -1)
  [ -n "$ip" ] && echo "$ip" && return
  ip=$(curl -4 -s --connect-timeout 4 --max-time 8 "http://ip.sb" 2>/dev/null | head -1)
  [ -n "$ip" ] && echo "$ip" && return
  echo ""
}}
if ip link show eth1 >/dev/null 2>&1; then
  iptables -t mangle -I OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
  exitip=$(get_exit_ip)
  iptables -t mangle -D OUTPUT -p tcp --dport 443 -j MARK --set-xmark 0xa 2>/dev/null
  echo "EXITIP|$exitip"
  echo "HAS_ETH1|YES"
else
  exitip=$(get_exit_ip)
  echo "EXITIP|$exitip"
  echo "HAS_ETH1|NO"
fi
'''
    try:
        # SSH 키 인증 우선, 실패 시 sshpass 비밀번호 인증 fallback
        ssh_base = (
            f"ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no "
            f"-o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 "
            f"root@{ip} bash << 'SITECHECKEOF'\n{script}\nSITECHECKEOF"
        )
        result = subprocess.run(ssh_base, shell=True, capture_output=True, text=True, timeout=150)
        if result.returncode != 0:
            # 키 인증 실패 → sshpass 비밀번호로 재시도
            ssh_pass = (
                f"sshpass -p 'ss135690' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 "
                f"root@{ip} bash << 'SITECHECKEOF'\n{script}\nSITECHECKEOF"
            )
            result = subprocess.run(ssh_pass, shell=True, capture_output=True, text=True, timeout=150)

        sites = {}
        exit_ip = ''
        has_eth1 = False
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('SITE|') or line.startswith('RETRY|'):
                parts = line.split('|')
                if len(parts) >= 3:
                    url = parts[1]
                    code = parts[2]
                    is_retry = line.startswith('RETRY|')
                    for key, _name, check_url in SITES_TO_CHECK:
                        if check_url == url:
                            new_ok = bool(code and code[0] in ('2', '3'))
                            if is_retry:
                                # 재시도: 성공하면 덮어쓰기, 실패해도 마지막 결과로 업데이트
                                prev = sites.get(key, {})
                                sites[key] = {
                                    'code': code,
                                    'ok': new_ok,
                                    'retried': True,
                                    'retry_count': prev.get('retry_count', 0) + 1,
                                }
                                if prev.get('first_code'):
                                    sites[key]['first_code'] = prev['first_code']
                                else:
                                    sites[key]['first_code'] = prev.get('code', '')
                            else:
                                sites[key] = {
                                    'code': code,
                                    'ok': new_ok,
                                }
                            break
            elif line.startswith('GEMINI_GEO|'):
                geo = line.split('|')[1].strip()
                # Gemini 차단 국가: cn(중국), 기타 차단 국가 도메인
                GEMINI_BLOCKED_GEOS = {'cn', 'hk', 'ru'}
                if 'gemini' in sites and geo in GEMINI_BLOCKED_GEOS:
                    sites['gemini']['ok'] = False
                    sites['gemini']['blocked'] = True
                    sites['gemini']['geo'] = geo
                elif 'gemini' in sites:
                    sites['gemini']['geo'] = geo
            elif line.startswith('EXITIP|'):
                val = line[7:].strip()
                if val and val != 'NO_ETH1' and val != 'DNS_FAIL':
                    exit_ip = val
                elif val == 'DNS_FAIL':
                    exit_ip = 'DNS_FAIL'
            elif line.startswith('HAS_ETH1|'):
                has_eth1 = line.split('|')[1].strip() == 'YES'

        # Cloudflare/CDN 봇 차단 처리 (403은 정상 — 브라우저 fingerprint 필요)
        # Twitter/X, ChatGPT 등 Cloudflare 보호 사이트는 curl에 403 반환
        BOT_BLOCKED_SITES = {'twitter', 'chatgpt'}
        for site_key in BOT_BLOCKED_SITES:
            if site_key in sites and sites[site_key].get('code') == '403':
                sites[site_key]['bot_blocked'] = True
                sites[site_key]['ok'] = True  # 실제 사이트 접속 가능, curl만 차단

        # KT0/1/2: V2RAY relay를 통해 google/gemini/youtube가 LG3로 우회됨
        V2RAY_RELAY_IPS = {'14.51.2.130', '14.51.2.131', '14.51.2.132'}
        if ip in V2RAY_RELAY_IPS:
            for key in ('gemini',):
                if key in sites and sites[key].get('blocked'):
                    sites[key]['v2ray_relay'] = True
                    sites[key]['relay_via'] = 'LG3 (1.221.16.187)'

        return {
            'ip': ip,
            'name': server_name,
            'sites': sites,
            'exit_ip': exit_ip,
            'exit_ip_diff': bool(exit_ip and exit_ip != ip),
            'has_eth1': has_eth1,
            'ssh_ok': True,
        }
    except subprocess.TimeoutExpired:
        return {
            'ip': ip, 'name': server_name, 'sites': {},
            'exit_ip': '', 'exit_ip_diff': False, 'has_eth1': False,
            'ssh_ok': False, 'error': 'SSH 타임아웃',
        }
    except Exception as e:
        return {
            'ip': ip, 'name': server_name, 'sites': {},
            'exit_ip': '', 'exit_ip_diff': False, 'has_eth1': False,
            'ssh_ok': False, 'error': str(e),
        }


@allow_admin
def api_start_site_check(request):
    """목표사이트 점검 시작 (전체 또는 단일 서버)"""
    if request.method != 'POST':
        return JsonResponse({'result': 400, 'msg': 'POST only'})

    status = _read_site_check_data()
    if status.get('running'):
        if time.time() - status.get('started', 0) < 300:
            return JsonResponse({'result': 409, 'msg': '점검이 이미 진행 중입니다.'})

    target_ip = request.POST.get('ip', '').strip()

    cursor = connections['default'].cursor()
    cursor.execute("SELECT hostip, name FROM tbl_agent3 WHERE is_active=1")
    servers = [{'ip': r[0], 'name': r[1]} for r in cursor.fetchall()]

    if target_ip:
        servers = [s for s in servers if s['ip'] == target_ip]
        if not servers:
            return JsonResponse({'result': 404, 'msg': 'Server not found'})

    started = time.time()
    _write_site_check_data({
        'running': True, 'started': started,
        'total': len(servers), 'completed': 0,
        'results': status.get('results', []),  # 이전 결과 유지
    })

    def run_check():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 단일 서버면 기존 결과에 merge, 전체면 새로 수집
        prev_results = {}
        if target_ip and status.get('results'):
            for r in status['results']:
                prev_results[r['ip']] = r

        new_results = {}
        completed = 0

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_check_single_server_sites, s['ip'], s['name']): s
                for s in servers
            }
            for future in as_completed(futures):
                s = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = {
                        'ip': s['ip'], 'name': s['name'], 'sites': {},
                        'exit_ip': '', 'exit_ip_diff': False,
                        'ssh_ok': False, 'error': str(e),
                    }
                new_results[r['ip']] = r
                completed += 1

                # 중간 상태 업데이트 — 새 결과를 이전 결과에 merge
                merged = dict(prev_results)
                merged.update(new_results)
                merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))
                _write_site_check_data({
                    'running': True, 'started': started,
                    'total': len(servers), 'completed': completed,
                    'results': merged_list,
                })

        merged = dict(prev_results)
        merged.update(new_results)
        merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))

        # ===== 실패 서버 자동 1회 재점검 (전체 점검 시에만) =====
        if not target_ip:
            def _is_failed(r):
                if not r.get('ssh_ok'):
                    return True
                if not r.get('exit_ip'):
                    return True
                for k, chk in (r.get('sites') or {}).items():
                    if chk and not chk.get('ok') and not chk.get('blocked'):
                        return True
                return False

            failed_servers = [r for r in merged_list if _is_failed(r)]
            if failed_servers:
                import logging
                logger = logging.getLogger('nasmonitor')
                logger.info(f"[site_check] {len(failed_servers)}개 실패 서버 자동 재점검 시작")
                _write_site_check_data({
                    'running': True, 'started': started,
                    'total': len(servers), 'completed': len(servers),
                    'results': merged_list,
                    'retry': True, 'retry_count': len(failed_servers),
                })
                retry_results = {}
                with ThreadPoolExecutor(max_workers=4) as executor:
                    retry_futures = {
                        executor.submit(_check_single_server_sites, r['ip'], r['name']): r
                        for r in failed_servers
                    }
                    for future in as_completed(retry_futures):
                        r_orig = retry_futures[future]
                        try:
                            r_new = future.result()
                        except Exception as e:
                            r_new = None  # 재시도 실패 → 원래 결과 유지

                        if r_new is None:
                            continue  # 에러 시 원래 결과 유지

                        # 재시도 결과가 원래보다 나을 때만 교체
                        orig = merged.get(r_orig['ip'], r_orig)
                        orig_ok_cnt = sum(1 for c in (orig.get('sites') or {}).values() if c and c.get('ok'))
                        new_ok_cnt = sum(1 for c in (r_new.get('sites') or {}).values() if c and c.get('ok'))
                        if r_new.get('ssh_ok') and (new_ok_cnt > orig_ok_cnt or (not orig.get('ssh_ok') and r_new.get('ssh_ok'))):
                            retry_results[r_new['ip']] = r_new
                        # 그렇지 않으면 원래 결과 유지
                # merge retry results
                merged.update(retry_results)
                merged_list = sorted(merged.values(), key=lambda x: x.get('name', ''))
                retry_ok = len([r for r in retry_results.values() if not _is_failed(r)])
                logger.info(f"[site_check] 재점검 완료: {retry_ok}/{len(failed_servers)}개 복구")

        _write_site_check_data({
            'running': False, 'started': started, 'finished': time.time(),
            'total': len(servers), 'completed': len(servers),
            'results': merged_list,
            'elapsed': round(time.time() - started, 1),
        })

        # DB에도 저장 (titan에서 고객 페이지용으로 읽을 수 있도록)
        try:
            from django.db import connections as _conns
            _cur = _conns['default'].cursor()
            ok_cnt = len([r for r in merged_list if r.get('ssh_ok')])
            fail_cnt = len(merged_list) - ok_cnt
            report = json.dumps({'servers': merged_list}, ensure_ascii=False, default=str)
            _cur.execute(
                "INSERT INTO tbl_nas_monitor_log (check_time, check_type, total_servers, ok_count, warning_count, critical_count, report_json) "
                "VALUES (NOW(), 'site_check', %s, %s, 0, %s, %s)",
                [len(merged_list), ok_cnt, fail_cnt, report]
            )
        except Exception:
            pass

    t = threading.Thread(target=run_check, daemon=True)
    t.start()
    return JsonResponse({'result': 200, 'msg': f'{len(servers)}개 서버 점검을 시작했습니다.'})


@allow_admin
def api_read_site_check_status(request):
    """목표사이트 점검 상태/결과 조회"""
    data = _read_site_check_data()
    running = data.get('running', False)
    started = data.get('started')
    elapsed = round(time.time() - started, 1) if started and running else data.get('elapsed')

    return JsonResponse({
        'result': 200,
        'running': running,
        'total': data.get('total', 0),
        'completed': data.get('completed', 0),
        'elapsed': elapsed,
        'retry': data.get('retry', False),
        'retry_count': data.get('retry_count', 0),
        'results': data.get('results', []),
        'sites': [{'key': s[0], 'name': s[1]} for s in SITES_TO_CHECK],
    })
