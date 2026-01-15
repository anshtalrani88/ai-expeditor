import os
import json
from datetime import datetime
import time
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, 'credentials.json')
TOKEN_FILE = os.path.join(PROJECT_ROOT, 'token.json')
SHEET_NAME = "PO Automation Database"
PO_SHEET_NAME = "PurchaseOrders"
ENTITIES_SHEET_NAME = "Entities"
HISTORY_SHEET_NAME = "ConversationHistory"

_SETUP_CACHE = None
_SETUP_CACHE_TS = None
_SETUP_CACHE_TTL_SECONDS = 60.0

_PO_ROWS_CACHE = None
_PO_ROWS_CACHE_TS = None
_PO_ROWS_CACHE_TTL_SECONDS = 30.0

_ENTITIES_ROWS_CACHE = None
_ENTITIES_ROWS_CACHE_TS = None
_ENTITIES_ROWS_CACHE_TTL_SECONDS = 30.0


def _invalidate_caches() -> None:
    global _SETUP_CACHE
    global _SETUP_CACHE_TS
    global _PO_ROWS_CACHE
    global _PO_ROWS_CACHE_TS
    global _ENTITIES_ROWS_CACHE
    global _ENTITIES_ROWS_CACHE_TS

    _SETUP_CACHE = None
    _SETUP_CACHE_TS = None
    _PO_ROWS_CACHE = None
    _PO_ROWS_CACHE_TS = None
    _ENTITIES_ROWS_CACHE = None
    _ENTITIES_ROWS_CACHE_TS = None

# --- Client Initialization & Sheet Setup ---
def get_sheets_client():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except FileNotFoundError:
                print(f"ERROR: credentials.json not found at {CREDENTIALS_FILE}")
                return None
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return gspread.authorize(creds)

def setup_spreadsheet():
    global _SETUP_CACHE
    global _SETUP_CACHE_TS

    now_ts = time.time()
    if _SETUP_CACHE is not None and _SETUP_CACHE_TS is not None:
        if (now_ts - _SETUP_CACHE_TS) <= _SETUP_CACHE_TTL_SECONDS:
            return _SETUP_CACHE

    client = get_sheets_client()
    if not client:
        return None, None, None, None
    try:
        try:
            sheet = _with_backoff(client.open, SHEET_NAME)
        except gspread.exceptions.SpreadsheetNotFound:
            sheet = _with_backoff(client.create, SHEET_NAME)
            _with_backoff(sheet.share, 'sj349279@gmail.com', perm_type='user', role='writer')
    except Exception as e:
        print(f"WARNING: setup_spreadsheet failed: {e}")
        return None, None, None, None

    def _get_or_create_worksheet(sheet, name, header):
        try:
            ws = _with_backoff(sheet.worksheet, name)
        except gspread.exceptions.WorksheetNotFound:
            ws = _with_backoff(sheet.add_worksheet, title=name, rows="100", cols="20")
            _with_backoff(ws.append_row, header)
        return ws

    po_ws = _get_or_create_worksheet(sheet, PO_SHEET_NAME, ['PO Number', 'Buyer', 'Vendor', 'Order Date', 'Expected Delivery', 'Status', 'Line Items', 'Buyer Email', 'Vendor Email', 'Original Sender'])
    entities_ws = _get_or_create_worksheet(sheet, ENTITIES_SHEET_NAME, ['Entity Name', 'Email', 'Role'])
    history_ws = _get_or_create_worksheet(sheet, HISTORY_SHEET_NAME, ['PO Number', 'Timestamp', 'From', 'Subject', 'Body'])

    _SETUP_CACHE = (client, po_ws, entities_ws, history_ws)
    _SETUP_CACHE_TS = now_ts
    return _SETUP_CACHE


def _with_backoff(fn, *args, **kwargs):
    delay = 1.0
    for _ in range(7):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            msg = str(e)
            retriable = (
                ("429" in msg)
                or ("Quota exceeded" in msg)
                or ("500" in msg)
                or ("502" in msg)
                or ("503" in msg)
                or ("504" in msg)
                or ("service is currently unavailable" in msg.lower())
            )
            if retriable:
                time.sleep(delay)
                delay = min(delay * 2.0, 60.0)
                continue
            raise
    return fn(*args, **kwargs)


def _get_po_rows_cached(po_ws) -> list[list[str]]:
    global _PO_ROWS_CACHE
    global _PO_ROWS_CACHE_TS
    now_ts = time.time()
    if _PO_ROWS_CACHE is not None and _PO_ROWS_CACHE_TS is not None:
        if (now_ts - _PO_ROWS_CACHE_TS) <= _PO_ROWS_CACHE_TTL_SECONDS:
            return _PO_ROWS_CACHE
    rows = _with_backoff(po_ws.get_all_values)
    _PO_ROWS_CACHE = rows
    _PO_ROWS_CACHE_TS = now_ts
    return rows


