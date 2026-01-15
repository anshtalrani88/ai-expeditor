import os
import magic
from pypdf import PdfReader
from docx import Document

UPLOAD_DIR = "docs"

def get_file_type(file_path):
    mime = magic.Magic(mime=True)
    return mime.from_file(file_path)

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def process_file(file_path):
    file_type = get_file_type(file_path)
    if file_type == "application/pdf":
        return extract_text_from_pdf(file_path)
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return extract_text_from_docx(file_path)
    else:
        return "Unsupported file type"
