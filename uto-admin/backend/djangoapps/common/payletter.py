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


    # 환불 함수
    def payments_cancel(self, pgcode, user_id, tid, amount):

        full_url = self.endpoint + 'v1.0/payments/cancel'
        payload = {
            "pgcode" : "kakaopay",
            "client_id": self.shop_id,
            "user_id": user_id,
            "tid": tid,
            "amount" : amount,
            "ip_addr": "127.0.0.1"
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)

        status_code = r.status_code
        parsed = json.loads(r.text)
        print('INFO -> refund info : ', json.dumps(parsed, indent=4, sort_keys=True))
        return status_code
