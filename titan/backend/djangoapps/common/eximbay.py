import os
import json
import requests
import sys
from django.conf import settings


# 엑심베이 위쳇페이 공통 클래스
class EximBay:


    def __init__(self, type):
        if type == 'LIVE':
            self.endpoint        = settings.PAYBOX_WECHATPAY_LIVE_ENDPOINT
            self.partner_id      = settings.PAYBOX_WECHATPAY_LIVE_PARTNER_ID
            self.partner_key     = settings.PAYBOX_WECHATPAY_LIVE_PARTNER_KEY
        elif type == 'TEST':
            self.endpoint        = settings.PAYBOX_WECHATPAY_TEST_ENDPOINT
            self.partner_id      = settings.PAYBOX_WECHATPAY_TEST_PARTNER_ID
            self.partner_key     = settings.PAYBOX_WECHATPAY_TEST_PARTNER_KEY


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
            callback_url = "https://"+settings.FULL_URL+"/paybox_callback"
        else:
            callback_url = "http://"+settings.FULL_URL+"/paybox_callback"

        if settings.HTTPS == True:
            return_url = "https://"+settings.FULL_URL+"/paybox_return"
        else:
            return_url = "http://"+settings.FULL_URL+"/paybox_return"

        if settings.HTTPS == True:
            cancel_url = "https://"+settings.FULL_URL+"/paybox_cancel"
        else:
            cancel_url = "http://"+settings.FULL_URL+"/paybox_cancel"

        # 페이박스 API 호출
        full_url = self.endpoint + 'Payment/Encrypt'
        payload = {
            "partnerAPIId"      : self.partner_id,
            "partnerAPIKey"     : self.partner_key,
            "paymentType"       : 1,
            "pgCode"            : pgcode,
            "orderNo"           : order_no,
            "transAmount"       : price,
            "notiUrl"           : callback_url,
            "returnUrl"         : return_url,
            "cancelUrl"         : cancel_url,
            "orderInfo"         : product_name,
            "email"             : email,
            "additionalInfo"    : custom_parameter
        }
        headers = {
            'Content-Type'      : 'application/json',
            'Accept'            : 'application/json'
        }
        r = requests.post(full_url, json=payload, headers=headers)
        r_json = json.loads(r.text)

        print('API DEBUG -> status_code : ', r.status_code)
        print('API DEBUG -> text : ', r.text)

        data = r_json["data"]
        url = self.endpoint + 'Payment/Request/Redirect/WECHAT' + '?param=' + data
        return url