def _get_entities_rows_cached(entities_ws) -> list[list[str]]:
    global _ENTITIES_ROWS_CACHE
    global _ENTITIES_ROWS_CACHE_TS
    now_ts = time.time()
    if _ENTITIES_ROWS_CACHE is not None and _ENTITIES_ROWS_CACHE_TS is not None:
        if (now_ts - _ENTITIES_ROWS_CACHE_TS) <= _ENTITIES_ROWS_CACHE_TTL_SECONDS:
            return _ENTITIES_ROWS_CACHE
    rows = _with_backoff(entities_ws.get_all_values)
    _ENTITIES_ROWS_CACHE = rows
    _ENTITIES_ROWS_CACHE_TS = now_ts
    return rows

# --- Data Classes ---
class PurchaseOrder:
    def __init__(self, po_number, buyer, vendor, status, **kwargs):
        self.po_number = po_number
        self.buyer = buyer
        self.vendor = vendor
        self.status = status
        # store additional optional fields if provided
        self.order_date = kwargs.get('order_date')
        self.expected_delivery_date = kwargs.get('expected_delivery_date')
        self.accepted_delivery_date = kwargs.get('accepted_delivery_date')
        self.remaining_delivery_date = kwargs.get('remaining_delivery_date')
        self.line_items = kwargs.get('line_items', [])
        self.original_sender = kwargs.get('original_sender')

class Entity:
    def __init__(self, name, email, role):
        self.name = name
        self.email = email
        self.role = role

# --- CRUD Operations ---
def create_po_bucket(po_data: dict, initial_email: dict):
    client, po_ws, entities_ws, history_ws = setup_spreadsheet()
    if not client: return None

    existing = get_purchase_order(po_data.get('po_number')) if po_data else None
    if existing:
        add_email_to_history(history_ws, po_data.get('po_number'), initial_email)
        print(f"INFO: PO Bucket already exists for '{po_data.get('po_number')}'.")
        return existing

    # 1. Create or Update Entities (Buyer and Vendor)
    from email.utils import parseaddr
    buyer_email = parseaddr(initial_email['from'])[1]
    vendor_email = parseaddr(initial_email['to'])[1]

    buyer = get_or_create_entity(entities_ws, po_data['buyer_name'], buyer_email, 'Buyer')
    vendor = get_or_create_entity(entities_ws, po_data['vendor_name'], vendor_email, 'Vendor')

    # 2. Create the Purchase Order
    line_items_json = json.dumps(po_data.get('line_items', []))
    # expected_delivery_date may be missing; write blank if absent
    edd = po_data.get('expected_delivery_date')
    if hasattr(edd, 'strftime'):
        edd_str = edd.strftime('%Y-%m-%d')
    else:
        edd_str = ''
    po_row = [
        po_data['po_number'],
        buyer.name,
        vendor.name,
        datetime.now().strftime('%Y-%m-%d'),
        edd_str,
        'ISSUED',
        line_items_json,
        buyer_email,
        vendor_email,
        buyer_email,
        '',
        '',
    ]
    _with_backoff(po_ws.append_row, po_row)
    _invalidate_caches()

    # 3. Log the initial email to conversation history
    add_email_to_history(history_ws, po_data['po_number'], initial_email)

    print(f"SUCCESS: Created new PO Bucket for '{po_data['po_number']}'.")
    return PurchaseOrder(po_data['po_number'], buyer, vendor, 'ISSUED', original_sender=buyer_email)

def get_or_create_entity(ws, name, email, role):
    cell = _with_backoff(ws.find, email, in_column=2)
    if cell:
        row = _with_backoff(ws.row_values, cell.row)
        return Entity(name=row[0], email=row[1], role=row[2])
    else:
        _with_backoff(ws.append_row, [name, email, role])
        _invalidate_caches()
        return Entity(name, email, role)

def add_email_to_history(history_ws, po_number, email_data):
    history_row = [
        po_number,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        email_data['from'],
        email_data['subject'],
        email_data.get('body', '')
    ]
    _with_backoff(history_ws.append_row, history_row)

