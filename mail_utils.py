# mail_utils.py
import smtplib
from email.message import EmailMessage
from config import MAIL_USER, MAIL_PASS

def send_email(to_email: str, subject: str, body: str):
    if not MAIL_USER or not MAIL_PASS:
        raise RuntimeError("Mail credentials not configured in environment")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_USER
    msg["To"] = to_email
    msg.set_content(body)

    # Gmail SMTP
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.login(MAIL_USER, MAIL_PASS)
        s.send_message(msg)
