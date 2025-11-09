import json
import requests

endpoint = 'http://www.titanvpn.io/'

url1 = endpoint + 'api_init_session'
url2 = endpoint + 'api_session_key'
url3 = endpoint + 'api_session_test'

r = requests.get(url1)
r = json.loads(r.text)
csrftoken = r['csrftoken']
sessionid = r['sessionid']

print('csrftoken -> ', csrftoken)
print('sessionid -> ', sessionid)

cookies = {
    'csrftoken': csrftoken,
    'sessionid': sessionid
}
payload = {
    'csrfmiddlewaretoken': csrftoken,
    'login_email': 'admin@naver.com',
    'login_password': 'a1350666'
}
r = requests.post(url2, data=payload, cookies=cookies)
print('r.text -> ', r.text)

cookies = {
    'csrftoken': csrftoken,
    'sessionid': sessionid
}
payload = {
    'csrfmiddlewaretoken': csrftoken
}
r = requests.post(url3, data=payload, cookies=cookies)
print('r.text -> ', r.text)
