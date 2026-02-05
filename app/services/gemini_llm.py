import os
from google import genai


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

def generate_answer(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )

    return response.text.strip()
