import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from app.api.v1.dependencies import get_current_user
from app.db.database import (
    get_db_connection,
    get_user_documents,
    get_resume_by_document_id,
    add_resume,
    add_job_description,
    add_resume_analysis,
    get_analyses_for_user,
    get_analysis_by_id
)
from app.utils.text_utils import extract_text
from app.services.resume_analyzer import run_resume_analysis
from app.services.cover_letter_generator import generate_cover_letter_and_email

router = APIRouter(prefix="/resume", tags=["Resume Analyzer"])

class AnalyzeRequest(BaseModel):
    filename: str
    jd_text: Optional[str] = None
    jd_title: Optional[str] = None
    jd_company: Optional[str] = None

def get_document_id(user_id: int, filename: str) -> Optional[int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM documents WHERE user_id = ? AND filename = ?", (user_id, filename))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["id"]
    return None

@router.post("/analyze")
async def analyze_resume_endpoint(
    req: AnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    
    # 1. Verify document exists for this user and is indexing/completed
    doc_id = get_document_id(user_id, req.filename)
    if not doc_id:
        raise HTTPException(status_code=404, detail="Document not found for this user.")
        
    # Check if the physical file exists
    file_path = os.path.join("uploads", f"{user_id}_{req.filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical resume file not found.")

    try:
        # 2. Check if raw text of the resume is already parsed and stored in the database
        resume_record = get_resume_by_document_id(doc_id)
        if resume_record:
            resume_text = resume_record["raw_text"]
            resume_id = resume_record["id"]
        else:
            # Parse text and add resume to DB
            print(f"[API RESUME] Extracting text for new resume record...")
            resume_text = extract_text(file_path)
            
            # Simple heuristic for candidate name or let it be empty
            from app.services.rag import extract_candidate_name
            candidate_name = extract_candidate_name([resume_text[:2000]])
            
            resume_id = add_resume(
                document_id=doc_id,
                raw_text=resume_text,
                structured_skills=None,
                extracted_name=candidate_name
            )
            
        # 3. Add Job Description if provided
        jd_id = None
        if req.jd_text and req.jd_text.strip():
            print(f"[API RESUME] Storing job description: {req.jd_title} at {req.jd_company}...")
            jd_id = add_job_description(
                user_id=user_id,
                title=req.jd_title or "Untitled Role",
                company=req.jd_company or "Unknown Company",
                jd_text=req.jd_text
            )
            
        # 4. Run structured analysis using Gemini
        print(f"[API RESUME] Running Gemini analysis...")
        analysis = run_resume_analysis(resume_text, req.jd_text)
        
        # 5. Save the analysis reports to DB
        print(f"[API RESUME] Saving analysis reports to database...")
        analysis_id = add_resume_analysis(
            resume_id=resume_id,
            job_description_id=jd_id,
            match_score=analysis.match_percentage,
            reasoning_json=json.dumps(analysis.jd_reasoning) if analysis.jd_reasoning else json.dumps(None),
            gap_analysis_json=json.dumps({
                "matching_skills": analysis.matching_skills,
                "missing_skills": analysis.missing_skills,
                "strengths": analysis.strengths,
                "tailoring_recommendations": analysis.tailoring_recommendations
            }),
            ats_score=analysis.ats_score,
            ats_feedback_json=json.dumps({
                "formatting_score": analysis.formatting_score,
                "keyword_density_score": analysis.keyword_density_score,
                "completeness_score": analysis.completeness_score,
                "detected_sections": analysis.detected_sections,
                "missing_sections": analysis.missing_sections,
                "formatting_issues": analysis.formatting_issues,
                "keyword_suggestions": [k.model_dump() for k in analysis.keyword_suggestions]
            }),
            interview_questions_json=json.dumps([q.model_dump() for q in analysis.interview_questions]),
            rewrite_suggestions_json=json.dumps([r.model_dump() for r in analysis.rewrite_suggestions])
        )
        
        # Return the response structure
        return {
            "analysis_id": analysis_id,
            "filename": req.filename,
            "match_score": analysis.match_percentage,
            "reasoning": analysis.jd_reasoning,
            "gap_analysis": {
                "matching_skills": analysis.matching_skills,
                "missing_skills": analysis.missing_skills,
                "strengths": analysis.strengths,
                "tailoring_recommendations": analysis.tailoring_recommendations
            },
            "ats_report": {
                "ats_score": analysis.ats_score,
                "formatting_score": analysis.formatting_score,
                "keyword_density_score": analysis.keyword_density_score,
                "completeness_score": analysis.completeness_score,
                "detected_sections": analysis.detected_sections,
                "missing_sections": analysis.missing_sections,
                "formatting_issues": analysis.formatting_issues,
                "keyword_suggestions": [k.model_dump() for k in analysis.keyword_suggestions]
            },
            "interview_questions": [q.model_dump() for q in analysis.interview_questions],
            "rewrite_suggestions": [r.model_dump() for r in analysis.rewrite_suggestions]
        }
        
    except Exception as e:
        print(f"[API RESUME ERROR] Failed to perform analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during resume analysis: {str(e)}"
        )

@router.get("/history")
async def get_analysis_history(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    try:
        analyses = get_analyses_for_user(user_id)
        # Process and unpack JSON lists/dicts for the client
        result = []
        for a in analyses:
            result.append({
                "id": a["id"],
                "filename": a["filename"],
                "jd_title": a["jd_title"],
                "jd_company": a["jd_company"],
                "match_score": a["match_score"],
                "created_at": a["created_at"]
            })
        return {"history": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis/{analysis_id}")
async def get_analysis_details(
    analysis_id: int,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    try:
        a = get_analysis_by_id(analysis_id, user_id)
        if not a:
            raise HTTPException(status_code=404, detail="Analysis report not found.")
            
        return {
            "id": a["id"],
            "filename": a["filename"],
            "jd_title": a["jd_title"],
            "jd_company": a["jd_company"],
            "jd_text": a["jd_text"],
            "match_score": a["match_score"],
            "reasoning": json.loads(a["reasoning_json"]) if a["reasoning_json"] else None,
            "gap_analysis": json.loads(a["gap_analysis_json"]),
            "ats_report": json.loads(a["ats_feedback_json"]),
            "interview_questions": json.loads(a["interview_questions_json"]),
            "rewrite_suggestions": json.loads(a["rewrite_suggestions_json"]),
            "created_at": a["created_at"]
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CoverLetterRequest(BaseModel):
    filename: str
    jd_text: str
    jd_title: Optional[str] = None
    jd_company: Optional[str] = None
    tone: Optional[str] = "professional"

@router.post("/cover-letter")
async def generate_cover_letter_endpoint(
    req: CoverLetterRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    
    # 1. Verify document exists for this user
    doc_id = get_document_id(user_id, req.filename)
    if not doc_id:
        raise HTTPException(status_code=404, detail="Document not found for this user.")
        
    # Check if the physical file exists
    file_path = os.path.join("uploads", f"{user_id}_{req.filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical resume file not found.")

    try:
        # 2. Get raw resume text from DB or extract it
        resume_record = get_resume_by_document_id(doc_id)
        if resume_record:
            resume_text = resume_record["raw_text"]
        else:
            print(f"[COVER LETTER API] Extracting text for document {doc_id} on the fly...")
            resume_text = extract_text(file_path)
            # Cache the parsed resume in DB
            add_resume(doc_id, resume_text, "", None)

        # 3. Call the generator service
        result = generate_cover_letter_and_email(
            resume_text=resume_text,
            jd_text=req.jd_text,
            jd_title=req.jd_title,
            jd_company=req.jd_company,
            tone=req.tone
        )
        
        return {
            "cover_letter": result.cover_letter,
            "cold_email": result.cold_email
        }
    except Exception as e:
        print(f"[COVER LETTER API ERROR] Failed to generate cover letter: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during cover letter generation: {str(e)}"
        )
