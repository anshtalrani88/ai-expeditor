import re
from typing import Optional, Dict, Any, List
from email.utils import parseaddr

from g_sheets.sheets_handler import setup_spreadsheet, get_purchase_order
from rag.huggingface_handler import get_llm_generation

# Treat these as internal org domains for role classification
INTERNAL_DOMAINS = {"denicx.com"}

# Supports common PO formats like:
# - PO-AX-301
# - PO-OG-202
# - PO-OG-2026-0147
_PO_REGEX = re.compile(r"\bPO-[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})+\b", re.IGNORECASE)


def _normalize(s: Optional[str]) -> str:
    return (s or "").strip()


def extract_po_number(subject: str, body: str) -> Optional[str]:
    for text in (_normalize(subject), _normalize(body)):
        if not text:
            continue
        m = _PO_REGEX.search(text)
        if m:
            return m.group(0).upper()
    return None


def _get_domain(email_addr: str) -> Optional[str]:
    _, addr = parseaddr(email_addr)
    if "@" in addr:
        return addr.split("@", 1)[1].lower()
    return None


def _list_suppliers() -> List[Dict[str, str]]:
    """Return [{name, email}] from the Entities sheet for rows with Role == supplier."""
    client, _po_ws, entities_ws, _history_ws = setup_spreadsheet()
    results: List[Dict[str, str]] = []
    if not entities_ws:
        return results
    try:
        values = entities_ws.get_all_values()  # rows incl header
        # Expect header: ['Entity Name', 'Email', 'Role']
        for i, row in enumerate(values):
            if i == 0:
                continue
            name = row[0] if len(row) > 0 else ""
            email = row[1] if len(row) > 1 else ""
            role = (row[2] if len(row) > 2 else "").lower()
            if name and role in {"supplier", "vendor"}:
                results.append({"name": name, "email": email})
    except Exception:
        pass
    return results


