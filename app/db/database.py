import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docusense.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        reset_token TEXT,
        reset_token_expires TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create documents table (with status tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        status TEXT DEFAULT 'indexing',
        summary TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN summary TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Create chats table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        is_general INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Create resumes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL UNIQUE,
        raw_text TEXT NOT NULL,
        structured_skills TEXT,
        extracted_name TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)

    # Create job_descriptions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_descriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT,
        company TEXT,
        jd_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Create resume_analyses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resume_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id INTEGER NOT NULL,
        job_description_id INTEGER,
        match_score REAL,
        reasoning_json TEXT,
        gap_analysis_json TEXT,
        ats_score REAL,
        ats_feedback_json TEXT,
        interview_questions_json TEXT,
        rewrite_suggestions_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
        FOREIGN KEY (job_description_id) REFERENCES job_descriptions(id) ON DELETE SET NULL
    )
    """)
    
    conn.commit()
    conn.close()
    print("[DATABASE] SQLite database initialized successfully.")

# User CRUD Operations
def create_user(name: str, email: str, password_hash: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email.lower().strip(), password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"id": user_id, "name": name, "email": email}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(email: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_user_reset_token(email: str, token: str | None, expires: str | None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE email = ?",
        (token, expires, email.lower().strip())
    )
    conn.commit()
    conn.close()

def get_user_by_reset_token(token: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE reset_token = ?",
        (token,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_user_password(user_id: int, password_hash: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE id = ?",
        (password_hash, user_id)
    )
    conn.commit()
    conn.close()

# Document operations
def add_document(user_id: int, filename: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if duplicate exists for this user
    cursor.execute("SELECT id FROM documents WHERE user_id = ? AND filename = ?", (user_id, filename))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO documents (user_id, filename, status) VALUES (?, ?, 'indexing')",
            (user_id, filename)
        )
        conn.commit()
    else:
        # If it was uploaded previously, reset status to indexing for re-indexing
        cursor.execute(
            "UPDATE documents SET status = 'indexing' WHERE user_id = ? AND filename = ?",
            (user_id, filename)
        )
        conn.commit()
    conn.close()

def update_document_status(user_id: int, filename: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET status = ? WHERE user_id = ? AND filename = ?",
        (status, user_id, filename)
    )
    conn.commit()
    conn.close()

def save_document_summary_and_status(user_id: int, filename: str, summary: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET summary = ?, status = ? WHERE user_id = ? AND filename = ?",
        (summary, status, user_id, filename)
    )
    conn.commit()
    conn.close()

def get_document_summary(user_id: int, filename: str) -> str | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT summary FROM documents WHERE user_id = ? AND filename = ?",
        (user_id, filename)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["summary"]
    return None

def get_user_documents(user_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, status FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Chat Operations
def add_chat_message(user_id: int, filename: str | None, role: str, text: str, is_general: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chats (user_id, filename, role, text, is_general) VALUES (?, ?, ?, ?, ?)",
        (user_id, filename, role, text, is_general)
    )
    conn.commit()
    conn.close()

def get_chat_history(user_id: int, filename: str | None) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if filename:
        cursor.execute(
            "SELECT role, text, is_general FROM chats WHERE user_id = ? AND filename = ? ORDER BY created_at ASC",
            (user_id, filename)
        )
    else:
        cursor.execute(
            "SELECT role, text, is_general FROM chats WHERE user_id = ? AND filename IS NULL ORDER BY created_at ASC",
            (user_id,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def clear_chat_history(user_id: int, filename: str | None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if filename:
        cursor.execute("DELETE FROM chats WHERE user_id = ? AND filename = ?", (user_id, filename))
    else:
        cursor.execute("DELETE FROM chats WHERE user_id = ? AND filename IS NULL", (user_id,))
    conn.commit()
    conn.close()

def delete_document_db(user_id: int, filename: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete from chats
    cursor.execute("DELETE FROM chats WHERE user_id = ? AND filename = ?", (user_id, filename))
    # Delete from documents
    cursor.execute("DELETE FROM documents WHERE user_id = ? AND filename = ?", (user_id, filename))
    conn.commit()
    conn.close()

# Resume specific database operations
def add_resume(document_id: int, raw_text: str, structured_skills: str | None = None, extracted_name: str | None = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO resumes (document_id, raw_text, structured_skills, extracted_name) VALUES (?, ?, ?, ?)",
        (document_id, raw_text, structured_skills, extracted_name)
    )
    conn.commit()
    resume_id = cursor.lastrowid
    conn.close()
    return resume_id

def get_resume_by_document_id(document_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resumes WHERE document_id = ?", (document_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def add_job_description(user_id: int, title: str | None, company: str | None, jd_text: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO job_descriptions (user_id, title, company, jd_text) VALUES (?, ?, ?, ?)",
        (user_id, title, company, jd_text)
    )
    conn.commit()
    jd_id = cursor.lastrowid
    conn.close()
    return jd_id

def add_resume_analysis(
    resume_id: int,
    job_description_id: int | None,
    match_score: float | None,
    reasoning_json: str,
    gap_analysis_json: str,
    ats_score: float,
    ats_feedback_json: str,
    interview_questions_json: str,
    rewrite_suggestions_json: str
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO resume_analyses (
            resume_id, job_description_id, match_score, reasoning_json, gap_analysis_json,
            ats_score, ats_feedback_json, interview_questions_json, rewrite_suggestions_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resume_id, job_description_id, match_score, reasoning_json, gap_analysis_json,
            ats_score, ats_feedback_json, interview_questions_json, rewrite_suggestions_json
        )
    )
    conn.commit()
    analysis_id = cursor.lastrowid
    conn.close()
    return analysis_id

def get_analyses_for_user(user_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ra.*, d.filename, jd.title as jd_title, jd.company as jd_company, jd.jd_text
        FROM resume_analyses ra
        JOIN resumes r ON ra.resume_id = r.id
        JOIN documents d ON r.document_id = d.id
        LEFT JOIN job_descriptions jd ON ra.job_description_id = jd.id
        WHERE d.user_id = ?
        ORDER BY ra.created_at DESC
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_analysis_by_id(analysis_id: int, user_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ra.*, d.filename, jd.title as jd_title, jd.company as jd_company, jd.jd_text, r.raw_text as resume_text
        FROM resume_analyses ra
        JOIN resumes r ON ra.resume_id = r.id
        JOIN documents d ON r.document_id = d.id
        LEFT JOIN job_descriptions jd ON ra.job_description_id = jd.id
        WHERE ra.id = ? AND d.user_id = ?
        """,
        (analysis_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

