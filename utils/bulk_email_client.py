from typing import List, Dict
from fastapi import FastAPI, HTTPException, APIRouter
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from log_config import logger
from pydantic import BaseModel

router = APIRouter()

# Load environment variables
load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("EMAIL_USER and EMAIL_PASSWORD must be set.")


class Invitee(BaseModel):
    first_name: str
    last_name: str
    token: str
    email: str
    parish_name: str


def send_bulk_invites(invitees: List[Invitee]):
    """Send bulk invitation emails in a single SMTP session."""
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        for invitee in invitees:
            msg = MIMEMultipart("alternative")
            subject = f"You're Invited to Join {invitee.parish_name} on Iparish!"
            invite_link = (
                f"http://iparish.bck.co.ke/register/{invitee.id}?token={invitee.token}"
            )

            text = (
                f"Hi {invitee.first_name} {invitee.last_name},\n\n"
                f"You've been invited to join {invitee.parish_name} on Iparish.\n\n"
                f"Click the link below to complete your registration:\n{invite_link}\n\n"
                "This email will expire after 48 hrs.\n\n"
                "If you were not expecting this invitation, you can safely ignore this message.\n\n"
                "Blessings,\nIparish Team"
            )

            html = f"""
            <html>
            <body>
                <h2>You're Invited to Join {invitee.parish_name} on Iparish!</h2>
                <p>Hi {invitee.first_name} {invitee.last_name},</p>
                <p>You've been invited to join <strong>{invitee.parish_name}</strong> on Iparish.</p>
                <p><a href="{invite_link}">Accept Invitation</a></p>
                <p>This email will expire in 48 hours.</p>
            </body>
            </html>
            """

            msg["From"] = EMAIL_USER
            msg["To"] = invitee.email
            msg["Subject"] = subject
            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))

            try:
                server.sendmail(EMAIL_USER, invitee.email, msg.as_string())
                logger.info(f"Invitation sent to {invitee.email}")
            except Exception as e:
                logger.error(
                    f"Failed to send to {invitee.email}: {e.__class__.__name__}"
                )

        server.quit()
    except Exception as e:
        logger.error(f"Bulk email session failed: {e.__class__.__name__}")
