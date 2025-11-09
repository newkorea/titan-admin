import pymysql
 
conn = pymysql.connect(
    host='1.234.70.54', 
    user='scv', 
    password='dhlwn12!@',
    db='titan', 
    charset='utf8'
)
 
curs = conn.cursor()
 
sql = '''
select name, memo
from tbl_code_detail
where group_code = 'phone_country'
'''
curs.execute(sql)
 
rows = curs.fetchall()

for r in rows:
    xxx = '''
    msgid "{e}"
    msgstr "{k}"
    '''.format(e=r[0], k=r[1])
    print(xxx)

conn.close()