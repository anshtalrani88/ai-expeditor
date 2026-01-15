from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from erp.erp_models import PurchaseOrderStatus

class DocumentBase(BaseModel):
    file_name: str
    file_path: str

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: int
    po_number: str

    class Config:
        orm_mode = True

class PurchaseOrderHistoryBase(BaseModel):
    action: str
    details: Optional[str] = None

class PurchaseOrderHistoryCreate(PurchaseOrderHistoryBase):
    pass

class PurchaseOrderHistory(PurchaseOrderHistoryBase):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class PurchaseOrderBase(BaseModel):
    po_number: str
    supplier_id: int
    expected_delivery_date: datetime
    original_sender: str

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrder(PurchaseOrderBase):
    id: int
    created_at: datetime
    status: PurchaseOrderStatus
    documents: List[Document] = []
    history: List[PurchaseOrderHistory] = []
    line_items: List['PurchaseOrderLineItem'] = []
    original_sender: str

    class Config:
        orm_mode = True

class PurchaseOrderLineItemBase(BaseModel):
    description: str
    quantity: int
    unit_price: str

class PurchaseOrderLineItemCreate(PurchaseOrderLineItemBase):
    pass

class PurchaseOrderLineItem(PurchaseOrderLineItemBase):
    id: int
    po_id: int

    class Config:
        orm_mode = True

class SupplierBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: str

class SupplierCreate(SupplierBase):
    pass

class Supplier(SupplierBase):
    id: int

    class Config:
        orm_mode = True
