import json
import os
from typing import Any, Dict, List

from bucket.po_bucket import compute_flags

_RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


def _load_rules() -> List[Dict[str, Any]]:
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
            return doc.get("rules", [])
    except FileNotFoundError:
        print(f"Rules file not found at {_RULES_PATH}")
        return []
    except Exception as e:
        print(f"Failed to load rules: {e}")
        return []


def _kw_any(keywords: List[str], text: str) -> bool:
    t = (text or "").lower()
    return any(kw.lower() in t for kw in keywords)


def _in_list(val: str, allowed: List[str]) -> bool:
    if val is None:
        return False
    return str(val) in set(allowed)


def _not_in_list(val: str, banned: List[str]) -> bool:
    if val is None:
        return True
    return str(val) not in set(banned)


def _match_when(when: Dict[str, Any], email: Dict[str, Any], state: Dict[str, Any], flags: Dict[str, Any]) -> bool:
    # During periodic system checks, only evaluate rules that explicitly opt-in.
    if (email.get("role") == "system") and ("from_role" not in when):
        return False

    # from_role
    if "from_role" in when:
        if not _in_list(email.get("role"), when["from_role"]):
            return False

    # entity
    if "entity" in when:
        if not _in_list(email.get("entity_name"), when["entity"]):
            return False

    # status inclusions/exclusions
    if "status_in" in when:
        if not _in_list(state.get("status"), when["status_in"]):
            return False
    if "status_not_in" in when:
        if not _not_in_list(state.get("status"), when["status_not_in"]):
            return False
    if "status_is" in when:
        if str(state.get("status")) != str(when["status_is"]):
            return False

    # delivery_date_past
    if when.get("delivery_date_past") is True and flags.get("delivery_date_past") is not True:
        return False

    # delivery_date_missing
    if when.get("delivery_date_missing") is True and flags.get("delivery_date_missing") is not True:
        return False

    # sla_hours_over
    if "sla_hours_over" in when:
        h = flags.get("hours_since_order")
        if h is None or h <= float(when["sla_hours_over"]):
            return False

    # supplier_silent_over_seconds_over
    if "supplier_silent_over_seconds_over" in when:
        s = flags.get("supplier_silent_over_seconds")
        if s is None or float(s) <= float(when["supplier_silent_over_seconds_over"]):
            return False

    # last_outbound_to_supplier_is_no_response_followup
    if "last_outbound_to_supplier_is_no_response_followup" in when:
        if bool(flags.get("last_outbound_to_supplier_is_no_response_followup")) is not bool(when["last_outbound_to_supplier_is_no_response_followup"]):
            return False

    # keywords_any (search in subject+body or keywords list)
    if "keywords_any" in when:
        # Email dict provides extracted keywords already; prefer exact matches
        kws = set(email.get("keywords", []))
        needed = set([str(x).lower() for x in when["keywords_any"]])
        if kws.intersection(needed):
            pass
        else:
            # Fallback to full-text contains
            text = f"{email.get('subject','')}\n{email.get('body','')}"
            if not _kw_any(list(needed), text):
                return False

    # intent_in (use LLM-produced intents)
    if "intent_in" in when:
        intents = set([str(x).lower() for x in email.get("intents", [])])
        needed = set([str(x).lower() for x in when["intent_in"]])
        if not intents.intersection(needed):
            return False

    return True


essential_rule_fields = {"name", "when", "then"}


def evaluate(email: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a list of actions for the first matching rule (POC)."""
    actions: List[Dict[str, Any]] = []
    rules = _load_rules()
    flags = compute_flags(state) if state else {}

    for rule in rules:
        if not essential_rule_fields.issubset(rule.keys()):
            continue
        when = rule.get("when", {})
        if _match_when(when, email, state, flags):
            then = rule.get("then", [])
            for act in then:
                act_copy = dict(act)
                act_copy["__rule_name"] = rule.get("name")
                actions.append(act_copy)
            break  # first-match for POC

    return actions
