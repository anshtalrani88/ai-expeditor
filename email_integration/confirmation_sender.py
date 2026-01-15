from email_integration.email_handler import send_email

def send_final_confirmation(po_number: str, vendor_name: str, original_sender: str):
    """
    Sends a final confirmation email to the original sender after vendor acknowledgment.

    Args:
        po: The PurchaseOrder object from the database.
        original_sender: The email address of the person who sent the initial PO.
    """
    try:
        # Format the email subject and body
        subject = f"Confirmation: Purchase Order {po_number} has been Acknowledged"

        body = f"""Hello,

        This is a confirmation that your Purchase Order **{po_number}** has been successfully received and acknowledged by the vendor, **{vendor_name}**.

        The PO status has been updated to 'Acknowledged' in our system.

        No further action is required from you at this time.

        Best regards,
        Denicx Automation
        """

        # Send the email
        print(f"Sending final confirmation for {po_number} to {original_sender}")
        send_email(
            to_recipient=original_sender,
            subject=subject,
            body=body
        )
        print("Successfully sent final confirmation email.")

    except Exception as e:
        print(f"An error occurred while sending the final confirmation: {e}")
