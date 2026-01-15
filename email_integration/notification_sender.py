from email_integration.email_handler import send_email, SENDER_EMAIL
import os
from rag.email_generator import generate_email_content
from bucket.po_bucket import append_thread


def send_vendor_po_notification(po_number: str, vendor_email: str, vendor_name: str, expected_delivery_date, line_items, pdf_path: str):
    """
    Sends a new purchase order notification to the vendor.

    Args:
        po: The PurchaseOrder object from the database.
        pdf_path: The file path to the original PO PDF to be attached.
    """
    try:
        # 1. Generate email content using the LLM
        email_data = {
            "po_number": po_number,
            "vendor_name": vendor_name,
            "items_list": "\n".join(
                [f"- {item.get('quantity')} x \"{item.get('description')}\" @ {item.get('unit_price')} each" for item in (line_items or [])]
            ),
            "expected_delivery_date": expected_delivery_date.strftime('%Y-%m-%d') if hasattr(expected_delivery_date, 'strftime') else str(expected_delivery_date or "")
        }
        email_content = generate_email_content("new_po_notification", email_data)

        if not email_content:
            print("Failed to generate email content for new PO notification.")
            return

        # 2. Check if the PDF attachment exists
        if not os.path.exists(pdf_path):
            print(f"Error: Attachment not found at {pdf_path}. Cannot send email.")
            return

        # 3. Send the email with the attachment
        # Do not send emails to placeholder addresses
        if vendor_email.endswith('@example.com'):
            print("--- SKIPPING EMAIL (PLACEHOLDER ADDRESS) ---")
            print(f"Recipient: {vendor_email}")
            print(f"Subject: {email_content['subject']}")
            print(f"Body:\n{email_content['body']}")
            print("------------------------------------------")
        else:
            print(f"Sending new PO notification for {po_number} to {vendor_email}")
            send_email(
                to_recipient=vendor_email,
                subject=email_content['subject'],
                body=email_content['body'],
                attachment_path=pdf_path
            )

        append_thread(
            po_number=po_number,
            direction="outbound",
            from_addr=SENDER_EMAIL,
            to_addr=vendor_email,
            subject=email_content.get("subject", ""),
            body=email_content.get("body", ""),
            labels=["new_po_notification", "to:supplier"],
        )
        print("Successfully sent vendor notification email.")

    except Exception as e:
        print(f"An error occurred while sending the vendor notification: {e}")
