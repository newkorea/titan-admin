import requests
import base64
from Crypto.Hash import SHA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Cipher import PKCS1_OAEP
from django.conf import settings


# Gompay Common Class
class GomPay:
    def __init__(self):
        self.url = settings.GOMPAY_URL
        self.app_id = settings.GOMPAY_APP_ID
        self.currency = 'KRW'
        self.body = settings.GOMPAY_BODY
        self.payment_channel = 'WECHAT'
        self.return_url = 'http://' + settings.FULL_URL + '/gompay_return'
        self.signType = 'RSA'
        self.PRIVATE_KEY = settings.GOMPAY_PRIVATE_KEY
        self.sign = ''
        self.raw_string = ''

    def payments_request(self,
                        pgcode,
                        user_id,
                        user_name,
                        price,
                        product_name,
                        order_no,
                        session,
                        month_type,
                        email):
        # 0. debug (dev)
        if settings.GOM_MODE == 'TEST':
            price = 100

        # make custom parameter
        body = str(user_id) + '_' + str(session) + '_' + str(month_type)
        self.body = body

        # 1. make raw string
        raw_string = "amount={amount}&app_id={app_id}&body={body}&currency={currency}&order_no={order_no}&payment_channel={payment_channel}&return_url={return_url}".format(
            amount=price,
            app_id=self.app_id,
            body=self.body,
            currency=self.currency,
            order_no=order_no,
            payment_channel=self.payment_channel,
            return_url=self.return_url)
        self.raw_string = raw_string

        # 2. sign
        private_key = RSA.importKey(self.PRIVATE_KEY)
        message = self.raw_string
        signer  = PKCS1_v1_5.new(private_key)
        h = SHA.new(message.encode('utf-8'))
        signature = signer.sign(h)
        self.sign = base64.b64encode(signature).hex()

        # 3. make url
        callUrl = self.url + '?' \
                  'app_id=' + str(self.app_id) + '&' + \
                  'payment_channel=' + str(self.payment_channel) + '&' + \
                  'order_no=' + str(order_no) + '&' + \
                  'amount=' + str(price) + '&' + \
                  'currency=' + str(self.currency) + '&' + \
                  'body=' + str(self.body) + '&' + \
                  'return_url=' + str(self.return_url) + '&' + \
                  'sign=' + str(self.sign) + '&' + \
                  'signType=' + str(self.signType)
        print('callUrl -> ', callUrl)
        return callUrl
