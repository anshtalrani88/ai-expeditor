import requests
import base64
import time

WEBHOOK_URL = "http://localhost:8000/webhook/email"
PO_PDF_PATH = "PO-OG-201.pdf"

def send_request_with_retry(payload, max_retries=5, delay=3):
    for i in range(max_retries):
        try:
            response = requests.post(WEBHOOK_URL, json=payload)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Attempt {i+1} failed: {e}")
            if i < max_retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Test failed.")
                return None

def run_test():
    # Test Case 1: New Purchase Order
    print("--- Test Case 1: New Purchase Order ---")
    with open(PO_PDF_PATH, "rb") as f:
        pdf_content = base64.b64encode(f.read()).decode()

    new_po_payload = {
        "from": "buyer@denicx.com",
        "subject": "New Purchase Order PO-OG-201",
        "body": "Please find the attached PO.",
        "attachments": [{
            "filename": "PO-OG-201.pdf",
            "content": pdf_content
        }]
    }

    response = send_request_with_retry(new_po_payload)
    if response:
        print("New PO email sent to webhook.")
        print("Response:", response.json())

    # Wait for the system to process
    print("\nWaiting for system to process PO...")
    time.sleep(5)

    # Test Case 2: Vendor Reply (Credit Hold)
    print("\n--- Test Case 2: Vendor Reply (Credit Hold) ---")
    credit_hold_payload = {
        "from": "vendor@acme.com",
        "subject": "Re: Your PO-OG-201 is on credit hold",
        "body": "This order is on credit hold until payment is received."
    }

    response = send_request_with_retry(credit_hold_payload)
    if response:
        print("Credit hold reply sent to webhook.")
        print("Response:", response.json())

if __name__ == "__main__":
    run_test()
