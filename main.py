
import argparse
import sys
import os

# Add the project root to the Python path to ensure local modules are found.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db.database import SessionLocal
from rag.conditional_logic import evaluate_po_conditions
from email_integration.email_handler import send_email

def run_poc(po_number: str, question: str, recipient_email: str):
    """
    Runs a single POC test case.

    Args:
        po_number: The PO number to query.
        question: The question to ask the Gemini model.
        recipient_email: The email address to send the final reply to.
    """
    print(f"--- Running POC for {po_number} ---")
    db = SessionLocal()
    try:
        # Evaluate the conditions to get the smart reply content
        decisions = evaluate_po_conditions(db, po_number, question)

        for decision in decisions:
            if decision.get("action") == "send_smart_reply":
                print(f"  - Action: Sending smart reply to {recipient_email}")
                print(f"  - Email Body:\n{decision['details']}")
                subject = f"AI-Powered Response Regarding {po_number}"
                send_email(recipient_email, subject, decision['details'])
            else:
                print(f"  - Received action: {decision.get('action')}. No email sent.")
    finally:
        db.close()
    print("--- POC Run Complete ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a POC test for the Purchasing Bot.")
    parser.add_argument("po_number", type=str, help="The Purchase Order number (e.g., PO-OG-201)")
    parser.add_argument("question", type=str, help="The question to ask about the PO.")
    parser.add_argument("recipient_email", type=str, help="The email address to send the reply to.")

    args = parser.parse_args()

    run_poc(args.po_number, args.question, args.recipient_email)
