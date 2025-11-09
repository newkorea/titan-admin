import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from backend.djangoapps.common.views import *
from backend.djangoapps.common.swal import get_swal
from backend.models import *
from django.db import transaction


# (2022-12-07)
@allow_admin
def api_reward_setting(request):
    with connections['default'].cursor() as cur:
        query = '''
            select id, percent
            from tbl_reward_setting
        '''.format()
        print(query)
        cur.execute(query)
        rows = dictfetchall(cur)
    
        if len(rows) > 0 :
            res = {
            	'id' : rows[0]['id'],
                'reward_percent': rows[0]['percent']
            }
            return JsonResponse({
                'resCode': 200, 
                'resMsg': '0000',
                'resData': res
            })
        else:
    	    return JsonResponse({
                'resCode': 404, 
                'resMsg': '0000'
            })


# (2022-12-07)
@allow_admin
def api_update_reward_setting(request):    
    percent = request.POST.get('percent')
    id = request.POST.get('reward_id')
    with connections['default'].cursor() as cur:
        query = '''
            select  percent
            from tbl_reward_setting
        '''.format()
        print(query)
        cur.execute(query)
        rows = dictfetchall(cur)
    
        print('Rows count = ', len(rows))
        if len(rows) == 0 :
            reward = TblRewardSetting(
                percent=percent,
                register_date=datetime.datetime.now()
            )
            reward.save()
            
            return JsonResponse({'result': 200})
        else:
            print('Reward ID = ', id)
            print('Percentage = ', percent)
            reward = TblRewardSetting.objects.get(id=id)
            reward.percent = percent
            reward.register_date=datetime.datetime.now()
            reward.save()
    	        	    
            return JsonResponse({'result': 200})
