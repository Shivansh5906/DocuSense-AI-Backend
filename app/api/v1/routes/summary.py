from fastapi import APIRouter
from pydantic import BaseModel
import os



router = APIRouter(prefix="/summary", tags=["Summary"])

UPLOAD_DIR = "uploads"

# Existing endpoint (keep)
@router.get("/")
def summary():
    return {"message": "Summary endpoint"}

# NEW: Auto summary after upload
class SummaryRequest(BaseModel):
    filename: str

@router.post("/auto")
def auto_summary(req: SummaryRequest):
    file_path = os.path.join(UPLOAD_DIR, req.filename)

    if not os.path.exists(file_path):
        return {"error": "File not found"}

    result = generate_document_summary(file_path)
    return result
