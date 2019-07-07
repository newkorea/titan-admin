import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.models import *
from datetime import datetime


@login_check
def dashboard(request):
    profit = 0
    refund = 0
    Teens = 0
    Twenties = 0
    Thirties = 0
    Fourties = 0
    fifties = 0
    Sixty = 0
    Seventies = 0
    Eighty = 0
    etc = 0

    now_year = datetime.today().year
    now_month = datetime.today().month
    now_day = datetime.today().day
    print(now_year, now_month, now_day)
    regist_today = len(TblUser.objects.filter(regist_date__year=now_year, regist_date__month=now_month, regist_date__day=now_day))
    login_today = len(TblUserLogin.objects.filter(login_date__year=now_year, login_date__month=now_month, login_date__day=now_day))
    today_profits = TblPriceHistory.objects.filter(regist_date__year=now_year, regist_date__month=now_month, regist_date__day=now_day, refund_yn='N')
    today_refunds = TblPriceHistory.objects.filter(refund_date__year=now_year, refund_date__month=now_month, refund_date__day=now_day, refund_yn='Y')
    user_count = len(TblUser.objects.filter(is_staff=0))
    admin_count = len(TblUser.objects.filter(is_staff=1))
    cs_count = len(TblUser.objects.filter(is_staff=2))
    chongpan_count = len(TblUser.objects.filter(is_staff=3))
    active_count = len(TblUser.objects.filter(is_active=1))
    deactive_count = len(TblUser.objects.filter(is_active=0))
    delete_count = len(TblUser.objects.filter(delete_yn='Y'))
    black_count = len(TblUser.objects.filter(black_yn='Y'))


    for today_profit in today_profits:
        profit += today_profit.amount
    print(profit)

    for today_refund in today_refunds:
        refund += today_refund.amount
    print(refund)


    u1 = TblUser.objects.all()

    for u in u1:
        user_year = u.birth_date[0:4]
        age = int(now_year) - int(user_year) + 1
        if age >= 10 and age < 20:
            Teens += 1
        elif age >= 20 and age < 30:
            Twenties += 1
        elif age >= 30 and age < 40:
            Thirties += 1
        elif age >= 40 and age < 50:
            Fourties += 1
        elif age >= 50 and age < 60:
            fifties += 1
        elif age >= 60 and age < 70:
            Sixty += 1
        elif age >= 70 and age < 80:
            Seventies += 1
        elif age >= 80 and age < 90:
            Eighty += 1
        else:
            etc += 1

    ages = [Teens, Twenties, Thirties, Fourties, fifties, Sixty, Seventies, Eighty, etc]


    men = len(TblUser.objects.filter(gender='m'))
    female = len(TblUser.objects.filter(gender='f'))

    gender_list = []
    gender_list.append(men)
    gender_list.append(female)

    context = {
        'regist_today': regist_today,
        'login_today': login_today,
        'profit': profit,
        'refund': refund,
        'user_count': user_count,
        'admin_count': admin_count,
        'cs_count': cs_count,
        'chongpan_count': chongpan_count,
        'active_count': active_count,
        'deactive_count': deactive_count,
        'delete_count': delete_count,
        'black_count': black_count,
        'men': men,
        'female': female,
        'ages': ages
    }
    return render(request, 'dashboard/dashboard.html', context)

