from app.utils.text_utils import extract_text
from app.services.chunker import chunk_text
from app.services.vector_store import store_chunks


def load_document(file_path: str, filename: str):
    text = extract_text(file_path)

    if not text.strip():
        return {
            "characters_extracted": 0,
            "total_chunks": 0
        }

    chunks = chunk_text(text)

    store_chunks(chunks, filename)

    return {
        "characters_extracted": len(text),
        "total_chunks": len(chunks)
    }
