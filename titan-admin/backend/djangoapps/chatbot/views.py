import json
import datetime
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import connections
from backend.djangoapps.common.views import allow_admin, dictfetchall
from backend.djangoapps.common.swal import get_swal


CATEGORY_CHOICES = [
    ('GENERIC', '일반'),
    ('DOWNLOAD', '다운로드/설치'),
    ('PAYMENT', '결제/연장'),
    ('SPEED', '속도'),
    ('WINDOWS_FAIL', '윈도우오류'),
    ('LOGIN', '로그인'),
    ('CONCURRENT', '동시접속'),
]


# ===== PAGE =====
@allow_admin
def chatbot_qa(request):
    context = {
        'categories': CATEGORY_CHOICES,
    }
    return render(request, 'admin/chatbot_qa.html', context)


# ===== API: LIST (DataTables) =====
@allow_admin
def api_read_chatbot_qa(request):
    draw = int(request.POST.get('draw', 1))
    start = int(request.POST.get('start', 0))
    length = int(request.POST.get('length', 20))
    search_value = request.POST.get('search[value]', '').strip()
    category_filter = request.POST.get('category', '').strip()
    active_filter = request.POST.get('is_active', '').strip()

    order_col_idx = request.POST.get('order[0][column]', '0')
    order_dir = request.POST.get('order[0][dir]', 'desc')

    col_map = {
        '0': 'id', '1': 'category', '2': 'question', '3': 'answer',
        '4': 'is_active', '5': 'hit_count', '6': 'priority', '7': 'updated_at'
    }
    order_col = col_map.get(order_col_idx, 'id')
    if order_dir not in ('asc', 'desc'):
        order_dir = 'desc'

    cursor = connections['default'].cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM tbl_chatbot_qa WHERE delete_yn='N'")
    total = cursor.fetchone()[0]

    # Filtered count + data
    where_parts = ["delete_yn='N'"]
    params = []

    if search_value:
        where_parts.append("(question LIKE %s OR answer LIKE %s)")
        params.extend([f'%{search_value}%', f'%{search_value}%'])

    if category_filter:
        where_parts.append("category = %s")
        params.append(category_filter)

    if active_filter != '':
        where_parts.append("is_active = %s")
        params.append(int(active_filter))

    where_sql = " AND ".join(where_parts)

    cursor.execute(f"SELECT COUNT(*) FROM tbl_chatbot_qa WHERE {where_sql}", params)
    filtered = cursor.fetchone()[0]

    sql = f"""
        SELECT id, chat_id, category, question, answer, is_active, priority,
               hit_count, created_at, updated_at
        FROM tbl_chatbot_qa
        WHERE {where_sql}
        ORDER BY {order_col} {order_dir}
        LIMIT %s OFFSET %s
    """
    cursor.execute(sql, params + [length, start])
    rows = dictfetchall(cursor)

    data = []
    for r in rows:
        data.append({
            'id': r['id'],
            'chat_id': r.get('chat_id', ''),
            'category': r['category'],
            'question': r['question'][:200] if r['question'] else '',
            'question_full': r['question'] or '',
            'answer': r['answer'][:200] if r['answer'] else '',
            'answer_full': r['answer'] or '',
            'is_active': r['is_active'],
            'priority': r['priority'],
            'hit_count': r['hit_count'],
            'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else '',
            'updated_at': r['updated_at'].strftime('%Y-%m-%d %H:%M') if r['updated_at'] else '',
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total,
        'recordsFiltered': filtered,
        'data': data,
    })


