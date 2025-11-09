import json
import datetime
import re
import uuid
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings
from backend.djangoapps.common.views import *
from urllib.parse import quote
from urllib.parse import unquote


# 이메일 공통 함수 (2019.09.09 12:53 점검완료)
def send_email(to_email, template, language):

    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_email = settings.SMTP_EMAIL
    smtp_id = settings.SMTP_ID
    smtp_pw = settings.SMTP_PW
    smtp_to = to_email

    # smtp = smtplib.SMTP(smtp_host)
    # smtp.ehlo()
    # smtp.starttls()
    # smtp.ehlo()

    smtp = smtplib.SMTP_SSL(smtp_host, smtp_port)
    smtp.login(smtp_id, smtp_pw)

    aes = AESCipher()
    before = datetime.datetime.now()
    before_time = before.strftime('%Y-%m-%d %H:%M')
    enc_email = quote(aes.encrypt(before_time+'|'+to_email).decode('ascii'))

    if language == 'ko':
        reg_e1 = '회원가입 인증 메일입니다'
        reg_e2 = '회원가입이 완료되었습니다'
        reg_e3 = '이메일 인증 확인'
        reg_e31 = '위링크로 확인이 안되시면 아래 링크를 이용해주세요!'
        reg_e4 = '여기를 클릭하시면 인증이 완료됩니다'
        reg_e5 = '이메일인증을 위한 두번째 링크'
        reg_e6 = '이메일인증을 위한 세번째 링크'
        for_e1 = '비밀번호 찾기 메일입니다'
        for_e2 = '비밀번호를 새롭게 변경하세요'
        for_e3 = '아래의 링크를 클릭하여 비밀번호를 새롭게 변경해주세요'
        for_e31 = '만약 위링크로 비번을 바꾸시지 못한다면 아래 링크중 하나를 클릭해주세요!'
        for_e4 = '여기를 클릭하시면 비밀번호 재설정이 가능합니다'
        for_e5 = '만약 위 링크가 열리지 않으면 여기를 눌러주세요. 비밀번호변경페이지2'
        for_e6 = '위 두링크가 열리지 않으면 여기를 눌러주세요. 비밀번호변경페이지3'
        com_e1 = 'TITAN NETWORKS을 이용해 주셔서 감사합니다'
        com_e2 = '본 메일은 발신전용 메일입니다'

    if language == 'en':
        reg_e1 = 'This is membership authentication mail'
        reg_e2 = 'membership registration completed'
        reg_e3 = 'Check email authentication'
        reg_e31 = 'If you have problem to see the link, Click one of below'
        reg_e5 = 'Second link for email verification' 
        reg_e6 = 'Third link for email verification'
        reg_e4 = 'Click here to complete authentication'
        for_e1 = 'Find Password Email'
        for_e2 = 'Refresh Password'
        for_e3 = 'Click the link below to change your password'
        for_e31 = 'If upper link could not be shown,  the link below to change your password'
        for_e4 = 'Click here to reset your password'
        for_e5 = 'Second Link for change your password'
        for_e6 = 'Third Link for change your password'
        com_e1 = 'Thank you for using your TITAN NETWORKS'
        com_e2 = 'This mail is outgoing only'

    if language == 'zh':
        reg_e1 = "这是注册会员认证邮件"
        reg_e2 = "会员注册已经结束"
        reg_e3 = "确认电子邮件认证"
        reg_e31 = "如果无法通过上述链接进行验证，请点击以下链接。"
        reg_e5 = "邮箱认证地址2"
        reg_e6 = "邮箱认证地址3"
        reg_e4 = "点击此处即可完成认证"
        for_e1 = "是寻找密码的邮件"
        for_e2 = "请重新变更密码"
        for_e3 = "点击下面的链接,重新更改密码"
        for_e31 = "点击下面的链接,重新更改密码"
        for_e4 = "点击这里就可以重新设置密码"
        for_e5 = "密码修改地址2"
        for_e6 = "密码修改地址3"
        com_e1 = "感谢您使用TITAN NETWORKS"
        com_e2 = "本邮件是发件专用邮件"

    if language == 'ja':
        reg_e1='会員加入認証メールです'
        reg_e2='会員加入が完了しました'
        reg_e3='メール認証確認'
        reg_e31='メール認証確認'
        reg_e5 = "Second Link"
        reg_e6 = "Third Link"
        reg_e4='ここをクリックすると、認証が完了します'
        for_e1='パスワード忘れのメールです'
        for_e2='秘密番号を新たに変更してください'
        for_e3='の下のリンクをクリックして秘密番号を新たに変更してください'
        for_e31='の下のリンクをクリックして秘密番号を新たに変更してください'
        for_e4='ここをクリックすると、暗証番号の再設定が可能です'
        for_e5='Second Link'
        for_e6='Third Link'
        com_e1='TITAN NETWORKSを利用してくださってありがとうございます'
        com_e2='本メールは、発信専用のメールです'

    # 가입
    if template == 1:
        subject = 'TITAN NETWORKS Account Activation Email'
        content = '''
        <div style="width: 600px;
                    border: solid 1px #bbbbbb;
                    text-align: center;
                    border: solid 6px #673AB7;">

          <div style='background-color: #673AB7;
                      text-align: center;
                      color: #ffffff;
                      padding: 15px;'>
            TITAN NETWORKS
          </div>

          <div style="margin-top: 30px;
                      margin-bottom: 10px;
                      font-weight: bold;
                      font-size: 20px;">
            {reg_e1}
          </div>
          <div style="font-size: 14px;
                      margin-bottom: 35px;">
            {reg_e2}
          </div>
          <div style="border-top: solid 1px #bbbbbb;
                      border-bottom: solid 1px #bbbbbb;
                      padding: 20px;
                      font-size: 15px;">
            <div style="font-size: 12px;
                        color: #6f6f6f;">
              {reg_e3}
            </div>
            <div style="margin-top: 5px;">
              <a href='http://{full_url}/api_login_active?active_code={enc_email}'>{reg_e4}</a>
            </div>
          </div>
	  <div style="border-top: solid 1px #bbbbbb;
                      border-bottom: solid 1px #bbbbbb;
                      padding: 20px;
                      font-size: 15px;">
            <div style="font-size: 12px;
                        color: #6f6f6f;">
              {reg_e31}
            </div>
            <div style="margin-top: 5px;">
              <a href='http://{full_url2}/api_login_active?active_code={enc_email}'>{reg_e5}</a>
            </div>
            <div style="margin-top: 5px;">
              <a href='http://{full_url3}/api_login_active?active_code={enc_email}'>{reg_e6}</a>
            </div>
          </div>
          <div style="padding: 35px;
                      font-size: 14px;">
            {com_e1}
          </div>
          <div style="padding: 20px;
                      background: #f5f5f5;
                      font-size: 14px;">
            {com_e2}
          </div>
        </div>
        '''.format(
            full_url=settings.FULL_URL,
            full_url2=settings.FULL_URL2,
            full_url3=settings.FULL_URL3,
            enc_email=enc_email,
            reg_e1=reg_e1,
            reg_e2=reg_e2,
            reg_e3=reg_e3,
            reg_e31=reg_e31,
	    reg_e4=reg_e4,
            reg_e5=reg_e5,
            reg_e6=reg_e6,
            com_e1=com_e1,
            com_e2=com_e2)

    # 비밀번호 찾기
    elif template == 2:
        subject = 'TITAN NETWORKS Forgot Password Email'
        content = '''
        <div style="width: 600px;
                    border: solid 1px #bbbbbb;
                    text-align: center;
                    border: solid 6px #673AB7;">

          <div style='background-color: #673AB7;
                      text-align: center;
                      color: #ffffff;
                      padding: 15px;'>
            TITAN NETWORKS
          </div>

          <div style="margin-top: 30px;
                      margin-bottom: 10px;
                      font-weight: bold;
                      font-size: 20px;">
            {for_e1}
          </div>
          <div style="font-size: 14px;
                      margin-bottom: 35px;">
            {for_e2}
          </div>
          <div style="border-top: solid 1px #bbbbbb;
                      border-bottom: solid 1px #bbbbbb;
                      padding: 20px;
                      font-size: 15px;">
            <div style="font-size: 12px;
                        color: #6f6f6f;">
              {for_e3}
            </div>
            <div style="margin-top: 5px;">
              <a href='http://{full_url}/api_login_fgp?active_code={enc_email}'>{for_e4}</a>
            </div>
          </div>
	  <div style="border-top: solid 1px #bbbbbb;
                      border-bottom: solid 1px #bbbbbb;
                      padding: 20px;
                      font-size: 15px;">
            <div style="font-size: 12px;
                        color: #6f6f6f;">
              {for_e31}
            </div>
            <div style="margin-top: 5px;">
              <a href='http://{full_url2}/api_login_fgp?active_code={enc_email}'>{for_e5}</a>
            </div>
	    <div style="margin-top: 5px;">
              <a href='http://{full_url3}/api_login_fgp?active_code={enc_email}'>{for_e6}</a>
            </div>
	  </div>
          <div style="padding: 35px;
                      font-size: 14px;">
            {com_e1}
          </div>
          <div style="padding: 20px;
                      background: #f5f5f5;
                      font-size: 14px;">
            {com_e2}
          </div>
        </div>
        '''.format(
            full_url=settings.FULL_URL,
            full_url2=settings.FULL_URL2,
            full_url3=settings.FULL_URL3,
            enc_email=enc_email,
            for_e1=for_e1,
            for_e2=for_e2,
            for_e3=for_e3,
            for_e31=for_e31,
            for_e4=for_e4,
            for_e5=for_e5,
            for_e6=for_e6,
            com_e1=com_e1,
            com_e2=com_e2)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = smtp_to

    part = MIMEText(content, 'html')
    msg.attach(part)

    smtp.sendmail(smtp_email, smtp_to, msg.as_string())
    smtp.quit()
