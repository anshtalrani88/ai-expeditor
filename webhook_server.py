import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import base64
import re

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from orchestration.main_handler import triage_email

# --- Pydantic Models for Webhook Payload ---
class Attachment(BaseModel):
    filename: str
    content: str  # Base64 encoded content

class EmailWebhookPayload(BaseModel):
    from_sender: str = Field(..., alias='from')
    to: Optional[str] = ""
    subject: str
    body: Optional[str] = ""
    attachments: Optional[List[Attachment]] = None

app = FastAPI()
ATTACHMENT_DIR = os.path.join(PROJECT_ROOT, 'attachments')

@app.on_event("startup")
def on_startup():
    if not os.path.exists(ATTACHMENT_DIR):
        os.makedirs(ATTACHMENT_DIR)
    print("Server startup complete.")

@app.post("/webhook/email")
async def email_webhook(payload: EmailWebhookPayload):
    try:
        from_ = payload.from_sender
        to_ = payload.to or ""
        subject = payload.subject
        body = payload.body

        print(f'\n--- Received new email from "{from_}" with subject "{subject}" ---')

        # If there's a PDF attachment, save it so triage_email can treat it as a new PO document.
        pdf_path = None
        if payload.attachments:
            pdf_attachment = next((att for att in payload.attachments if att.filename.lower().endswith('.pdf')), None)
            if pdf_attachment:
                filename = pdf_attachment.filename
                filepath = os.path.join(ATTACHMENT_DIR, filename)
                
                try:
                    pdf_content = base64.b64decode(pdf_attachment.content)
                except base64.binascii.Error as e:
                    print(f"Error decoding base64 content for {filename}: {e}")
                    raise HTTPException(status_code=400, detail="Invalid base64 content in attachment")

                with open(filepath, "wb") as f:
                    f.write(pdf_content)
                print(f'Saved PDF attachment: {filename}')
                pdf_path = filepath

        email_data = {
            "from": from_,
            "to": to_,
            "subject": subject,
            "body": body or "",
            "pdf_path": pdf_path,
        }
        triage_email(email_data)
        return {"status": "processed", "attachment_saved": bool(pdf_path)}
    except Exception as e:
        print(f"An error occurred processing the webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    print("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
