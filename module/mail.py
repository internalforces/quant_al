"""SMTP 메일 발송 유틸"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


def send_email(
    subject: str,
    body: str,
    sender: str,
    recipient: str,
    smtp_server: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("MB Quant", sender))
    msg["To"] = recipient

    # 587 → STARTTLS, 465 → SSL
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(sender, [recipient], msg.as_string())
    else:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender, [recipient], msg.as_string())