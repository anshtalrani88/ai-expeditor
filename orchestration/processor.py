from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import re
import json

from email_integration.classifier import classify_email
from bucket.po_bucket import get_po_state, update_status, set_flag, append_thread, compute_flags
from rules.engine import evaluate as evaluate_rules
from rag.email_generator import generate_email_content
from rag.huggingface_handler import get_llm_generation
from email_integration.threaded_email_handler import send_threaded_email
from email_integration.email_handler import SENDER_EMAIL
from email_integration.finance_notification import FINANCE_EMAIL
from g_sheets.sheets_handler import (
    update_po_expected_delivery,
    update_po_partial_delivery_dates,
    update_po_eta,
    list_pos_with_eta,
    get_purchase_order,
    update_po_mtc_received,
    list_pos_needing_mtc,
)

# Configure internal routing addresses for POC
ENGINEERING_EMAIL = "engineering@example.com"


_DATE_PATTERNS = [
    # 2026-01-15 or 2026/01/15
    re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b"),
    # 15-01-2026 or 15/01/2026
    re.compile(r"\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2})\b"),
]


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


_TEXT_DATE_PATTERNS = [
    # 13 january 2026
    re.compile(r"\b(0?[1-9]|[12]\d|3[01])\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(20\d{2})\b"),
    # january 13 2026
    re.compile(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(0?[1-9]|[12]\d|3[01])\s+(20\d{2})\b"),
]


def _extract_relative_date(text: str, reference_date: datetime) -> Optional[datetime]:
    if not reference_date:
        return None

    text = text.lower()
    
    # Tomorrow
    if "tomorrow" in text:
        return reference_date + timedelta(days=1)

    # Next week
    if "next week" in text:
        return reference_date + timedelta(weeks=1)

    # In X days/weeks
    m = re.search(r"\b(in|within)\s+(\d+)\s+(day|week)s?\b", text)
    if m:
        num = int(m.group(2))
        unit = m.group(3)
        if unit == "day":
            return reference_date + timedelta(days=num)
        elif unit == "week":
            return reference_date + timedelta(weeks=num)

    # Next Monday, Tuesday, etc.
    days_of_week = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
        "friday": 4, "saturday": 5, "sunday": 6
    }
    m = re.search(r"\b(next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    if m:
        target_day = days_of_week[m.group(2)]
        days_ahead = target_day - reference_date.weekday()
        if days_ahead <= 0: # Target day has already passed this week
            days_ahead += 7
        return reference_date + timedelta(days=days_ahead)

    return None

def _extract_any_date(subject: str, body: str, reference_date: Optional[datetime] = None) -> Optional[datetime]:
    text = f"{subject}\n{body}".lower()

    if reference_date:
        relative_dt = _extract_relative_date(text, reference_date)
        if relative_dt:
            return relative_dt

    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            if pat is _DATE_PATTERNS[0]:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(year=y, month=mo, day=d)
        except Exception:
            return None

    for pat in _TEXT_DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            if pat is _TEXT_DATE_PATTERNS[0]:
                d = int(m.group(1))
                mo = _MONTHS.get(m.group(2), None)
                y = int(m.group(3))
            else:
                mo = _MONTHS.get(m.group(1), None)
                d = int(m.group(2))
                y = int(m.group(3))
            if not mo:
                return None
            return datetime(year=y, month=mo, day=d)
        except Exception:
            return None

    return None


def _infer_accepted_date_from_threads(state: Dict[str, Any], reference_date: Optional[datetime] = None) -> Optional[str]:
    threads = state.get("threads") or []
    for msg in reversed(threads):
        if (msg.get("direction") or "").lower() != "inbound":
            continue
        labels = msg.get("labels") or []
        if any((l or "").lower() == "intent:partial_availability" for l in labels) or any("partial" in (l or "").lower() for l in labels):
            # Note: This will not have the original email's date for relative calculations.
            # This is a limitation of the current architecture.
            dt = _extract_any_date(msg.get("subject") or "", msg.get("body") or "", reference_date=reference_date)
            if dt:
                return dt.strftime('%Y-%m-%d')
    return None


def _extract_partial_decision_llm(subject: str, body: str) -> Optional[str]:
    allowed = ["ACCEPT_PARTIAL", "REJECT_PARTIAL", "WAIT_FULL", "SPLIT_PO", "NONE"]
    prompt = f"""
You are an assistant that extracts a buyer's decision from an email reply about a partial availability situation.

Return STRICT JSON only with this schema:
{{"decision": "<one of {allowed}>"}}

Interpret the following as:
- option 1 => ACCEPT_PARTIAL
- option 2 => SPLIT_PO
- option 3 => WAIT_FULL

If the buyer is not deciding yet or the message is unrelated, return NONE.

Email:
Subject: {subject}
Body: {body}
"""
    try:
        raw = (get_llm_generation(prompt) or "").strip()
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        decision = data.get("decision")
        if not isinstance(decision, str):
            return None
        decision = decision.strip().upper()
        if decision == "NONE":
            return None
        if decision in allowed:
            return decision
        return None
    except Exception:
        return None


def _extract_partial_decision(subject: str, body: str) -> Optional[str]:
    text = f"{subject}\n{body}".lower()

    # Some buyers reply with "option 1/2/3" based on our enumerated options.
    # Mapping (based on partial_quantity_confirmation template):
    # - option 1: accept partial shipment
    # - option 2: split PO
    # - option 3: wait for full availability
    if any(k in text for k in ["option 1", "option one", "1st option", "first option"]):
        return "ACCEPT_PARTIAL"
    if any(k in text for k in ["option 2", "option two", "2nd option", "second option"]):
        return "SPLIT_PO"
    if any(k in text for k in ["option 3", "option three", "3rd option", "third option"]):
        return "WAIT_FULL"

    # accept
    if any(k in text for k in ["accept the partial", "accept partial", "accept", "ok with partial", "okay with partial", "proceed with partial"]):
        return "ACCEPT_PARTIAL"

    # reject
    if any(k in text for k in ["reject", "decline", "do not accept", "don't accept", "not accept", "cancel"]):
        return "REJECT_PARTIAL"

    # split
    if "split" in text:
        return "SPLIT_PO"

    # wait
    if any(k in text for k in ["wait", "hold", "full availability", "ship all", "deliver all together"]):
        return "WAIT_FULL"

    return None


def _infer_remaining_date_from_threads(state: Dict[str, Any], reference_date: Optional[datetime] = None) -> Optional[str]:
    threads = state.get("threads") or []
    # Search most recent inbound supplier message first
    for msg in reversed(threads):
        if (msg.get("direction") or "").lower() != "inbound":
            continue
        labels = msg.get("labels") or []
        if any((l or "").lower() == "intent:partial_availability" for l in labels) or any("partial" in (l or "").lower() for l in labels):
            # Note: This will not have the original email's date for relative calculations.
            # This is a limitation of the current architecture.
            dt = _extract_any_date(msg.get("subject") or "", msg.get("body") or "", reference_date=reference_date)
            if dt:
                return dt.strftime('%Y-%m-%d')
    return None


def _extract_all_dates(subject: str, body: str, reference_date: Optional[datetime] = None) -> List[datetime]:
    text = f"{subject}\n{body}".lower()
    out: List[datetime] = []

    if reference_date:
        relative_dt = _extract_relative_date(text, reference_date)
        if relative_dt:
            out.append(relative_dt)

    def _add(dt: Optional[datetime]) -> None:
        if not dt:
            return
        if all(dt.date() != existing.date() for existing in out):
            out.append(dt)

    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if pat is _DATE_PATTERNS[0]:
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                _add(datetime(year=y, month=mo, day=d))
            except Exception:
                continue

    for pat in _TEXT_DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if pat is _TEXT_DATE_PATTERNS[0]:
                    d = int(m.group(1))
                    mo = _MONTHS.get(m.group(2), None)
                    y = int(m.group(3))
                else:
                    mo = _MONTHS.get(m.group(1), None)
                    d = int(m.group(2))
                    y = int(m.group(3))
                if not mo:
                    continue
                _add(datetime(year=y, month=mo, day=d))
            except Exception:
                continue

    out.sort()
    return out


def _extract_partial_delivery_dates_llm(subject: str, body: str) -> Dict[str, Optional[str]]:
    prompt = f"""
You are an assistant that extracts delivery dates from a supplier email about partial availability.

We need TWO dates:
- accepted_delivery_date: when the available/accepted quantity can ship/deliver (if mentioned)
- remaining_delivery_date: when the remaining/backordered quantity can ship/deliver (if mentioned)

Return STRICT JSON only:
{{
  "accepted_delivery_date": "YYYY-MM-DD" or null,
  "remaining_delivery_date": "YYYY-MM-DD" or null
}}

If only one date is mentioned and it clearly refers to the available-now portion, set it as accepted_delivery_date.
If only one date is mentioned and it clearly refers to the backorder/remaining portion, set it as remaining_delivery_date.

Email:
Subject: {subject}
Body: {body}
"""
    try:
        raw = (get_llm_generation(prompt) or "").strip()
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)

        def _norm(v: Any) -> Optional[str]:
            if v is None:
                return None
            if not isinstance(v, str):
                return None
            v = v.strip()
            return v or None

        return {
            "accepted_delivery_date": _norm(data.get("accepted_delivery_date")),
            "remaining_delivery_date": _norm(data.get("remaining_delivery_date")),
        }
    except Exception:
        return {"accepted_delivery_date": None, "remaining_delivery_date": None}


