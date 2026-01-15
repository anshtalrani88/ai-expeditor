import os
from huggingface_hub import InferenceClient
import requests

# --- IMPORTANT ---
# Please provide your Hugging Face API token here.
# You can get one from https://huggingface.co/settings/tokens
HUGGINGFACE_API_TOKEN = "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"

# Initialize the Inference Client for Llama 3.3
client = InferenceClient(token=HUGGINGFACE_API_TOKEN)

def get_huggingface_response(document_text: str, user_query: str) -> str:
    """
    Queries the Llama 3.3 model on Hugging Face with document context and a user question.

    Args:
        document_text: The content of the PO PDF.
        user_query: The supplier's question from their email.

    Returns:
        A string containing the model's answer.
    """
    if not HUGGINGFACE_API_TOKEN:
        return "Error: Hugging Face API token is not set. Please add your token to rag/huggingface_handler.py."

    # This prompt template is specific to Llama 3.3 Instruct models
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert purchasing assistant. Based on the following Purchase Order document and the user's query, provide a clear and concise answer. Do not repeat the question; just provide the answer.<|eot_id|><|start_header_id|>user<|end_header_id|>

**Purchase Order Document:**
---
{document_text}
---

**User's Query:**
\"{user_query}\"<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

    try:
        # Use the OpenAI-compatible chat.completions.create method
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            stream=False,
        )
        
        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "The model did not return a valid response."

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "Authentication Error: The Hugging Face API token is invalid or you have not accepted the model's license."
        elif e.response.status_code >= 500:
            return "Hugging Face Server Error: The model may be loading or unavailable. Please try again in a few moments."
        else:
            return f"An HTTP error occurred: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def find_best_matching_po(email_content: str, po_histories: dict) -> str:
    """
    Uses the LLM to find the best matching PO for a new email based on conversation history.

    Args:
        email_content: The text of the new email.
        po_histories: A dictionary where keys are PO numbers and values are their conversation histories.

    Returns:
        The PO number of the best match, or None.
    """
    formatted_histories = ""
    for po_number, history in po_histories.items():
        formatted_histories += f"--- PO_NUMBER: {po_number} ---\n{history}\n\n"

    prompt = f"""Based on the new email below, which of the following Purchase Order conversations is it most likely related to? 
    Respond with ONLY the PO_NUMBER (e.g., 'PO-OG-123') and nothing else. 
    If there is no clear match, respond with 'NONE'.

    **NEW EMAIL:**
    ---
    {email_content}
    ---

    **CONVERSATION HISTORIES:**
    {formatted_histories}
    """

    response = get_llm_generation(prompt)

    # Clean up the response to get only the PO number
    match = response.strip()
    if match in po_histories:
        return match
    return None

def get_llm_generation(prompt: str) -> str:
    """
    Gets a direct generation from the LLM based on a given prompt.

    Args:
        prompt: The full prompt to send to the model.

    Returns:
        A string containing the model's generated text.
    """
    if not HUGGINGFACE_API_TOKEN:
        return "Error: Hugging Face API token is not set."

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            stream=False,
        )
        
        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "The model did not return a valid response."

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "Authentication Error: The Hugging Face API token is invalid or you have not accepted the model's license."
        elif e.response.status_code >= 500:
            return "Hugging Face Server Error: The model may be loading or unavailable. Please try again in a few moments."
        else:
            return f"An HTTP error occurred: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"
