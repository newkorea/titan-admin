import re

regist_password = '1111111aa'
#regist_password = 'aaaaaaaaa'
#regist_password = 'AAAAAAAAA'
#regist_password = 'AAAAAA!@#'

check_cnt = 0
pattern1 = re.search('[0-9]', regist_password)
pattern2 = re.search('[a-zA-Z]', regist_password)
pattern3 = re.search('[~!@#$%^&*()_+|<>?:{}]', regist_password)
if pattern1 != None:
    print('INFO -> pattern1 match')
    check_cnt += 1
if pattern2 != None:
    print('INFO -> pattern2 match')
    check_cnt += 1
if pattern3 != None:
    print('INFO -> pattern3 match')
    check_cnt += 1
print('INFO -> check_cnt : ', check_cnt)
if checkt_cnt >= 2:
    pass
else:
    # error
