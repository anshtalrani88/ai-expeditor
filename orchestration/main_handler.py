from g_sheets import sheets_handler as db
from rag import pdf_parser, huggingface_handler

def triage_email(email_data):
    """
    First-level triage to decide if an email is a new PO or a follow-up.
    """
    if email_data.get('pdf_path'):
        handle_new_document(email_data)
    else:
        handle_follow_up(email_data)

def handle_new_document(email_data):
    """
    Handles emails with PDF attachments, validating if they are POs.
    """
    print(f"--- Handling potential new document from {email_data['from']} ---")
    is_po = pdf_parser.is_document_a_po(email_data['pdf_path'])

    if is_po:
        print(f"CONFIRMED: Attachment is a Purchase Order.")
        po_data = pdf_parser.parse_po_pdf(email_data['pdf_path'])
        if not po_data or not po_data.get('po_number'):
            print("WARNING: Could not extract a PO number from the PDF. Treating as follow-up.")
            handle_follow_up(email_data)
            return

        existing_po = db.get_purchase_order(po_data['po_number'])
        if existing_po:
            print(f"INFO: PO {po_data['po_number']} already exists. Treating attached PDF email as follow-up.")
            history_ws = db.setup_spreadsheet()[3]
            db.add_email_to_history(history_ws, po_data['po_number'], email_data)
            try:
                from orchestration.processor import process_inbound_email
                process_inbound_email(
                    from_sender=email_data['from'],
                    subject=email_data.get('subject', ''),
                    body=email_data.get('body', ''),
                    po_number_hint=po_data['po_number'],
                )
            except Exception as e:
                print(f"WARNING: Follow-up rule evaluation failed for {po_data['po_number']}: {e}")
            return

        # Extract sender name from 'from' field (e.g., "John Doe <john.doe@example.com>")
        from email.utils import parseaddr
        sender_name, sender_email = parseaddr(email_data['from'])
        recipient_name, recipient_email = parseaddr(email_data['to'])

        po_data['buyer_name'] = sender_name if sender_name else sender_email.split('@')[0]
        po_data['vendor_name'] = po_data.get('supplier_name', recipient_name if recipient_name else recipient_email.split('@')[0])

        initial_email_context = {
            'from': email_data['from'],
            'to': email_data['to'],
            'subject': email_data['subject'],
            'body': email_data.get('body', '')
        }
        created_po = db.create_po_bucket(po_data, initial_email_context)

        try:
            from bucket.po_bucket import append_thread
            append_thread(
                po_number=po_data.get('po_number'),
                direction="outbound",
                from_addr=sender_email,
                to_addr=recipient_email,
                subject=email_data.get('subject', ''),
                body=email_data.get('body', ''),
                labels=["initial_po_email", "to:supplier"],
            )
        except Exception as e:
            print(f"WARNING: Failed to log initial PO thread for {po_data.get('po_number')}: {e}")

        # Immediately evaluate rules for state-driven scenarios (e.g., missing delivery date)
        try:
            from orchestration.processor import process_system_check
            po_num = po_data.get('po_number') if po_data else None
            if po_num:
                process_system_check(po_num)
        except Exception as e:
            print(f"WARNING: Post-creation rule evaluation failed for {po_data.get('po_number')}: {e}")
    else:
        print(f"REJECTED: Attachment is not a Purchase Order.")
        handle_follow_up(email_data)

def handle_follow_up(email_data):
    """
    Handles emails without attachments, checking for replies or new threads from known entities.
    """
    print(f"--- Handling follow-up email from {email_data['from']} ---")
    sender_email = email_data['from'] # Simplified: assumes clean email address
    active_pos = db.get_active_pos_by_email(sender_email)

    if not active_pos:
        print(f"INFO: No active POs found for {sender_email}. Ignoring email.")
        return

    if len(active_pos) == 1:
        po_number = active_pos[0]
        print(f"INFO: Found one active PO ({po_number}) for {sender_email}. Appending to history.")
        history_ws = db.setup_spreadsheet()[3]
        db.add_email_to_history(history_ws, po_number, email_data)

        try:
            from orchestration.processor import process_inbound_email
            process_inbound_email(
                from_sender=sender_email,
                subject=email_data.get('subject', ''),
                body=email_data.get('body', ''),
                po_number_hint=po_number,
            )
        except Exception as e:
            print(f"WARNING: Follow-up rule evaluation failed for {po_number}: {e}")
    else:
        # Semantic Search for multiple active POs
        print(f"INFO: Found multiple active POs for {sender_email}. Performing semantic search...")
        po_histories = db.get_conversation_histories(active_pos)
        email_content = f"Subject: {email_data['subject']}\n\n{email_data.get('body', '')}"
        
        best_match_po = huggingface_handler.find_best_matching_po(email_content, po_histories)
        
        if best_match_po:
            print(f"SUCCESS: Email best matches PO {best_match_po}. Appending to history.")
            history_ws = db.setup_spreadsheet()[3]
            db.add_email_to_history(history_ws, best_match_po, email_data)

            try:
                from orchestration.processor import process_inbound_email
                process_inbound_email(
                    from_sender=sender_email,
                    subject=email_data.get('subject', ''),
                    body=email_data.get('body', ''),
                    po_number_hint=best_match_po,
                )
            except Exception as e:
                print(f"WARNING: Follow-up rule evaluation failed for {best_match_po}: {e}")
        else:
            print("WARNING: Could not determine a confident match for the email.")
