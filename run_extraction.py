import os
from rag.file_processor import process_file

# This script is designed to be run from the root of the project directory

def extract_and_print(file_path):
    print(f"--- Analyzing content for: {os.path.basename(file_path)} ---")
    try:
        content = process_file(file_path)
        print(content)
    except Exception as e:
        print(f"An error occurred: {e}")
    print(f"--- End of content for: {os.path.basename(file_path)} ---\n")

if __name__ == "__main__":
    files_to_process = [
        "scenarios.docx",
        "PO-OG-201.pdf",
        "PO-OG-202.pdf",
        "PO-OG-203.pdf"
    ]

    for file_name in files_to_process:
        path = os.path.join(os.path.dirname(__file__), file_name)
        if os.path.exists(path):
            extract_and_print(path)
        else:
            print(f"File not found: {path}")
