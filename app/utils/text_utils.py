import os
import fitz  # PyMuPDF
from docx import Document
from unstructured.partition.auto import partition


def extract_text_from_pdf(file_path: str) -> str:
    text = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text.append(page.get_text())
        return "\n".join(text)
    except Exception:
        # fallback for scanned / weird PDFs
        elements = partition(filename=file_path)
        return "\n".join([str(el) for el in elements])


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type")
