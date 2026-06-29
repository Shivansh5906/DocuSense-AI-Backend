import os
import fitz  # PyMuPDF
from docx import Document


def extract_text_from_pdf(file_path: str) -> str:
    text = []
    try:
        print(f"    [TEXT UTILS] Attempting PyMuPDF (fitz) text extraction for: {file_path}...")
        doc = fitz.open(file_path)
        for page in doc:
            text.append(page.get_text())
        print(f"    [TEXT UTILS] PyMuPDF extraction successful. Extracted {len(doc)} pages.")
        return "\n".join(text)
    except Exception as e:
        print(f"    [TEXT UTILS] PyMuPDF failed with error: {e}. Falling back to unstructured partition...")
        print(f"    [TEXT UTILS] Running unstructured.partition on {file_path} (this can take a long time on first run)...")
        from unstructured.partition.auto import partition
        elements = partition(filename=file_path)
        print(f"    [TEXT UTILS] Unstructured partition finished. Extracted {len(elements)} elements.")
        return "\n".join([str(el) for el in elements])



def extract_text_from_docx(file_path: str) -> str:
    print(f"    [TEXT UTILS] Extracting Word document contents for: {file_path}...")
    doc = Document(file_path)
    text = "\n".join(p.text for p in doc.paragraphs)
    print(f"    [TEXT UTILS] Word document extraction successful.")
    return text


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    print(f"    [TEXT UTILS] Detected file extension: {ext}")

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type")
