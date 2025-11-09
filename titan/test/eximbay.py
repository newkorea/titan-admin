test = 'baserate=&cur=KRW&dm_reject=&cardno1=4111&resdt=20200714205437&cardno4=1111&foreignrate=&mid=1849705C64&amt=10000&accesscountry=KR&ref=demo20170418202020&paymethod=P101&dm_review=&email=email%40email.com&ver=230&foreignamt=&basecur=&dccrate=&transid=1849705C6420200714000005&dm_decision=&param3=&resmsg=Success.&cardholder=aa&param1=&rescode=0000&param2=&authcode=161821&fgkey=804FB9B5CB2FA399CA9D1D4D1BB244755F687A4E3C3FD4B0640CCB9E3E740741&txntype=PAYMENT&foreigncur=&payto=EXIMBAY.COM&baseamt='

data_set = test.split('&')
print('data_set = ', data_set)

result_data = {}
for data in data_set:
    data = data.split('=')
    data[0]
    data[1]
    result_data[data[0]] = data[1]

print('result_data -> ', result_data)

if result_data['rescode'] == '0000':
    tid = result_data['transid']
    user_id = request.POST.get('payerid')
    pgcode = result_data['paymethod']
    product_name = result_data['param2']
    custom = result_data['param1']
    custom_parameter = custom.split('_')
    session = custom_parameter[0]
    month_type = custom_parameter[1]
    price = result_data['amt']
    taxfree_amount = None
    tax_amount = None
    autopay_flag = 'N'
    billkey = None
    refund_yn = 'N'
    refund_date = None
    auto_end_date = None

    # 로깅
    print('INFO -> tid : ', tid)
    print('INFO -> user_id : ', user_id)
    print('INFO -> pgcode : ', pgcode)
    print('INFO -> custom : ', custom)
    print('INFO -> session : ', session)
    print('INFO -> month_type : ', month_type)
    print('INFO -> product_name : ', product_name)
    print('INFO -> price : ', price)
    print('INFO -> taxfree_amount : ', taxfree_amount)
    print('INFO -> tax_amount : ', tax_amount)
    print('INFO -> autopay_flag : ', autopay_flag)
    print('INFO -> billkey : ', billkey)
    print('INFO -> refund_yn : ', refund_yn)
    print('INFO -> refund_date : ', refund_date)
    print('INFO -> auto_end_date : ', auto_end_date)
    return HttpResponse("rescode=0000&resmsg=Success")
else:
    return HttpResponse("rescode=5000&resmsg=Error")
