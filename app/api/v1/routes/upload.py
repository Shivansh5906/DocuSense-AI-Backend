from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks
import os
import shutil
import json
from pydantic import BaseModel

from app.services.document_loader import load_document
from app.api.v1.dependencies import get_current_user
from app.db.database import add_document, get_user_documents, update_document_status

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_and_index_document(file_path: str, filename: str, user_id: int):
    """Background task to extract text, generate embeddings, and index into ChromaDB."""
    try:
        print(f"[BACKGROUND LOADER] Starting background ingestion for {filename}...")
        load_document(file_path, filename, user_id)
        
        # Set status to completed
        from app.db.database import update_document_status
        update_document_status(user_id, filename, "completed")
        print(f"[BACKGROUND LOADER] Ingestion completed successfully for {filename}!")
    except Exception as e:
        print(f"[BACKGROUND LOADER] Error during ingestion for {filename}: {str(e)}")
        from app.db.database import save_document_summary_and_status
        save_document_summary_and_status(user_id, filename, str(e), "failed")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    print(f"\n[UPLOAD ROUTE] Received upload request for file: {file.filename} from user: {user_id}")
    
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{safe_filename}")

    print(f"[UPLOAD ROUTE] Saving file to {file_path}...")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    print(f"[UPLOAD ROUTE] File saved successfully.")

    # Record the document relation in SQLite DB with status 'indexing'
    add_document(user_id, safe_filename)

    # Queue background task to run ingestion (chunking, embeddings, ChromaDB write)
    background_tasks.add_task(load_and_index_document, file_path, safe_filename, user_id)

    return {
        "message": "File uploaded successfully and indexing started in the background",
        "filename": safe_filename,
        "status": "indexing"
    }


@router.get("")
async def list_documents(current_user: dict = Depends(get_current_user)):
    try:
        docs = get_user_documents(current_user["id"])
        # Sort documents by filename key
        docs_sorted = sorted(docs, key=lambda d: d["filename"])
        return {"documents": docs_sorted}
    except Exception as e:
        return {"documents": [], "error": str(e)}


class SuggestionsRequest(BaseModel):
    filename: str

@router.post("/suggestions")
async def get_document_suggestions(
    req: SuggestionsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Dynamically generates 3 basic suggested questions specific to the uploaded document context."""
    user_id = current_user["id"]
    safe_filename = os.path.basename(req.filename)

    # Check status
    docs = get_user_documents(user_id)
    doc_status = next((d["status"] for d in docs if d["filename"] == safe_filename), None)
    
    if doc_status != "completed":
        return {"suggestions": []}

    try:
        # Retrieve context from ChromaDB
        from app.services.vector_store import get_collection
        collection = get_collection()
        results = collection.get(
            where={"$and": [{"filename": safe_filename}, {"user_id": user_id}]},
            limit=4
        )
        chunks = results.get("documents", [])
        if not chunks:
            return {"suggestions": ["What is this document about?", "Give me a summary of this document."]}
            
        context = "\n".join(chunks[:4])

        prompt = f"""You are a helpful assistant.
Based on the following document context, generate exactly 3 simple, basic, and specific questions a user might want to ask about this document.
Keep each question short (under 10 words).
Return your response ONLY as a JSON list of strings. Do not include markdown formatting or extra text.

Context:
{context}

Response (JSON list of strings only):"""

        from app.services.gemini_llm import generate_answer
        res = generate_answer(prompt, models_to_try=["gemini-2.5-flash-lite"])
        
        # Parse JSON array safely
        clean_res = res.strip()
        if "```json" in clean_res:
            clean_res = clean_res.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_res:
            clean_res = clean_res.split("```")[1].split("```")[0].strip()
            
        suggestions = json.loads(clean_res)
        if isinstance(suggestions, list):
            return {"suggestions": suggestions[:3]}
    except Exception as e:
        print(f"[SUGGESTIONS ERROR] Failed to generate: {str(e)}")

    # Fallback basic suggestions
    return {
        "suggestions": [
            "What is this document about?",
            "What are the main takeaways?",
            "Summarize this document"
        ]
    }


@router.delete("/{filename}")
async def delete_document(
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    safe_filename = os.path.basename(filename)
    print(f"\n[DELETE ROUTE] Received delete request for document: {safe_filename} from user: {user_id}")

    # 1. Delete physical file from uploads folder
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{safe_filename}")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[DELETE ROUTE] Deleted physical file: {file_path}")
        except Exception as e:
            print(f"[DELETE ROUTE] Failed to delete file: {e}")

    # 2. Delete database records (document metadata and related chat logs)
    from app.db.database import delete_document_db
    delete_document_db(user_id, safe_filename)
    print(f"[DELETE ROUTE] Deleted SQLite records.")

    # 3. Delete vector embeddings from ChromaDB
    try:
        from app.services.vector_store import get_collection
        collection = get_collection()
        collection.delete(
            where={"$and": [{"filename": safe_filename}, {"user_id": user_id}]}
        )
        print(f"[DELETE ROUTE] Removed embeddings from ChromaDB.")
    except Exception as e:
        print(f"[DELETE ROUTE] Failed to delete from ChromaDB: {e}")

    return {"message": "Document deleted successfully", "filename": safe_filename}


