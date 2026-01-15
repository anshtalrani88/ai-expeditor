from sqlalchemy.orm import Session
from rag.conditional_logic import evaluate_po_conditions
from erp import crud

def run_po_evaluation(db: Session, po_number: str):
    """
    Orchestrates the evaluation of a purchase order against all defined scenarios.
    Logs the decisions and returns a list of actions to be taken.
    """
    po = crud.get_purchase_order(db, po_number)
    if not po:
        return {"error": "Purchase Order not found"}

    # Evaluate all conditions for the PO
    decisions = evaluate_po_conditions(db, po_number)

    if not decisions:
        return {"po_number": po_number, "status": "No actions required."}

    # Log the decisions as history events
    for decision in decisions:
        crud.add_history_to_po(
            db,
            po_id=po.id,
            action=f"Decision: {decision['action']}",
            details=decision['details']
        )

    # The list of decisions is returned, which will be used by n8n to execute actions
    return {"po_number": po_number, "actions_triggered": decisions}
