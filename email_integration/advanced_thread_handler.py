from bucket.po_bucket import get_po_state
from orchestration.processor import process_inbound_email
from rag.huggingface_handler import find_best_matching_po
from g_sheets.sheets_handler import get_active_pos_by_email, get_conversation_histories

def handle_unthreaded_reply(email_data):
    """
    Handles an unthreaded reply by finding the correct PO and re-establishing the thread.
    """
    sender_email = email_data['from']
    active_pos = get_active_pos_by_email(sender_email)

    if not active_pos:
        print(f"INFO: No active POs found for {sender_email}. Ignoring email.")
        return

    po_number = None
    if len(active_pos) == 1:
        po_number = active_pos[0]
    else:
        # Semantic Search for multiple active POs
        po_histories = get_conversation_histories(active_pos)
        email_content = f"Subject: {email_data['subject']}\n\n{email_data.get('body', '')}"
        po_number = find_best_matching_po(email_content, po_histories)

    if not po_number:
        print("WARNING: Could not determine a confident match for the email.")
        return

    # Re-establish the thread
    po_state = get_po_state(po_number)
    last_message_id = None
    if po_state and po_state.get('threads'):
        # Find the last message with a message_id
        for message in reversed(po_state['threads']):
            if message.get('message_id'):
                last_message_id = message.get('message_id')
                break

    process_inbound_email(
        from_sender=sender_email,
        subject=email_data.get('subject', ''),
        body=email_data.get('body', ''),
        po_number_hint=po_number,
        message_id=last_message_id,  # Use the last message_id to re-establish the thread
        references=last_message_id
    )
