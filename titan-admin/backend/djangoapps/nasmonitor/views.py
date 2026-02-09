import json
import subprocess
import threading
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

    return JsonResponse({'result': 200, 'health': health, 'service': service})


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
                    SELECT server_ip, cn_telecom, MAX(check_time) AS max_ct
                    FROM titan.tbl_server_telecom_ping
                    WHERE check_time > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    AND cn_telecom = %s
                    GROUP BY server_ip, cn_telecom
                ) latest ON p.server_ip = latest.server_ip AND p.check_time = latest.max_ct
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
