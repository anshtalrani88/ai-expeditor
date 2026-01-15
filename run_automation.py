from email_integration.email_receiver import fetch_and_process_emails
from orchestration.main_handler import triage_email
from orchestration.processor import process_system_check
from g_sheets.sheets_handler import list_active_po_numbers

_LAST_SYSTEM_CHECK_TS = 0.0

def main_workflow_loop():
    """
    The main orchestration loop for the intelligent email automation workflow.
    """
    print("Starting intelligent automation workflow...")
    
    # Fetch all unread emails and categorize them by their content
    all_new_emails = fetch_and_process_emails()
    
    if not all_new_emails:
        print("No new emails to process.")
    else:
        for email_data in all_new_emails:
            try:
                triage_email(email_data)
            except Exception as e:
                print(f"WARNING: Failed to process inbound email: {e}")

    global _LAST_SYSTEM_CHECK_TS
    now_ts = __import__("time").time()
    if (now_ts - _LAST_SYSTEM_CHECK_TS) >= 60.0:
        _LAST_SYSTEM_CHECK_TS = now_ts
        try:
            active_pos = list_active_po_numbers()
            for po in active_pos:
                process_system_check(po)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Quota exceeded" in msg:
                _LAST_SYSTEM_CHECK_TS = now_ts + 180.0
            print(f"WARNING: Periodic system checks failed: {e}")
            
    print("\nIntelligent automation workflow run complete.")

if __name__ == "__main__":
    import time
    while True:
        main_workflow_loop()
        print("--- Waiting for 15 seconds before next check ---")
        time.sleep(15)