def get_purchase_order(po_number: str):
    _, po_ws, entities_ws, _ = setup_spreadsheet()
    if not po_ws: return None
    rows = _get_po_rows_cached(po_ws)
    row = None
    for i, r in enumerate(rows):
        if i == 0:
            continue
        if r and len(r) > 0 and r[0] == po_number:
            row = r
            break
    if row:

        buyer_email = row[7] if len(row) > 7 else ""
        vendor_email = row[8] if len(row) > 8 else ""
        original_sender = row[9] if len(row) > 9 else None

        # Prefer email-based resolution when possible (avoids collisions on name)
        buyer = get_entity_by_email(entities_ws, buyer_email) if buyer_email else None
        vendor = get_entity_by_email(entities_ws, vendor_email) if vendor_email else None

        # Backward compatible fallback
        if buyer is None:
            buyer = get_entity_by_name(entities_ws, row[1])
        if vendor is None:
            vendor = get_entity_by_name(entities_ws, row[2])
        # Parse dates and line items if present
        order_date = None
        expected_delivery_date = None
        accepted_delivery_date = None
        remaining_delivery_date = None
        try:
            if len(row) > 3 and row[3]:
                order_date = datetime.strptime(row[3], '%Y-%m-%d')
        except Exception:
            order_date = None
        try:
            if len(row) > 4 and row[4]:
                expected_delivery_date = datetime.strptime(row[4], '%Y-%m-%d')
        except Exception:
            expected_delivery_date = None

        try:
            if len(row) > 10 and row[10]:
                accepted_delivery_date = datetime.strptime(row[10], '%Y-%m-%d')
        except Exception:
            accepted_delivery_date = None

        try:
            if len(row) > 11 and row[11]:
                remaining_delivery_date = datetime.strptime(row[11], '%Y-%m-%d')
        except Exception:
            remaining_delivery_date = None

        line_items = []
        try:
            if len(row) > 6 and row[6]:
                line_items = json.loads(row[6])
        except Exception:
            line_items = []

        return PurchaseOrder(
            po_number=row[0],
            buyer=buyer,
            vendor=vendor,
            status=row[5],
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            accepted_delivery_date=accepted_delivery_date,
            remaining_delivery_date=remaining_delivery_date,
            line_items=line_items,
            original_sender=original_sender,
        )
    return None


def update_po_partial_delivery_dates(
    po_number: str,
    accepted_delivery_date=None,
    remaining_delivery_date=None,
):
    _, po_ws, _, _ = setup_spreadsheet()
    if not po_ws:
        return
    cell = _with_backoff(po_ws.find, po_number, in_column=1)
    if not cell:
        return

    if accepted_delivery_date is not None:
        if hasattr(accepted_delivery_date, "strftime"):
            value = accepted_delivery_date.strftime('%Y-%m-%d')
        else:
            value = str(accepted_delivery_date or "").strip()
        _with_backoff(po_ws.update_cell, cell.row, 11, value)  # Accepted Delivery Date

    if remaining_delivery_date is not None:
        if hasattr(remaining_delivery_date, "strftime"):
            value = remaining_delivery_date.strftime('%Y-%m-%d')
        else:
            value = str(remaining_delivery_date or "").strip()
        _with_backoff(po_ws.update_cell, cell.row, 12, value)  # Remaining Delivery Date

    _invalidate_caches()

def get_entity_by_email(ws, email):
    rows = _get_entities_rows_cached(ws)
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if len(row) > 1 and row[1] == email:
            role = row[2] if len(row) > 2 else ""
            return Entity(name=row[0], email=row[1], role=role)
    return None

def get_entity_by_name(ws, name):
    rows = _get_entities_rows_cached(ws)
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if len(row) > 0 and row[0] == name:
            email = row[1] if len(row) > 1 else ""
            role = row[2] if len(row) > 2 else ""
            return Entity(name=row[0], email=email, role=role)
    return None

def get_active_pos_by_email(email: str):
    _, po_ws, entities_ws, _ = setup_spreadsheet()
    if not po_ws or not entities_ws:
        return []

    # Resolve entity name if present (fallback matching)
    entity_name = None
    ent = get_entity_by_email(entities_ws, email)
    if ent:
        entity_name = ent.name

    # Avoid get_all_records(): it fails if header row has duplicate/blank values
    rows = _get_po_rows_cached(po_ws)  # includes header row
    active_pos = []
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if not row or not row[0]:
            continue

        po_number = row[0]
        buyer_name = row[1] if len(row) > 1 else ""
        vendor_name = row[2] if len(row) > 2 else ""
        status = row[5] if len(row) > 5 else ""
        buyer_email = row[7] if len(row) > 7 else ""
        vendor_email = row[8] if len(row) > 8 else ""

        # Prefer matching by stored emails; fall back to name match if needed
        matches = (email and (email == buyer_email or email == vendor_email))
        if not matches and entity_name:
            matches = (buyer_name == entity_name or vendor_name == entity_name)

        if matches and status not in ['COMPLETED', 'CANCELLED']:
            active_pos.append(po_number)

    return active_pos

