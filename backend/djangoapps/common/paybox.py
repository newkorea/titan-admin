import os
import json
import requests
import sys
from django.conf import settings


# 페이박스 위쳇페이 공통 클래스
class Paybox:


    def __init__(self, type):
        if type == 'LIVE':
            self.endpoint        = settings.PAYBOX_WECHATPAY_LIVE_ENDPOINT
            self.partner_id      = settings.PAYBOX_WECHATPAY_LIVE_PARTNER_ID
            self.partner_key     = settings.PAYBOX_WECHATPAY_LIVE_PARTNER_KEY
        elif type == 'TEST':
            self.endpoint        = settings.PAYBOX_WECHATPAY_TEST_ENDPOINT
            self.partner_id      = settings.PAYBOX_WECHATPAY_TEST_PARTNER_ID
            self.partner_key     = settings.PAYBOX_WECHATPAY_TEST_PARTNER_KEY


    # 토큰생성 함수
    def load_token(self):

        full_url = self.endpoint + 'Create/Token'
        payload = {
            "partnerAPIId"      : self.partner_id,
            "partnerAPIKey"     : self.partner_key
        }
        headers = {
            'Content-Type'      : 'application/json',
            'Accept'            : 'application/json'
        }
        print('full_url : ', full_url)
        r = requests.post(full_url, json=payload, headers=headers)

        status_code = r.status_code
        print('status_code : ', status_code)
        print('html : ', r.text)
        try:
            data = json.loads(r.text)
            token = data['data']
        except BaseException as err:
            print('ERROR -> ', err)
            return 500

        print('token : ', token)
        return token

    # 환불 함수
    def payments_cancel(self, pgcode, user_id, tid, amount, token):
        full_url = self.endpoint + 'Api/Payment/Cancel'
        payload = {
            "cancelType"      : 1,
            "transactionId"   : tid,
            "transAmount"     : amount
        }
        headers = {
            'Content-Type'      : 'application/json',
            'Accept'            : 'application/json',
            'Authorization '    : token
        }
        r = requests.post(full_url, json=payload, headers=headers)

        print('full_url : ', full_url)
        print('payload : ', payload)
        print('headers : ', headers)

        status_code = r.status_code
        print('status_code : ', status_code)
        print('html : ', r.text)
        try:
            data = json.loads(r.text)
            res = data['data']['resultCode']
            return res
        except BaseException as err:
            print('ERROR -> ', err)
            return 500
