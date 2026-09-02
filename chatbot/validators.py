import zipfile
from pathlib import Path

from django.core.exceptions import ValidationError

MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_SIZE = 20 * 1024 * 1024
MAX_DOCX_ENTRIES = 1000
PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
ALLOWED_CONTENT_TYPES = {
    PDF_CONTENT_TYPE,
    DOCX_CONTENT_TYPE,
    "application/octet-stream",
}


def detect_document_type(uploaded_file) -> str:
    """Validate file signature and return the normalized MIME type."""
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(8)
        uploaded_file.seek(0)
        if header.startswith(b"%PDF-"):
            return PDF_CONTENT_TYPE
        if header.startswith(b"PK"):
            try:
                with zipfile.ZipFile(uploaded_file) as archive:
                    entries = archive.infolist()
                    if (
                        len(entries) > MAX_DOCX_ENTRIES
                        or sum(entry.file_size for entry in entries)
                        > MAX_DOCX_UNCOMPRESSED_SIZE
                    ):
                        raise ValidationError(
                            "The DOCX archive expands beyond safe limits."
                        )
                    names = {entry.filename for entry in entries}
                    if {"[Content_Types].xml", "word/document.xml"} <= names:
                        return DOCX_CONTENT_TYPE
            except (OSError, zipfile.BadZipFile):
                pass
        raise ValidationError("Upload a valid PDF or DOCX document.")
    finally:
        uploaded_file.seek(position)


def validate_candidate_document(uploaded_file) -> None:
    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError("Documents must be 5 MB or smaller.")

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValidationError("Only PDF and DOCX documents are supported.")

    claimed_type = getattr(uploaded_file, "content_type", "")
    if claimed_type and claimed_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("The uploaded document has an unsupported content type.")

    detected_type = detect_document_type(uploaded_file)
    expected_type = PDF_CONTENT_TYPE if suffix == ".pdf" else DOCX_CONTENT_TYPE
    if detected_type != expected_type:
        raise ValidationError(
            "The filename extension does not match the document content."
        )
