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
        print("    [VECTOR STORE] Initializing ChromaDB PersistentClient...")
        _client = chromadb.Client(
            Settings(
                persist_directory=CHROMA_DIR,
                anonymized_telemetry=False
            )
        )
        print("    [VECTOR STORE] ChromaDB PersistentClient initialized.")

    if _collection is None:
        print(f"    [VECTOR STORE] Getting or creating collection '{COLLECTION_NAME}'...")
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME
        )
        print(f"    [VECTOR STORE] Collection '{COLLECTION_NAME}' ready.")

    return _collection


def store_chunks(chunks: list[dict], filename: str, user_id: int):
    if not chunks:
        print("    [VECTOR STORE] No chunks to store.")
        return

    documents = [c["text"] for c in chunks]

    print(f"    [VECTOR STORE] Embedding {len(chunks)} text chunks in parallel...")
    from app.services.embeddings import embed_texts_parallel
    embeddings = embed_texts_parallel(documents)
    print("    [VECTOR STORE] Text embeddings generated successfully.")

    print("    [VECTOR STORE] Retrieving ChromaDB collection...")
    collection = get_collection()

    # User-scoped IDs to prevent cross-user document overwrites
    ids = [f"{user_id}_{filename}_{i}" for i in range(len(chunks))]
    
    metadatas = []
    for c in chunks:
        meta = {"filename": filename, "user_id": user_id}
        if "metadata" in c:
            meta.update(c["metadata"])
        metadatas.append(meta)

    print(f"    [VECTOR STORE] Writing {len(chunks)} documents to ChromaDB...")
    collection.add(
        documents=documents,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas
    )
    print("    [VECTOR STORE] Documents written successfully.")
