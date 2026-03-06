import io
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response

from backend.services.planner_agent import plan_document
from backend.services.question_agent import generate_questions
from backend.services.generator_agent import generate_document_sections
from backend.services.excel_generator_agent import generate_excel_sections, refine_excel_section
from backend.services.refinement_agent import refine_section
from backend.services.excel_exporter import generate_excel_file
from backend.services.notion_service import push_to_notion, update_notion_page
from backend.database import init_db, save_document, list_documents, get_document, delete_document, list_versions_by_id, delete_all_versions, get_latest_version
from backend.services.redis_service import redis_svc
from backend.services.redis_service import redis_svc, ThrottleExceeded

log = logging.getLogger(__name__)
app = FastAPI()


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()
    status = redis_svc.status()
    log.info(status["message"])


# ── Plan ──────────────────────────────────────────────────────────────────────

@app.post("/plan")
def plan(payload: dict):
    prompt = payload["prompt"]

    # Dedupe: same prompt within 5 min returns cached plan
    cached = redis_svc.get_cached_plan(prompt)
    if cached:
        return cached

    result = plan_document(prompt)
    redis_svc.cache_plan(prompt, result)
    return result


# ── Questions ─────────────────────────────────────────────────────────────────

@app.post("/questions")
def questions(payload: dict):
    title    = payload["title"]
    sections = payload["sections"]

    # Dedupe: same title+sections within 5 min
    cached = redis_svc.get_cached_questions(title, sections)
    if cached:
        return cached

    result = generate_questions(title, sections)
    redis_svc.cache_questions(title, sections, result)
    return result


# ── Generate (async job-tracked) ──────────────────────────────────────────────

@app.post("/generate")
def generate(payload: dict):
    """
    Synchronous generation with dedupe caching.
    Returns document content directly.
    """
    doc_format = payload.get("doc_format", "word")

    cached = redis_svc.get_cached_generation(payload["title"], payload["sections"], doc_format)
    if cached:
        return cached
    if doc_format == "excel":
        result = generate_excel_sections(
            payload["title"], payload["sections"], payload["answers"]
        )
    else:
        result = generate_document_sections(
            payload["title"], payload["sections"], payload["answers"]
        )

    redis_svc.cache_generation(payload["title"], payload["sections"], doc_format, result)
    return result




# ── Refine (throttled) ────────────────────────────────────────────────────────

@app.post("/refine-section")
def refine(payload: dict):
    """
    Throttled: max 10 refinements per minute per document title.
    Prevents runaway LLM calls if user clicks rapidly.
    """
    title = payload.get("section_name", "unknown")
    try:
        redis_svc.check_refine_limit(title)
    except ThrottleExceeded as e:
        raise HTTPException(
            status_code=429,
            detail=f"Too many refinements. Please wait a moment. ({e})"
        )

    doc_format = payload.get("doc_format", "word")
    if doc_format == "excel":
        updated_sheet = refine_excel_section(
            payload["section_name"],
            payload.get("current_data", {}),
            payload["feedback"]
        )
        return {"updated_sheet": updated_sheet}
    else:
        updated = refine_section(
            payload["section_name"],
            payload["original_text"],
            payload["feedback"]
        )
        return {"updated_text": updated}


# ── Export Excel ──────────────────────────────────────────────────────────────

@app.post("/export/excel")
def export_excel(payload: dict):
    try:
        buf = generate_excel_file(payload)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=document.xlsx"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


# ── Document history ──────────────────────────────────────────────────────────

