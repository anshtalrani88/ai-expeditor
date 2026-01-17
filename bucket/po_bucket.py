import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import gspread

from g_sheets.sheets_handler import (
    setup_spreadsheet,
    get_purchase_order as sheets_get_po,
    update_po_status as sheets_update_status,
    update_po_flag,
    get_sheets_client,
    SHEET_NAME,
    _with_backoff,
)

THREADS_SHEET_NAME = "Threads"

_THREADS_CACHE_ROWS: Optional[List[List[str]]] = None
_THREADS_CACHE_TS: Optional[datetime] = None
_THREADS_CACHE_TTL_SECONDS = 120.0

_THREADS_WS_CACHE: Optional[gspread.Worksheet] = None
_THREADS_WS_CACHE_TS: Optional[datetime] = None
_THREADS_WS_CACHE_TTL_SECONDS = 120.0


def _ensure_threads_ws(client: gspread.Client) -> gspread.Worksheet:
    global _THREADS_WS_CACHE
    global _THREADS_WS_CACHE_TS

    now = datetime.now(timezone.utc)
    if _THREADS_WS_CACHE is not None and _THREADS_WS_CACHE_TS is not None:
        age = (now - _THREADS_WS_CACHE_TS).total_seconds()
        if age <= _THREADS_WS_CACHE_TTL_SECONDS:
            return _THREADS_WS_CACHE

    sheet = _with_backoff(client.open, SHEET_NAME)
    try:
        ws = _with_backoff(sheet.worksheet, THREADS_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = _with_backoff(sheet.add_worksheet, title=THREADS_SHEET_NAME, rows="200", cols="10")
        header = [
            "PO Number",
            "Timestamp",
            "Direction",
            "From",
            "To",
            "Subject",
            "Body",
            "Labels",
            "Message-ID",
        ]
        _with_backoff(ws.append_row, header)

    _THREADS_WS_CACHE = ws
    _THREADS_WS_CACHE_TS = now
    return ws


def _get_threads_rows_cached(ws: gspread.Worksheet) -> List[List[str]]:
    global _THREADS_CACHE_ROWS
    global _THREADS_CACHE_TS

    now = datetime.now(timezone.utc)
    if _THREADS_CACHE_ROWS is not None and _THREADS_CACHE_TS is not None:
        age = (now - _THREADS_CACHE_TS).total_seconds()
        if age <= _THREADS_CACHE_TTL_SECONDS:
            return _THREADS_CACHE_ROWS

    rows = _with_backoff(ws.get_all_values)
    _THREADS_CACHE_ROWS = rows
    _THREADS_CACHE_TS = now
    return rows


def _load_threads(po_number: str) -> List[Dict[str, Any]]:
    client = None
    try:
        client = setup_spreadsheet()[0]
    except Exception:
        client = None
    if not client:
        client = get_sheets_client()
    if not client:
        return []
    ws = _ensure_threads_ws(client)
    rows = _get_threads_rows_cached(ws)
    results: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if len(row) == 0:
            continue
        if row[0] == po_number:
            results.append({
                "po_number": row[0],
                "timestamp": row[1],
                "direction": row[2],
                "from": row[3],
                "to": row[4],
                "subject": row[5],
                "body": row[6],
                "labels": row[7].split(",") if len(row) > 7 and row[7] else [],
                "message_id": row[8] if len(row) > 8 else None,
            })
    return results


def append_thread(po_number: str, direction: str, from_addr: str, to_addr: str,
                  subject: str, body: str, labels: Optional[List[str]] = None, message_id: Optional[str] = None) -> None:
    global _THREADS_CACHE_ROWS
    global _THREADS_CACHE_TS
    global _THREADS_WS_CACHE
    global _THREADS_WS_CACHE_TS

    client = None
    try:
        client = setup_spreadsheet()[0]
    except Exception:
        client = None
    if not client:
        client = get_sheets_client()
    if not client:
        return
    ws = _ensure_threads_ws(client)
    ts = datetime.now(timezone.utc).isoformat()
    trimmed_body = (body or "")
    if len(trimmed_body) > 500:
        trimmed_body = trimmed_body[:500] + "..."
    _with_backoff(ws.append_row, [
        po_number,
        ts,
        direction,
        from_addr,
        to_addr,
        subject or "",
        trimmed_body,
        ",".join(labels or []),
        message_id or "",
    ])

    _THREADS_CACHE_ROWS = None
    _THREADS_CACHE_TS = None
    _THREADS_WS_CACHE = None
    _THREADS_WS_CACHE_TS = None


def get_po_state(po_number: str) -> Optional[Dict[str, Any]]:
    po = sheets_get_po(po_number)
    if not po:
        return None
    supplier_name = getattr(po.vendor, "name", None) if po.vendor else None
    supplier_email = getattr(po.vendor, "email", None) if po.vendor else None
    buyer_name = getattr(po.buyer, "name", None) if po.buyer else None
    buyer_email = getattr(po.buyer, "email", None) if po.buyer else None
    state = {
        "po_number": po.po_number,
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "supplier_name": supplier_name,
        "supplier_email": supplier_email,
        "order_date": po.order_date,
        "expected_delivery_date": po.expected_delivery_date,
        "accepted_delivery_date": getattr(po, "accepted_delivery_date", None),
        "remaining_delivery_date": getattr(po, "remaining_delivery_date", None),
        "status": po.status,
        "line_items": po.line_items,
        "original_sender": po.original_sender,
        "threads": _load_threads(po.po_number),
        "mtc_needed": po.mtc_needed,
        "mtc_received": po.mtc_received,
        "payment_hold": po.payment_hold,
        "needs_info": po.needs_info,
        "awaiting_acknowledgment": po.awaiting_acknowledgment,
        "overdue": po.overdue,
        "partial_availability": po.partial_availability,
        "clarification_requested": po.clarification_requested,
        "mtc_pending": po.mtc_pending,
    }
    return state


def update_status(po_number: str, new_status: str) -> None:
    sheets_update_status(po_number, new_status)

def set_flag(po_number: str, flag_name: str, value: bool) -> None:
    update_po_flag(po_number, flag_name, value)


def compute_flags(state: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    delivery_date_past = False
    delivery_date_missing = False
    if isinstance(state.get("expected_delivery_date"), datetime):
        delivery_date_past = state["expected_delivery_date"].date() < now.date()
    else:
        delivery_date_missing = True

    hours_since_order = None
    if isinstance(state.get("order_date"), datetime):
        delta = now - state["order_date"].replace(tzinfo=timezone.utc)
        hours_since_order = delta.total_seconds() / 3600.0

    supplier_silent_over_seconds = None
    last_outbound_to_supplier_is_no_response_followup = False
    threads = state.get("threads") or []
    supplier_email = (state.get("supplier_email") or "").strip().lower()

    first_outbound_to_supplier_ts = None
    last_inbound_from_supplier_ts = None
    has_sent_no_response_followup = False

    def _parse_ts(ts: Any) -> Optional[datetime]:
        if not ts or not isinstance(ts, str):
            return None
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    for msg in threads:
        ts = _parse_ts(msg.get("timestamp"))
        if not ts:
            continue
        direction = (msg.get("direction") or "").lower()
        from_addr = (msg.get("from") or "").strip().lower()
        to_addr = (msg.get("to") or "").strip().lower()
        labels = msg.get("labels") or []

        if supplier_email and direction == "outbound" and to_addr == supplier_email:
            if first_outbound_to_supplier_ts is None or ts < first_outbound_to_supplier_ts:
                first_outbound_to_supplier_ts = ts

            if any((l or "").strip().lower() == "vendor_no_response_followup" for l in labels):
                has_sent_no_response_followup = True

        if supplier_email and direction == "inbound" and from_addr == supplier_email:
            if last_inbound_from_supplier_ts is None or ts > last_inbound_from_supplier_ts:
                last_inbound_from_supplier_ts = ts

    if first_outbound_to_supplier_ts is not None:
        # Make this sticky: once we have sent the no-response followup once, never trigger it again,
        # regardless of other outbound emails.
        last_outbound_to_supplier_is_no_response_followup = has_sent_no_response_followup

        # Start the timer from the FIRST outbound to supplier (PO creation / initial notification).
        # Do NOT reset it on subsequent outbound messages.
        if last_inbound_from_supplier_ts is None or last_inbound_from_supplier_ts < first_outbound_to_supplier_ts:
            supplier_silent_over_seconds = (now - first_outbound_to_supplier_ts).total_seconds()
        else:
            supplier_silent_over_seconds = 0.0

    return {
        "delivery_date_past": delivery_date_past,
        "delivery_date_missing": delivery_date_missing,
        "hours_since_order": hours_since_order,
        "supplier_silent_over_seconds": supplier_silent_over_seconds,
        "last_outbound_to_supplier_is_no_response_followup": last_outbound_to_supplier_is_no_response_followup,
    }
