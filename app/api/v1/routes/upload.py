from fastapi import APIRouter, UploadFile, File
import os
import shutil

from app.services.document_loader import load_document

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

   
    ingestion_result = load_document(file_path, file.filename)

    return {
        "message": "File uploaded and indexed successfully",
        "filename": file.filename,
        **ingestion_result
    }
