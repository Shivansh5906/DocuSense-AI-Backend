from google import genai

client = genai.Client(http_options={'api_version': 'v1alpha'})

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="Who is Narendra Modi",
)

print(response.text)