import requests
import base64
from Crypto.Hash import SHA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Cipher import PKCS1_OAEP


class GomPay:
    def __init__(self):
        self.url = 'https://nms.nova2pay.com/payment/otoSoft/v3/onlinePay.html'
        self.app_id = '5190'
        self.currency = 'KRW'
        self.body = 'paymentTest'
        self.payment_channel = 'WECHAT'
        self.amount = '1000'
        self.order_no = 'helloworld002'
        self.return_url = 'http://dev.titanvpn.io'
        self.signType = 'RSA'
        self.sign = ''
        self.raw_string = ''
        # 5190.txt
        self.PRIVATE_KEY = '''-----BEGIN RSA PRIVATE KEY-----
        MIICWwIBAAKBgQCLwC2tWwBbthOdLfqpJPc+1jYSXbNQhl/DHq6QU+XGZU3wz1jM
        W2ZxxzXC/eTu/XrFl2MBWfx/90ACJjgP0SJnqlE+NjKy0jJ6S01Jg82ohRlrPwMw
        hVAVPpsonggM6fKb/2gQhhW22qpqxX1Dg+OGM23DZ+fGqZyJ+XLLHTe7UQIDAQAB
        AoGAA2wocjdpUdWqs0299sh9+Z77YgXDb3RrAfdNZSF43hv7Bau+S/rtDlpHmcfo
        BGZWzGIBvbW7dlLS0XqoItMHWaNJLbS4xs1fBYT784+DUcsYZdVuxAEwgskJ+DWD
        rarFP/zR/Z+/1+EHKCnbR3CjbYLK1qdXIyuLL39Gutg61fUCQQDNoFKTYERsXBhO
        Hs4Q+PM7+5o1Z9A3HL5s2zuzsP3ZturFN5jNMy7GOWd0YMNXu3BX4syCluYBaKNw
        yeCeBfhnAkEArfyGhya5VwgqKZt+kIRuFO3RYjG3ZoWlXavyvWDrQ3JHyRsu3xc5
        8dLql4pZlhYyiGMElZk1uOTH/tBz/l47hwJAe0zBd0HohZmLsXxjUGYXZEZwp8mC
        XynLPfcQC6X78grvKCc4ZwNj7tUJJg3H1Nm+edSzkTLu5LVcHAvRtrAZzQJAGJ7V
        gqaOL6yuGrkwTc8PrNKCgLy8UTu0TO8aKIZghGjVk7XPCi7FOl04aT1gtAZsHDS2
        31yQ55soWfyxjVtUXQJAD7EUlflFHNJ88B8F+ZGFoRzV/J/iietwy8wWxxSsvm/m
        tGa0ct/7WMdozFiPOGgIsgPU/9cMuWlrxy5Uz0YmyQ==
        -----END RSA PRIVATE KEY-----
        '''
        self.PUBLIC_KEY = '''-----BEGIN PUBLIC KEY-----
        MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCQiXQtriMyIpGPIU4NksodtTi2c0A7JW+L5uem
        hN5vqIBkj2DIXQz3roNC8YH44o41XszAEMH3s+x2XSRTxYmaAgOBeECL5O7Xs3UpT54GTJVZOYMD
        j1KAUT0IKgEN/axqWEGRTvoXJKWhjp4ux2pNx1taPvAHQl78Uxa+z3T+ZwIDAQAB
        -----END PUBLIC KEY-----
        '''

    def checkVariable(self):
        print('url -> ', self.url)
        print('app_id -> ', self.app_id)
        print('currency -> ', self.currency)
        print('body -> ', self.body)
        print('payment_channel -> ', self.payment_channel)
        print('amount -> ', self.amount)
        print('order_no -> ', self.order_no)
        print('return_url -> ', self.return_url)
        print('signType -> ', self.signType)
        print('sign -> ', self.sign)

    def setRawString(self):
        raw_string = "amount={amount}&app_id={app_id}&body={body}&currency={currency}&order_no={order_no}&payment_channel={payment_channel}&return_url={return_url}".format(
            amount=self.amount,
            app_id=self.app_id,
            body=self.body,
            currency=self.currency,
            order_no=self.order_no,
            payment_channel=self.payment_channel,
            return_url=self.return_url)
        print ("setRawString -> " ,raw_string )
        self.raw_string = raw_string

    def makeSign(self):
        private_key = RSA.importKey(self.PRIVATE_KEY)
        message = self.raw_string
        signer  = PKCS1_v1_5.new(private_key)
        h = SHA.new(message.encode('utf-8'))
        signature = signer.sign(h)
        self.sign = base64.b64encode(signature).hex()

    def callAPI(self):
        params = {
            'app_id': self.app_id,
            'currency': self.currency,
            'body': self.body,
            'payment_channel': self.payment_channel,
            'amount': self.amount,
            'order_no': self.order_no,
            'return_url': self.return_url,
            'signType':self. signType,
            'sign': self.sign,
        }
        r = requests.get(self.url, params=params)
        print(r.text)


if __name__ == "__main__":
    gom = GomPay()
    gom.setRawString()
    gom.makeSign()
    gom.checkVariable()
    gom.callAPI()
