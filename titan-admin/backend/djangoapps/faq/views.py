# FAQ 관리 — 자주 묻는 질문 CRUD
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from backend.djangoapps.common.views import allow_admin, dictfetchall
from backend.djangoapps.common.swal import get_swal


# ===== PAGE =====
@allow_admin
def faq_manage(request):
    cursor = connections['default'].cursor()
    cursor.execute("SELECT id, category_key, title_ko FROM tbl_faq_category WHERE is_active=1 ORDER BY sort_order")
    categories = dictfetchall(cursor)
    return render(request, 'admin/faq_manage.html', {'categories': categories})


# ===== API: 카테고리 목록 =====
@allow_admin
def api_read_faq_categories(request):
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT c.id, c.category_key, c.icon, c.color_class, c.gradient, c.sort_order, c.is_active,
               c.title_ko, c.title_zh, c.title_en, c.updated_at,
               COUNT(i.id) AS item_count
        FROM tbl_faq_category c
        LEFT JOIN tbl_faq_item i ON i.category_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order
    """)
    rows = dictfetchall(cursor)
    data = []
    for r in rows:
        data.append({
            'id': r['id'],
            'category_key': r['category_key'],
            'icon': r['icon'],
            'color_class': r['color_class'],
            'gradient': r['gradient'],
            'sort_order': r['sort_order'],
            'is_active': r['is_active'],
            'title_ko': r['title_ko'],
            'title_zh': r['title_zh'],
            'title_en': r['title_en'],
            'item_count': r['item_count'],
            'updated_at': r['updated_at'].strftime('%Y-%m-%d %H:%M') if r['updated_at'] else '',
        })
    return JsonResponse({'result': 200, 'data': data})


# ===== API: 카테고리 수정 =====
@allow_admin
def api_update_faq_category(request):
    cat_id = request.POST.get('id')
    if not cat_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    icon = request.POST.get('icon', '').strip()
    title_ko = request.POST.get('title_ko', '').strip()
    title_zh = request.POST.get('title_zh', '').strip()
    title_en = request.POST.get('title_en', '').strip()
    sort_order = int(request.POST.get('sort_order', 0))
    is_active = int(request.POST.get('is_active', 1))
    gradient = request.POST.get('gradient', '').strip()

    cursor = connections['default'].cursor()
    cursor.execute("""
        UPDATE tbl_faq_category
        SET icon=%s, title_ko=%s, title_zh=%s, title_en=%s, sort_order=%s, is_active=%s, gradient=%s
        WHERE id=%s
    """, [icon, title_ko, title_zh, title_en, sort_order, is_active, gradient, cat_id])

    return JsonResponse({'result': 200, 'title': '성공', 'text': '카테고리가 수정되었습니다.'})


# ===== API: 카테고리 추가 =====
@allow_admin
def api_create_faq_category(request):
    category_key = request.POST.get('category_key', '').strip().upper()
    icon = request.POST.get('icon', '').strip()
    title_ko = request.POST.get('title_ko', '').strip()
    title_zh = request.POST.get('title_zh', '').strip()
    title_en = request.POST.get('title_en', '').strip()
    sort_order = int(request.POST.get('sort_order', 99))
    gradient = request.POST.get('gradient', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)').strip()
    color_class = request.POST.get('color_class', '').strip() or ('cat-' + category_key.lower().replace('_', ''))

    if not category_key or not title_ko:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '카테고리 키와 한국어 제목을 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        INSERT INTO tbl_faq_category (category_key, icon, color_class, gradient, sort_order, title_ko, title_zh, title_en)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [category_key, icon, color_class, gradient, sort_order, title_ko, title_zh, title_en])

    return JsonResponse({'result': 200, 'title': '성공', 'text': '카테고리가 추가되었습니다.'})


# ===== API: FAQ 항목 목록 (카테고리별) =====
@allow_admin
def api_read_faq_items(request):
    category_id = request.POST.get('category_id', '')

    cursor = connections['default'].cursor()
    where = "1=1"
    params = []
    if category_id:
        where = "i.category_id = %s"
        params.append(int(category_id))

    cursor.execute(f"""
        SELECT i.id, i.category_id, c.category_key, c.title_ko AS cat_title,
               i.sort_order, i.is_active,
               i.content_ko, i.content_zh, i.content_en,
               i.created_at, i.updated_at
        FROM tbl_faq_item i
        JOIN tbl_faq_category c ON c.id = i.category_id
        WHERE {where}
        ORDER BY c.sort_order, i.sort_order
    """, params)
    rows = dictfetchall(cursor)
    data = []
    for r in rows:
        data.append({
            'id': r['id'],
            'category_id': r['category_id'],
            'category_key': r['category_key'],
            'cat_title': r['cat_title'],
            'sort_order': r['sort_order'],
            'is_active': r['is_active'],
            'content_ko': r['content_ko'] or '',
            'content_zh': r['content_zh'] or '',
            'content_en': r['content_en'] or '',
            'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else '',
            'updated_at': r['updated_at'].strftime('%Y-%m-%d %H:%M') if r['updated_at'] else '',
        })
    return JsonResponse({'result': 200, 'data': data})


# ===== API: FAQ 항목 상세 =====
@allow_admin
def api_read_faq_item_detail(request):
    item_id = request.POST.get('item_id')
    if not item_id:
        return JsonResponse({'result': 400, 'msg': 'missing item_id'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT i.*, c.category_key, c.title_ko AS cat_title
        FROM tbl_faq_item i
        JOIN tbl_faq_category c ON c.id = i.category_id
        WHERE i.id = %s
    """, [item_id])
    rows = dictfetchall(cursor)
    if not rows:
        return JsonResponse({'result': 404, 'msg': 'not found'})

    r = rows[0]
    return JsonResponse({
        'result': 200,
        'data': {
            'id': r['id'],
            'category_id': r['category_id'],
            'category_key': r['category_key'],
            'sort_order': r['sort_order'],
            'is_active': r['is_active'],
            'content_ko': r['content_ko'] or '',
            'content_zh': r['content_zh'] or '',
            'content_en': r['content_en'] or '',
        }
    })


