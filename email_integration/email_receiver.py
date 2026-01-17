import imaplib
import email
from email.header import decode_header
import os

# --- Credentials to be provided by the user ---
IMAP_SERVER = "imap.gmail.com"
IMAP_USERNAME = "talraniansh2@gmail.com"
IMAP_PASSWORD = "bfvp idnn rdxk dtxu"

ATTACHMENT_DIR = os.path.join(os.path.dirname(__file__), '..', 'attachments')

import re

def fetch_and_process_emails():
    """
    Connects to the IMAP server, fetches new emails, extracts their content,
    and returns a unified list of email data dictionaries.
    """
    if not all([IMAP_SERVER, IMAP_USERNAME, IMAP_PASSWORD]):
        print("Email receiving is not configured. Please provide IMAP credentials.")
        return []

    all_emails_data = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USERNAME, IMAP_PASSWORD)
        mail.select('inbox')
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK' or not messages[0]:
            return []

        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} new emails.")

        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK': continue

            msg = email.message_from_bytes(msg_data[0][1])
            subject_header = decode_header(msg["Subject"])[0]
            subject = subject_header[0].decode(subject_header[1] or 'utf-8') if isinstance(subject_header[0], bytes) else subject_header[0]

            email_data = {
                "from": email.utils.parseaddr(msg.get("From"))[1],
                "to": email.utils.parseaddr(msg.get("To"))[1],
                "subject": subject,
                "date": email.utils.parsedate_to_datetime(msg.get("Date")),
                "message_id": msg.get("Message-ID"),
                "in_reply_to": msg.get("In-Reply-To"),
                "references": msg.get("References"),
                "body": "",
                "pdf_path": None
            }

            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                    email_data["body"] = part.get_payload(decode=True).decode(errors='ignore')
                elif "attachment" in str(part.get("Content-Disposition")):
                    filename = part.get_filename()
                    if filename and filename.lower().endswith('.pdf'):
                        filepath = os.path.join(ATTACHMENT_DIR, filename)
                        if not os.path.exists(ATTACHMENT_DIR): os.makedirs(ATTACHMENT_DIR)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        email_data["pdf_path"] = filepath
            
            all_emails_data.append(email_data)
            mail.store(email_id, '+FLAGS', '\\Seen')

    except Exception as e:
        print(f"An error occurred while fetching emails: {e}")
    finally:
        if mail and mail.state == 'SELECTED':
            mail.close()
            mail.logout()
    
    return all_emails_data

if __name__ == '__main__':
    # This allows for direct testing of the email fetching logic
    fetch_and_process_emails()
