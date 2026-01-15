import sys
import os

# Add the project root to the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from email_integration.email_handler import send_email

if __name__ == "__main__":
    print("Sending a test email to trigger the workflow...")
    send_email(
        to_recipient="atalrani8@gmail.com",
        subject="Final Test Purchase Order: PO-SELF-TEST",
        body="This is a test email sent from the system itself.",
        attachment_path="PO-OG-201.pdf",
        cc_recipients=["talraniansh2@gmail.com"]
    )
    print("Test email sent.")
