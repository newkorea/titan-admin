import smtplib
#from email.MIMEMultipart import MIMEMultipart
#from email.mime.multipart import MIMEMultipart
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email import encoders
import os

def sendMail(to, fro, subject, text, files=[],server="smtp.titanvpn.io"):
    msg = MIMEMultipart()
    msg['From'] = fro
    msg['To'] = COMMASPACE.join(to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach( MIMEText(text) )

    for file in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(file,"rb").read() )
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"'
                       % os.path.basename(file))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo
    smtp.login('titanvpnsupport','xkdlxks12!@')
    smtp.sendmail(fro, to, msg.as_string() )
    smtp.close()

# Example:
sendMail('hackx@naver.com','titanvpnsupport@titanvpn.io','Hello Python!','Heya buddy! Say hello to Python! :)')
