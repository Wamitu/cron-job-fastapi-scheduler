import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uuid import UUID
from dotenv import load_dotenv
from log_config import logger

# Load environment variables
load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise ValueError("EMAIL_USER and EMAIL_PASSWORD must be set.")


def send_email_invite(
    invitee_first_name: str,
    invitee_last_name: str,
    invitee_id: UUID,
    invitee_token: str,
    to_email: str,
    parish_name: str,
):
    """
    Sends an invitation email to a user with a registration link.

    Args:
        invitee_first_name (str): First name of the invitee
        invitee_last_name (str): Last name of the invitee
        invitee_id (UUID): Unique ID of the invitee
        invitee_token (str): Secure token for verifying invite
        to_email (str): Recipient's email address
        parish_name (str): Parish inviting the user

    Returns:
        bool: True if sent successfully, False otherwise
    """
    subject = f"You're Invited to Join {parish_name} on Iparish!"
    invite_link = (
        f"http://iparish.bck.co.ke/register/{invitee_id}?token={invitee_token}"
    )

    text = (
        f"Hi {invitee_first_name} {invitee_last_name},\n\n"
        f"You've been invited to join {parish_name} on Iparish.\n\n"
        f"Click the link below to complete your registration:\n{invite_link}\n\n"
        "This email will expire after 48 hrs.\n\n"
        "If you were not expecting this invitation, you can safely ignore this message.\n\n"
        "Blessings,\nIparish Team"
    )

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: white; border: 1px solid #ddd; border-radius: 10px; padding: 30px;">

        <div style="text-align: center; margin-bottom: 20px;">
            <img src="https://i.pinimg.com/736x/e7/32/9f/e7329f1f4835afb318ebaa887e1d2948.jpg"
                alt="Iparish Logo"
                style="width: 150px; border-radius: 12px;" />
        </div>

        <h2 style="color: #2c3e50; text-align: center;">You're Invited to Join {parish_name} on Iparish!</h2>

        <p>Hi {invitee_first_name} {invitee_last_name},</p>

        <p>You've been invited to join <strong>{parish_name}</strong> on Iparish.</p>

        <p style="text-align: center; margin: 30px 0;">
            <a href="{invite_link}"
            style="background-color: #6a0dad; color: white; padding: 12px 24px; text-decoration: none;
                    border-radius: 5px; font-weight: bold; display: inline-block;">
            Accept Invitation
            </a>
        </p>

        <p>This email will expire in 48 hours.</p>
        <p>If you weren't expecting this invitation, you can safely ignore this message.</p>

        <p style="margin-top: 30px;">Blessings,<br>Iparish Team</p>
        </div>
    </body>
    </html>
    """

    # Construct the message container
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    # Send the email
    try:
        logger.info("Sending invitation email.")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.set_debuglevel(0)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        logger.info("Invitation email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {e.__class__.__name__}")
        return False


def send_success_email(
    to_email: str, first_name: str, last_name: str, parish_name: str
):
    """
    Sends a welcome email after successful registration.

    Args:
        to_email (str): Recipient email
        first_name (str): First name of the new user
        last_name (str): Last name of the new user
        parish_name (str): Parish name they joined

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = f"Registration Successful – Welcome to {parish_name} on Iparish!"

    text = (
        f"Hi {first_name},\n\n"
        f"Your registration to {parish_name} on Iparish is now complete!\n\n"
        "You can now log in to your account and access your parish community.\n\n"
        "Blessings,\nIparish Team\n\n"
        'John 10:16 - "I have other sheep that are not of this sheep pen. I must bring them also. '
        'They too will listen to my voice, and there shall be one flock and one shepherd."'
    )

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #fff; border-radius: 10px; padding: 30px; border: 1px solid #ddd;">

        <!-- Logo -->
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="https://i.pinimg.com/736x/e7/32/9f/e7329f1f4835afb318ebaa887e1d2948.jpg"
                alt="Iparish Logo"
                style="width: 150px; border-radius: 12px;" />
        </div>

        <!-- Heading -->
        <h2 style="color: #2c3e50; text-align: center;">Welcome to {parish_name} on Iparish!</h2>

        <!-- Body -->
        <p>Hi {first_name} {last_name},</p>
        <p>Your registration to <strong>{parish_name}</strong> on Iparish is now complete.</p>
        <p>You can now log in to your account and access your parish community.</p>

        <!-- Button -->
        <div style="text-align: center; margin: 30px 0;">
            <a href="http://iparish.bck.co.ke/login"
            style="background-color: #6a0dad; color: white; padding: 12px 24px; text-decoration: none;
                    border-radius: 5px; font-weight: bold; display: inline-block;">
            Log In Now
            </a>
        </div>

        <!-- Blessings -->
        <p>Blessings,<br />Iparish Team</p>
        </div>
    </body>
    </html>
    """

    # Construct email
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    # Send email
    try:
        logger.info("Sending success confirmation email.")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.set_debuglevel(0)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        logger.info("Success email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Success email sending failed: {e.__class__.__name__}")
        return False
