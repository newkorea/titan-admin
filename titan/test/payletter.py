import json
import requests

"""
inbound allow

TEST
121.254.205.166

LIVE
211.115.72.37
211.115.72.38
211.115.117.11 (temp)
"""


pgCodeTable = {
    'creditcard': '신용카드',
    'kftc': '인터넷뱅킹(금융결제원)',
    'inibank': '인터넷뱅킹(이니시스)',
    'virtualaccount': '가상계좌',
    'mobile': '휴대폰',
    'book': '도서상품권',
    'culture': '문화상품권',
    'smartculture': '스마트문상',
    'happymoney': '해피머니상품권',
    'mobilepop': '모바일팝',
    'teencash': '틴캐시',
    'tmoney': '교통카드결제',
    'cvs': '편의점캐시',
    'eggmoney': '에그머니',
    'oncash': '온캐시',
    'phonebill': '폰빌',
    'cashbee': '캐시비',
    'kakaopay': '카카오페이',
    'payco': '페이코',
    'checkpay': '체크페이',
    'toss': '토스'
}


class Payletter:


    def __init__(self, type):
        if type == 'live':
            self.endpoint = 'https://pgapi.payletter.com/'
            self.shop_id = ''
            self.api_key_payment = ''
            self.api_key_search = ''
        elif type == 'test':
            self.endpoint = 'https://testpgapi.payletter.com/'
            self.shop_id = 'pay_test'
            self.api_key_payment = 'MTFBNTAzNTEwNDAxQUIyMjlCQzgwNTg1MkU4MkZENDA='
            self.api_key_search = 'MUI3MjM0RUExQTgyRDA1ODZGRDUyOEM4OTY2QTVCN0Y='


    # 커넥션 확인
    def connection_test(self):
        url = 'https://stagepg.payletter.com/TLSTest/test.html'
        r = requests.get(url)

        if r.text == 'OK':
            print('status -> connect success')
        else:
            print('status -> connect fail')


    # 변수체크
    def check_self(self):
        print('self.endpoint -> ', self.endpoint)
        print('self.shop_id -> ', self.shop_id)
        print('self.api_key_payment -> ', self.api_key_payment)
        print('self.api_key_search -> ', self.api_key_search)


    # 결제요청
    def payments_request(self, pgcode, user_id, user_name, price, product_name, order_no):

        full_url = self.endpoint + 'v1.0/payments/request'
        payload = {
            "pgcode" : pgcode,
            "user_id": user_id,
            "user_name": user_name,
            "service_name": "TITAN VPN",
            "client_id": self.shop_id,
            "order_no": order_no,
            "amount": 500,
            "taxfree_amount": 100,
            "tax_amount": 20,
            "product_name": product_name,
            "email_flag":"Y",
            "email_addr":"93immm@naver.com",
            "autopay_flag": "N",
            "receipt_flag": "Y",
            "custom_parameter":"",
            "return_url":"http://127.0.0.1:8000/payletter_return",
            "callback_url":"http://127.0.0.1:8000/payletter_callback",
            "cancel_url":"http://127.0.0.1:8000/payletter_cancel"
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)

        print('r.status_code -> ', r.status_code)
        print('r.text -> ', r.text)

        parsed = json.loads(r.text)
        print(json.dumps(parsed, indent=4, sort_keys=True))

        return r.text


    # 결제취소
    def payments_cancel(self):

        full_url = self.endpoint + 'v1.0/payments/cancel'
        payload = {
            "pgcode" : "kakaopay",
            "client_id": "pay_test",
            "user_id": "12",
            "tid": "tpay_test-201906307592272",
            "amount" : 500,
            "ip_addr": "127.0.0.1"
        }

        headers = {
            'content-type': 'application/json',
            'Authorization': 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)

        print('r.status_code -> ', r.status_code)
        print('r.text -> ', r.text)
        parsed = json.loads(r.text)
        print(json.dumps(parsed, indent=4, sort_keys=True))


    # 자동결제
    def payments_autopay(self):

        full_url = self.endpoint + 'v1.0/payments/autopay'
        payload = {
            "pgcode" : "mobile",
            "client_id":"pay_test",
            "service_name":"페이레터",
            "user_id":"test_user_id",
            "user_name":"테스터",
            "order_no":"1234567890",
            "amount":1000,
            "taxfree_amount": 100,
            "tax_amount": 20,
            "product_name":"테스트상품",
            "billkey":"tbpay_test201801012359590002",
            "sequence_no":1,
            "ip_addr":"127.0.0.1"
        }

        headers = {
            'content-type': 'application/json',
            'Authorization': 'PLKEY ' + self.api_key_payment
        }
        r = requests.post(full_url, json=payload, headers=headers)

        print('r.status_code -> ', r.status_code)
        print('r.text -> ', r.text)
        parsed = json.loads(r.text)
        print(json.dumps(parsed, indent=4, sort_keys=True))


    # 결제내역 조회
    def payments_list(self):

        full_url = self.endpoint + 'v1.0/payments/transaction/list'
        full_url += '?client_id=pay_test&date=20180918&date_type=transaction'
        headers = {
            'Authorization': 'PLKEY ' + self.api_key_search
        }
        r = requests.get(full_url, headers=headers)

        print('r.status_code -> ', r.status_code)
        print('r.text -> ', r.text)
        parsed = json.loads(r.text)
        print(json.dumps(parsed, indent=4, sort_keys=True))


if __name__ == '__main__':
    p = Payletter('test')
    #p.connection_test()
    #p.check_self()
    #print('-------------------------')
    #p.payments_request()
    #print('-------------------------')
    p.payments_cancel()
    #print('-------------------------')
    #p.payments_autopay()
    #print('-------------------------')
    #p.payments_list()
    #print('-------------------------')
