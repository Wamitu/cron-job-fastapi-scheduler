import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(recipient: str, subject: str, message: str) -> None:
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")

    if not email_user or not email_password:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD environment variables must be set")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = recipient
    msg.attach(MIMEText(message, "plain"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(email_user, email_password)
        server.sendmail(email_user, recipient, msg.as_string())