def resolve_entity(from_email: str, po_number: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Staged resolution:
    - Stage 2: If PO known, use its supplier from the bucket (Sheets)
    - Stage 1: Otherwise, map sender domain to supplier email domain (from Suppliers sheet)
    - Stage 3: LLM fallback (TODO)
    Returns dict with entity_name and role ('supplier'|'internal')
    """
    sender_domain = _get_domain(from_email) or ""
    role = "internal" if sender_domain in INTERNAL_DOMAINS else "supplier"

    # Stage 2: If PO known, resolve role by exact email match against buyer/vendor
    if po_number:
        po_obj = get_purchase_order(po_number)
        if po_obj:
            buyer_email = getattr(po_obj.buyer, "email", None) if po_obj.buyer else None
            vendor_email = getattr(po_obj.vendor, "email", None) if po_obj.vendor else None

            if buyer_email and from_email == buyer_email:
                return {"entity_name": getattr(po_obj.buyer, "name", None), "role": "internal"}
            if vendor_email and from_email == vendor_email:
                return {"entity_name": getattr(po_obj.vendor, "name", None), "role": "supplier"}

            # Fallback to vendor name if present (keeps previous behavior)
            if po_obj.vendor and getattr(po_obj.vendor, "name", None):
                return {"entity_name": po_obj.vendor.name, "role": role}

    # Stage 1: Try to map by domain
    if sender_domain:
        for sup in _list_suppliers():
            sup_email = (sup.get("email") or "").lower()
            if "@" in sup_email and sup_email.split("@", 1)[1] == sender_domain:
                return {"entity_name": sup.get("name"), "role": role}

    # Stage 3: Placeholder for LLM-based entity inference
    return {"entity_name": None, "role": role}


def classify_email(from_email: str, subject: str, body: str) -> Dict[str, Any]:
    po_number = extract_po_number(subject, body)
    ent = resolve_entity(from_email, po_number)

    text = f"{subject}\n{body}".lower()
    keywords: List[str] = []
    for kw in [
        "credit hold",
        "payment hold",
        "on hold",
        "technical",
        "datasheet",
        "spec",
        "drawing",
        "acknowledge",
        "ack",
        "partial",
        "backorder",
        "delay",
        "late",
    ]:
        if kw in text:
            keywords.append(kw)

    po_context = None
    if po_number:
        po_obj = get_purchase_order(po_number)
        if po_obj:
            line_items: List[Dict[str, Any]] = []
            for li in (po_obj.line_items or []):
                if isinstance(li, dict):
                    desc = li.get("description") or li.get("item") or li.get("item_description") or ""
                    qty = li.get("quantity") if "quantity" in li else li.get("qty")
                else:
                    desc = getattr(li, "item_description", None) or getattr(li, "description", None) or getattr(li, "item", None) or ""
                    qty = getattr(li, "quantity", None) if hasattr(li, "quantity") else getattr(li, "qty", None)
                line_items.append({"item": desc, "qty": qty})

            po_context = {
                "status": po_obj.status,
                "line_items": line_items,
            }

    intents = _extract_llm_intents(subject, body, po_context)

    # Always run heuristic signals and union them in.
    # The LLM can return a non-empty set that misses critical operational intents.
    heuristic: List[str] = []
    if any(k in text for k in ["credit hold", "payment hold", "on hold"]):
        heuristic.append("credit_hold")
    if any(k in text for k in ["partial", "partially", "some items", "not all", "available", "only have", "dont have", "don't have"]):
        heuristic.append("partial_availability")
    if any(k in text for k in ["delay", "late", "cannot deliver on time"]):
        heuristic.append("delivery_delay")
    if any(k in text for k in ["payment confirmation", "paid"]):
        heuristic.append("payment_confirmation")
    if any(k in text for k in ["docs missing", "certificate", "compliance"]):
        heuristic.append("docs_missing")
    if any(k in text for k in ["extension", "reschedule"]):
        heuristic.append("extension_request")
    if any(k in text for k in ["third party", "sub-supplier", "raw material"]):
        heuristic.append("third_party_issue")
    if any(k in text for k in ["acknowledge", "ack", "confirmed"]):
        heuristic.append("acknowledgment")
    if any(k in text for k in ["technical", "datasheet", "spec", "drawing"]):
        heuristic.append("technical_query")
    delivered_positive = re.search(
        r"\b(has\s+been\s+delivered|delivered\s+already|delivery\s+completed|delivered\s+today|delivered\s+on|goods\s+delivered|received\s+already|has\s+been\s+received|received\s+by)\b",
        text,
    )
    delivered_negative = re.search(
        r"\b(will\s+be\s+delivered|to\s+be\s+delivered|expected\s+to\s+be\s+delivered|deliver\s+by|delivery\s+by)\b",
        text,
    )
    if delivered_positive and not delivered_negative:
        heuristic.append("delivery_completed")

    # De-dupe while preserving order preference (LLM first, then heuristics).
    merged: List[str] = []
    for i in (intents + heuristic):
        if i and i not in merged:
            merged.append(i)
    intents = merged

    return {
        "from_email": from_email,
        "subject": subject,
        "body": body,
        "po_number": po_number,
        "entity_name": ent.get("entity_name"),
        "role": ent.get("role"),
        "keywords": keywords,
        "intents": intents,
    }


ALLOWED_INTENTS = {
    "info_missing",
    "partial_availability",
    "delivery_delay",
    "delivery_completed",
    "credit_hold",
    "technical_query",
    "acknowledgment",
    "payment_confirmation",
    "docs_missing",
    "extension_request",
    "third_party_issue",
    "other",
}


def _extract_llm_intents(subject: str, body: str, po_context: Optional[Dict[str, Any]] = None) -> List[str]:
    # Use a more robust prompt with context and a one-shot example
    prompt = f"""
You are an email triage assistant for procurement. Your task is to read an email and classify its intent.

Read the email and current PO information below. Categorize the email into zero or more intents from this controlled list only:
INTENTS = {list(ALLOWED_INTENTS)}

Return a STRICT JSON object with a single key "intents" whose value is an array of strings from INTENTS. If no intents match, return an empty array.

--- EXAMPLE ---
PO Context: {{'status': 'ISSUED', 'line_items': [{{'item': 'Pressure Transmitter', 'qty': 10}}]}}
Email:
Subject: Update on PO-123
Body: Good morning, we can only ship 8 of the 10 transmitters this week. The rest will follow next week.

JSON Response:
{{
  "intents": ["partial_availability"]
}}
--- END EXAMPLE ---

--- TASK ---
PO Context: {po_context or 'Not available'}
Email:
Subject: {subject}
Body: {body}

JSON Response:
"""
    try:
        raw = get_llm_generation(prompt).strip()
        # remove markdown fences if present
        clean = raw.replace('```json', '').replace('```', '').strip()
        import json
        data = json.loads(clean)
        intents = data.get("intents", [])
        if not isinstance(intents, list):
            return []
        # keep only allowed intents
        return [i for i in intents if i in ALLOWED_INTENTS]
    except Exception:
        return []
