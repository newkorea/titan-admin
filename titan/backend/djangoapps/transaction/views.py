import os
import json
import datetime
import hashlib
import uuid
import requests
from pytz import timezone
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.payletter import Payletter
from backend.djangoapps.common.payletter_global import PayletterGlobal
from backend.models import *
from backend.models_radius import Radcheck

def dictfetchall(cursor):
    """쿼리 결과를 dict 형태로 변환"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# 거래 내역 페이지
def transaction(request):
    LANGUAGE_CODE = getattr(request, 'LANGUAGE_CODE', 'ko') or 'ko'
    return render(request, 'new/transaction.html', {"data": "", "LANGUAGE_CODE": LANGUAGE_CODE})

# 거래 내역 조회
from django.http import JsonResponse, HttpResponse

@csrf_exempt
def get_transaction(request):
    """사용자의 거래 내역을 조회하여 JSON으로 반환"""
    if 'id' not in request.session:
        return JsonResponse({"status": "fail", "message": "로그인이 필요합니다."}, status=403)

    user_id = request.session['id']

    try:
        with connections['default'].cursor() as cur:
            query = f'''
                SELECT 
                    id, '' as tid, product_name, session, month_type, krw, usd, status, type, regist_date, refund_date, null as email
                FROM tbl_send_history
                WHERE user_id = {user_id}
                UNION ALL
                SELECT 
                    id, COALESCE(tid, '') as tid, product_name, session, month_type, krw, usd, refund_yn as status, pgcode as type, regist_date, refund_date, null
                FROM tbl_price_history
                WHERE user_id = {user_id}
                UNION ALL
                SELECT
                    tr.id, '' as tid, '추천보상' as product_name, NULL as session, tr.reward_days as month_type, NULL as krw, NULL as usd, NULL as status, NULL as type, tr.register_date as regist_date, NULL as refund_date, tu.email
                FROM tbl_reward_log tr 
                JOIN tbl_user tu ON tr.registrant_id = tu.id
                WHERE tr.rewarder_id = {user_id}
                ORDER BY regist_date DESC
            '''
            cur.execute(query)
            rows = dictfetchall(cur)

        new_array = []
        for i, row in enumerate(rows, start=1):
            tmp = {
                "id": i,
                "tid": str(row.get('tid', '')).strip(),
                "product_name": row.get('product_name', ''),
                "session": str(row.get('session', '')) if row.get('session') is not None else "",
                "month_type": str(row.get('month_type', '')) if row.get('month_type') is not None else "",
                "krw": f"￦{row['krw']}" if row.get('krw') else (f"${row['usd']}" if row.get('usd') else ""),
                "status": str(row.get('status', '')) if row.get('status') is not None else "",
                "type": str(row.get('type', '')) if row.get('type') is not None else "",
                "regist_date": row['regist_date'].isoformat() if isinstance(row.get('regist_date'), datetime.datetime) else str(row.get('regist_date', '')),
                "refund_date": row['refund_date'].isoformat() if isinstance(row.get('refund_date'), datetime.datetime) else "",  
                "email": row.get('email', '') if row.get('email') is not None else ""
            }
            new_array.append(tmp)

        response_data = {
            "recordsTotal": len(new_array),
            "recordsFiltered": len(new_array),
            "data": new_array
        }

        json_str = json.dumps(response_data, ensure_ascii=False, indent=None)
        response = HttpResponse(json_str, content_type="application/json; charset=utf-8")
        response["Content-Length"] = str(len(json_str.encode("utf-8")))  # ✅ Content-Length 강제 설정
        return response

    except Exception as e:
        print(f"🚨 거래 내역 조회 오류: {e}")
        return JsonResponse({"status": "error", "message": "서버 오류 발생"}, status=500)


# 거래명세서 조회 API
@csrf_exempt
def get_receipt(request):
    """페이레터 API를 통해 거래명세서 URL 조회"""
    if request.method != "POST":
        return JsonResponse({"status": "fail", "message": "잘못된 요청입니다."}, status=400)

    transaction_id = request.POST.get("transaction_id", "").strip()

    if not transaction_id:
        print("🚨 [get_receipt] 요청된 transaction_id가 없음")
        return JsonResponse({"status": "fail", "message": "유효한 거래 ID가 없습니다."}, status=400)

    print(f"✅ [get_receipt] 요청된 transaction_id: {transaction_id}")

    PAYLETTER_API_URL = f"{settings.PAYLETTER_KOR_LIVE_ENDPOINT}/v1.0/receipt/info/{transaction_id}/?client_id={settings.PAYLETTER_KOR_LIVE_SHOPID}"
    API_KEY = settings.PAYLETTER_KOR_LIVE_APIKEY_SEARCH

    headers = {
        "Authorization": f"PLKEY {API_KEY}"
    }

    try:
        response = requests.get(PAYLETTER_API_URL, headers=headers)
        print(f"✅ [get_receipt] Payletter 응답 코드: {response.status_code}")
        print(f"✅ [get_receipt] Payletter 응답 본문: {response.text}")

        if response.status_code == 200:
            data = response.json()
            receipt_url = data.get("receipt_url")

            if receipt_url:
                print(f"✅ [get_receipt] 거래명세서 URL: {receipt_url}")
                return JsonResponse({"status": "success", "receipt_url": receipt_url})

        print(f"🚨 [get_receipt] 거래명세서 없음 또는 오류: {response.text}")
        return JsonResponse({"status": "fail", "message": "거래명세서 URL을 가져올 수 없습니다."}, status=500)

    except requests.RequestException as e:
        print(f"🚨 [get_receipt] API 요청 실패: {e}")
        return JsonResponse({"status": "error", "message": "서버 오류 발생"}, status=500)
