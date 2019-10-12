import json
import datetime
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *


# 공지사항 추가 API (2019.10.12 16:00 점검완료)
@login_check
def api_create_notice(request):
    title_ko = request.POST.get('title_ko')
    title_en = request.POST.get('title_en')
    title_zh = request.POST.get('title_zh')
    title_ja = request.POST.get('title_ja')
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    content_ja = request.POST.get('content_ja')
    TblNotice(
        title_ko = title_ko,
        title_en = title_en,
        title_zh = title_zh,
        title_ja = title_ja,
        content_ko = content_ko,
        content_en = content_en,
        content_zh = content_zh,
        content_ja = content_ja,
        regist_date = datetime.now(),
        delete_yn = 'N'
    ).save()
    return JsonResponse({'result': '200'})


# 공지사항 수정 API (2019.10.12 16:00 점검완료)
@login_check
def api_update_notice(request):
    no = request.POST.get('no')
    title_ko = request.POST.get('title_ko')
    title_en = request.POST.get('title_en')
    title_zh = request.POST.get('title_zh')
    title_ja = request.POST.get('title_ja')
    content_ko = request.POST.get('content_ko')
    content_en = request.POST.get('content_en')
    content_zh = request.POST.get('content_zh')
    content_ja = request.POST.get('content_ja')
    notice = TblNotice.objects.get(id=no)
    notice.title_ko = title_ko
    notice.title_en = title_en
    notice.title_zh = title_zh
    notice.title_ja = title_ja
    notice.content_ko = content_ko
    notice.content_en = content_en
    notice.content_zh = content_zh
    notice.content_ja = content_ja
    notice.save()
    return JsonResponse({'result': '200'})


# 공지사항 삭제 API (2019.10.12 16:00 점검완료)
@login_check
def api_delete_notice(request):
    no = request.POST.get('no')
    notice = TblNotice.objects.get(id=no)
    notice.delete()
    return JsonResponse({'result': '200'})


# 공지사항 렌더링 (2019.10.12 15:30 점검완료)
@login_check
def notice(request):
    noticeList = TblNotice.objects.filter(delete_yn='N')
    rows = []
    for notice in noticeList:
        item = {
            'id': notice.id,
            'title': notice.title_ko,
            'regist_date': notice.regist_date
        }
        rows.append(item)
    context = {}
    context['rows'] = rows
    return render(request, 'company/admin_notice.html', context)


# 공지사항 추가 렌더링 (2019.10.12 15:30 점검완료)
@login_check
def create_notice(request):
    context = {}
    return render(request, 'company/admin_create_notice.html', context)


# 공지사항 상세 렌더링 (2019.10.12 15:30 점검완료)
@login_check
def notice_inner(request, no):
    try:
        notice = TblNotice.objects.get(id=no)
    except BaseException:
        return redirect('/company/notice')
    context = {}
    context['no'] = no
    context['title_en'] = notice.title_en.replace('"',"&quot;")
    context['title_ko'] = notice.title_ko.replace('"',"&quot;")
    context['title_ja'] = notice.title_ja.replace('"',"&quot;")
    context['title_zh'] = notice.title_zh.replace('"',"&quot;")
    context['content_en'] = notice.content_en.replace('"',"&quot;")
    context['content_ko'] = notice.content_ko.replace('"',"&quot;")
    context['content_ja'] = notice.content_ja.replace('"',"&quot;")
    context['content_zh'] = notice.content_zh.replace('"',"&quot;")
    return render(request, 'company/admin_notice_inner.html', context)


# 회사소개 렌더링 (2019.09.15 11:56 점검완료)
@login_check
def about(request):

    with connections['default'].cursor() as cur:
        query = '''
            select en, ko, ja, zh
            from tbl_company_manage
            where type = 'M';
        '''
        cur.execute(query)
        row = cur.fetchall()
        en = row[0][0]
        ko = row[0][1]
        ja = row[0][2]
        zh = row[0][3]
        kind = 'M'
        context = {
            'en': en,
            'ko': ko,
            'ja': ja,
            'zh': zh,
            'kind': kind
        }

    return render(request, 'company/admin_about.html', context)


# 회사소개 편집 API (2019.09.15 11:56 점검완료)
@login_check
def api_company_edit(request):
    sum = request.POST.get('sum')
    kind = request.POST.get('kind')
    lang = request.POST.get('lang')

    t1 = TblCompanyManage.objects.get(type=kind)

    if lang == 'en':
        t1.en = sum
        t1.en_modify_date = datetime.now()
        t1.save()
    elif lang == 'ko':
        t1.ko = sum
        t1.ko_modify_date = datetime.now()
        t1.save()
    elif lang == 'ja':
        t1.ja = sum
        t1.ja_modify_date = datetime.now()
        t1.save()
    elif lang == 'zh':
        t1.zh = sum
        t1.zh_modify_date = datetime.now()
        t1.save()
    return JsonResponse({'result': '200'})


# 회사소개 로드 API (2019.09.15 11:56 점검완료)
@login_check
def api_company_load(request):
    kind = request.POST.get('kind')

    rows = TblCompanyManage.objects.filter(type=kind)

    list = []
    for t in rows:
        sd = {}
        sd['en'] = t.en
        sd['ko'] = t.ko
        sd['ja'] = t.ja
        sd['zh'] = t.zh
        list.append(sd)

    return JsonResponse({'result': list})
