"""
database.py
------------
PostgreSQL connection pool and table initialisation.
Uses psycopg2 with a simple connection pool.

Tables:
  documents — stores every generated document (word or excel)
"""

import os
import json
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

# ── Connection pool (min 1, max 10) ──────────────────────────────────────────
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "docforge"),
            user=os.getenv("POSTGRES_USER", "userap"),
            password=os.getenv("POSTGRES_PASSWORD", "appassword"),
        )
    return _pool


def get_conn():
    return get_pool().getconn()


def release_conn(conn):
    get_pool().putconn(conn)


# ── Table init ────────────────────────────────────────────────────────────────

def init_db():
    """
    Create the documents table if it doesn't exist.
    Call once at FastAPI startup.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id          SERIAL PRIMARY KEY,
                    title       TEXT NOT NULL,
                    doc_type    TEXT NOT NULL,          -- 'word' or 'excel'
                    doc_format  TEXT NOT NULL,
                    content     JSONB NOT NULL,         -- full generated content
                    file_bytes  BYTEA,                  -- exported .docx/.xlsx binary
                    file_ext    TEXT,                   -- 'docx' or 'xlsx'
                    created_at  TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()
    finally:
        release_conn(conn)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def save_document(title: str, doc_type: str, doc_format: str,
                  content: dict, file_bytes: bytes = None, file_ext: str = None) -> int:
    """
    Insert a document record. Returns the new document id.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (title, doc_type, doc_format, content, file_bytes, file_ext)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    title,
                    doc_type,
                    doc_format,
                    json.dumps(content),
                    psycopg2.Binary(file_bytes) if file_bytes else None,
                    file_ext,
                )
            )
            doc_id = cur.fetchone()[0]
            conn.commit()
            return doc_id
    finally:
        release_conn(conn)


def list_documents(limit: int = 50) -> list[dict]:
    """
    Return document history — metadata only, no heavy content/bytes.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, doc_type, doc_format, file_ext,
                       created_at,
                       LEFT(content::text, 200) AS preview_snippet
                FROM documents
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,)
            )
            rows = cur.fetchall()
            cols = ["id", "title", "doc_type", "doc_format",
                    "file_ext", "created_at", "preview_snippet"]
            return [dict(zip(cols, row)) for row in rows]
    finally:
        release_conn(conn)


def get_document(doc_id: int) -> dict | None:
    """
    Fetch a single document including full content and file bytes.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, doc_type, doc_format, content,
                       file_bytes, file_ext, created_at
                FROM documents
                WHERE id = %s
                """,
                (doc_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = ["id", "title", "doc_type", "doc_format", "content",
                    "file_bytes", "file_ext", "created_at"]
            doc = dict(zip(cols, row))
            # content is already a dict from JSONB
            if isinstance(doc["content"], str):
                doc["content"] = json.loads(doc["content"])
            # Convert memoryview → bytes
            if doc["file_bytes"] is not None:
                doc["file_bytes"] = bytes(doc["file_bytes"])
            return doc
    finally:
        release_conn(conn)


def delete_document(doc_id: int) -> bool:
    """Delete a document by id. Returns True if deleted."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
    finally:
        release_conn(conn)


# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# import os

# DATABASE_URL = os.getenv(
#     "DATABASE_URL",
#     "postgresql://userap:appassword@localhost:5432/docforge"
# )

# engine = create_engine(DATABASE_URL)

# SessionLocal = sessionmaker(
#     autocommit=False,
#     autoflush=False,
#     bind=engine
# )

# Base = declarative_base()


# # Dependency for FastAPI
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()