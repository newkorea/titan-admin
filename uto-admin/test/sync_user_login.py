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
insert into tbl_user_login(user_id)
select a.id
from tbl_user a
left join tbl_user_login b
on a.id = b.user_id
where b.user_id is null;
'''
curs.execute(sql1)

print(sql1)

conn.commit()
conn.close()
