import pymysql

conn = pymysql.connect(
    host='1.234.70.54',
    user='scv',
    password='dhlwn12!@',
    db='titan',
    charset='utf8'
)

curs = conn.cursor()

sql1 = '''
delete a
from tbl_user_login a
left join tbl_user b
on b.id = a.user_id
where b.id is null;
'''
curs.execute(sql1)

print(sql1)

conn.commit()
conn.close()
