import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "talraniansh2@gmail.com"
SMTP_PASSWORD = "bfvp idnn rdxk dtxu"
SENDER_EMAIL = "talraniansh2@gmail.com"

def send_email(to_recipient: str, subject: str, body: str, attachment_path: str = None, attachment_content: bytes = None, attachment_filename: str = None, cc_recipients: list = None):
    """
    Sends an email using Gmail's SMTP server.

    Args:
        to_recipient: The email address of the recipient.
        subject: The subject of the email.
        body: The HTML or plain text content of the email.
        cc_recipients: List of email addresses to CC.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_recipient
        if cc_recipients:
            msg['Cc'] = ', '.join(cc_recipients)
        msg['Subject'] = subject

        msg.attach(MIMEText(body.replace("\n", "<br>"), 'html'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {os.path.basename(attachment_path)}",
            )
            msg.attach(part)
        elif attachment_content and attachment_filename:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_content)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {attachment_filename}",
            )
            msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, to_recipient, text)
        server.quit()
        print(f"Successfully sent email to {to_recipient}")
        return {"status": "success"}
    except Exception as e:
        print(f"An error occurred while sending email: {e}")
        return None
