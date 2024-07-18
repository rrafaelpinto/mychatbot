import os
import fitz  # PyMuPDF
from docx import Document


def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text


def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)


def process_resume(uploaded_file_path):
    file_ext = os.path.splitext(uploaded_file_path)[1].lower()
    if file_ext == '.pdf':
        resume_text = extract_text_from_pdf(uploaded_file_path)
    elif file_ext == '.docx':
        resume_text = extract_text_from_docx(uploaded_file_path)
    else:
        resume_text = ""
    print(resume_text)
    return resume_text