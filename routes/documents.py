"""
Documents Route — Upload, manage, and query enterprise documents.
"""
import os
import json
import logging
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from models.database import get_db, User, Document
from models.schemas import DocumentResponse, DocumentListResponse
from services.auth_utils import get_current_user, require_role
from services.document_processor import process_document

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "xlsx", "txt", "md", "csv"}
MAX_FILE_SIZE_MB = 50
UPLOAD_DIR = "/tmp/atlas_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    department: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all uploaded documents with optional filters."""
    query = db.query(Document)

    if department:
        query = query.filter(Document.department == department)
    if doc_type:
        query = query.filter(Document.file_type == doc_type)
    if status:
        query = query.filter(Document.status == status)

    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return DocumentListResponse(documents=docs, total=total)


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document for indexing.
    Supports PDF, DOCX, XLSX, TXT, CSV.
    """
    # Validate file type
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    # Read file
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Maximum: {MAX_FILE_SIZE_MB}MB",
        )

    # Save to disk temporarily
    from models.database import generate_id
    doc_id = generate_id()
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create document record
    document = Document(
        id=doc_id,
        title=title or filename.rsplit(".", 1)[0],
        filename=filename,
        file_type=ext,
        file_size=len(content),
        department=department,
        tags=json.loads(tags) if tags else [],
        status="processing",
        uploaded_by_id=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Process asynchronously (in production: send to Celery)
    try:
        result = await process_document(
            file_path=file_path,
            document_id=doc_id,
            title=document.title,
            metadata={
                "department": department or "",
                "doc_type": doc_type or ext,
                "tags": document.tags,
                "file_type": ext,
            },
        )

        document.status = "indexed" if result["success"] else "failed"
        document.chunk_count = result.get("chunk_count", 0)
        if not result["success"]:
            document.error_message = result.get("error", "Unknown error")

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        logger.error(f"Document processing error: {e}")

    finally:
        # Clean up temp file
        try:
            os.remove(file_path)
        except Exception:
            pass

    db.commit()
    db.refresh(document)
    return document


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_alias(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for POST /api/documents — same handler, alternate path."""
    return await upload_document(
        file=file,
        title=title,
        department=department,
        doc_type=doc_type,
        tags=tags,
        current_user=current_user,
        db=db,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted", "document_id": document_id}
