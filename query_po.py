import sys
import os

# Add the project root to the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from g_sheets import sheets_handler as db

if __name__ == "__main__":
    po_number_to_query = "PO-OG-2026-1060"
    print(f"--- Querying PO Bucket for: {po_number_to_query} ---\n")

    # 1. Get Purchase Order Details
    po = db.get_purchase_order(po_number_to_query)
    if po:
        print("**Purchase Order Details:**")
        print(f"  - PO Number: {po.po_number}")
        print(f"  - Buyer: {po.buyer.name} ({po.buyer.email})")
        print(f"  - Vendor: {po.vendor.name} ({po.vendor.email})")
        print(f"  - Status: {po.status}")
    else:
        print("Could not find Purchase Order details.")

    # 2. Get Conversation History
    print("\n**Conversation History:**")
    history = db.get_conversation_history(po_number_to_query)
    if history:
        print(history)
    else:
        print("No conversation history found.")
