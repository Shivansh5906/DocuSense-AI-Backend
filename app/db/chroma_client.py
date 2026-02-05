import chromadb

client = chromadb.Client()
collection = client.get_or_create_collection("documents")

def get_chroma_collection():
    return collection
