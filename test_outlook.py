import requests
import json
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://localhost:8000"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/technical-query-webhook"

TEST_PO_NUMBER = "PO-TEST-101"

def run_test():
    print("--- Starting Outlook Connection Test ---")

    # 1. Create a test Purchase Order
    try:
        print(f"Creating test purchase order: {TEST_PO_NUMBER}")
        po_payload = {
            "po_number": TEST_PO_NUMBER,
            "supplier_id": 1, # Assuming a supplier with ID 1 exists
            "expected_delivery_date": (datetime.utcnow() + timedelta(days=10)).isoformat()
        }
        response = requests.post(f"{API_BASE_URL}/purchase_orders/", json=po_payload)
        response.raise_for_status()
        print(f"Successfully created PO: {response.json()['po_number']}")
    except requests.exceptions.RequestException as e:
        print(f"Error creating PO: {e}")
        # Attempt to delete if it exists from a previous failed run
        if e.response and e.response.status_code == 400: # Bad request, likely exists
            print("PO might already exist from a previous run. Proceeding...")
        else:
            return

    # 2. Trigger the n8n workflow with a simulated technical query
    try:
        print("Triggering n8n workflow with a simulated technical email...")
        webhook_payload = {
            "po_number": TEST_PO_NUMBER,
            "email_body": "Hello, we have a question about the technical datasheet for this order."
        }
        response = requests.post(N8N_WEBHOOK_URL, json=webhook_payload)
        response.raise_for_status()
        print("Webhook sent successfully. n8n should now be processing the request.")
        print("Please check the n8n UI for the execution status of the 'Technical Query Forwarder' workflow.")
        print("If successful, an email should be forwarded to engineer@example.com.")

    except requests.exceptions.RequestException as e:
        print(f"Error triggering webhook: {e}")

    print("--- Test Complete ---")

if __name__ == "__main__":
    run_test()
