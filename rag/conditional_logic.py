import os
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from erp import crud, erp_models
from rag.huggingface_handler import get_huggingface_response
from rag.file_processor import process_file

# Scenario 1: No PO Acknowledgment
def check_po_acknowledgment(db: Session, po: erp_models.PurchaseOrder):
    ack_events = [h for h in po.history if h.action == "PO Acknowledged"]
    if not ack_events and (datetime.utcnow() > po.created_at + timedelta(hours=24)):
        return {"action": "send_reminder", "details": "PO acknowledgment is overdue."}
    return None

# Scenario 3: Lapsed Delivery Date
def check_lapsed_delivery(db: Session, po: erp_models.PurchaseOrder):
    if datetime.utcnow().date() > po.expected_delivery_date.date() and po.status != erp_models.PurchaseOrderStatus.DELIVERED:
        return {"action": "send_inquiry", "details": "Delivery date has passed."}
    return None

# POC Scenario: Smart Inquiry (Combines Hugging Face LLM and ERP)
def handle_smart_inquiry(db: Session, po: erp_models.PurchaseOrder, email_text: str):
    """
    Handles a supplier inquiry by querying the OpenAI model with the PO PDF content
    and checking the ERP for status, then formats a consolidated reply.
    """
    # 1. Get the text content of the PO PDF
    pdf_path = os.path.join(os.path.dirname(__file__), '..', f"{po.po_number}.pdf")
    if not os.path.exists(pdf_path):
        return {"action": "error", "details": f"Could not find PDF for {po.po_number}"}
    
    document_text = process_file(pdf_path)

    # 2. Query Hugging Face for an intelligent answer
    huggingface_answer = get_huggingface_response(document_text, email_text)

    # 3. Get ERP status
    erp_status = po.status.value

    # 4. Format the consolidated reply
    reply_body = f"""Hello,

Thank you for your inquiry regarding **{po.po_number}**.

Our AI assistant has analyzed your question based on the official PO document and provides the following information:
**{huggingface_answer}**

For your reference, our ERP database shows the current status for this PO is: **{erp_status}**.

Best regards,
Purchasing Automation Bot"""

    return {"action": "send_smart_reply", "details": reply_body, "recipient": po.supplier.email}


# Orchestrator function to evaluate all conditions for a given PO
def evaluate_po_conditions(db: Session, po_number: str, email_content: str = None):
    po = crud.get_purchase_order(db, po_number)
    if not po:
        return []

    decisions = []

    # If email content is present, prioritize the Smart Inquiry for the POC
    if email_content:
        decision = handle_smart_inquiry(db, po, email_content)
        if decision: decisions.append(decision)
        return decisions # Return immediately to ensure only this action is triggered for the POC

    # Original Time-based checks (will not run if there's email content)
    decision = check_po_acknowledgment(db, po)
    if decision: decisions.append(decision)

    decision = check_lapsed_delivery(db, po)
    if decision: decisions.append(decision)

    return decisions