def get_conversation_history(po_number: str):
    _, _, _, history_ws = setup_spreadsheet()
    if not history_ws: return ""
    all_history = _with_backoff(history_ws.get_all_records)
    conversation = ""
    for record in all_history:
        if record['PO Number'] == po_number:
            conversation += f"From: {record['From']}\nSubject: {record['Subject']}\n{record['Body']}\n---\n"
    return conversation


def get_conversation_histories(po_numbers: list[str]) -> dict[str, str]:
    """Batch version: returns {po_number: formatted_history} for given po_numbers."""
    _, _, _, history_ws = setup_spreadsheet()
    if not history_ws:
        return {po: "" for po in po_numbers}
    wanted = set(po_numbers)
    histories: dict[str, str] = {po: "" for po in po_numbers}
    # Using get_all_values avoids header strictness issues
    rows = _with_backoff(history_ws.get_all_values)
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if len(row) < 4:
            continue
        po = row[0]
        if po not in wanted:
            continue
        from_addr = row[2] if len(row) > 2 else ""
        subject = row[3] if len(row) > 3 else ""
        body = row[4] if len(row) > 4 else ""
        histories[po] += f"From: {from_addr}\nSubject: {subject}\n{body}\n---\n"
    return histories

def update_po_status(po_number: str, status: str):
    _, po_ws, _, _ = setup_spreadsheet()
    if not po_ws: return
    cell = _with_backoff(po_ws.find, po_number, in_column=1)
    if cell:
        _with_backoff(po_ws.update_cell, cell.row, 6, status) # Status is now in column 6
        _invalidate_caches()

def list_active_po_numbers() -> list[str]:
    """Returns PO numbers that are not in a terminal status."""
    _, po_ws, _entities_ws, _history_ws = setup_spreadsheet()
    if not po_ws:
        return []

    terminal = {"DELIVERED", "CLOSED", "COMPLETED", "CANCELLED"}
    rows = _get_po_rows_cached(po_ws)
    out: list[str] = []
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if not row or not row[0]:
            continue
        po_number = row[0].strip()
        status = (row[5] if len(row) > 5 else "").strip().upper()
        if status and status in terminal:
            continue
        out.append(po_number)
    return out

def update_po_expected_delivery(po_number: str, expected_delivery_date):
    _, po_ws, _, _ = setup_spreadsheet()
    if not po_ws: return
    cell = _with_backoff(po_ws.find, po_number, in_column=1)
    if not cell:
        return

    if hasattr(expected_delivery_date, "strftime"):
        value = expected_delivery_date.strftime('%Y-%m-%d')
    else:
        value = str(expected_delivery_date or "").strip()
    _with_backoff(po_ws.update_cell, cell.row, 5, value)  # Expected Delivery is column 5
    _invalidate_caches()

def clear_all_data():
    client, po_ws, entities_ws, history_ws = setup_spreadsheet()
    if not client:
        return

    po_header = ['PO Number', 'Buyer', 'Vendor', 'Order Date', 'Expected Delivery', 'Status', 'Line Items', 'Buyer Email', 'Vendor Email', 'Original Sender', 'Accepted Delivery Date', 'Remaining Delivery Date']
    entities_header = ['Entity Name', 'Email', 'Role']
    history_header = ['PO Number', 'Timestamp', 'From', 'Subject', 'Body']
    threads_header = [
        'PO Number',
        'Timestamp',
        'Direction',
        'From',
        'To',
        'Subject',
        'Body',
        'Labels',
    ]

    if po_ws:
        _with_backoff(po_ws.clear)
        _with_backoff(po_ws.append_row, po_header)
        print("Cleared PurchaseOrders sheet.")
    if entities_ws:
        _with_backoff(entities_ws.clear)
        _with_backoff(entities_ws.append_row, entities_header)
        print("Cleared Entities sheet.")
    if history_ws:
        _with_backoff(history_ws.clear)
        _with_backoff(history_ws.append_row, history_header)
        print("Cleared ConversationHistory sheet.")

    try:
        sheet = _with_backoff(client.open, SHEET_NAME)
        try:
            threads_ws = _with_backoff(sheet.worksheet, "Threads")
        except gspread.exceptions.WorksheetNotFound:
            threads_ws = _with_backoff(sheet.add_worksheet, title="Threads", rows="200", cols="10")
        _with_backoff(threads_ws.clear)
        _with_backoff(threads_ws.append_row, threads_header)
        print("Cleared Threads sheet.")
    except Exception as e:
        print(f"WARNING: Failed to clear Threads sheet: {e}")

    _invalidate_caches()
