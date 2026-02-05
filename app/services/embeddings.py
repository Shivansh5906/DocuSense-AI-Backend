from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_texts(texts):
    return _model.encode(texts).tolist()
