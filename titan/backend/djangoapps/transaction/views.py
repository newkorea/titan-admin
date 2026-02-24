import os
import json
import datetime
import hashlib
import uuid
import requests
from pytz import timezone
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
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


def _fix_encoding(val):
    """이중 인코딩된 UTF-8 바이트를 복원 (latin1 / cp1252)"""
    if val is None:
        return ''
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except Exception:
            return val.decode('latin1', errors='replace')
    s = str(val)
    # latin1 경유 이중 인코딩
    try:
        return s.encode('latin1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    # cp1252 경유 이중 인코딩 (0x80-0x9F 범위 문자 포함)
    try:
        return s.encode('cp1252').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


# 거래 내역 페이지
def transaction(request):
    LANGUAGE_CODE = getattr(request, 'LANGUAGE_CODE', 'ko') or 'ko'
    return render(request, 'new/transaction.html', {"data": "", "LANGUAGE_CODE": LANGUAGE_CODE})


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
                    id, '' as tid, product_name, session, month_type, krw, usd, cny, jpy,
                    status, type, regist_date, refund_date, null as email, 'send_history' as src
                FROM tbl_send_history
                WHERE user_id = {user_id}
                UNION ALL
                SELECT
                    id, COALESCE(tid, '') as tid, product_name, session, month_type, krw, usd, cny, jpy,
                    refund_yn as status, pgcode as type, regist_date, refund_date, null, 'price_history' as src
                FROM tbl_price_history
                WHERE user_id = {user_id}
                UNION ALL
                SELECT
                    tr.id, '' as tid, '추천보상' as product_name, NULL as session, tr.reward_days as month_type,
                    NULL as krw, NULL as usd, NULL as cny, NULL as jpy,
                    NULL as status, NULL as type, tr.register_date as regist_date, NULL as refund_date, tu.email, 'reward' as src
                FROM tbl_reward_log tr
                JOIN tbl_user tu ON tr.registrant_id = tu.id
                WHERE tr.rewarder_id = {user_id}
                ORDER BY regist_date DESC
            '''
            cur.execute(query)
            rows = dictfetchall(cur)

            # 발급된 invoice 조회
            cur.execute("SELECT source_table, source_id, id FROM tbl_invoice WHERE user_id = %s", [user_id])
            invoice_map = {}
            for inv_row in cur.fetchall():
                invoice_map[(inv_row[0], inv_row[1])] = inv_row[2]

        new_array = []
        for i, row in enumerate(rows, start=1):
            amount_display = ''
            if row.get('krw'):
                amount_display = f"\uffe6{row['krw']}"
            elif row.get('usd'):
                amount_display = f"${row['usd']}"
            elif row.get('cny'):
                amount_display = f"\u00a5{row['cny']}"
            elif row.get('jpy'):
                amount_display = f"\u00a5{row['jpy']}"

            src = row.get('src', '')
            src_id = row.get('id', 0)
            invoice_id = invoice_map.get((src, src_id), None)

            tmp = {
                "id": i,
                "tid": str(row.get('tid', '')).strip(),
                "product_name": _fix_encoding(row.get('product_name', '')),
                "session": str(row.get('session', '')) if row.get('session') is not None else "",
                "month_type": str(row.get('month_type', '')) if row.get('month_type') is not None else "",
                "krw": amount_display,
                "krw_raw": str(row.get('krw', '')) if row.get('krw') else '',
                "usd_raw": str(row.get('usd', '')) if row.get('usd') else '',
                "cny_raw": str(row.get('cny', '')) if row.get('cny') else '',
                "jpy_raw": str(row.get('jpy', '')) if row.get('jpy') else '',
                "status": str(row.get('status', '')) if row.get('status') is not None else "",
                "type": str(row.get('type', '')) if row.get('type') is not None else "",
                "regist_date": row['regist_date'].isoformat() if isinstance(row.get('regist_date'), datetime.datetime) else str(row.get('regist_date', '')),
                "refund_date": row['refund_date'].isoformat() if isinstance(row.get('refund_date'), datetime.datetime) else "",
                "email": row.get('email', '') if row.get('email') is not None else "",
                "src": src,
                "src_id": src_id,
                "invoice_id": invoice_id,
            }
            new_array.append(tmp)

        response_data = {
            "recordsTotal": len(new_array),
            "recordsFiltered": len(new_array),
            "data": new_array
        }

        json_str = json.dumps(response_data, ensure_ascii=False, indent=None)
        response = HttpResponse(json_str, content_type="application/json; charset=utf-8")
        response["Content-Length"] = str(len(json_str.encode("utf-8")))
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


# Invoice 생성 API
@csrf_exempt
def generate_invoice(request):
    """거래 데이터 + 영문회사명으로 Invoice 생성, DB 저장 후 HTML 반환"""
    if request.method != "POST":
        return JsonResponse({"status": "fail"}, status=400)
    if 'id' not in request.session:
        return JsonResponse({"status": "fail", "message": "로그인이 필요합니다."}, status=403)

    user_id = request.session['id']
    source_table = request.POST.get('src', '').strip()
    source_id = request.POST.get('src_id', '').strip()

    # 이미 발급된 invoice가 있으면 거부
    if source_table and source_id:
        try:
            with connections['default'].cursor() as cur:
                cur.execute(
                    "SELECT id FROM tbl_invoice WHERE source_table=%s AND source_id=%s",
                    [source_table, source_id]
                )
                if cur.fetchone():
                    return HttpResponse('<h2>Invoice already issued. Please use the download button.</h2>', status=400)
        except Exception:
            pass

    company_name = request.POST.get('company_name', '').strip() or 'N/A'
    product_name = request.POST.get('product_name', '').strip()
    payment_type = request.POST.get('payment_type', '').strip()
    amount = request.POST.get('amount', '').strip()
    regist_date = request.POST.get('regist_date', '').strip()
    session_cnt = request.POST.get('session', '').strip()
    month_type = request.POST.get('month_type', '').strip()
    krw_raw = request.POST.get('krw_raw', '').strip()
    usd_raw = request.POST.get('usd_raw', '').strip()
    cny_raw = request.POST.get('cny_raw', '').strip()
    jpy_raw = request.POST.get('jpy_raw', '').strip()

    inv_data = _calc_invoice_amount(payment_type, session_cnt, month_type,
                                     krw_raw, usd_raw, cny_raw, jpy_raw, amount)

    # 날짜 파싱
    try:
        dt = datetime.datetime.fromisoformat(regist_date)
        date_display = dt.strftime('%B %d, %Y')
        inv_no = dt.strftime('%Y%m%d') + '001'
    except Exception:
        date_display = regist_date
        inv_no = datetime.datetime.now().strftime('%Y%m%d') + '001'

    payment_label = _get_payment_label(payment_type)

    # DB 저장
    if source_table and source_id:
        try:
            with connections['default'].cursor() as cur:
                cur.execute("""
                    INSERT INTO tbl_invoice
                        (user_id, source_table, source_id, company_name, product_name,
                         payment_type, inv_amount, inv_currency, inv_currency_code,
                         inv_no, date_display, payment_label, session_cnt, month_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [user_id, source_table, source_id, company_name, product_name,
                      payment_type, inv_data['amount'], inv_data['currency'],
                      inv_data['currency_code'], inv_no, date_display, payment_label,
                      session_cnt, month_type])
        except Exception as e:
            print(f"Invoice DB 저장 오류: {e}")

    LANGUAGE_CODE = getattr(request, 'LANGUAGE_CODE', 'ko') or 'ko'
    return render(request, 'new/invoice.html', {
        'company_name': company_name,
        'product_name': product_name,
        'payment_label': payment_label,
        'inv_amount': inv_data['amount'],
        'inv_currency': inv_data['currency'],
        'inv_currency_code': inv_data['currency_code'],
        'date_display': date_display,
        'inv_no': inv_no,
        'session_cnt': session_cnt,
        'month_type': month_type,
        'LANGUAGE_CODE': LANGUAGE_CODE,
    })


# 발급된 Invoice 다운로드
@csrf_exempt
def download_invoice(request):
    """DB에 저장된 기발급 Invoice를 다시 렌더링"""
    if request.method != "POST":
        return JsonResponse({"status": "fail"}, status=400)
    if 'id' not in request.session:
        return JsonResponse({"status": "fail", "message": "로그인이 필요합니다."}, status=403)

    user_id = request.session['id']
    invoice_id = request.POST.get('invoice_id', '').strip()

    if not invoice_id:
        return HttpResponse('Invoice not found', status=404)

    try:
        with connections['default'].cursor() as cur:
            cur.execute("""
                SELECT company_name, product_name, payment_label, inv_amount, inv_currency,
                       inv_currency_code, inv_no, date_display, session_cnt, month_type
                FROM tbl_invoice WHERE id=%s AND user_id=%s
            """, [invoice_id, user_id])
            row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        return HttpResponse('Invoice not found', status=404)

    LANGUAGE_CODE = getattr(request, 'LANGUAGE_CODE', 'ko') or 'ko'
    return render(request, 'new/invoice.html', {
        'company_name': row[0],
        'product_name': row[1],
        'payment_label': row[2],
        'inv_amount': row[3],
        'inv_currency': row[4],
        'inv_currency_code': row[5],
        'date_display': row[7],
        'inv_no': row[6],
        'session_cnt': row[8],
        'month_type': row[9],
        'LANGUAGE_CODE': LANGUAGE_CODE,
    })


def _calc_invoice_amount(payment_type, session_cnt, month_type,
                          krw_raw, usd_raw, cny_raw, jpy_raw, amount_fallback):
    """결제종류에 따라 Invoice 금액/통화 결정"""
    wechat_alipay_types = ('W', 'A', 'WECHAT', 'ALIPAY', 'PLUnionPay')
    is_chinese_pay = payment_type.upper() in [t.upper() for t in wechat_alipay_types]

    if is_chinese_pay and not cny_raw and session_cnt and month_type:
        try:
            with connections['default'].cursor() as cur:
                cur.execute(
                    "SELECT item_price_cny FROM tbl_price WHERE type_session=%s AND type_month=%s LIMIT 1",
                    [session_cnt, month_type]
                )
                row = cur.fetchone()
                if row and row[0]:
                    cny_raw = str(row[0])
        except Exception:
            pass

    if is_chinese_pay and cny_raw:
        raw = cny_raw; sym = '¥'; code = 'CNY'
    elif usd_raw:
        raw = usd_raw; sym = '$'; code = 'USD'
    elif jpy_raw:
        raw = jpy_raw; sym = '¥'; code = 'JPY'
    elif krw_raw:
        raw = krw_raw; sym = '₩'; code = 'KRW'
    else:
        raw = (amount_fallback or '0').replace('￦','').replace('$','').replace('¥','').replace(',','')
        sym = ''; code = ''

    try:
        formatted = f"{float(raw):,.2f}"
    except (ValueError, TypeError):
        formatted = raw or '0.00'

    return {'amount': formatted, 'currency': sym, 'currency_code': code}


def _get_payment_label(payment_type):
    """결제수단 영문 라벨"""
    labels = {
        'W': 'WeChat Pay', 'A': 'AliPay', 'WECHAT': 'WeChat Pay', 'ALIPAY': 'AliPay',
        'PLUnionPay': 'UnionPay', 'creditcard': 'Credit Card', 'PLCreditCard': 'Intl Credit Card',
        'toss': 'Toss Pay', 'kakaopay': 'Kakao Pay', 'payco': 'PAYCO',
        'kftc': 'Bank Transfer', 'virtualaccount': 'Virtual Account',
        'apple': 'Apple Pay', 'ssgpay': 'SSG Pay', 'PLCreditCartMpi': 'Intl Credit Card'
    }
    return labels.get(payment_type, payment_type or 'N/A')
