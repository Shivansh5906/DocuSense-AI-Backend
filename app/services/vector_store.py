import chromadb
from chromadb.config import Settings

from app.services.embeddings import embed_texts

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "docusense_documents"


_client = None
_collection = None


def get_collection():
    global _client, _collection

    if _client is None:
        _client = chromadb.Client(
            Settings(
                persist_directory=CHROMA_DIR,
                anonymized_telemetry=False
            )
        )

    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME
        )

    return _collection


def store_chunks(chunks: list[str], filename: str):
    if not chunks:
        return

    embeddings = embed_texts(chunks)
    collection = get_collection()

    ids = [f"{filename}_{i}" for i in range(len(chunks))]

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids
    )
