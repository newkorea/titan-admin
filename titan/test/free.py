from pytz import timezone
import datetime

def enc_radius_time(obj):
    radius_time = obj.strftime('%d') + ' ' + \
                  obj.strftime('%B')[:3] + ' ' + \
                  obj.strftime('%Y') + ' ' + \
                  obj.strftime('%H') + ':' + \
                  obj.strftime('%M') + ':' + \
                  obj.strftime('%S') + ' KST'

    return radius_time

if __name__ == "__main__":
    now = datetime.datetime.now(timezone('Asia/Seoul'))
    radius_time = enc_radius_time(now)
    print('DEBUG -> now : ', now)
    print('DEBUG -> radius_time : ', radius_time)

    input = '2019-11-01 00:00:00'
    x = datetime.datetime.strptime(input, '%Y-%m-%d %H:%M:%S')
    print('x -> ', x)
    radius_time = enc_radius_time(x)
    print('DEBUG -> radius_time : ', radius_time)
