from django.shortcuts import render
from django.db import connections


def _dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def faq(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE or 'ko'

    cursor = connections['default'].cursor()
    cursor.execute("SET NAMES utf8mb4")

    # 카테고리 로드
    cursor.execute("""
        SELECT id, category_key, icon, color_class, gradient, sort_order,
               title_ko, title_zh, title_en
        FROM tbl_faq_category
        WHERE is_active = 1
        ORDER BY sort_order
    """)
    categories = _dictfetchall(cursor)

    # 항목 로드
    cursor.execute("""
        SELECT i.id, i.category_id, i.sort_order,
               i.content_ko, i.content_zh, i.content_en
        FROM tbl_faq_item i
        JOIN tbl_faq_category c ON c.id = i.category_id
        WHERE i.is_active = 1 AND c.is_active = 1
        ORDER BY c.sort_order, i.sort_order
    """)
    items = _dictfetchall(cursor)

    # 카테고리별 항목 그룹핑
    items_by_cat = {}
    for item in items:
        cat_id = item['category_id']
        if cat_id not in items_by_cat:
            items_by_cat[cat_id] = []
        items_by_cat[cat_id].append(item)

    # 언어별 title/content 필드명
    lang_key = 'ko'
    if LANGUAGE_CODE.startswith('zh'):
        lang_key = 'zh'
    elif LANGUAGE_CODE.startswith('en'):
        lang_key = 'en'

    context = {
        'LANGUAGE_CODE': LANGUAGE_CODE,
        'categories': categories,
        'items_by_cat': items_by_cat,
        'lang_key': lang_key,
    }
    return render(request, 'new/faq.html', context)