# ===== API: FAQ 항목 생성 =====
@allow_admin
def api_create_faq_item(request):
    category_id = request.POST.get('category_id')
    content_ko = request.POST.get('content_ko', '').strip()
    content_zh = request.POST.get('content_zh', '').strip()
    content_en = request.POST.get('content_en', '').strip()
    sort_order = int(request.POST.get('sort_order', 0))
    is_active = int(request.POST.get('is_active', 1))

    if not category_id or not content_ko:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '카테고리와 한국어 내용을 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        INSERT INTO tbl_faq_item (category_id, sort_order, is_active, content_ko, content_zh, content_en)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [category_id, sort_order, is_active, content_ko, content_zh, content_en])

    return JsonResponse({'result': 200, 'title': '성공', 'text': 'FAQ 항목이 등록되었습니다.'})


# ===== API: FAQ 항목 수정 =====
@allow_admin
def api_update_faq_item(request):
    item_id = request.POST.get('item_id')
    if not item_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    category_id = request.POST.get('category_id')
    content_ko = request.POST.get('content_ko', '').strip()
    content_zh = request.POST.get('content_zh', '').strip()
    content_en = request.POST.get('content_en', '').strip()
    sort_order = int(request.POST.get('sort_order', 0))
    is_active = int(request.POST.get('is_active', 1))

    if not content_ko:
        return JsonResponse({'result': 400, 'title': '오류', 'text': '한국어 내용을 입력하세요.'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        UPDATE tbl_faq_item
        SET category_id=%s, sort_order=%s, is_active=%s, content_ko=%s, content_zh=%s, content_en=%s
        WHERE id=%s
    """, [category_id, sort_order, is_active, content_ko, content_zh, content_en, item_id])

    return JsonResponse({'result': 200, 'title': '성공', 'text': 'FAQ 항목이 수정되었습니다.'})


# ===== API: FAQ 항목 삭제 =====
@allow_admin
def api_delete_faq_item(request):
    item_id = request.POST.get('item_id')
    if not item_id:
        return JsonResponse({'result': 400, 'title': '오류', 'text': 'ID가 없습니다.'})

    cursor = connections['default'].cursor()
    cursor.execute("DELETE FROM tbl_faq_item WHERE id=%s", [item_id])

    return JsonResponse({'result': 200, 'title': '성공', 'text': 'FAQ 항목이 삭제되었습니다.'})


# ===== API: FAQ 항목 활성/비활성 토글 =====
@allow_admin
def api_toggle_faq_item(request):
    item_id = request.POST.get('item_id')
    if not item_id:
        return JsonResponse({'result': 400})

    cursor = connections['default'].cursor()
    cursor.execute("UPDATE tbl_faq_item SET is_active = IF(is_active=1, 0, 1) WHERE id=%s", [item_id])

    return JsonResponse({'result': 200, 'title': '성공', 'text': '상태가 변경되었습니다.'})
