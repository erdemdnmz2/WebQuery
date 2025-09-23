import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
import config

def send_email(subject: str, body: str, to_email: str = config.ADMIN_EMAIL):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = config.SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        text = MIMEText(body, "plain", 'utf-8')
        msg.attach(text)

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            if config.SMTP_TLS:
                server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        return False
        