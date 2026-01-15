from sqlalchemy.orm import Session
from erp import erp_models, schemas

def delete_purchase_order_by_number(db: Session, po_number: str):
    """
    Deletes a purchase order and all of its line items.
    """
    db_po = get_purchase_order(db, po_number)
    if db_po:
        # Delete associated line items first to maintain foreign key constraints
        db.query(erp_models.PurchaseOrderLineItem).filter(erp_models.PurchaseOrderLineItem.po_id == db_po.id).delete()
        db.delete(db_po)
        db.commit()
        print(f"Deleted existing PO: {po_number}")
        return True
    return False

def get_purchase_order(db: Session, po_number: str):
    return db.query(erp_models.PurchaseOrder).filter(erp_models.PurchaseOrder.po_number == po_number).first()

def get_purchase_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(erp_models.PurchaseOrder).offset(skip).limit(limit).all()

def create_purchase_order_with_items(db: Session, po: schemas.PurchaseOrderCreate, items: list[schemas.PurchaseOrderLineItemCreate]):
    # Create the main PO object
    db_po = erp_models.PurchaseOrder(
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        expected_delivery_date=po.expected_delivery_date,
        original_sender=po.original_sender
    )
    db.add(db_po)
    db.flush()  # Use flush to get the db_po.id before committing

    # Create the line item objects
    for item in items:
        db_item = erp_models.PurchaseOrderLineItem(**item.dict(), po_id=db_po.id)
        db.add(db_item)

    db.commit()
    db.refresh(db_po)
    
    # Add initial history event
    add_history_to_po(db, po_id=db_po.id, action="PO Created", details=f"PO {db_po.po_number} created from PDF and issued to supplier.")
    return db_po

def create_purchase_order(db: Session, po: schemas.PurchaseOrderCreate):
    db_po = erp_models.PurchaseOrder(
        po_number=po.po_number, 
        supplier_id=po.supplier_id,
        expected_delivery_date=po.expected_delivery_date
    )
    db.add(db_po)
    db.commit()
    db.refresh(db_po)
    # Add initial history event
    add_history_to_po(db, po_id=db_po.id, action="PO Created", details=f"PO {db_po.po_number} created and issued to supplier.")
    return db_po

def add_document_to_po(db: Session, doc: schemas.DocumentCreate, po_number: str):
    po = get_purchase_order(db, po_number)
    if not po:
        return None
    db_doc = erp_models.Document(**doc.dict(), po_number=po_number)
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    add_history_to_po(db, po_id=po.id, action="Document Added", details=f"Document {db_doc.file_name} added.")
    return db_doc

def update_po_status(db: Session, po_number: str, status: schemas.PurchaseOrderStatus):
    """
    Updates the status of a purchase order and adds a history event.
    """
    db_po = get_purchase_order(db, po_number)
    if db_po:
        db_po.status = status
        db.commit()
        db.refresh(db_po)
        add_history_to_po(db, po_id=db_po.id, action=f"Status Updated to {status.value}")
        print(f"Updated status for {po_number} to {status.value}")
        return db_po
    return None

def add_history_to_po(db: Session, po_id: int, action: str, details: str = None):
    db_history = erp_models.PurchaseOrderHistory(po_id=po_id, action=action, details=details)
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

def get_supplier_by_name(db: Session, name: str):
    return db.query(erp_models.Supplier).filter(erp_models.Supplier.name == name).first()

def create_supplier(db: Session, supplier: schemas.SupplierCreate):
    db_supplier = erp_models.Supplier(**supplier.dict())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier
