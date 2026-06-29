import json
from pydantic import BaseModel, Field
from typing import List, Optional
from google.genai import types
from app.services.gemini_llm import client, generate_answer

# Pydantic models for structured output
class KeywordSuggestion(BaseModel):
    keyword: str = Field(description="The recommended keyword")
    frequency_in_resume: int = Field(description="How many times it appears in the resume")
    recommended_frequency: int = Field(description="Target frequency for ATS optimization")

class BulletRewrite(BaseModel):
    original: str = Field(description="The original weak or descriptive bullet point")
    suggested: str = Field(description="The suggested metrics-driven, action-oriented bullet point")
    rationale: str = Field(description="Explanation of why the suggestion is stronger (e.g., action verb used, metric added)")

class InterviewQuestion(BaseModel):
    section: str = Field(description="The section or job experience this question is based on")
    question: str = Field(description="The behavioral or technical question tailored to the experience")
    intent: str = Field(description="What the interviewer is trying to evaluate with this question")
    suggested_approach: str = Field(description="Suggested STAR-method approach or talking points for the candidate")

class FullResumeAnalysis(BaseModel):
    # Job Description Matching (Optional/Nullable if no JD is provided)
    match_percentage: Optional[float] = Field(default=None, description="Matching score between 0 and 100 based on JD. Set to null if no JD is provided.")
    matching_skills: List[str] = Field(default=[], description="Skills present in both resume and JD. Empty if no JD.")
    missing_skills: List[str] = Field(default=[], description="Critical skills requested in the JD but missing or weak in the resume. Empty if no JD.")
    strengths: List[str] = Field(default=[], description="List of candidate's key strengths corresponding to the JD. Empty if no JD.")
    jd_reasoning: Optional[str] = Field(default=None, description="Detailed explanation of the matching score and alignment. Set to null if no JD.")
    tailoring_recommendations: List[str] = Field(default=[], description="Suggestions to tailor the resume specifically for this JD. Empty if no JD.")

    # ATS Checker
    ats_score: float = Field(description="ATS friendliness score between 0 and 100")
    formatting_score: float = Field(description="Formatting and readability score between 0 and 100")
    keyword_density_score: float = Field(description="Keyword density score between 0 and 100")
    completeness_score: float = Field(description="Section completeness score between 0 and 100")
    detected_sections: List[str] = Field(description="List of detected sections (e.g. Summary, Experience, Education, Skills)")
    missing_sections: List[str] = Field(description="Crucial resume sections that are missing (e.g. Projects, Summary)")
    formatting_issues: List[str] = Field(description="Any issues found like tables, complex columns, graphics, fonts, headers/footers")
    keyword_suggestions: List[KeywordSuggestion] = Field(description="Suggestions for industry keywords to add or adjust frequency")

    # Interview Prep
    interview_questions: List[InterviewQuestion] = Field(description="List of 3-5 generated interview questions tailored to the resume content")

    # Rewrite Suggestions
    rewrite_suggestions: List[BulletRewrite] = Field(description="List of 3-5 weak bullet points from the resume rewritten into metrics-driven statements")


def run_resume_analysis(resume_text: str, jd_text: Optional[str] = None) -> FullResumeAnalysis:
    """
    Analyzes a resume (and optional Job Description) using Gemini structured output.
    """
    
    # Construct the instruction and prompts
    if jd_text and jd_text.strip():
        prompt = f"""
You are an expert technical recruiter and ATS evaluation system.
Analyze the following Resume/CV text against the provided Job Description (JD).

Job Description:
\"\"\"
{jd_text}
\"\"\"

Resume Text:
\"\"\"
{resume_text}
\"\"\"

Perform a deep analysis and fill in ALL fields in the response schema:
1. Compare skills, experience, and projects in the resume against the JD to calculate a matching score (0-100) and identify missing/matching skills, strengths, and recommendations.
2. Evaluate the resume for ATS compatibility (give scores for formatting, keyword density, completeness) and suggest keyword additions.
3. Generate 3-5 behavioral/technical interview questions based on the candidate's actual experience listed.
4. Identify 3-5 weak, descriptive, or task-oriented bullet points from the resume and rewrite them into strong, metrics-driven, action-oriented versions using industry standards (e.g., Google's X-Y-Z formula: Accomplished [X] as measured by [Y], by doing [Z]).
"""
    else:
        prompt = f"""
You are an expert technical recruiter and ATS evaluation system.
Analyze the following Resume/CV text. Since NO Job Description (JD) was provided, focus on a general resume critique.

Resume Text:
\"\"\"
{resume_text}
\"\"\"

Perform a deep analysis and fill in the response schema:
1. Keep JD-related fields (match_percentage, matching_skills, missing_skills, strengths, jd_reasoning, tailoring_recommendations) as null or empty lists as appropriate.
2. Evaluate the resume generally for ATS compatibility (give scores for formatting, keyword density, completeness) and suggest keyword additions.
3. Generate 3-5 behavioral/technical interview questions based on the candidate's actual experience listed.
4. Identify 3-5 weak, descriptive, or task-oriented bullet points from the resume and rewrite them into strong, metrics-driven, action-oriented versions using industry standards (e.g., Google's X-Y-Z formula: Accomplished [X] as measured by [Y], by doing [Z]).
"""

    import time
    import re

    def get_retry_delay(error_exception) -> float | None:
        try:
            err_msg = str(error_exception)
            match = re.search(r"Please retry in (\d+\.?\d*)s", err_msg)
            if match:
                return float(match.group(1)) + 1.0
        except Exception:
            pass
        return None

    import os
    tuned_model = os.getenv("TUNED_MODEL_ID")
    models = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    if tuned_model:
        models.insert(0, tuned_model)
        
    last_exception = None

    for model_name in models:
        for attempt in range(3):
            try:
                print(f"[RESUME ANALYZER] Attempting analysis using {model_name} (Attempt {attempt+1}/3)...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=FullResumeAnalysis,
                        temperature=0.2,  # Low temperature for more analytical/factual output
                    )
                )
                # Parse the response into our Pydantic model
                data = json.loads(response.text)
                return FullResumeAnalysis(**data)
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                
                # Check for rate limit or transient errors
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    sleep_time = (2 ** attempt) + 3.0
                    delay = get_retry_delay(e)
                    if delay is not None:
                        sleep_time = delay
                    
                    print(f"[RESUME ANALYZER] Rate limit or transient error on {model_name}. Waiting {sleep_time:.2f}s before retry...")
                    time.sleep(sleep_time)
                    continue
                
                # Permanent exceptions (e.g. invalid model/config) break to next model
                print(f"[RESUME ANALYZER] Permanent error on model {model_name}: {e}")
                break

    # If all fail, raise the last exception
    raise last_exception
