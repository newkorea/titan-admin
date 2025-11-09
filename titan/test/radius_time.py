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

def dec_radius_time(radius_time):
    radius_time = radius_time.replace(' KST', '')

    radius_time = radius_time.replace('Jan', 'January')
    radius_time = radius_time.replace('Feb', 'February')
    radius_time = radius_time.replace('Mar', 'March')
    radius_time = radius_time.replace('Apr', 'April')
    radius_time = radius_time.replace('May', 'May')
    radius_time = radius_time.replace('Jun', 'June')
    radius_time = radius_time.replace('Jul', 'July')
    radius_time = radius_time.replace('Aug', 'August')
    radius_time = radius_time.replace('Sep', 'September')
    radius_time = radius_time.replace('Oct', 'October')
    radius_time = radius_time.replace('Nov', 'November')
    radius_time = radius_time.replace('Dec', 'December')

    radius_time = datetime.datetime.strptime(radius_time, '%d %B %Y %H:%M:%S')
    return radius_time

if __name__ == '__main__':
    now = datetime.datetime.now(timezone('Asia/Seoul')) + datetime.timedelta(n)
    print('now -> ', now)
    now = enc_radius_time(now)
    print('now -> ', now)
    now = dec_radius_time(now)
    print('now -> ', now)
    print('---------------------------')