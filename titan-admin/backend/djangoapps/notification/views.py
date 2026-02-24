# 알림 관리 — 푸시 알림 발송·조회
import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from django.db import transaction

# (2023-05-25) Added by Zhao
@allow_admin
def notification(request):
    context = {}
    return render(request, 'admin/notification.html', context)

# (2023-05-25) Added by Zhao
@allow_admin
def api_delete_notification(request):
    notification_id = request.POST.get('notification_id')
    try:
        tb = TblNotice.objects.get(id=notification_id)
        tb.delete_yn = 'Y'
        tb.delete_date = datetime.datetime.now()
        tb.save()
        title, text = get_swal('SUCCESS_REGIST_BAN_DEL')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        print('err => ', err)
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})


# (2023-05-25) Added by Zhao
@allow_admin
def get_notifications(request):

    # datatables 기본 파라미터
    platform = request.POST.get('platform')
    start_at = request.POST.get('start_at')
    end_at = request.POST.get('end_at')
    
    start = int(request.POST.get('start'))
    length = int(request.POST.get('length'))
    draw = int(request.POST.get('draw'))
    orderby_col = int(request.POST.get('order[0][column]'))
    orderby_opt = request.POST.get('order[0][dir]')
    
    wc = ' where 1=1 '
    if platform != 'All':
        wc += " and platform = '{platform}' ".format(platform=platform)
    if start_at != '':
        wc += '''
            and end_date >= '{start_at}'
        '''.format(start_at=start_at)
    if end_at != '':
        wc += '''
            and end_date < '{end_at}'
        '''.format(end_at=end_at)
    
    # order by 리스트
    column_name = [
        'id'
    ]

    # 데이터테이블즈 - 카운팅 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select count(*)
            from tbl_notice
            {wc} and delete_yn = 'N'
        '''.format(wc=wc)
        # print(query)
        cur.execute(query)
        rows = cur.fetchall()
        total = rows[0][0]
        # print('DEBUG -> total : ', total)

    # 데이터테이블즈 - 메인 쿼리
    with connections['default'].cursor() as cur:
        query = '''
            select  id,
            		content_ko,
            		content_en,
            		content_zh,
            		platform,
            		concat(platform, '@', id) as user,
                    end_date,
            		regist_date
            from tbl_notice
            {wc} and delete_yn = 'N'
            order by {orderby_col} {orderby_opt}
            limit {start}, 10
        '''.format(
            wc=wc,
            orderby_col=column_name[orderby_col],
            orderby_opt=orderby_opt,
            start=start
        )
        cur.execute(query)
        rows = dictfetchall(cur)

    ret = {
        "recordsTotal": total,
        "recordsFiltered": total,
        "draw": draw,
        "data": rows
    }
    return JsonResponse(ret)


# (2023-05-25) Added By Zhao
@allow_admin
def api_create_notification(request):
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    platform = request.POST.get('platform')
    end_date = request.POST.get('end_date')
    user_emails = request.POST.get('user_emails', '')
    # 존재여부 체크
    sh = TblNotice(
        content_ko = content_ko,
        content_en = content_en,
        content_zh = content_zh,
        platform = platform,
        end_date = end_date,
        delete_yn = 'N',
        regist_date = datetime.datetime.now())
    sh.save()

    # User 플랫폼인 경우 이메일 목록으로 유저 자동 추가
    user_results = []
    if platform == 'User' and user_emails.strip():
        import re
        emails = [e.strip() for e in re.split(r'[,\n;\s]+', user_emails) if e.strip()]
        for email in emails:
            try:
                u1 = TblUser.objects.get(email=email)
                # 중복 체크
                existing = TblNoticeUser.objects.filter(notice_id=sh.id, user_id=u1.id).count()
                if existing > 0:
                    user_results.append({'email': email, 'status': 'duplicate', 'reason': '이미 추가됨'})
                else:
                    TblNoticeUser(
                        user_id=u1.id,
                        notice_id=sh.id,
                        regist_date=datetime.datetime.now()
                    ).save()
                    user_results.append({'email': email, 'status': 'ok'})
            except TblUser.DoesNotExist:
                user_results.append({'email': email, 'status': 'not_found', 'reason': '존재하지 않는 이메일'})
            except Exception as e:
                user_results.append({'email': email, 'status': 'error', 'reason': str(e)})

    return JsonResponse({'result': 200, 'user_results': user_results})

# (2023-05-25) Added By Zhao
@allow_admin
def api_read_notification_detail(request):
    notification_id = request.POST.get('notification_id')
    # 존재여부 체크
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT content_en, content_ko, content_zh, platform, end_date
                FROM tbl_notice WHERE id = {notification_id};
        '''.format(
            notification_id = notification_id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        return JsonResponse({'result' : 200 , 'data' : rows[0]})


# (2023-05-25) Added by Zhao
@allow_admin
def api_update_notification(request):
    id = request.POST.get('notification_id')
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    platform = request.POST.get('platform')
    end_date = request.POST.get('end_date')
    
    try:
        notification = TblNotice.objects.get(id=id)
        notification.content_ko = content_ko
        notification.content_en = content_en
        notification.content_zh = content_zh
        notification.platform = platform
        notification.end_date = end_date
        notification.save()
        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})
     
