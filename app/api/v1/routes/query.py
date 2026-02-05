from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag import run_rag

router = APIRouter(tags=["Query"])


class QueryRequest(BaseModel):
    question: str


@router.post("/query")
async def query_document(request: QueryRequest):
    answer = run_rag(request.question)
    return {
        "question": request.question,
        "answer": answer
    }
