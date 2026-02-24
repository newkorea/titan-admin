#!/usr/bin/env python3
"""
유저 문제 자동 분석 & 통지 생성 스크립트
- 2시간마다 크론으로 실행
- 실패율 높은 유저, 강제종료 빈번 유저, ISP 이상 감지
- tbl_notification에 pending 통지 생성 → 관리자 승인 후 앱 통지

Usage:
    python3 analyze_user_issues.py                  # 최근 2시간 분석
    python3 analyze_user_issues.py --hours 24       # 최근 24시간
    python3 analyze_user_issues.py --dry-run        # DB 저장 없이 미리보기
    python3 analyze_user_issues.py --force           # 중복 체크 없이 강제 생성
"""

import os, sys, json, logging, argparse
from datetime import datetime, timedelta
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)

# Django setup
sys.path.insert(0, '/home/newkorea/project/titan-admin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from django.db import connections
from backend.djangoapps.common.views import dictfetchall

LOG_FILE = '/home/newkorea/project/scripts/analyze_user_issues.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ===== 설정 =====
FAIL_RATE_CRITICAL = 30      # 성공률 30% 미만 = CRITICAL
FAIL_RATE_WARNING = 60       # 성공률 60% 미만 = WARNING
MIN_SESSIONS = 5             # 최소 세션 수 (이하면 무시)
MIN_FAILS = 10               # 최소 실패 수 (실패 10회 미만이면 통지 안 함)
DISCONNECT_THRESHOLD = 5     # 2시간 내 강제종료 N회 이상
ISP_ANOMALY_THRESHOLD = 0.3  # ISP 전체 실패율 30% 이상이면 이상
ISP_MIN_USERS = 3            # ISP 이상 감지 최소 유저 수

PROTO_MAP = {
    'Virtual': 'IKEv2', 'ISDN': 'OpenVPN', '61': 'SSTP', 'V2RAY': 'V2RAY'
}

# ===== 한국어 + 중국어 통지 메시지 템플릿 =====
MSG_TEMPLATES = {
    'fail_rate_critical': {
        'title': '[긴급] {email} 접속 성공률 {rate}% — 심각한 연결 문제',
        'recommendation': (
            '🔧 연결 개선 안내\n'
            '현재 접속 성공률이 낮습니다. 다음을 시도해 보세요:\n'
            '1. 앱에서 "서버 자동선택" 사용\n'
            '2. 프로토콜을 {best_proto}로 변경\n'
            '3. 추천 서버: {best_servers}\n'
            '4. WiFi ↔ 모바일 데이터 전환 시도\n'
            '\n'
            '🔧 连接改善指南\n'
            '当前连接成功率较低，请尝试以下方法：\n'
            '1. 在APP中使用"自动选择服务器"\n'
            '2. 将协议更改为{best_proto}\n'
            '3. 推荐服务器：{best_servers}\n'
            '4. 尝试切换WiFi和移动数据'
        )
    },
    'fail_rate_warning': {
        'title': '[주의] {email} 접속 성공률 {rate}% — 연결 불안정',
        'recommendation': (
            '📡 연결 안정화 안내\n'
            '일부 서버에서 연결 문제가 감지되었습니다.\n'
            '추천 서버: {best_servers}\n'
            '추천 프로토콜: {best_proto}\n'
            '\n'
            '📡 连接稳定化指南\n'
            '在部分服务器上检测到连接问题。\n'
            '推荐服务器：{best_servers}\n'
            '推荐协议：{best_proto}'
        )
    },
    'disconnect_frequent': {
        'title': '[강제종료] {email} — {hours}h 내 {count}회 강제종료',
        'recommendation': (
            '⚠️ 동시접속 초과 안내\n'
            '여러 기기에서 동시 접속하여 강제종료가 발생했습니다.\n'
            '허용 기기수: {session_limit}대\n'
            '해결: 사용하지 않는 기기의 VPN을 먼저 끊어주세요.\n'
            '\n'
            '⚠️ 同时连接超限通知\n'
            '由于多台设备同时连接，已被强制断开。\n'
            '允许设备数：{session_limit}台\n'
            '解决方法：请先断开未使用设备的VPN连接。'
        )
    },
    'isp_anomaly': {
        'title': '[ISP이상] {isp} — 실패율 {rate}% ({user_count}명 영향)',
        'recommendation': (
            '🌐 네트워크 불안정 안내\n'
            '현재 {isp} 네트워크에서 접속 장애가 감지되었습니다.\n'
            '추천: {best_proto} 프로토콜로 변경하거나 잠시 후 재시도해 주세요.\n'
            '\n'
            '🌐 网络不稳定通知\n'
            '当前{isp}网络检测到连接故障。\n'
            '建议：请更改为{best_proto}协议或稍后重试。'
        )
    },
    'win_ikev2_miniport': {
        'title': '[Windows] {email} — IKEv2 연속 실패 ({fail_count}회), 미니포트 갱신 필요',
        'recommendation': (
            '🖥️ Windows IKEv2 미니포트 갱신 안내\n'
            'Windows에서 IKEv2 연결이 계속 실패하고 있습니다.\n'
            'WAN Miniport (IKEv2) 드라이버를 재설치하면 해결됩니다.\n'
            '\n'
            '해결 방법:\n'
            '1. "장치 관리자"를 관리자 권한으로 실행\n'
            '2. "네트워크 어댑터" 펼치기\n'
            '3. "WAN Miniport (IKEv2)" 우클릭 → "디바이스 제거"\n'
            '4. 상단 메뉴 "동작" → "하드웨어 변경 사항 검색" 클릭\n'
            '5. 자동으로 재설치됨 → VPN 재연결\n'
            '\n'
            '그래도 안 되면:\n'
            '- 관리자 CMD에서: netsh winsock reset 실행 후 재부팅\n'
            '- 또는 프로토콜을 SSTP나 OpenVPN으로 변경\n'
            '\n'
            '🖥️ Windows IKEv2 WAN Miniport 更新指南\n'
            'Windows上IKEv2连接持续失败。\n'
            '重新安装WAN Miniport (IKEv2)驱动程序可以解决此问题。\n'
            '\n'
            '解决方法：\n'
            '1. 以管理员权限打开"设备管理器"\n'
            '2. 展开"网络适配器"\n'
            '3. 右键"WAN Miniport (IKEv2)" → "卸载设备"\n'
            '4. 点击菜单"操作" → "扫描检测硬件改动"\n'
            '5. 自动重新安装 → 重新连接VPN\n'
            '\n'
            '如仍无法解决：\n'
            '- 管理员CMD中执行: netsh winsock reset 后重启\n'
            '- 或将协议更改为SSTP或OpenVPN'
        )
    }
}


def get_cursor():
    return connections['default'].cursor()


def resolve_server_name(cursor, ip):
    """IP → 서버명"""
    cursor.execute("SELECT name FROM tbl_agent3 WHERE hostip=%s LIMIT 1", [ip])
    rows = dictfetchall(cursor)
    if rows:
        return rows[0]['name']
    # DHCP hostname
    if 'jobjapan' in ip or '.' not in ip:
        parts = ip.replace('.jobjapan.net', '').replace('.jobjapan.com', '')
        return parts.upper().replace('KT10GDHCP', 'KOREA-LG').replace('KTDB', 'KOREA-KT').replace('KTD', 'KOREA-KT')
    return ip


def analyze_fail_rate(cursor, hours, batch_id, dry_run=False, force=False):
    """실패율 높은 유저 감지"""
    notifications = []
    
    # Step 1: 중국 유저 이메일 목록 (최근 로그인 기준)
    cursor.execute("""
        SELECT DISTINCT u.email
        FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.device_country = 'China'
          AND d.login_time >= NOW() - INTERVAL 7 DAY
    """)
    china_emails = set(r['email'] for r in dictfetchall(cursor))
    if not china_emails:
        log.info("중국 유저 없음 — 스킵")
        return notifications
    log.info(f"중국 유저 {len(china_emails)}명 감지")
    
    # Step 2: radacct에서 분석 (China 유저만)
    placeholders = ','.join(['%s'] * len(china_emails))
    cursor.execute(f"""
        SELECT r.username,
               SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
               SUM(CASE WHEN r.acctsessiontime <= 10 AND r.acctterminatecause = 'User-Request' THEN 1 ELSE 0 END) as rotation,
               SUM(CASE WHEN r.acctsessiontime <= 10 AND (r.acctterminatecause IS NULL OR r.acctterminatecause != 'User-Request') THEN 1 ELSE 0 END) as fail,
               COUNT(*) as total
        FROM radius.radacct r
        WHERE r.acctstarttime >= NOW() - INTERVAL %s HOUR
          AND r.username IN ({placeholders})
        GROUP BY r.username
        HAVING COUNT(*) >= %s
           AND SUM(CASE WHEN r.acctsessiontime <= 10 AND (r.acctterminatecause IS NULL OR r.acctterminatecause != 'User-Request') THEN 1 ELSE 0 END) >= %s
    """, [hours] + list(china_emails) + [MIN_SESSIONS, MIN_FAILS])
    
    users = dictfetchall(cursor)
    log.info(f"실패율 분석: {len(users)}명 대상 (>={MIN_SESSIONS} 세션)")
    
    for u in users:
        real_total = u['success'] + u['fail']
        if real_total == 0:
            continue
        rate = round(u['success'] / real_total * 100, 1)
        
        if rate >= FAIL_RATE_WARNING:
            continue
            
        severity = 'critical' if rate < FAIL_RATE_CRITICAL else 'warning'
        noti_type = 'fail_rate'
        
        # 중복 체크: 같은 유저에게 24시간 내 같은 타입 통지가 있으면 스킵
        if not force:
            cursor.execute("""
                SELECT id FROM tbl_notification 
                WHERE username=%s AND noti_type=%s AND created_at >= NOW() - INTERVAL 24 HOUR
                  AND status IN ('pending', 'approved', 'sent')
            """, [u['username'], noti_type])
            if dictfetchall(cursor):
                log.debug(f"  스킵 (24h 내 중복): {u['username']}")
                continue
        
        # 서버별 성과 분석
        cursor.execute("""
            SELECT r.nasipaddress,
                   SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN r.acctsessiontime <= 10 AND (r.acctterminatecause IS NULL OR r.acctterminatecause != 'User-Request') THEN 1 ELSE 0 END) as fail,
                   MAX(r.acctsessiontime) as max_dur
            FROM radius.radacct r
            WHERE r.username = %s AND r.acctstarttime >= NOW() - INTERVAL %s HOUR
            GROUP BY r.nasipaddress
            ORDER BY success DESC
        """, [u['username'], hours])
        servers = dictfetchall(cursor)
        
        best_servers = []
        for s in servers:
            name = resolve_server_name(cursor, s['nasipaddress'])
            st = s['success'] + s['fail']
            sr = round(s['success'] / st * 100) if st > 0 else 0
            if sr >= 70 and s['success'] >= 2:
                best_servers.append(name)
        
        # 프로토콜별 성과
        cursor.execute("""
            SELECT r.nasporttype,
                   SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN r.acctsessiontime <= 10 AND (r.acctterminatecause IS NULL OR r.acctterminatecause != 'User-Request') THEN 1 ELSE 0 END) as fail
            FROM radius.radacct r
            WHERE r.username = %s AND r.acctstarttime >= NOW() - INTERVAL %s HOUR
            GROUP BY r.nasporttype
        """, [u['username'], hours])
        protos = dictfetchall(cursor)
        
        best_proto = 'IKEv2'
        best_proto_rate = 0
        for p in protos:
            pname = PROTO_MAP.get(p['nasporttype'], p['nasporttype'])
            pt = p['success'] + p['fail']
            pr = p['success'] / pt * 100 if pt > 0 else 0
            if pr > best_proto_rate:
                best_proto_rate = pr
                best_proto = pname
        
        tmpl_key = 'fail_rate_critical' if severity == 'critical' else 'fail_rate_warning'
        tmpl = MSG_TEMPLATES[tmpl_key]
        
        bs_str = ', '.join(best_servers[:3]) if best_servers else '자동선택 권장'
        title = tmpl['title'].format(email=u['username'], rate=rate)
        recommendation = tmpl['recommendation'].format(best_proto=best_proto, best_servers=bs_str)
        
        message = (
            f"성공: {u['success']}건, 실패: {u['fail']}건, 로테이션: {u['rotation']}건, "
            f"전체: {u['total']}건\n"
            f"실질 성공률: {rate}%\n"
            f"추천 서버: {bs_str}\n"
            f"추천 프로토콜: {best_proto} ({best_proto_rate:.0f}%)"
        )
        
        analysis = {
            'success': u['success'], 'fail': u['fail'], 'rotation': u['rotation'],
            'total': u['total'], 'rate': rate, 'best_servers': best_servers[:3],
            'best_proto': best_proto, 'hours': hours
        }
        
        notifications.append({
            'username': u['username'], 'noti_type': noti_type, 'severity': severity,
            'title': title, 'message': message, 'recommendation': recommendation,
            'analysis_json': json.dumps(analysis, ensure_ascii=False, cls=DecimalEncoder), 'batch_id': batch_id
        })
        
        log.info(f"  [{severity.upper()}] {u['username']}: 성공률 {rate}% (성공{u['success']}/실패{u['fail']})")
    
    return notifications


def analyze_disconnects(cursor, hours, batch_id, dry_run=False, force=False):
    """강제종료 빈번 유저 감지"""
    notifications = []
    
    cursor.execute("""
        SELECT d.username, COUNT(*) as cnt,
               MAX(d.connected_count) as max_conn,
               MAX(d.user_session) as session_limit,
               GROUP_CONCAT(DISTINCT d.server_name ORDER BY d.server_name) as servers,
               GROUP_CONCAT(DISTINCT d.protocol ORDER BY d.protocol) as protos
        FROM tbl_disconnection d
        WHERE d.disconnected_time >= NOW() - INTERVAL %s HOUR
        GROUP BY d.username
        HAVING cnt >= %s
        ORDER BY cnt DESC
    """, [hours, DISCONNECT_THRESHOLD])
    
    users = dictfetchall(cursor)
    log.info(f"강제종료 분석: {len(users)}명 감지 (>={DISCONNECT_THRESHOLD}회/{hours}h)")
    
    for u in users:
        # 중복 체크
        if not force:
            cursor.execute("""
                SELECT id FROM tbl_notification 
                WHERE username=%s AND noti_type='disconnect' AND created_at >= NOW() - INTERVAL 24 HOUR
                  AND status IN ('pending', 'approved', 'sent')
            """, [u['username']])
            if dictfetchall(cursor):
                continue
        
        severity = 'critical' if u['cnt'] >= DISCONNECT_THRESHOLD * 3 else 'warning'
        
        tmpl = MSG_TEMPLATES['disconnect_frequent']
        title = tmpl['title'].format(email=u['username'], hours=hours, count=u['cnt'])
        recommendation = tmpl['recommendation'].format(session_limit=u['session_limit'] or 2)
        
        message = (
            f"강제종료: {u['cnt']}회 (최근 {hours}시간)\n"
            f"최대 동시접속: {u['max_conn']} / 허용: {u['session_limit']}\n"
            f"서버: {u['servers']}\n"
            f"프로토콜: {u['protos']}"
        )
        
        analysis = {
            'count': u['cnt'], 'max_conn': u['max_conn'],
            'session_limit': u['session_limit'], 'servers': u['servers'],
            'protos': u['protos'], 'hours': hours
        }
        
        notifications.append({
            'username': u['username'], 'noti_type': 'disconnect', 'severity': severity,
            'title': title, 'message': message, 'recommendation': recommendation,
            'analysis_json': json.dumps(analysis, ensure_ascii=False, cls=DecimalEncoder), 'batch_id': batch_id
        })
        
        log.info(f"  [{severity.upper()}] {u['username']}: {u['cnt']}회 강제종료")
    
    return notifications


def analyze_isp_anomaly(cursor, hours, batch_id, dry_run=False, force=False):
    """ISP별 이상 감지 (관리자 참고용 — 앱 발송 안 함)"""
    notifications = []
    
    # 중국 유저의 ISP 매핑 가져오기 (2-step: 먼저 이메일+ISP 수집, 후 radacct 조회)
    cursor.execute("""
        SELECT u.email, d.device_isp, d.id as did
        FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.device_country = 'China'
          AND d.login_time >= NOW() - INTERVAL 7 DAY
          AND d.device_isp IS NOT NULL AND d.device_isp != ''
        ORDER BY d.id DESC
    """)
    # 유저별 가장 최신 ISP만 유지
    email_isp = {}
    for r in dictfetchall(cursor):
        if r['email'] not in email_isp:
            email_isp[r['email']] = r['device_isp']
    if not email_isp:
        return notifications
    
    # ISP별 전체 등록 유저 수 집계
    isp_registered = {}
    for email, isp in email_isp.items():
        isp_registered[isp] = isp_registered.get(isp, 0) + 1
    
    china_emails_list = list(email_isp.keys())
    placeholders = ','.join(['%s'] * len(china_emails_list))
    cursor.execute(f"""
        SELECT r.username,
               SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
               SUM(CASE WHEN r.acctsessiontime <= 10 AND (r.acctterminatecause IS NULL OR r.acctterminatecause != 'User-Request') THEN 1 ELSE 0 END) as fail,
               COUNT(*) as total
        FROM radius.radacct r
        WHERE r.acctstarttime >= NOW() - INTERVAL %s HOUR
          AND r.username IN ({placeholders})
        GROUP BY r.username
    """, [hours] + china_emails_list)
    user_stats = dictfetchall(cursor)
    
    # ISP별 집계 (상세 브레이크다운 포함)
    isp_agg = {}
    for us in user_stats:
        isp = email_isp.get(us['username'], 'Unknown')
        if isp not in isp_agg:
            isp_agg[isp] = {'isp': isp, 'active_users': 0, 'ok_users': 0, 'partial_fail_users': 0,
                            'full_fail_users': 0, 'success': 0, 'fail': 0, 'total': 0}
        a = isp_agg[isp]
        a['active_users'] += 1
        a['success'] += us['success']
        a['fail'] += us['fail']
        a['total'] += us['total']
        if us['fail'] == 0:
            a['ok_users'] += 1
        elif us['success'] == 0:
            a['full_fail_users'] += 1
        else:
            a['partial_fail_users'] += 1
    
    isps = [v for v in isp_agg.values() if v['active_users'] >= ISP_MIN_USERS and v['total'] >= 10]
    log.info(f"ISP 이상 분석: {len(isps)}개 ISP 대상")
    
    for isp in isps:
        real_total = isp['success'] + isp['fail']
        if real_total == 0:
            continue
        rate = round(isp['fail'] / real_total * 100, 1)
        
        if rate < ISP_ANOMALY_THRESHOLD * 100:
            continue
        
        isp_name = isp['isp'] or 'Unknown'
        registered = isp_registered.get(isp_name, 0)
        
        if not force:
            cursor.execute("""
                SELECT id FROM tbl_notification 
                WHERE noti_type='isp_anomaly' AND created_at >= NOW() - INTERVAL 6 HOUR
                  AND status IN ('pending', 'approved', 'sent')
                  AND title LIKE %s
            """, [f'%{isp_name}%'])
            if dictfetchall(cursor):
                continue
        
        # 프로토콜별 성과 (해당 ISP 유저들)
        isp_users = [email for email, isp_val in email_isp.items() if isp_val == isp_name]
        if not isp_users:
            continue
        ph2 = ','.join(['%s'] * len(isp_users))
        cursor.execute(f"""
            SELECT r.nasporttype,
                   SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN r.acctsessiontime <= 10 THEN 1 ELSE 0 END) as fail
            FROM radius.radacct r
            WHERE r.acctstarttime >= NOW() - INTERVAL %s HOUR
              AND r.username IN ({ph2})
            GROUP BY r.nasporttype
        """, [hours] + isp_users)
        protos = dictfetchall(cursor)
        
        best_proto = None
        best_rate = 0
        proto_details = []
        for p in protos:
            pname = PROTO_MAP.get(p['nasporttype'], p['nasporttype'])
            pt = p['success'] + p['fail']
            pr = p['success'] / pt * 100 if pt > 0 else 0
            proto_details.append(f"{pname} {pr:.0f}%(성공{p['success']}/실패{p['fail']})")
            if pr > best_rate:
                best_rate = pr
                best_proto = pname
        
        # 추천 프로토콜 판단
        if best_rate >= 50:
            proto_advice = f"추천: {best_proto} ({best_rate:.0f}%)"
        elif best_rate > 0:
            proto_advice = f"전체 불안정 (최선: {best_proto} {best_rate:.0f}%)"
        else:
            proto_advice = "전체 프로토콜 장애"
        
        severity = 'critical' if rate >= 50 else 'warning'
        
        title = f'[ISP이상] {isp_name} — 실패율 {rate}% (활동 {isp["active_users"]}명/{registered}명 등록)'
        
        message = (
            f"ISP: {isp_name}\n"
            f"등록 유저(7일): {registered}명 | 활동 유저({hours}h): {isp['active_users']}명\n"
            f"  ├ 정상: {isp['ok_users']}명 | 부분실패: {isp['partial_fail_users']}명 | 완전실패: {isp['full_fail_users']}명\n"
            f"세션: 성공 {isp['success']}건, 실패 {isp['fail']}건 (실패율 {rate}%)\n"
            f"프로토콜별: {' | '.join(proto_details)}\n"
            f"{proto_advice}"
        )
        
        recommendation = (
            f"관리자 참고용 (ISP 이상 리포트)\n"
            f"{isp_name}에서 실패율 {rate}% 감지\n"
            f"활동 {isp['active_users']}명 중 완전실패 {isp['full_fail_users']}명\n"
            f"{proto_advice}\n"
            f"\n이 통지는 관리자 현황 파악용이며, 고객에게 직접 발송되지 않습니다."
        )
        
        analysis = {
            'isp': isp_name, 'registered': registered, 'active_users': isp['active_users'],
            'ok_users': isp['ok_users'], 'partial_fail': isp['partial_fail_users'],
            'full_fail': isp['full_fail_users'],
            'success': isp['success'], 'fail': isp['fail'], 'rate': rate,
            'proto_details': proto_details, 'best_proto': best_proto or 'N/A',
            'best_rate': best_rate, 'hours': hours, 'admin_only': True
        }
        
        notifications.append({
            'username': f'ISP:{isp_name}', 'noti_type': 'isp_anomaly', 'severity': severity,
            'title': title, 'message': message, 'recommendation': recommendation,
            'analysis_json': json.dumps(analysis, ensure_ascii=False, cls=DecimalEncoder), 'batch_id': batch_id
        })
        
        log.info(f"  [{severity.upper()}] ISP {isp_name}: 실패율 {rate}% (활동{isp['active_users']}/{registered}등록, 완전실패{isp['full_fail_users']}명)")
    
    return notifications


# Windows IKEv2 미니포트 분석 설정
WIN_IKEV2_MIN_FAIL = 2  # 최소 실패 횟수


def analyze_win_ikev2_fail(cursor, hours, batch_id, dry_run=False, force=False):
    """Windows에서 IKEv2가 항시 실패하는 유저 감지 → 미니포트 갱신 안내"""
    notifications = []

    # Step 1: 최근 7일 내 Windows + 중국 유저 이메일 목록
    cursor.execute("""
        SELECT DISTINCT u.email
        FROM tbl_device_info d
        JOIN tbl_user u ON d.user_id = u.id
        WHERE d.device_type = 'Windows'
          AND d.device_country = 'China'
          AND d.login_time >= NOW() - INTERVAL 7 DAY
    """)
    win_emails = [r['email'] for r in dictfetchall(cursor)]
    if not win_emails:
        log.info("Windows 중국 유저 없음 — 스킵")
        return notifications
    log.info(f"Windows 중국 유저 {len(win_emails)}명 감지")

    # Step 2: radacct에서 IKEv2(Virtual)만 필터, 성공 0 + 실패 N회 이상
    placeholders = ','.join(['%s'] * len(win_emails))
    cursor.execute(f"""
        SELECT r.username,
               SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
               SUM(CASE WHEN r.acctsessiontime <= 10 THEN 1 ELSE 0 END) as fail,
               COUNT(*) as total,
               GROUP_CONCAT(DISTINCT r.nasipaddress ORDER BY r.nasipaddress) as servers
        FROM radius.radacct r
        WHERE r.acctstarttime >= NOW() - INTERVAL %s HOUR
          AND r.nasporttype = 'Virtual'
          AND r.username IN ({placeholders})
        GROUP BY r.username
        HAVING SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) = 0
           AND SUM(CASE WHEN r.acctsessiontime <= 10 THEN 1 ELSE 0 END) >= %s
        ORDER BY fail DESC
    """, [hours] + win_emails + [WIN_IKEV2_MIN_FAIL])
    users = dictfetchall(cursor)
    log.info(f"Windows IKEv2 항시실패: {len(users)}명 감지 (성공0, 실패>={WIN_IKEV2_MIN_FAIL}회/{hours}h)")

    for u in users:
        # 중복 체크: 같은 유저에게 48시간 내 같은 타입 통지가 있으면 스킵 (미니포트 갱신은 시간이 걸림)
        if not force:
            cursor.execute("""
                SELECT id FROM tbl_notification
                WHERE username=%s AND noti_type='win_ikev2_miniport'
                  AND created_at >= NOW() - INTERVAL 48 HOUR
                  AND status IN ('pending', 'approved', 'sent')
            """, [u['username']])
            if dictfetchall(cursor):
                log.debug(f"  스킵 (48h 내 중복): {u['username']}")
                continue

        # 해당 유저가 다른 프로토콜로는 성공하는지 확인
        cursor.execute("""
            SELECT r.nasporttype,
                   SUM(CASE WHEN r.acctsessiontime > 10 THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN r.acctsessiontime <= 10 THEN 1 ELSE 0 END) as fail
            FROM radius.radacct r
            WHERE r.username = %s AND r.acctstarttime >= NOW() - INTERVAL %s HOUR
              AND r.nasporttype != 'Virtual'
            GROUP BY r.nasporttype
        """, [u['username'], hours])
        other_protos = dictfetchall(cursor)

        other_proto_info = []
        for p in other_protos:
            pname = PROTO_MAP.get(p['nasporttype'], p['nasporttype'])
            pt = p['success'] + p['fail']
            pr = round(p['success'] / pt * 100) if pt > 0 else 0
            other_proto_info.append(f"{pname}({pr}%)")

        # 서버명 변환
        server_ips = (u.get('servers') or '').split(',')
        server_names = []
        for ip in server_ips[:5]:
            ip = ip.strip()
            if ip:
                server_names.append(resolve_server_name(cursor, ip))

        severity = 'warning'
        if u['fail'] >= 5:
            severity = 'critical'

        tmpl = MSG_TEMPLATES['win_ikev2_miniport']
        title = tmpl['title'].format(email=u['username'], fail_count=u['fail'])
        recommendation = tmpl['recommendation']

        message = (
            f"Windows IKEv2 항시 실패\n"
            f"IKEv2 시도: {u['total']}회 (성공 0, 실패 {u['fail']})\n"
            f"시도한 서버: {', '.join(server_names) if server_names else 'N/A'}\n"
            f"다른 프로토콜: {', '.join(other_proto_info) if other_proto_info else '시도 기록 없음'}\n"
            f"→ WAN Miniport(IKEv2) 갱신 필요"
        )

        analysis = {
            'fail_count': u['fail'], 'total': u['total'],
            'servers': server_names, 'other_protos': other_proto_info,
            'hours': hours, 'device': 'Windows', 'protocol': 'IKEv2'
        }

        notifications.append({
            'username': u['username'], 'noti_type': 'win_ikev2_miniport', 'severity': severity,
            'title': title, 'message': message, 'recommendation': recommendation,
            'analysis_json': json.dumps(analysis, ensure_ascii=False, cls=DecimalEncoder),
            'batch_id': batch_id
        })

        log.info(f"  [{severity.upper()}] {u['username']}: IKEv2 실패 {u['fail']}회 (Windows 미니포트)")

    return notifications


def save_notifications(cursor, notifications):
    """통지를 DB에 저장"""
    saved = 0
    for n in notifications:
        cursor.execute("""
            INSERT INTO tbl_notification (username, noti_type, severity, title, message, recommendation, analysis_json, status, batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)
        """, [n['username'], n['noti_type'], n['severity'], n['title'], n['message'],
              n['recommendation'], n['analysis_json'], n['batch_id']])
        saved += 1
    return saved


def main():
    parser = argparse.ArgumentParser(description='유저 문제 자동 분석 & 통지 생성')
    parser.add_argument('--hours', type=int, default=2, help='분석 기간 (시간, 기본 2)')
    parser.add_argument('--dry-run', action='store_true', help='DB 저장 없이 미리보기')
    parser.add_argument('--force', action='store_true', help='중복 체크 없이 강제 생성')
    args = parser.parse_args()
    
    batch_id = datetime.now().strftime('%Y%m%d%H%M')
    log.info(f"===== 유저 문제 분석 시작 (batch: {batch_id}, hours: {args.hours}) =====")
    
    cursor = get_cursor()
    all_notifications = []
    
    # 1. 실패율 분석
    try:
        noti = analyze_fail_rate(cursor, args.hours, batch_id, args.dry_run, args.force)
        all_notifications.extend(noti)
    except Exception as e:
        log.error(f"실패율 분석 에러: {e}", exc_info=True)
    
    # 2. 강제종료 분석
    try:
        noti = analyze_disconnects(cursor, args.hours, batch_id, args.dry_run, args.force)
        all_notifications.extend(noti)
    except Exception as e:
        log.error(f"강제종료 분석 에러: {e}", exc_info=True)
    
    # 3. ISP 이상 감지
    try:
        noti = analyze_isp_anomaly(cursor, args.hours, batch_id, args.dry_run, args.force)
        all_notifications.extend(noti)
    except Exception as e:
        log.error(f"ISP 분석 에러: {e}", exc_info=True)
    
    # 4. Windows IKEv2 미니포트 분석
    try:
        noti = analyze_win_ikev2_fail(cursor, args.hours, batch_id, args.dry_run, args.force)
        all_notifications.extend(noti)
    except Exception as e:
        log.error(f"Windows IKEv2 분석 에러: {e}", exc_info=True)
    
    # 결과
    log.info(f"총 통지 생성: {len(all_notifications)}건 (fail_rate: {sum(1 for n in all_notifications if n['noti_type']=='fail_rate')}, "
             f"disconnect: {sum(1 for n in all_notifications if n['noti_type']=='disconnect')}, "
             f"isp_anomaly: {sum(1 for n in all_notifications if n['noti_type']=='isp_anomaly')}, "
             f"win_ikev2: {sum(1 for n in all_notifications if n['noti_type']=='win_ikev2_miniport')})")
    
    if args.dry_run:
        log.info("=== DRY RUN — DB 저장 안 함 ===")
        for n in all_notifications:
            print(f"\n[{n['severity'].upper()}] {n['title']}")
            print(f"  {n['message']}")
            print(f"  → 추천: {n['recommendation'][:100]}...")
    else:
        saved = save_notifications(cursor, all_notifications)
        log.info(f"DB 저장 완료: {saved}건")
    
    log.info(f"===== 분석 완료 (batch: {batch_id}) =====")
    return len(all_notifications)


if __name__ == '__main__':
    main()
