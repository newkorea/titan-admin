import json
import requests
import datetime
import hashlib
import uuid
from django.conf import settings


# 페이레터 해외 공통 클래스
class PayletterGlobal:


    def __init__(self, type):
        if type == 'LIVE':
            self.endpoint      = settings.PAYLETTER_GLOBAL_LIVE_ENDPOINT
            self.endpoint_api      = settings.PAYLETTER_GLOBAL_LIVE_ENDPOINT_API
            self.storeid       = settings.PAYLETTER_GLOBAL_LIVE_STOREID
            self.store_hashkey = settings.PAYLETTER_GLOBAL_LIVE_STORE_HASHKEY
        elif type == 'TEST':
            self.endpoint      = settings.PAYLETTER_GLOBAL_TEST_ENDPOINT
            self.endpoint_api      = settings.PAYLETTER_GLOBAL_TEST_ENDPOINT_API
            self.storeid       = settings.PAYLETTER_GLOBAL_TEST_STOREID
            self.store_hashkey = settings.PAYLETTER_GLOBAL_TEST_STORE_HASHKEY


    # 환불 함수
    def payments_cancel(self, pgcode, user_id, tid, amount):

        # 헤더생성
        unixtime = str(datetime.datetime.now().timestamp())[:10]
        if settings.PAYLETTER_MODE == 'TEST':
            request_url_enc = 'https%3a%2f%2fdev-api.payletter.com%2fpayment%2f' + pgcode.lower() + '%2frefund'
        elif settings.PAYLETTER_MODE == 'LIVE':
            request_url_enc = 'https%3a%2f%2fapi.payletter.com%2fpayment%2f' + pgcode.lower() + '%2frefund'
        nonce = str(uuid.uuid4())
        request_content = 'storeid=' + self.storeid + '&paytoken=' + tid + '&currency=USD&amount=' + amount + '&pginfo=' + pgcode
        request_string = self.storeid + self.store_hashkey + 'POST' + request_url_enc + unixtime + nonce + request_content
        signature = hashlib.sha256(request_string.encode('utf-8')).hexdigest()
        header_authorization = 'POQAPI ' + self.storeid + ':' + signature + ':' + nonce + ':' + unixtime

        print('API DEBUG -> request_string : ', request_string)
        print('API DEBUG -> signature : ', signature)
        print('API DEBUG -> header_authorization : ', header_authorization)

        full_url = self.endpoint_api + 'payment/' + pgcode + '/refund'
        payload = {
            'storeid': self.storeid,
            'paytoken': tid,
            'currency': 'USD',
            'amount': amount,
            'pginfo': pgcode
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': header_authorization
        }
        print('API DEBUG -> payload : ', payload)
        r = requests.post(full_url, data=payload, headers=headers)

        print('API DEBUG -> r.status_code : ', r.status_code)
        print('API DEBUG -> r.text : ', r.text)

        status_code = r.status_code
        return status_code
