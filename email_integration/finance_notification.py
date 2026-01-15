from email_integration.email_handler import send_email
from rag.email_generator import generate_email_content

# --- Configuration ---
FINANCE_EMAIL = "ansh@denicx.com"  # Finance department contact

def send_credit_hold_alert(po_number: str, vendor_name: str, vendor_reply_body: str):
    """
    Sends an alert to the finance department about a PO on credit hold.

    Args:
        po: The PurchaseOrder object from the database.
        vendor_reply_body: The body of the vendor's email explaining the issue.
        original_body: The original body of the email.
    """
    try:
        # 1. Generate email content using the LLM
        email_data = {
            "po_number": po_number,
            "vendor_name": vendor_name,
            "original_body": vendor_reply_body
        }
        email_content = generate_email_content("credit_hold_alert", email_data)

        if not email_content:
            print("Failed to generate email content for credit hold alert.")
            return

        # 2. Send the email
        print(f"Sending credit hold alert for {po_number} to {FINANCE_EMAIL}")
        send_email(
            to_recipient=FINANCE_EMAIL,
            subject=email_content['subject'],
            body=email_content['body']
        )
        print("Successfully sent credit hold alert.")

    except Exception as e:
        print(f"An error occurred while sending the credit hold alert: {e}")
