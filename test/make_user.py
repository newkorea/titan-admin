import pymysql

conn = pymysql.connect(
    host='1.234.70.54',
    user='scv',
    password='dhlwn12!@',
    db='titan',
    charset='utf8'
)

curs = conn.cursor()

for n in range(10000, 100000):
    sql1 = '''
    INSERT INTO `titan`.`tbl_user` (`email`, `password`, `username`, `phone`, `phone_country`, `gender`, `birth_date`, `sns_code`, `sns_name`, `rec`, `regist_rec`, `regist_ip`, `is_active`, `is_staff`, `delete_yn`, `black_yn`)
    VALUES ('{email}', '33520a0e494e83089688a41c14b2a6800a2178b2aa9767e209170f5c149e4418:50da9f67158f462d96bb5cff267e60e2', '오버테스트', '01099999999', '82', 'f', '19930208', 'K1', 'hello', 'over', '123', '127.0.0.1', '1', '0', 'N', 'N');
    '''.format(email='overtest' + str(n) + '@naver.com');
    curs.execute(sql1)

print(sql1)

conn.commit()
conn.close()
