import json
import re
from rag.huggingface_handler import get_llm_generation


def _extract_json_string_value(text: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*"', text)
    if not m:
        return None
    i = m.end()
    out_chars = []
    escaped = False
    while i < len(text):
        ch = text[i]
        if escaped:
            out_chars.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == '"':
            return "".join(out_chars)
        out_chars.append(ch)
        i += 1
    return None

def _format_line_items(line_items: list) -> str:
    """Formats a list of line items into a string for email body."""
    if not line_items:
        return ""
    
    formatted_items = "\n\n**Order Details:**\n"
    for item in line_items:
        desc = item.get('description', 'N/A')
        qty = item.get('quantity', 'N/A')
        price = item.get('unit_price', 'N/A')
        formatted_items += f"- {desc} (Quantity: {qty}, Unit Price: {price})\n"
    return formatted_items

def generate_email_content(scenario: str, data: dict) -> dict:
    """
    Generates a professional email subject and body using an LLM.

    Args:
        scenario: The context for the email (e.g., 'new_po_notification', 'credit_hold_alert').
        data: A dictionary containing relevant information for the email 
              (e.g., {'po_number': 'PO-123', 'vendor_name': 'Supplier Inc.'}).

    Returns:
        A dictionary with 'subject' and 'body' keys, or None if generation fails.
    """
    prompt = "" # Initialize prompt
    line_items_str = _format_line_items(data.get('line_items'))

    if scenario == "new_po_notification":
        prompt = f"""
        Generate a professional and concise email to a vendor about a new purchase order.
        The tone should be formal and clear.
        
        **Details:**
        - Purchase Order Number: {data.get('po_number')}
        - Vendor Name: {data.get('vendor_name')}
        {line_items_str}
        
        **Instructions:**
        1. Create a clear subject line that includes the PO number.
        2. Write a short email body stating that a new PO is attached.
        3. Keep the body brief and professional.
        4. Sign off as 'Denicx Automation'.
        
        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        Example format: {{"subject": "Email Subject", "body": "Email body content."}}
        """
    elif scenario == "credit_hold_alert":
        prompt = f"""
        Generate a professional internal alert email to the finance department about a purchase order on credit hold.
        The tone should be urgent but formal.

        **Details:**
        - Purchase Order Number: {data.get('po_number')}
        - Vendor Name: {data.get('vendor_name')}
        - Original Vendor Message: "{data.get('original_body')}"
        {line_items_str}

        **Instructions:**
        1. Create a subject line that clearly states the PO is on hold and requires action.
        2. Explain that the vendor has placed the PO on hold due to a payment issue.
        3. Include the vendor's original message for context.
        4. Request that the finance team provide a payment confirmation to resolve the issue.
        5. Sign off as 'Procurement System'.

        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        """
    elif scenario == "payment_confirmation_forward":
        prompt = f"""
        Generate a professional email to a vendor, forwarding a payment confirmation to release a hold.
        The tone should be polite and direct.

        **Details:**
        - Purchase Order Number: {data.get('po_number')}
        - Vendor Name: {data.get('vendor_name')}
        {line_items_str}

        **Instructions:**
        1. Create a subject line referencing the original PO number.
        2. State that a payment confirmation is attached regarding the recent credit hold.
        3. Politely request that they proceed with processing the order.
        4. Sign off as 'Denicx Accounts Team'.

        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        """
    elif scenario == "technical_query_forward":
        prompt = f"""
        Generate a concise internal email to the engineering team summarizing a vendor's technical query.
        The tone should be professional and actionable.

        **Details:**
        - Purchase Order Number: {data.get('po_number')}
        - Vendor Name: {data.get('vendor_name')}
        - Vendor Query: "{data.get('original_body')}"
        {line_items_str}

        **Instructions:**
        1. Create a subject line referencing the PO number and that this is a technical query.
        2. Briefly summarize the vendor's question and any key terms.
        3. Request the engineering team to advise and reply-all with the next steps.
        4. Keep it brief and clearly indicate urgency only if apparent from the text.
        5. Sign off as 'Denicx Automation'.

        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        """
    elif scenario == "missing_delivery_date_request":
        prompt = f"""
        Generate a concise professional email to the buyer requesting the missing expected delivery date for a newly issued Purchase Order.
        Keep it polite and action-oriented.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Buyer Name: {data.get('buyer_name')}
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and reference missing delivery date.
        2. Ask the buyer to provide the expected delivery date to proceed with vendor communication.
        3. Keep it brief and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "partial_availability_buyer_decision_supplier":
        prompt = f"""
        Generate a concise email to the supplier conveying the buyer's decision on how to proceed with partial availability.
        Tone should be clear and action-oriented.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        - Buyer Decision: {data.get('partial_decision')} (one of ACCEPT_PARTIAL, REJECT_PARTIAL, WAIT_FULL, SPLIT_PO)
        - Accepted-items delivery date (if known): {data.get('accepted_delivery_date')}
        - Remaining items promised delivery date (if known): {data.get('remaining_delivery_date')}
        - Buyer's message: "{data.get('original_body')}"
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and reference buyer decision.
        2. Clearly state the buyer decision.
        3. If accepted-items delivery date is known, ask supplier to confirm it for the available quantity shipment.
        4. If remaining delivery date is known, ask supplier to confirm it for the balance.
        4. Keep it brief and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "partial_availability_request_remaining_date":
        prompt = f"""
        Generate a concise email to the supplier asking for the committed delivery date for the remaining quantity/items.
        Tone should be professional and specific.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        - Supplier message: "{data.get('original_body')}"
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and request remaining delivery date.
        2. Acknowledge the partial availability and ask for the committed delivery date for the remaining balance.
        3. Keep it brief and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "delivery_date_update_buyer":
        prompt = f"""
        Generate a concise email to the buyer notifying them that the supplier has provided an updated promised delivery date.
        Tone should be clear and informative.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        - New Promised Delivery Date (YYYY-MM-DD): {data.get('promised_delivery_date')}
        - Supplier's message: "{data.get('original_body')}"
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and indicate updated delivery date.
        2. State the new promised delivery date.
        3. Keep it brief and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "delivery_delay_followup":
        prompt = f"""
        Generate a concise follow-up email to the supplier regarding a delivery date that has lapsed.
        Tone should be firm yet professional.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and indicate overdue delivery.
        2. Ask for an updated committed delivery date and reason for the delay.
        3. Keep it brief and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "partial_quantity_confirmation":
        prompt = f"""
        Generate a concise email to the buyer summarizing the supplier's partial availability and asking for a decision.
        Tone should be clear and decision-oriented.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        - Accepted-items delivery date (if provided): {data.get('accepted_delivery_date')}
        - Remaining items promised delivery date (if provided): {data.get('remaining_delivery_date')}
        - Extracted context (if any) from supplier's message: "{data.get('original_body')}"
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and indicate partial availability.
        2. Summarize that supplier can only supply part of the requested quantity.
        3. If an accepted-items delivery date is provided, mention it clearly.
        4. If a remaining delivery date is provided, mention it clearly.
        5. Ask buyer if they want to accept partial shipment, split the PO, or wait for full availability.
        6. Sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    elif scenario == "request_clarification":
        prompt = f"""
        Generate a professional and concise email to a supplier requesting clarification on a purchase order.
        The tone should be polite and specific.
        
        **Details:**
        - Purchase Order Number: {{data.get('po_number')}}
        - Vendor Name: {{data.get('vendor_name')}}
        - Point of Confusion: "{{data.get('discrepancy_reason')}}"
        {{line_items_str}}
        
        **Instructions:**
        1. Create a clear subject line that includes the PO number and asks for clarification.
        2. Write a short email body that states the point of confusion we have identified.
        3. Politely ask the supplier to provide more information to resolve the discrepancy.
        4. Sign off as 'Denicx Automation'.
        
        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        """
    elif scenario == "request_mtc":
        prompt = f"""
        Generate a professional and concise email to a supplier requesting the Material Test Certificate (MTC) for a purchase order.
        The tone should be polite and clear.
        
        **Details:**
        - Purchase Order Number: {data.get('po_number')}
        - Vendor Name: {data.get('vendor_name')}
        {line_items_str}
        
        **Instructions:**
        1. Create a clear subject line that includes the PO number and mentions the MTC request.
        2. Write a short email body politely reminding the supplier that an MTC is required for this order.
        3. Ask them to provide it at their earliest convenience.
        4. Sign off as 'Denicx Automation'.
        
        Return the result as a single, valid JSON object with two keys: "subject" and "body".
        """
    elif scenario == "vendor_no_response_followup":
        prompt = f"""
        Generate a concise follow-up email to the supplier when no response has been received.
        Tone should be firm and professional.

        Details:
        - Purchase Order Number: {data.get('po_number')}
        - Supplier Name: {data.get('supplier_name')}
        {line_items_str}

        Instructions:
        1. Subject should include the PO number and indicate a follow-up.
        2. Body should politely state that we are following up on our previous query and are awaiting a response.
        3. Keep it short and sign off as 'Denicx Automation'.

        Return a single JSON object: {{"subject": "...", "body": "..."}}
        """
    else:
        print(f"Unknown email scenario: {scenario}")
        return None

    llm_response = get_llm_generation(prompt)

    # Clean the response by stripping markdown fences and whitespace
    clean_response = llm_response.strip().replace('```json', '').replace('```', '').strip()

    # Extract the first JSON object if extra text is present
    if '{' in clean_response and '}' in clean_response:
        clean_response = clean_response[clean_response.find('{'):clean_response.rfind('}') + 1]

    # Remove invalid control characters (common issue with LLM outputs)
    clean_response = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", clean_response)

    try:
        email_content = json.loads(clean_response)
        if "subject" in email_content and "body" in email_content:
            return email_content
    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"Error processing LLM response for email generation: {e}")
        return None

    subject = _extract_json_string_value(clean_response, "subject")
    body = _extract_json_string_value(clean_response, "body")
    if subject is not None and body is not None:
        return {"subject": subject, "body": body}

    print("Error processing LLM response for email generation: Could not parse subject/body")
    return None