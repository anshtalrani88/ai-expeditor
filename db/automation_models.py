from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.automation_database import Base


class Entity(Base):
    __tablename__ = "automation_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # Buyer | Vendor | Supplier | Internal


class PurchaseOrder(Base):
    __tablename__ = "automation_purchase_orders"

    po_number: Mapped[str] = mapped_column(String, primary_key=True)

    buyer_name: Mapped[str] = mapped_column(String, nullable=True)
    buyer_email: Mapped[str] = mapped_column(String, index=True, nullable=True)

    vendor_name: Mapped[str] = mapped_column(String, nullable=True)
    vendor_email: Mapped[str] = mapped_column(String, index=True, nullable=True)

    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String, default="ISSUED")

    line_items_json: Mapped[str] = mapped_column(Text, default="[]")
    original_sender: Mapped[str] = mapped_column(String, nullable=True)


class ThreadMessage(Base):
    __tablename__ = "automation_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String, index=True, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # inbound | outbound

    from_addr: Mapped[str] = mapped_column(String, nullable=False)
    to_addr: Mapped[str] = mapped_column(String, nullable=False)

    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")

    labels_csv: Mapped[str] = mapped_column(Text, default="")
