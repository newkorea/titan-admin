import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SMTP_HOST = 'smtp.titanvpn.io'
SMTP_PORT = 25
SMTP_EMAIL = 'titanvpnsupport@titanvpn.io'
SMTP_ID = 'titanvpnsupport'
SMTP_PW = 'xkdlxks12!@'


def send_email(to_email, template, language):

    smtp_host = SMTP_HOST
    smtp_port = SMTP_PORT
    smtp_email = SMTP_EMAIL
    smtp_id = SMTP_ID
    smtp_pw = SMTP_PW
    smtp_to = to_email

    smtp = smtplib.SMTP(smtp_host)
    smtp.ehlo()      # say Hello
    smtp.starttls()  # TLS 사용시 필요
    smtp.ehlo()
    smtp.login(smtp_id, smtp_pw)

    subject = '20시 16분 테스트'
    content = 'world'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_email
    msg['To'] = smtp_to

    part = MIMEText(content, 'html')
    msg.attach(part)

    smtp.sendmail(smtp_email, smtp_to, msg.as_string())
    smtp.quit()


if __name__ == "__main__":
    send_email('hackx@naver.com', 1, 'ko')
