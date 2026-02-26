import os
import json
import requests
import sys
from django.conf import settings


# 페이레터 국내 공통 클래스
class Payletter:


    def __init__(self, type):
        if type == 'LIVE':
            self.endpoint        = settings.PAYLETTER_KOR_LIVE_ENDPOINT
            self.shop_id         = settings.PAYLETTER_KOR_LIVE_SHOPID
            self.api_key_payment = settings.PAYLETTER_KOR_LIVE_APIKEY_PAYMENT
            self.api_key_search  = settings.PAYLETTER_KOR_LIVE_APIKEY_SEARCH
        elif type == 'TEST':
            self.endpoint        = settings.PAYLETTER_KOR_TEST_ENDPOINT
            self.shop_id         = settings.PAYLETTER_KOR_TEST_SHOPID
            self.api_key_payment = settings.PAYLETTER_KOR_TEST_APIKEY_PAYMENT
            self.api_key_search  = settings.PAYLETTER_KOR_TEST_APIKEY_SEARCH


    # 결제요청 함수
    def payments_request(self,
                        pgcode,
                        user_id,
                        user_name,
                        price,
                        product_name,
                        order_no,
                        custom_parameter,
                        email):

        # 입력 파라미터 로깅
        print('API DEBUG -> pgcode : ', pgcode)
        print('API DEBUG -> user_id : ', user_id)
        print('API DEBUG -> user_name : ', user_name)
        print('API DEBUG -> price : ', price)
        print('API DEBUG -> product_name : ', product_name)
        print('API DEBUG -> order_no : ', order_no)
        print('API DEBUG -> custom_parameter : ', custom_parameter)
        print('API DEBUG -> email : ', email)

        # set url
        if settings.HTTPS == True:
            callback_url = "https://"+settings.FULL_URL+"/payletter_callback"
        else:
            callback_url = "http://"+settings.FULL_URL+"/payletter_callback"

        if settings.HTTPS == True:
            return_url = "https://"+settings.FULL_URL+"/payletter_return"
        else:
            return_url = "http://"+settings.FULL_URL+"/payletter_return"

        if settings.HTTPS == True:
            cancel_url = "https://"+settings.FULL_URL+"/payletter_cancel"
        else:
            cancel_url = "http://"+settings.FULL_URL+"/payletter_cancel"

        # 페이레터 API 호출
        full_url = self.endpoint + 'v1.0/payments/request'
        payload = {
            "pgcode"            : pgcode,
            "user_id"           : user_id,
            "user_name"         : user_name,
            "service_name"      : "TITAN NETWORKS",
            "client_id"         : self.shop_id,
            "order_no"          : order_no,
            "amount"            : price,
            "taxfree_amount"    : 0,
            "tax_amount"        : 0,
            "product_name"      : product_name,
            "email_flag"        : "Y",
            "email_addr"        : email,
            "autopay_flag"      : "N",
            "receipt_flag"      : "Y",
            "custom_parameter"  : custom_parameter,
            "return_url"        : return_url,
            "callback_url"      : callback_url,
            "cancel_url"        : cancel_url
        }
        headers = {
            'content-type'      : 'application/json',
            'Authorization'     : 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)
        parsed = json.loads(r.text)
        parsed_txt = json.dumps(parsed, indent=4, sort_keys=True)

        print('API DEBUG -> status_code : ', r.status_code)
        print('API DEBUG -> parsed_txt : ', parsed_txt)

        return r.text


    # 자동결제 등록 결제요청 (autopay_flag=Y → 빌키 발급)
    def payments_request_autopay(self,
                        pgcode,
                        user_id,
                        user_name,
                        price,
                        product_name,
                        order_no,
                        custom_parameter,
                        email):

        print('API DEBUG [AUTOPAY] -> pgcode : ', pgcode)
        print('API DEBUG [AUTOPAY] -> user_id : ', user_id)

        scheme = "https" if settings.HTTPS else "http"
        base = scheme + "://" + settings.FULL_URL
        callback_url = base + "/payletter_callback"
        return_url = base + "/payletter_return"
        cancel_url = base + "/payletter_cancel"

        full_url = self.endpoint + 'v1.0/payments/request'
        payload = {
            "pgcode"            : pgcode,
            "user_id"           : user_id,
            "user_name"         : user_name,
            "service_name"      : "TITAN NETWORKS",
            "client_id"         : self.shop_id,
            "order_no"          : order_no,
            "amount"            : price,
            "taxfree_amount"    : 0,
            "tax_amount"        : 0,
            "product_name"      : product_name,
            "email_flag"        : "Y",
            "email_addr"        : email,
            "autopay_flag"      : "Y",
            "receipt_flag"      : "Y",
            "custom_parameter"  : custom_parameter,
            "return_url"        : return_url,
            "callback_url"      : callback_url,
            "cancel_url"        : cancel_url
        }
        headers = {
            'content-type'      : 'application/json',
            'Authorization'     : 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)
        print('API DEBUG [AUTOPAY] -> status_code : ', r.status_code)
        print('API DEBUG [AUTOPAY] -> response : ', r.text[:500])
        return r.text


    # 빌키로 자동결제 실행 (서버 to 서버, 사용자 인증 없이 결제)
    def autopay_payment(self,
                        billkey,
                        user_id,
                        user_name,
                        price,
                        product_name,
                        order_no,
                        custom_parameter,
                        email):

        print('API DEBUG [AUTOPAY EXEC] -> billkey : ', billkey[:10] + '...')
        print('API DEBUG [AUTOPAY EXEC] -> user_id : ', user_id)
        print('API DEBUG [AUTOPAY EXEC] -> amount : ', price)

        scheme = "https" if settings.HTTPS else "http"
        callback_url = scheme + "://" + settings.FULL_URL + "/payletter_callback"

        full_url = self.endpoint + 'v1.0/payments/autopay'
        payload = {
            "pgcode"            : "creditcard",
            "user_id"           : str(user_id),
            "user_name"         : user_name,
            "service_name"      : "TITAN NETWORKS",
            "client_id"         : self.shop_id,
            "order_no"          : order_no,
            "amount"            : price,
            "taxfree_amount"    : 0,
            "tax_amount"        : 0,
            "product_name"      : product_name,
            "email_flag"        : "Y",
            "email_addr"        : email,
            "billkey"           : billkey,
            "custom_parameter"  : custom_parameter,
            "callback_url"      : callback_url
        }
        headers = {
            'content-type'      : 'application/json',
            'Authorization'     : 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)
        print('API DEBUG [AUTOPAY EXEC] -> status_code : ', r.status_code)
        print('API DEBUG [AUTOPAY EXEC] -> response : ', r.text[:500])
        return r.status_code, r.text