# ===== API: DETAIL =====
@allow_admin
def api_read_chatbot_qa_detail(request):
    qa_id = request.POST.get('qa_id')
    if not qa_id:
        return JsonResponse({'result': 400, 'msg': 'missing qa_id'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT id, chat_id, category, question, answer, is_active, priority,
               hit_count, created_at, updated_at
        FROM tbl_chatbot_qa WHERE id=%s AND delete_yn='N'
    """, [qa_id])
    rows = dictfetchall(cursor)
    if not rows:
        return JsonResponse({'result': 404, 'msg': 'not found'})

    r = rows[0]
    return JsonResponse({
        'result': 200,
        'data': {
            'id': r['id'],
            'chat_id': r.get('chat_id', ''),
            'category': r['category'],
            'question': r['question'],
            'answer': r['answer'],
            'is_active': r['is_active'],
            'priority': r['priority'],
            'hit_count': r['hit_count'],
            'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else '',
            'updated_at': r['updated_at'].strftime('%Y-%m-%d %H:%M') if r['updated_at'] else '',
        }
    })


# ===== API: CREATE =====
@allow_admin
def api_create_chatbot_qa(request):
    category = request.POST.get('category', 'GENERIC')
    question = request.POST.get('question', '').strip()
    answer = request.POST.get('answer', '').strip()
    is_active = int(request.POST.get('is_active', 1))
    priority = int(request.POST.get('priority', 0))

    if not question or not answer:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '질문과 답변을 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        INSERT INTO tbl_chatbot_qa (category, question, answer, is_active, priority)
        VALUES (%s, %s, %s, %s, %s)
    """, [category, question, answer, is_active, priority])

    title, text = get_swal('SUCCESS_COMMON')
    return JsonResponse({'result': 200, 'title': title, 'text': 'Q&A가 등록되었습니다.'})


# ===== API: UPDATE =====
@allow_admin
def api_update_chatbot_qa(request):
    qa_id = request.POST.get('qa_id')
    if not qa_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    category = request.POST.get('category', 'GENERIC')
    question = request.POST.get('question', '').strip()
    answer = request.POST.get('answer', '').strip()
    is_active = int(request.POST.get('is_active', 1))
    priority = int(request.POST.get('priority', 0))

    if not question or not answer:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '질문과 답변을 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        UPDATE tbl_chatbot_qa
        SET category=%s, question=%s, answer=%s, is_active=%s, priority=%s
        WHERE id=%s AND delete_yn='N'
    """, [category, question, answer, is_active, priority, qa_id])

    title, text = get_swal('SUCCESS_COMMON')
    return JsonResponse({'result': 200, 'title': title, 'text': 'Q&A가 수정되었습니다.'})


# ===== API: DELETE =====
@allow_admin
def api_delete_chatbot_qa(request):
    qa_id = request.POST.get('qa_id')
    if not qa_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    cursor = connections['default'].cursor()
    cursor.execute("UPDATE tbl_chatbot_qa SET delete_yn='Y' WHERE id=%s", [qa_id])

    title, text = get_swal('SUCCESS_REGIST_BAN_DEL')
    return JsonResponse({'result': 200, 'title': title, 'text': 'Q&A가 삭제되었습니다.'})


# ===== API: TOGGLE ACTIVE =====
@allow_admin
def api_toggle_chatbot_qa(request):
    qa_id = request.POST.get('qa_id')
    if not qa_id:
        return JsonResponse({'result': 400})

    cursor = connections['default'].cursor()
    cursor.execute("""
        UPDATE tbl_chatbot_qa SET is_active = IF(is_active=1, 0, 1) WHERE id=%s AND delete_yn='N'
    """, [qa_id])

    return JsonResponse({'result': 200, 'title': '성공', 'text': '상태가 변경되었습니다.'})


# ===== API: STATS =====
@allow_admin
def api_read_chatbot_qa_stats(request):
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT category, COUNT(*) as cnt,
               SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active_cnt,
               SUM(hit_count) as total_hits
        FROM tbl_chatbot_qa WHERE delete_yn='N'
        GROUP BY category ORDER BY cnt DESC
    """)
    rows = dictfetchall(cursor)

    cursor.execute("SELECT COUNT(*) as total FROM tbl_chatbot_qa WHERE delete_yn='N'")
    total = cursor.fetchone()[0]

    return JsonResponse({'result': 200, 'data': rows, 'total': total})
