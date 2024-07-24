import os
import fitz  # PyMuPDF
import re
from docx import Document


def clean_text(text):
    # Remove bullets and special characters
    text = re.sub(r'[\u2022\u2023\u25E6\u2043\u2219]', '', text)  # Remover bullets comuns
    #text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remover caracteres não ASCII
    #text = re.sub(r'\s+', ' ', text).strip()  # Remover múltiplos espaços
    return text

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
    clean_text_content = clean_text(resume_text)
    print(clean_text_content)

    # Remove the uploaded file after processing
    if os.path.exists(uploaded_file_path):
        os.remove(uploaded_file_path)

    return clean_text_content