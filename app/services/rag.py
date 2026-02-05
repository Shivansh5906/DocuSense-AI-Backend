from app.services.vector_store import get_collection
from app.services.embeddings import embed_texts
from app.services.gemini_llm import generate_answer
import re


def extract_candidate_name(chunks: list[str]) -> str | None:
    """
    Heuristic-based resume name extraction
    """
    for chunk in chunks[:5]:  
        lines = chunk.splitlines()
        for line in lines:
            clean = line.strip()
      
            if (
                2 <= len(clean.split()) <= 4
                and clean.replace(" ", "").isalpha()
                and clean.isupper()
            ):
                return clean.title()
    return None


def run_rag(question: str, top_k: int = 10) -> str:
    collection = get_collection()

 
    all_docs_raw = collection.get().get("documents", [])
    all_docs = []
    for group in all_docs_raw:
        all_docs.extend(group)

   
    if "name" in question.lower() and "candidate" in question.lower():
        name = extract_candidate_name(all_docs)
        if name:
            return name

    
    rewritten_question = f"""
Answer strictly from the uploaded document.

Question: {question}
"""

    question_embedding = embed_texts([rewritten_question])[0]

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]

    if not documents:
        return "Not found in the document"

    context = "\n\n".join(documents)

    prompt = f"""
You are a helpful AI assistant.

Use ONLY the information from the context below.
If the answer is not present, say "Not found in the document".

Context:
{context}

Question:
{question}

Answer:
"""

    return generate_answer(prompt)
