import sys
import os

# Ensure the local project path is included
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("--- Running Conflict Diagnostic ---")

try:
    # Import the suspected conflicting libraries first
    print("Importing langchain and llama_index...")
    import langchain
    import llama_index
    print("Successfully imported langchain and llama_index.")

    # Now, attempt to use the google-genai library
    print("\nAttempting to use the google-genai library...")
    from rag.gemini_handler import get_gemini_response

    # This call will fail if the environment is corrupted
    response = get_gemini_response("test document", "test query")
    print(f"\nGemini Response: {response}")

    if "v1beta" in response:
        print("\n\033[91mConflict Confirmed: The 'v1beta' error was reproduced.\033[0m")
    else:
        print("\n\033[92mConflict Not Found: The API call succeeded.\033[0m")

except Exception as e:
    print(f"\n\033[91mAn error occurred during the test: {e}\033[0m")