# (2023-05-26) Added by Zhao
@allow_admin
def api_add_user(request):
    email = request.POST.get('email')
    notice_id = request.POST.get('notification_id')
    
    try:
        u1 = TblUser.objects.get(email=email)
    except BaseException:
        return JsonResponse({'result': 600})
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT *
                FROM tbl_notice_user WHERE notice_id = {notice_id} and user_id = {user_id};
        '''.format(
            notice_id = notice_id,
            user_id = u1.id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        if len(rows) != 0:
            return JsonResponse({'result' : 400})
    try:
        sh = TblNoticeUser(
            user_id = u1.id,
            notice_id = notice_id,
            regist_date = datetime.datetime.now())
        sh.save()
        title, text = get_swal('SUCCESS_COMMON')
        return JsonResponse({'result': 200, 'title': title, 'text': text})
    except BaseException as err:
        title, text = get_swal('UNKNOWN_ERROR')
        return JsonResponse({'result': 500, 'title': title, 'text': text})

# (2023-05-26) Added by Zhao
@allow_admin
def api_get_user(request):
    notice_id = request.POST.get('notification_id')
    
    with connections['default'].cursor() as cur:
        sql = '''
            SELECT tu.email FROM tbl_notice_user tn
            JOIN tbl_user tu ON tn.user_id = tu.id
            WHERE tn.notice_id= {notice_id}
            ORDER BY tu.email;
        '''.format(
            notice_id = notice_id
        )
        cur.execute(sql)
        rows = dictfetchall(cur)
        return JsonResponse({'result' : 200, 'data': rows})


# ==============================================================================
# 유저 이슈 자동 통지 관리 (tbl_notification) — 2026-02-16 추가
# ==============================================================================

class UserIssueNotificationViews:
    """자동 분석 → 통지 생성 → 관리자 승인 → 앱 발송 관리"""

    @staticmethod
    @allow_admin
    def page_notification_manage(request):
        return render(request, 'admin/notification_manage.html', {})

    @staticmethod
    @allow_admin
    def api_read_notifications(request):
        """통지 목록 조회"""
        status = request.GET.get('status', 'pending')
        noti_type = request.GET.get('type', '')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        offset = (page - 1) * page_size

        cursor = connections['default'].cursor()
        where = []
        params = []
        if status != 'all':
            where.append("n.status = %s")
            params.append(status)
        if noti_type:
            where.append("n.noti_type = %s")
            params.append(noti_type)
        where_clause = "WHERE " + " AND ".join(where) if where else ""

        cursor.execute(f"SELECT COUNT(*) as cnt FROM tbl_notification n {where_clause}", params)
        total = dictfetchall(cursor)[0]['cnt']

        cursor.execute(f"""
            SELECT n.id, n.username, n.noti_type, n.severity, n.title, n.message,
                   n.recommendation, n.analysis_json, n.status, n.batch_id,
                   DATE_FORMAT(n.created_at, '%%Y-%%m-%%d %%H:%%i') as created_at,
                   DATE_FORMAT(n.approved_at, '%%Y-%%m-%%d %%H:%%i') as approved_at,
                   DATE_FORMAT(n.sent_at, '%%Y-%%m-%%d %%H:%%i') as sent_at,
                   n.approved_by
            FROM tbl_notification n
            {where_clause}
            ORDER BY FIELD(n.severity, 'critical', 'warning', 'info'), n.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        notifications = dictfetchall(cursor)

        for n in notifications:
            if n.get('analysis_json'):
                try:
                    n['analysis'] = json.loads(n['analysis_json'])
                except:
                    n['analysis'] = {}
            else:
                n['analysis'] = {}

        cursor.execute("""
            SELECT status, COUNT(*) as cnt FROM tbl_notification
            WHERE created_at >= NOW() - INTERVAL 7 DAY GROUP BY status
        """)
        status_counts = {r['status']: r['cnt'] for r in dictfetchall(cursor)}

        return JsonResponse({
            'result': 200, 'notifications': notifications, 'total': total,
            'page': page, 'page_size': page_size, 'status_counts': status_counts
        })

    @staticmethod
    @allow_admin
    def api_update_notification(request):
        """통지 상태 변경"""
        noti_id = request.POST.get('id')
        action = request.POST.get('action')
        if not noti_id or not action:
            return JsonResponse({'result': 400, 'msg': 'id, action 필수'})

        cursor = connections['default'].cursor()
        admin_id = request.session.get('admin_id', 'unknown')

        if action == 'approve':
            cursor.execute("UPDATE tbl_notification SET status='approved', approved_at=NOW(), approved_by=%s WHERE id=%s AND status='pending'", [admin_id, noti_id])
        elif action == 'approve_send':
            cursor.execute("UPDATE tbl_notification SET status='sent', approved_at=NOW(), sent_at=NOW(), approved_by=%s WHERE id=%s AND status IN ('pending','approved')", [admin_id, noti_id])
        elif action == 'dismiss':
            cursor.execute("UPDATE tbl_notification SET status='dismissed' WHERE id=%s AND status IN ('pending','approved')", [noti_id])
        elif action == 'edit':
            recommendation = request.POST.get('recommendation', '')
            cursor.execute("UPDATE tbl_notification SET recommendation=%s WHERE id=%s", [recommendation, noti_id])
        elif action == 'delete':
            cursor.execute("DELETE FROM tbl_notification WHERE id=%s", [noti_id])
        else:
            return JsonResponse({'result': 400, 'msg': '잘못된 action'})

        return JsonResponse({'result': 200})

    @staticmethod
    @allow_admin
    def api_batch_notification(request):
        """일괄 처리"""
        action = request.POST.get('action')
        if not action:
            return JsonResponse({'result': 400, 'msg': 'action 필수'})

        cursor = connections['default'].cursor()
        admin_id = request.session.get('admin_id', 'unknown')

        # delete_all은 ids 불필요
        if action == 'delete_all':
            status_filter = request.POST.get('status', '')
            if status_filter and status_filter != 'all':
                cursor.execute("DELETE FROM tbl_notification WHERE status=%s", [status_filter])
            else:
                cursor.execute("DELETE FROM tbl_notification")
            return JsonResponse({'result': 200, 'affected': cursor.rowcount})

        ids = request.POST.get('ids', '')
        if not ids:
            return JsonResponse({'result': 400, 'msg': 'ids 필수'})

        id_list = [int(x.strip()) for x in ids.split(',') if x.strip().isdigit()]
        if not id_list:
            return JsonResponse({'result': 400, 'msg': '유효한 id 없음'})

        ph = ','.join(['%s'] * len(id_list))

        if action == 'approve':
            cursor.execute(f"UPDATE tbl_notification SET status='approved', approved_at=NOW(), approved_by=%s WHERE id IN ({ph}) AND status='pending'", [admin_id] + id_list)
        elif action == 'approve_send':
            cursor.execute(f"UPDATE tbl_notification SET status='sent', approved_at=NOW(), sent_at=NOW(), approved_by=%s WHERE id IN ({ph}) AND status IN ('pending','approved')", [admin_id] + id_list)
        elif action == 'dismiss':
            cursor.execute(f"UPDATE tbl_notification SET status='dismissed' WHERE id IN ({ph}) AND status IN ('pending','approved')", id_list)
        elif action == 'delete':
            cursor.execute(f"DELETE FROM tbl_notification WHERE id IN ({ph})", id_list)
        else:
            return JsonResponse({'result': 400, 'msg': '잘못된 action'})

        return JsonResponse({'result': 200, 'affected': cursor.rowcount})

    @staticmethod
    @allow_admin
    def api_run_analysis(request):
        """수동 분석 실행"""
        hours = int(request.POST.get('hours', 2))
        import subprocess, os, re
        try:
            result = subprocess.run(
                ['python3', '/home/newkorea/project/scripts/analyze_user_issues.py', '--hours', str(hours)],
                capture_output=True, text=True, timeout=120,
                cwd='/home/newkorea/project/titan-admin',
                env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'main.settings'}
            )
            output = result.stdout + result.stderr
            m = re.search(r'총 통지 생성: (\d+)건', output)
            created = int(m.group(1)) if m else 0
            return JsonResponse({'result': 200, 'created': created, 'output': output[-3000:]})
        except subprocess.TimeoutExpired:
            return JsonResponse({'result': 500, 'msg': '분석 타임아웃 (120s)'})
        except Exception as e:
            return JsonResponse({'result': 500, 'msg': str(e)})

    @staticmethod
    @allow_admin
    def api_read_notification_stats(request):
        """통지 통계"""
        cursor = connections['default'].cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status='dismissed' THEN 1 ELSE 0 END) as dismissed,
                SUM(CASE WHEN status='read' THEN 1 ELSE 0 END) as user_read,
                SUM(CASE WHEN severity='critical' AND status='pending' THEN 1 ELSE 0 END) as critical_pending,
                COUNT(*) as total
            FROM tbl_notification WHERE created_at >= NOW() - INTERVAL 7 DAY
        """)
        stats = dictfetchall(cursor)[0]

        cursor.execute("""
            SELECT batch_id, COUNT(*) as cnt, DATE_FORMAT(MIN(created_at), '%%Y-%%m-%%d %%H:%%i') as created_at
            FROM tbl_notification WHERE batch_id IS NOT NULL
            GROUP BY batch_id ORDER BY batch_id DESC LIMIT 5
        """)
        batches = dictfetchall(cursor)

        return JsonResponse({'result': 200, 'stats': stats, 'recent_batches': batches})