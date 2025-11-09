from django.shortcuts import render, redirect
from django.db import connections
from django.utils import timezone
from backend.models import TblUser

def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def price_table(request):
    LANGUAGE_CODE = request.LANGUAGE_CODE
    user_email = 'guest'
    user_regdate = ''
    expiration = None
    simultaneous_use = None

    if 'id' in request.session:
        id = request.session['id']
        try:
            u1 = TblUser.objects.get(id=id)
            if u1.email:
                user_email = u1.email
                user_regdate = u1.regist_date

                try:
                    with connections['default'].cursor() as cur:
                        sql = '''
                            SELECT attribute, value
                            FROM   radius.radcheck
                            WHERE  username = %s
                        '''
                        cur.execute(sql, [u1.email])
                        rows = dictfetchall(cur)

                        for row in rows:
                            if row["attribute"] == "Simultaneous-Use":
                                simultaneous_use = row["value"]
                            elif row["attribute"] == "Expiration":
                                expiration = row["value"]
                except Exception as e:
                    print("Database query failed:", e)

        except TblUser.DoesNotExist:
            pass

    expiration_str = expiration if expiration else "None"
    simultaneous_use_str = simultaneous_use if simultaneous_use else "None"

    context = {
        'LANGUAGE_CODE': LANGUAGE_CODE,
        'user_email': user_email,
        'username': user_email,
        'regdate': str(user_regdate) if user_regdate else '',
        'simultaneous_use': simultaneous_use_str,
        'expiration': expiration_str,
    }

    return render(request, 'new/price_table.html', context)
