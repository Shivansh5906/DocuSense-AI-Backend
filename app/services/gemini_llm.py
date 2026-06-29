import os
from google import genai


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

import time
import re

def get_retry_delay(error_exception) -> float | None:
    try:
        err_msg = str(error_exception)
        # Extract the sleep delay if specified by the Gemini quota error
        match = re.search(r"Please retry in (\d+\.?\d*)s", err_msg)
        if match:
            return float(match.group(1)) + 1.0
    except Exception:
        pass
    return None

def generate_answer(prompt: str, models_to_try: list[str] = None) -> str:
    # Fallback chain for free tier users to bypass 429 quota exhaustion on a single model
    if not models_to_try:
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
    
    last_exception = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                
                # If rate limited (429) or overloaded/unavailable (503/500)
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    sleep_time = (2 ** attempt) + 2.0
                    delay_from_err = get_retry_delay(e)
                    if delay_from_err is not None:
                        sleep_time = delay_from_err
                        print(f"Gemini API rate limit hit for {model_name}. Waiting {sleep_time:.2f}s as requested by API...")
                    else:
                        print(f"Gemini API rate limit hit for {model_name}. Waiting {sleep_time:.2f}s before retry (Attempt {attempt+1}/3)...")
                    
                    time.sleep(sleep_time)
                    continue
                # Raise other configuration or API issues immediately
                raise e
                
        print(f"Model {model_name} failed all retries. Attempting fallback model...")
            
    # If all models in the fallback list fail
    raise last_exception

