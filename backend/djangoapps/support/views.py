import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


@login_check
def support(request):

    tcg = TblCodeGroup.objects.filter(memo='support')
    context = {}
    context['code_group'] = tcg
    return render(request, 'support/support.html', context)


@login_check
def api_support_getSubOption(request):

    group_code = request.POST.get('group_code')
    
    tcd = TblCodeDetail.objects.filter(group_code=group_code)

    rr = []
    for f in tcd:
        tmp = {}
        tmp['code'] = f.code
        tmp['name'] = f.memo
        rr.append(tmp)

    return JsonResponse({'result': rr})


# parameter : yyyy-mm-dd
def convertStrToDatetime(strTypedate):

    tmp = strTypedate.split('-')
    yyyy = int(tmp[0])
    mm = int(tmp[1])
    dd = int(tmp[2])
    return datetime.datetime(yyyy, mm, dd)


@login_check
def api_support_getContent(request):

    main_sel = request.POST.get('main_sel')
    sub_sel = request.POST.get('sub_sel')
    send_yn = request.POST.get('send_yn')
    target_date = request.POST.get('target_date')
    
    # life cycle bug fix
    if sub_sel == '':
        sub_sel = '0'

    print('----------------------------')
    print('main_sel -> ', main_sel)
    print('sub_sel -> ', sub_sel)
    print('sub_sel -> ', type(sub_sel))
    print('send_yn -> ', send_yn)
    print('target_date -> ', target_date)
    print('----------------------------')

    with connections['default'].cursor() as cur:
        if sub_sel == '0' and send_yn != 'D':
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and date(regist_date) = date('{target_date}')
                and send_yn='{send_yn}'
                and delete_yn = 'N';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()
        elif sub_sel != '0' and send_yn != 'D':
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and sub_type='{sub_sel}'
                and date(regist_date) = date('{target_date}')
                and send_yn='{send_yn}'
                and delete_yn = 'N';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()
        elif sub_sel == '0' and send_yn == 'D':
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and date(regist_date) = date('{target_date}')
                and delete_yn='Y';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()
        elif sub_sel != '0' and send_yn == 'D':
            query = '''
                select id, title, DATE_FORMAT(regist_date, "%Y-%m-%d %H:%i") AS regist_date
                from tbl_support
                where main_type='{main_sel}'
                and sub_type='{sub_sel}'
                and date(regist_date) = date('{target_date}')
                and delete_yn='Y';
            '''.format(main_sel=main_sel, sub_sel=sub_sel, target_date=target_date, send_yn=send_yn)
            print(query)
            cur.execute(query)
            rows = cur.fetchall()      

    print('len(rows) -> ', len(rows))

    rr = []
    for row in rows:
        tmp = {}
        tmp['id'] = row[0]

        print('row[1] -> ', row[1])
        print('len(row[1]) -> ', len(row[1]))

        # text overflow detect
        title = row[1]
        if len(title) > 20:
            title = title[0:20] + '...'

        tmp['title'] = title
        tmp['regist_date'] = row[2]
        rr.append(tmp)

    return JsonResponse({'result': rr})


@login_check
def api_support_getSelectContent(request):

    id = request.POST.get('id')

    ts = TblSupport.objects.get(id=id)

    tcg = TblCodeGroup.objects.get(
        code=ts.main_type
    )

    tcd = TblCodeDetail.objects.get(
        group_code=ts.main_type,
        code=ts.sub_type
    )

    tf = TblFile.objects.filter(
        gname=ts.main_type,
        gid=id
    )

    rr = {}
    rr['main_type'] = tcg.name
    rr['sub_type'] = tcd.memo
    rr['email'] = ts.email
    rr['title'] = ts.title
    rr['send_title'] = ts.send_title
    rr['send_content'] = ts.send_content
    rr['send_date'] = ts.send_date
    rr['content'] = xssProtect(ts.content) # xss protext
    
    if len(tf) == 0:
        rr['file1'] = ''
        rr['file2'] = ''
    if len(tf) == 1 or len(tf) == 2:
        print('tf[0].save_path -> ', tf[0].save_path)
        rr['file1'] = tf[0].save_path.replace('/home/vagrant/project/titan', '')
        rr['file2'] = ''
    if len(tf) == 2:
        print('tf[1].save_path -> ', tf[1].save_path)
        rr['file2'] = tf[1].save_path.replace('/home/vagrant/project/titan', '')
    return JsonResponse({'result': rr})


def api_support_deleteItem(request):
    id = request.POST.get('id')

    ts = TblSupport.objects.get(id=id)

    ts.delete_yn = 'Y'
    ts.delete_date = datetime.now()
    ts.save()

    return JsonResponse({'result': 200})

def api_support_sendItem(request):
    id = request.POST.get('id')
    to_email = request.POST.get('email')
    subject = request.POST.get('subject')
    content = request.POST.get('content')

    print(type(content))
    print('content------------->', content)

    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_id = settings.SMTP_ID
    smtp_pw = settings.SMTP_PW
    smtp_to = to_email

    smtp = smtplib.SMTP(smtp_host, smtp_port)
    smtp.ehlo()      # say Hello
    smtp.starttls()  # TLS 사용시 필요
    smtp.ehlo()
    smtp.login(smtp_id, smtp_pw)

    msg = MIMEText(content)
    msg['Subject'] = subject
    msg['From'] = smtp_id
    msg['To'] = smtp_to
    smtp.sendmail(smtp_id, smtp_to, msg.as_string())

    smtp.quit()

    ts = TblSupport.objects.get(id=id)

    # 띄어쓰기 픽스 txt -> html
    content = content.replace('\n', '<br>')

    ts.send_yn = 'Y'
    ts.send_title = subject
    ts.send_content = content
    ts.send_date = datetime.now()
    ts.save()

    return JsonResponse({'result': 200})