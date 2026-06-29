import json
import os
import time
import re
from pydantic import BaseModel, Field
from typing import Optional
from google.genai import types
from app.services.gemini_llm import client

class CoverLetterResponse(BaseModel):
    cover_letter: str = Field(
        description="A customized, formal cover letter tailored to the job description and the candidate's resume, structured in markdown."
    )
    cold_email: str = Field(
        description="A concise, high-impact cold email or LinkedIn outreach message (under 200 words) targeting the recruiter or hiring manager."
    )

def generate_cover_letter_and_email(
    resume_text: str,
    jd_text: str,
    jd_title: Optional[str] = None,
    jd_company: Optional[str] = None,
    tone: str = "professional"
) -> CoverLetterResponse:
    """
    Generates a cover letter and a cold email/LinkedIn message tailored to the candidate's resume
    and the target job description using Gemini.
    """
    
    prompt = f"""
You are an expert career coach and professional copywriter.
Generate a tailored Cover Letter and a high-impact Cold Email/LinkedIn Outreach message based on the candidate's Resume and the target Job Description (JD).

Company Name: {jd_company or "the target company"}
Job Title: {jd_title or "the target position"}
Preferred Tone: {tone}

Resume Text:
\"\"\"
{resume_text}
\"\"\"

Job Description Text:
\"\"\"
{jd_text}
\"\"\"

Guidelines for Cover Letter:
1. Format with placeholder fields (e.g. [Date], [Hiring Manager Name], [Your Address]) in clean markdown.
2. Align candidate's relevant skills and top accomplishments directly with the key requirements of the JD.
3. Keep the length professional (typically 3-4 paragraphs, under 400 words).
4. Maintain the specified tone ({tone}).

Guidelines for Cold Email / LinkedIn Outreach:
1. Must be concise (under 200 words) and hook the reader's attention immediately.
2. Include a clear, catchy subject line placeholder.
3. Keep it conversational but professional. Focus on how the candidate can add value to the team.

Fill in the response schema with the generated markdown content for both fields.
"""

    models = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    last_exception = None

    for model_name in models:
        for attempt in range(3):
            try:
                print(f"[COVER LETTER GENERATOR] Attempting generation using {model_name} (Attempt {attempt+1}/3)...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CoverLetterResponse,
                        temperature=0.7,  # Slightly higher temperature for creative writing
                    )
                )
                data = json.loads(response.text)
                return CoverLetterResponse(**data)
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    sleep_time = (2 ** attempt) + 2.0
                    time.sleep(sleep_time)
                    continue
                break
        print(f"[COVER LETTER GENERATOR] Model {model_name} failed. Trying fallback model...")

    raise last_exception if last_exception else ValueError("Failed to generate cover letter.")
