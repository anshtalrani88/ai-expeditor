import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

def send_threaded_email(to_recipient, subject, body, original_message_id=None, references=None):
    """
    Sends an email as a reply to an existing thread.
    """
    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL]):
        print("Email sending is not configured. Please provide SMTP credentials in .env file.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_recipient
    msg['Subject'] = subject

    if original_message_id:
        msg['In-Reply-To'] = original_message_id
        if references:
            msg['References'] = f"{references} {original_message_id}"
        else:
            msg['References'] = original_message_id

    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Threaded email sent to {to_recipient}")
    except Exception as e:
        print(f"Failed to send threaded email: {e}")
