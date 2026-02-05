# 🧠 DocuSense AI – Backend

DocuSense AI Backend is the core service that powers intelligent document analysis, summarization, and question-answering using AI techniques.

This backend handles document ingestion, text processing, embeddings generation, and Retrieval Augmented Generation (RAG) to provide accurate answers based on uploaded documents.

---

## 🚀 Features

- 📄 Document upload and processing
- ✂️ Text extraction and chunking
- 🧠 AI-powered document summarization
- 🔍 Semantic search using vector embeddings
- 💬 Question Answering using RAG (Retrieval Augmented Generation)
- 🔗 REST APIs for frontend integration

---

## 🛠 Tech Stack

### Backend
- Python
- FastAPI / Flask *(whichever you used)*
- Uvicorn (ASGI server)

### AI & NLP
- Large Language Model (LLM)
- Embeddings model
- Vector Database (FAISS / Chroma)



*(Structure may vary slightly based on implementation)*

---

## ⚙️ How It Works (High-Level Flow)

1. User uploads a document from frontend  
2. Backend extracts and cleans text  
3. Text is split into chunks  
4. Embeddings are generated for each chunk  
5. Embeddings are stored in a vector database  
6. User asks a question  
7. Relevant chunks are retrieved  
8. LLM generates a contextual answer  

---

## ⚙️ Setup & Run Locally

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Shivansh5906/DocuSense-AI-Backend.git


cd DocuSense-AI-Backend


python -m venv venv

pip install -r requirements.txt

uvicorn main:app --reload

http://localhost:8000/docs


🔗 Frontend Integration

This backend is consumed by the DocuSense AI frontend for:

Document uploads

Summary generation

Chat-based question answering

👉 Frontend Repository:
https://github.com/Shivansh5906/DocuSense-AI-Frontend

📌 Use Cases

AI-powered document summarization

Intelligent search in PDFs and text files

Academic notes analysis

Enterprise document understanding

v🔒 Security Notes

Environment variables are stored in .env (not pushed to GitHub)

Vector database files are excluded via .gitignore

👨‍💻 Author

Shivansh Chitranshi
B.Tech CSE | Java Full Stack & AI Enthusiast

GitHub: https://github.com/Shivansh5906