def _extract_promised_delivery_date(subject: str, body: str, date: Optional[datetime] = None) -> Optional[datetime]:
    text = f"{subject}\n{body}".lower()
    # Only treat as ETA if there's some delivery-related hint
    if not any(k in text for k in ["deliver", "delivery", "eta", "ship", "dispatch", "by "]):
        return None

    return _extract_any_date(subject, body, reference_date=date)


def _recipient_for(to: str, state: Dict[str, Any]) -> Optional[str]:
    to_norm = (to or "").lower()
    if to_norm == "supplier":
        return state.get("supplier_email")
    if to_norm == "buyer":
        return state.get("buyer_email") or state.get("original_sender")
    if to_norm == "finance":
        return FINANCE_EMAIL
    if to_norm == "engineering":
        return ENGINEERING_EMAIL
    return None


def _exec_send_email(action: Dict[str, Any], email_info: Dict[str, Any], state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    to = action.get("to")
    scenario = action.get("scenario")
    recipient = _recipient_for(to, state)
    if not recipient:
        return {"error": f"No recipient resolved for to={to}"}

    # Find the last message from the recipient to maintain the thread
    last_message_id = None
    references = None
    threads = state.get('threads', [])
    for message in reversed(threads):
        if message.get('direction') == 'inbound' and message.get('from') == recipient and message.get('message_id'):
            last_message_id = message.get('message_id')
            references = message.get('message_id') # Start a new reference chain
            break

    # Fallback to the current email's threading info if no history is found
    if not last_message_id:
        last_message_id = email_info.get("message_id")
        references = email_info.get("references")

    data: Dict[str, Any] = {
        "po_number": state.get("po_number"),
        "vendor_name": state.get("supplier_name"),
        "supplier_name": state.get("supplier_name"),
        "buyer_name": state.get("buyer_name"),
        "original_body": email_info.get("body"),
        "promised_delivery_date": email_info.get("promised_delivery_date") or state.get("expected_delivery_date"),
        "accepted_delivery_date": email_info.get("accepted_delivery_date") or state.get("accepted_delivery_date"),
        "remaining_delivery_date": email_info.get("remaining_delivery_date") or state.get("remaining_delivery_date"),
        "partial_decision": email_info.get("partial_decision"),
        "line_items": state.get("line_items"),
        "discrepancy_reason": email_info.get("discrepancy_reason"),
    }

    content = generate_email_content(scenario, data)
    if not content:
        return {"error": f"Email content generation failed for scenario {scenario}"}

    send_threaded_email(
        to_recipient=recipient,
        subject=content["subject"],
        body=content["body"],
        original_message_id=last_message_id,
        references=references
    )

    # Log outbound thread
    append_thread(
        po_number=state.get("po_number"),
        direction="outbound",
        from_addr=SENDER_EMAIL,
        to_addr=recipient,
        subject=content["subject"],
        body=content["body"],
        labels=[scenario, f"to:{to}"],
        message_id=None,  # This will be set by the email server
    )

    po_number = state.get("po_number")
    # Set a 24-hour ETA for follow-up if we're waiting on the supplier
    if po_number and to == "supplier":
        try:
            eta = datetime.now() + timedelta(hours=24)
            update_po_eta(po_number, eta)
        except Exception as e:
            print(f"WARNING: Failed to update ETA for PO {po_number}: {e}")

    return {"sent_to": recipient, "scenario": scenario}


def process_inbound_email(
    from_sender: str,
    subject: str,
    body: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    po_number_hint: Optional[str] = None,
    message_id: Optional[str] = None,
    references: Optional[str] = None,
    date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Orchestrates: classify -> load bucket -> evaluate rules -> execute actions.
    Always records the inbound message as a thread entry if a PO is identified.
    """
    email_info = classify_email(from_sender, subject, body, attachments=attachments)
    email_info['message_id'] = message_id
    email_info['references'] = references
    result: Dict[str, Any] = {"email": email_info, "actions": []}

    po_number = email_info.get("po_number")
    if not po_number and po_number_hint:
        po_number = po_number_hint
        email_info["po_number"] = po_number_hint

    if not po_number:
        result["warning"] = "No PO number detected; skipping rule evaluation."
        return result

    state = get_po_state(po_number)
    if not state:
        result["warning"] = f"PO {po_number} not found in bucket."
        return result

    # If the supplier has provided an MTC, mark it as received.
    if "mtc_provided" in (email_info.get("intents") or []):
        update_po_mtc_received(po_number, received=True)
        state["mtc_received"] = True

    # If supplier replies with an ETA while the PO is overdue, capture it and update the bucket.
    prior_flags = compute_flags(state)
    promised = None
    if email_info.get("role") == "supplier" and prior_flags.get("delivery_date_past") is True:
        promised = _extract_promised_delivery_date(subject, body, date)
        if promised:
            update_po_expected_delivery(po_number, promised)
            state["expected_delivery_date"] = promised
            email_info["promised_delivery_date"] = promised.strftime('%Y-%m-%d')

    # Partial availability nuance: supplier has some qty now; rest later.
    # If an ETA for remaining items is present, include it in buyer email.
    # If missing, ask supplier for the committed delivery date for remaining items.
    partial_flow = False
    partial_remaining_dt = None
    if email_info.get("role") == "supplier" and "partial_availability" in (email_info.get("intents") or []):
        partial_flow = True
        extracted = _extract_partial_delivery_dates_llm(subject, body)
        ad_str = extracted.get("accepted_delivery_date")
        rd_str = extracted.get("remaining_delivery_date")

        ad_dt = None
        rd_dt = None
        try:
            if ad_str:
                ad_dt = datetime.strptime(ad_str, '%Y-%m-%d')
        except Exception:
            ad_str = None
        try:
            if rd_str:
                rd_dt = datetime.strptime(rd_str, '%Y-%m-%d')
        except Exception:
            rd_str = None

        if not ad_str and not rd_str:
            dates = _extract_all_dates(subject, body, reference_date=date)
            if len(dates) == 1:
                ad_dt = dates[0]
            elif len(dates) >= 2:
                ad_dt = dates[0]
                rd_dt = dates[-1]

        if ad_dt is not None:
            email_info["accepted_delivery_date"] = ad_dt.strftime('%Y-%m-%d')
        if rd_dt is not None:
            email_info["remaining_delivery_date"] = rd_dt.strftime('%Y-%m-%d')

        try:
            if ad_dt is not None or rd_dt is not None:
                update_po_partial_delivery_dates(po_number, accepted_delivery_date=ad_dt, remaining_delivery_date=rd_dt)
                state["accepted_delivery_date"] = ad_dt
                state["remaining_delivery_date"] = rd_dt
        except Exception:
            pass

        partial_remaining_dt = rd_dt

    # Buyer decision on partial availability: accept/reject/wait/split.
    buyer_partial_decision = None
    if email_info.get("role") == "internal" and state.get("partial_availability") is True:
        buyer_partial_decision = _extract_partial_decision_llm(subject, body) or _extract_partial_decision(subject, body)
        if buyer_partial_decision:
            email_info["partial_decision"] = buyer_partial_decision
            if not email_info.get("accepted_delivery_date"):
                inferred2 = _infer_accepted_date_from_threads(state, reference_date=date)
                if inferred2:
                    email_info["accepted_delivery_date"] = inferred2
            if not email_info.get("remaining_delivery_date"):
                inferred = _infer_remaining_date_from_threads(state, reference_date=date)
                if inferred:
                    email_info["remaining_delivery_date"] = inferred

    # Log inbound thread with intents as labels as well
    append_thread(
        po_number=po_number,
        direction="inbound",
        from_addr=from_sender,
        to_addr=SENDER_EMAIL,
        subject=subject,
        body=body,
        labels=(email_info.get("keywords", []) + [f"intent:{i}" for i in email_info.get("intents", [])]),
        message_id=email_info.get("message_id"),
    )

    actions = evaluate_rules(email_info, state)

    # If we extracted a promised delivery date from the supplier, always notify the buyer.
    if promised:
        actions.insert(0, {"action": "send_email", "to": "buyer", "scenario": "delivery_date_update_buyer"})

    # If buyer has responded with a decision, notify supplier and update PO status.
    if buyer_partial_decision:
        decision_to_status = {
            "ACCEPT_PARTIAL": "PARTIAL_ACCEPTED",
            "REJECT_PARTIAL": "PARTIAL_REJECTED",
            "WAIT_FULL": "WAITING_FULL_AVAILABILITY",
            "SPLIT_PO": "SPLIT_REQUESTED",
        }
        new_status = decision_to_status.get(buyer_partial_decision)
        actions.insert(0, {"action": "send_email", "to": "supplier", "scenario": "partial_availability_buyer_decision_supplier"})
        if new_status:
            actions.insert(1, {"action": "update_status", "value": new_status})

    for act in actions:
        action_type = act.get("action")
        if action_type == "update_status":
            val = act.get("value")
            if val:
                update_status(po_number, val)
                result["actions"].append({"updated_status": val})
        elif action_type == "set_flag":
            flag = act.get("flag")
            val = act.get("value")
            if flag:
                set_flag(po_number, flag, val)
                result["actions"].append({"set_flag": f"{flag}={val}"})
        elif action_type == "send_email":
            sent = _exec_send_email(act, email_info, state)
            result["actions"].append({"send_email": sent})
        else:
            result["actions"].append({"ignored_action": action_type})

    return result


def process_eta_check(po_number: str) -> Dict[str, Any]:
    """
    Evaluate rules for a PO where the ETA for a reply has passed.
    """
    state = get_po_state(po_number)
    if not state:
        return {"warning": f"PO {po_number} not found in bucket."}

    email_info: Dict[str, Any] = {
        "from_email": "system@local",
        "subject": "",
        "body": "",
        "po_number": po_number,
        "entity_name": None,
        "role": "system",
        "keywords": ["eta_lapsed"],  # Special keyword for the rules engine
        "intents": [],
    }

    result: Dict[str, Any] = {"email": email_info, "actions": []}
    actions = evaluate_rules(email_info, state)
    for act in actions:
        if act.get("action") == "update_status":
            val = act.get("value")
            if val:
                update_status(po_number, val)
                result["actions"].append({"updated_status": val})
        elif act.get("action") == "send_email":
            sent = _exec_send_email(act, email_info, state)
            result["actions"].append({"send_email": sent})
        else:
            result["actions"].append({"ignored_action": act.get("action")})

    # Clear the ETA after processing to prevent multiple follow-ups
    update_po_eta(po_number, None)

    return result


def run_eta_follow_ups():
    """
    Checks all active POs with an ETA and triggers follow-ups for those that are overdue.
    """
    print("Running ETA follow-up checks...")
    po_numbers = list_pos_with_eta()
    if not po_numbers:
        print("No POs with an active ETA found.")
        return

    for po_number in po_numbers:
        try:
            po = get_purchase_order(po_number)
            if not po or not po.eta:
                continue

            if datetime.now() > po.eta:
                print(f"ETA lapsed for PO {po_number}. Triggering follow-up.")
                process_eta_check(po_number)

        except Exception as e:
            print(f"WARNING: Failed to process ETA check for PO {po_number}: {e}")


def process_mtc_check(po_number: str) -> Dict[str, Any]:
    """
    Evaluate rules for a PO that is missing its MTC.
    """
    state = get_po_state(po_number)
    if not state:
        return {"warning": f"PO {po_number} not found in bucket."}

    email_info: Dict[str, Any] = {
        "from_email": "system@local",
        "subject": "",
        "body": "",
        "po_number": po_number,
        "entity_name": None,
        "role": "system",
        "keywords": ["mtc_missing"],  # Special keyword for the rules engine
        "intents": [],
    }

    result: Dict[str, Any] = {"email": email_info, "actions": []}
    actions = evaluate_rules(email_info, state)
    for act in actions:
        action_type = act.get("action")
        if action_type == "update_status":
            val = act.get("value")
            if val:
                update_status(po_number, val)
                result["actions"].append({"updated_status": val})
        elif action_type == "set_flag":
            flag = act.get("flag")
            val = act.get("value")
            if flag:
                set_flag(po_number, flag, val)
                result["actions"].append({"set_flag": f"{flag}={val}"})
        elif action_type == "send_email":
            sent = _exec_send_email(act, email_info, state)
            result["actions"].append({"send_email": sent})
        else:
            result["actions"].append({"ignored_action": action_type})

    return result


def run_mtc_follow_ups():
    """
    Checks all active POs that require an MTC and triggers follow-ups for those that are missing it.
    """
    print("Running MTC follow-up checks...")
    po_numbers = list_pos_needing_mtc()
    if not po_numbers:
        print("No POs needing an MTC found.")
        return

    for po_number in po_numbers:
        try:
            # Add a check to see if we've already sent a follow-up recently
            po = get_purchase_order(po_number)
            if po and po.eta and po.eta > datetime.now():
                continue # An ETA is set, so we're waiting for a response

            print(f"MTC missing for PO {po_number}. Triggering follow-up.")
            process_mtc_check(po_number)

        except Exception as e:
            print(f"WARNING: Failed to process MTC check for PO {po_number}: {e}")


def process_system_check(po_number: str) -> Dict[str, Any]:
    """
    Evaluate rules for a PO without an inbound email (e.g., scheduled checks).
    Uses deterministic flags like delivery_date_past or delivery_date_missing.
    """
    state = get_po_state(po_number)
    if not state:
        return {"warning": f"PO {po_number} not found in bucket."}

    email_info: Dict[str, Any] = {
        "from_email": "system@local",
        "subject": "",
        "body": "",
        "po_number": po_number,
        "entity_name": None,
        "role": "system",
        "keywords": [],
        "intents": [],
    }

    result: Dict[str, Any] = {"email": email_info, "actions": []}
    actions = evaluate_rules(email_info, state)
    for act in actions:
        if act.get("action") == "update_status":
            val = act.get("value")
            if val:
                update_status(po_number, val)
                result["actions"].append({"updated_status": val})
        elif act.get("action") == "send_email":
            sent = _exec_send_email(act, email_info, state)
            result["actions"].append({"send_email": sent})
        else:
            result["actions"].append({"ignored_action": act.get("action")})

    return result
