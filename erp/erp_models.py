from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime
import enum

class PurchaseOrderStatus(enum.Enum):
    ISSUED = "Issued"
    AWAITING_ACKNOWLEDGMENT = "Awaiting Acknowledgment"
    ACKNOWLEDGED = "Acknowledged"
    ON_HOLD = "On Hold"
    PARTIAL_DELIVERY = "Partial Delivery"
    DELIVERED = "Delivered"
    OVERDUE = "Overdue"
    PAYMENT_PENDING = "Payment Pending"
    PAYMENT_HOLD = "Payment Hold"
    CLOSED = "Closed"
    REJECTED = "Rejected"

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    contact_person = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, index=True)
    file_path = Column(String)
    po_number = Column(String, ForeignKey("purchase_orders.po_number"))

    purchase_order = relationship("PurchaseOrder", back_populates="documents")

class PurchaseOrderLineItem(Base):
    __tablename__ = "purchase_order_line_items"

    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"))
    description = Column(String)
    quantity = Column(Integer)
    unit_price = Column(String)  # Using String to accommodate various currency formats

    purchase_order = relationship("PurchaseOrder", back_populates="line_items")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    expected_delivery_date = Column(DateTime)
    status = Column(SQLAlchemyEnum(PurchaseOrderStatus), default=PurchaseOrderStatus.ISSUED)
    original_sender = Column(String)

    supplier = relationship("Supplier")
    documents = relationship("Document", back_populates="purchase_order")
    email_threads = relationship("EmailThread", back_populates="purchase_order")
    history = relationship("PurchaseOrderHistory", back_populates="purchase_order")
    line_items = relationship("PurchaseOrderLineItem", back_populates="purchase_order")

class PurchaseOrderHistory(Base):
    __tablename__ = "purchase_order_history"

    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String)
    details = Column(Text, nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="history")

class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, ForeignKey("purchase_orders.po_number"))
    thread_id = Column(String, unique=True, index=True)
    subject = Column(String)
    last_message_at = Column(DateTime)

    purchase_order = relationship("PurchaseOrder", back_populates="email_threads")