@app.post("/documents/save")
def save_doc(payload: dict):
    """
    Save a document.

    payload fields:
      title, doc_type, doc_format, content, file_bytes (hex), file_ext  — required
      save_mode    : "new_version" (default) | "overwrite"
      overwrite_id : int — required when save_mode="overwrite"

    Returns: { id, version, parent_id, mode, message }
    """
    try:
        raw_bytes = None
        if payload.get("file_bytes"):
            raw_bytes = bytes.fromhex(payload["file_bytes"])

        save_mode    = payload.get("save_mode", "new_version")
        overwrite_id = payload.get("overwrite_id")

        if save_mode == "overwrite" and not overwrite_id:
            raise HTTPException(
                status_code=400,
                detail="overwrite_id is required when save_mode is 'overwrite'"
            )

        result = save_document(
            title        = payload["title"],
            doc_type     = payload.get("doc_type", "document"),
            doc_format   = payload.get("doc_format", "word"),
            content      = payload.get("content", {}),
            file_bytes   = raw_bytes,
            file_ext     = payload.get("file_ext"),
            save_mode    = save_mode,
            overwrite_id = overwrite_id,
        )

        mode_label = "overwritten" if result["mode"] == "overwrite" else f"saved as version {result['version']}"
        return {
            "id":        result["id"],
            "version":   result["version"],
            "parent_id": result["parent_id"],
            "mode":      result["mode"],
            "message":   f"Document {mode_label}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
def get_documents():
    try:
        docs = list_documents()
        for doc in docs:
            if doc.get("created_at"):
                doc["created_at"] = doc["created_at"].strftime("%d %b %Y, %I:%M %p")
            doc["version_label"] = f"v{doc.get('version', 1)}"
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}")
def get_doc(doc_id: int):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.pop("file_bytes", None)
    if doc.get("created_at"):
        doc["created_at"] = doc["created_at"].strftime("%d %b %Y, %I:%M %p")
    return doc


@app.get("/documents/{doc_id}/download")
def download_doc(doc_id: int):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.get("file_bytes"):
        raise HTTPException(status_code=404, detail="No file stored for this document")
    ext  = doc.get("file_ext", "docx")
    mime = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == "xlsx"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    safe_title = doc["title"].replace(" ", "_")[:40]
    return Response(
        content=doc["file_bytes"],
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename={safe_title}.{ext}"}
    )


@app.delete("/documents/{doc_id}")
def delete_doc(doc_id: int):
    deleted = delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}


# ── Document versions ────────────────────────────────────────────────────────

@app.post("/documents/check-version")
def check_version(payload: dict):
    """
    Check if a document title already exists in the database.
    Call this before saving to decide whether to show the
    'Save as new version / Overwrite' dialog in the UI.

    Returns:
      { exists: false }                                      — first save
      { exists: true, latest_id: 5, latest_version: 2 }    — already saved
    """
    title  = payload.get("title", "")
    latest = get_latest_version(title)
    if not latest:
        return {"exists": False}
    return {
        "exists":          True,
        "latest_id":       latest["id"],
        "latest_version":  latest["version"],
    }

@app.get("/documents/{doc_id}/versions")
def get_doc_versions(doc_id: int):
    """Return all versions of the document family containing doc_id."""
    versions = list_versions_by_id(doc_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"versions": versions, "total": len(versions)}


@app.delete("/documents/{doc_id}/all-versions")
def delete_doc_all_versions(doc_id: int):
    """Delete all versions of a document family by any version's id."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    count = delete_all_versions(doc["title"])
    return {"message": f"Deleted {count} version(s) of '{doc['title']}'"}


# ── Notion ────────────────────────────────────────────────────────────────────

@app.post("/notion/push")
def notion_push(payload: dict):
    try:
        db_id   = payload.get("db_id")
        version = 1
        # Look up the actual version number from the DB if we have an id
        if db_id:
            doc = get_document(db_id)
            if doc:
                version = doc.get("version", 1)
        result = push_to_notion(
            title      = payload["title"],
            doc_format = payload.get("doc_format", "word"),
            content    = payload.get("content", {}),
            db_id      = db_id,
            version    = version,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion push failed: {str(e)}")


@app.post("/notion/update")
def notion_update(payload: dict):
    try:
        result = update_notion_page(
            page_id    = payload["page_id"],
            title      = payload["title"],
            doc_format = payload.get("doc_format", "word"),
            content    = payload.get("content", {}),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion update failed: {str(e)}")


# ── Redis status + Health ─────────────────────────────────────────────────────

@app.get("/redis/status")
def redis_status():
    return redis_svc.status()


@app.get("/health")
def health():
    return {"status": "ok", "redis": redis_svc.is_available()}