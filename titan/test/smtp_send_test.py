import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

smtp_host = 'smtp.gmail.com'
smtp_port = 587
smtp_id = 'titanvpndev@gmail.com'
smtp_pw = 'dhlwn12!'
smtp_to = '93immm@naver.com'

smtp = smtplib.SMTP(smtp_host, smtp_port)
smtp.ehlo()      # say Hello
smtp.starttls()  # TLS 사용시 필요
smtp.ehlo()
smtp.login(smtp_id, smtp_pw)

msg = MIMEMultipart('alternative')
msg['Subject'] = 'TITAN VPN Account Activation Email'
msg['From'] = smtp_id
msg['To'] = smtp_to
html = '''
<div style="width: 600px;
            border: solid 1px #bbbbbb;
            text-align: center;
            border-top: solid 3px #673AB7;">
  <div style="margin-top: 30px;
              margin-bottom: 10px;
              font-weight: bold;
              font-size: 20px;">
    회원가입 인증 메일입니다.
  </div>
  <div style="font-size: 14px;
              margin-bottom: 35px;">
    회원가입이 완료되었습니다
  </div>
  <div style="border-top: solid 1px #bbbbbb;
              border-bottom: solid 1px #bbbbbb;
              padding: 20px;
              font-size: 15px;">
    이메일 인증 확인 : <a href='#'>여기를 클릭하시면 인증이 완료됩니다</a>
  </div>
  <div style="padding: 35px;
              font-size: 14px;">
    TITAN VPN을 이용해 주셔서 감사합니다.
  </div>
  <div style="padding: 20px;
              background: #f5f5f5;
              font-size: 14px;">
    본 메일은 발신전용 메일입니다
  </div>
</div>

'''

part = MIMEText(html, 'html')
msg.attach(part)

smtp.sendmail(smtp_id, smtp_to, msg.as_string())
smtp.quit()
