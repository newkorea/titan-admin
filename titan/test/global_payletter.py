import json
import requests
import datetime
import hashlib


class GlobalPayletter:


    def __init__(self, type):
        if type == 'live':
            pass
        elif type == 'test':
            self.endpoint = 'https://dev-gpgclient.payletter.com/'
            self.endpoint_api = 'https://dev-api.payletter.com/'
            self.storeid = 'titanvpn'
            # self.payerid = 'titanvpn'
            self.store_hashkey = 'titanvpn_190613'


    def payments_request(self, pgcode, user_id, user_name, price, product_name, order_no, custom_parameter):
        print('API DEBUG -> pgcode : ', pgcode)
        print('API DEBUG -> user_id : ', user_id)
        print('API DEBUG -> user_name : ', user_name)
        print('API DEBUG -> price : ', price)
        print('API DEBUG -> product_name : ', product_name)
        print('API DEBUG -> order_no : ', order_no)
        print('API DEBUG -> custom_parameter : ', custom_parameter)

        x = requests.get('https://earthquake.kr:23490/query/USDKRW')
        xxx = json.loads(x.text)
        dolor = xxx['USDKRW'][0]
        price_won = float(price)
        price_dol = float(dolor)
        real_dol = round(price_won / price_dol, 2)
        full_url = self.endpoint + 'Web/Payment.aspx'
        unixtime = str(datetime.datetime.now().timestamp())[:10]
        currency = 'USD'
        storeorderno = unixtime
        payamt = real_dol
        data = self.storeid + currency + str(order_no) + str(payamt) + str(user_id) + str(unixtime) + self.store_hashkey
        hs = hashlib.sha256(data.encode()).hexdigest()
        payload = {
            'storeid': self.storeid,
            'currency': currency,
            'storeorderno': order_no,
            'payamt': payamt,
            'payerid': user_id,
            'payeremail': user_id,
            'servicename': product_name,
            'returnurl': 'http://dev.titanvpn.io/globalpayletter_return',
            'backurl': 'http://dev.titanvpn.io/globalpayletter_cancel',
            'custom': custom_parameter,
            'pginfo': pgcode,
            'recurringtype': 'N',
            'timestamp': unixtime,
            'hash': hs,
        }
        r = requests.post(full_url, data=payload)

        if pgcode == 'PLCreditCard':
            text = str(r.text).replace('/Web/Payment/PLCard/CreditCardKeyIn/CardKeyInFrm.aspx', 'https://dev-gpgclient.payletter.com/Web/Payment/PLCard/CreditCardKeyIn/CardKeyInFrm.aspx')
        elif pgcode == 'PLUnionPay':
            text = str(r.text).replace('/Web/Payment/PLCard/UnionPay/UnionPayProc.aspx', 'https://dev-gpgclient.payletter.com/Web/Payment/PLCard/UnionPay/UnionPayProc.aspx')
        text = text.replace("target='_self'", '')
        text = text.replace("<script>document.gopay.submit();</script>", '')

        return text

    def test(self):
        print('hello world')

if __name__ == "__main__":
    gp = GlobalPayletter('test')
    text = gp.payments_request('PLCreditCard', '3', 'david', '100000', '봉하마을티켓', '20190101000000', '1_1')
    print('text -> ', text)
