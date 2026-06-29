from typing import List
import re
import math

def detect_section(sentence: str, current_section: str) -> str:
    """
    Heuristically detects if the sentence is a resume/CV section header.
    Returns the updated section name or the current section name.
    """
    clean = sentence.strip().lower().replace(":", "").replace("-", "").strip()
    
    sections_map = {
        "education": "education",
        "academic history": "education",
        "experience": "experience",
        "work experience": "experience",
        "professional experience": "experience",
        "employment history": "experience",
        "work history": "experience",
        "skills": "skills",
        "technical skills": "skills",
        "expertise": "skills",
        "projects": "projects",
        "personal projects": "projects",
        "academic projects": "projects",
        "certifications": "certifications",
        "awards": "certifications",
        "achievements": "certifications",
        "summary": "summary",
        "professional summary": "summary",
        "objective": "summary",
        "languages": "languages",
        "publications": "publications"
    }
    
    if len(clean.split()) <= 4:
        for kw, sec in sections_map.items():
            if clean == kw:
                return sec
    return current_section

def chunk_text(text: str, threshold: float = 0.70, min_size: int = 200, max_size: int = 1200) -> List[dict]:
    """
    Splits document text into chunks semantically based on topic transitions
    and tags each chunk with its corresponding resume section metadata.
    Returns a list of dicts: {"text": str, "metadata": {"section": str}}
    """
    if not text or not text.strip():
        return []
        
    # Split text into sentences/lines (matching periods or newline boundaries)
    sentence_end = re.compile(r'(?:(?<=[.?!])\s+|\n+)')
    sentences = [s.strip() for s in sentence_end.split(text) if s.strip()]
    
    if not sentences:
        return []
        
    if len(sentences) == 1:
        return [{
            "text": sentences[0],
            "metadata": {"section": detect_section(sentences[0], "general")}
        }]
        
    # Detect sections for all sentences
    current_section = "general"
    sentence_sections = []
    for s in sentences:
        current_section = detect_section(s, current_section)
        sentence_sections.append(current_section)
        
    # Fetch embeddings in parallel using the parallel embedding utility
    from app.services.embeddings import embed_texts_parallel
    embeddings = embed_texts_parallel(sentences)
    
    # Calculate cosine similarities between consecutive sentences
    similarities = []
    for i in range(len(sentences) - 1):
        u = embeddings[i]
        v = embeddings[i+1]
        dot = sum(a * b for a, b in zip(u, v))
        norm_u = math.sqrt(sum(a * a for a in u))
        norm_v = math.sqrt(sum(b * b for b in v))
        sim = dot / (norm_u * norm_v) if norm_u > 0 and norm_v > 0 else 0.0
        similarities.append(sim)
        
    chunks = []
    current_chunk = []
    current_len = 0
    current_chunk_start_idx = 0
    
    for idx, sentence in enumerate(sentences):
        # Handle exceptionally long sentences
        if len(sentence) > max_size:
            if current_chunk:
                chunks.append({
                    "text": " ".join(current_chunk),
                    "metadata": {"section": sentence_sections[current_chunk_start_idx]}
                })
                current_chunk = []
                current_len = 0
            # Split long sentence character-wise safely
            for j in range(0, len(sentence), max_size - 150):
                chunks.append({
                    "text": sentence[j:j + max_size],
                    "metadata": {"section": sentence_sections[idx]}
                })
            continue
            
        # Start new chunk if current is empty
        if not current_chunk:
            current_chunk.append(sentence)
            current_len = len(sentence)
            current_chunk_start_idx = idx
            continue
            
        # Transition similarity is the similarity between sentence[idx-1] and sentence[idx]
        sim = similarities[idx-1]
        
        potential_len = current_len + 1 + len(sentence)
        
        should_split = False
        # Force split if transition to a new resume section
        prev_sec = sentence_sections[idx-1]
        curr_sec = sentence_sections[idx]
        if curr_sec != prev_sec:
            should_split = True
        # Split if topic transitions (similarity below threshold) AND we have context of minimum size
        elif sim < threshold and current_len >= min_size:
            should_split = True
        # Or split if adding this sentence exceeds the maximum size allowed
        elif potential_len > max_size:
            should_split = True
            
        if should_split:
            chunks.append({
                "text": " ".join(current_chunk),
                "metadata": {"section": sentence_sections[current_chunk_start_idx]}
            })
            current_chunk = [sentence]
            current_len = len(sentence)
            current_chunk_start_idx = idx
        else:
            current_chunk.append(sentence)
            current_len = potential_len
            
    if current_chunk:
        chunks.append({
            "text": " ".join(current_chunk),
            "metadata": {"section": sentence_sections[current_chunk_start_idx]}
        })
        
    return chunks
