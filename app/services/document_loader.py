import json
import time
from pydantic import BaseModel, Field
from google.genai import types
from app.services.gemini_llm import client
from app.utils.text_utils import extract_text
from app.services.chunker import chunk_text
from app.services.vector_store import store_chunks

class DocumentValidation(BaseModel):
    is_resume_or_cv: bool = Field(
        description="True if the document is a Resume, CV, or Professional Profile. False if it is a marksheet, transcript, certificate, invoice, exam admit card, utility bill, syllabus, book, or other document."
    )
    reason: str = Field(
        description="A brief explanation of why the document is classified this way (e.g., 'The document is an academic marksheet listing subjects and marks obtained' or 'The document is a professional resume')."
    )

def is_resume_or_cv(text: str) -> tuple[bool, str]:
    """
    Verifies if the extracted text belongs to a resume or CV using a hybrid approach:
    1. Local check for empty or extremely short text.
    2. High-confidence local rejections (e.g., marksheets, transcripts, invoices).
    3. Positive indicators scan to ensure general structure is present.
    4. Gemini LLM structured output classification as the final check for ambiguous files.
    """
    if not text or not text.strip():
        return False, "The document text is empty."

    if len(text) < 150:
        return False, "The document is too short to be a valid Resume or CV."

    text_lower = text.lower()

    # 1. High-confidence local rejections
    rejection_keywords = [
        "mark sheet", "marksheet", "transcript of academic", "academic transcript",
        "grade sheet", "grade card", "report card", "marks obtained",
        "maximum marks", "subject code", "admit card", "hall ticket",
        "examination ticket", "roll number", "roll no", "invoice", "receipt",
        "purchase order", "passport application", "visa application",
        "boarding pass", "utility bill"
    ]
    for kw in rejection_keywords:
        if kw in text_lower:
            return False, f"The document is identified as a non-resume ({kw}). Please upload a valid Resume/CV."

    # 2. Local positive checks
    resume_indicators = [
        "experience", "work history", "employment", "professional experience",
        "education", "academic", "skills", "technologies", "expertise",
        "projects", "publications", "certifications", "achievements",
        "contact info", "resume", "curriculum vitae", "c.v."
    ]
    matches = [kw for kw in resume_indicators if kw in text_lower]
    if len(matches) < 2:
        return False, "The document does not contain standard resume sections (e.g., Education, Experience, Skills)."

    # 3. Gemini LLM structured check for final classification
    print("  [LOADER] Heuristics passed. Running Gemini LLM classification for final check...")
    prompt = f"""
    Analyze the following text extracted from a document. Determine if this document is a Resume, Curriculum Vitae (CV), or Professional Profile.
    Note: Academic marksheets, grade reports, certificates, transcripts, invoices, syllabus outlines, books, letters, and exam tickets are NOT resumes.

    Text:
    \"\"\"
    {text[:4000]}
    \"\"\"
    """

    models = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    last_exception = None

    for model_name in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DocumentValidation,
                        temperature=0.1,
                    )
                )
                data = json.loads(response.text)
                validation = DocumentValidation(**data)
                return validation.is_resume_or_cv, validation.reason
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    time.sleep(1.0)
                    continue
                break
        print(f"[LOADER] Model {model_name} failed. Trying fallback model...")

    print(f"[LOADER] LLM validation call failed: {last_exception}. Falling back to heuristic result.")
    # Fallback to local heuristic since it passed rejection/positive tests
    return True, "Passed local heuristic checks."

def load_document(file_path: str, filename: str, user_id: int):
    print(f"  [LOADER] Starting text extraction from: {file_path}...")
    text = extract_text(file_path)
    print(f"  [LOADER] Text extraction complete. Total characters: {len(text)}")

    if not text.strip():
        print(f"  [LOADER] REJECTED: Extracted text is empty or whitespace-only!")
        raise ValueError("No text could be extracted from the document. Please ensure the document is a text-based PDF/Word file and not a scanned image or photo.")

    # Verify if document is a Resume or CV
    print(f"  [LOADER] Verifying if document is a Resume/CV...")
    is_valid, reason = is_resume_or_cv(text)
    if not is_valid:
        print(f"  [LOADER] REJECTED: {reason}")
        raise ValueError(reason)
    print(f"  [LOADER] PASSED: {reason}")

    print(f"  [LOADER] Chunking text...")
    chunks = chunk_text(text)
    print(f"  [LOADER] Chunking complete. Total chunks: {len(chunks)}")

    print(f"  [LOADER] Storing chunks in vector database...")
    store_chunks(chunks, filename, user_id)
    print(f"  [LOADER] Storage complete.")

    return {
        "characters_extracted": len(text),
        "total_chunks": len(chunks)
    }
