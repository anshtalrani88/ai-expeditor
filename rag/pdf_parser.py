import json
import re
from datetime import datetime, timedelta
from rag.huggingface_handler import get_llm_generation
from rag.file_processor import process_file

def is_document_a_po(pdf_path: str) -> bool:
    """
    Uses an LLM to classify if the text from a PDF is a purchase order.
    """
    document_text = process_file(pdf_path)
    if not document_text or len(document_text) < 50: # Basic sanity check
        return False

    prompt = f"""Does the following text represent a Purchase Order? Answer only with a single word: YES or NO.

    --- TEXT ---
    {document_text[:2000]} # Use a snippet for efficiency
    --- END TEXT ---
    """
    response = get_llm_generation(prompt)
    return "yes" in response.lower()

def parse_po_pdf(pdf_path: str):
    """
    Processes a PO PDF and extracts structured details using an LLM.
    Returns a dictionary with the extracted data or None.
    """
    try:
        document_text = process_file(pdf_path)
        if not document_text:
            return None

        prompt = f"""From the following purchase order text, extract the following information in a valid JSON format:
        - po_number (string)
        - supplier_name (string)
        - expected_delivery_date (string, in YYYY-MM-DD format)
        - line_items (an array of objects, each with 'description', 'quantity' (integer), and 'unit_price' (string))
        - mtc_needed (boolean, true if a Material Test Certificate or MTC is mentioned as required, otherwise false)

        **Purchase Order Document:**
        ---
        {document_text}
        ---

        **JSON Output:**
        """

        llm_response = get_llm_generation(prompt)

        try:
            # Use regex to find the JSON block, even if it's surrounded by text
            json_match = re.search(r'```json\n(.*?)```', llm_response, re.DOTALL)
            if json_match:
                clean_response = json_match.group(1).strip()
            else:
                # Fallback for when the LLM doesn't use markdown fences
                clean_response = llm_response[llm_response.find('{'):llm_response.rfind('}')+1]

            po_data = json.loads(clean_response)

            # expected_delivery_date may be absent or malformed; set None in that case
            edd_raw = po_data.get('expected_delivery_date')
            if edd_raw:
                try:
                    parsed_edd = datetime.strptime(edd_raw, '%Y-%m-%d')
                    now = datetime.now()
                    if parsed_edd < (now - timedelta(days=365 * 2)) or parsed_edd > (now + timedelta(days=365 * 5)):
                        po_data['expected_delivery_date'] = None
                    else:
                        po_data['expected_delivery_date'] = parsed_edd
                except Exception:
                    po_data['expected_delivery_date'] = None
            else:
                po_data['expected_delivery_date'] = None

            return po_data
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
            print(f"Error: LLM did not return valid, complete JSON. Error: {e}\nResponse:\n{llm_response}")
            return None

    except Exception as e:
        print(f"An unexpected error occurred during PDF parsing: {e}")
        return None
