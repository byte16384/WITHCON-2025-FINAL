from fastapi import APIRouter, HTTPException, Cookie, Response
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime
import os
from models.schemas import SignerAdd, SignerTokenResponse
from core.security import create_signing_token, safe_markdown
from core.state import state
import time
from models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentStatus,
    DocumentListResponse
)
from core.security import generate_session_id, generate_document_id
from core.config import settings
from core.pdf_renderer import pdf_renderer
from core.job_queue import job_queue
import time

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate, response: Response, session_id: Optional[str]=Cookie(None)):
    if not session_id:
        session_id = generate_session_id()
        response.set_cookie(key="session_id", value=session_id, httponly=True)

    if len(doc.markdown_content.encode("utf-8")) > settings.MAX_MARKDOWN_SIZE:
        raise HTTPException(status_code=413, detail="Markdown content too large")

    document_id = generate_document_id()
    
    # FIXED: Decode with UTF-8, not UTF-7!
    safe_markdown_content = safe_markdown(doc.markdown_content).decode("utf-8")
    
    created_at = datetime.utcnow().isoformat()

    state.create_document(document_id, session_id, doc.title, created_at)

    def _do_render():
        try:
            result = pdf_renderer.render_pdf(document_id, safe_markdown_content, doc.title)
            if result.get("status") == "success":
                state.update_document(document_id, {
                    "status": "completed",
                    "pdf_path": result.get("pdf_path", ""),
                    "title": doc.title,
                })
            else:
                state.update_document(document_id, {
                    "status": "failed",
                    "error": result.get("error", "Unknown error"),
                })
        except Exception as e:
            state.update_document(document_id, {
                "status": "failed",
                "error": str(e),
            })

    job_queue.enqueue(_do_render)

    return DocumentResponse(
        document_id=document_id,
        title=doc.title,
        status="processing",
        created_at=created_at,
        preview_url=None,
    )

@router.get("/{document_id}", response_model=DocumentStatus)
async def get_document_status(document_id: str, session_id: Optional[str] = Cookie(None)):
    if not state.document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = state.get_document(document_id)
    if not session_id or doc.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return DocumentStatus(
        document_id=document_id,
        status=doc.get("status", "unknown"),
        message=doc.get("error")
    )

@router.get("/{document_id}/preview")
async def get_preview_pdf(document_id: str, session_id: Optional[str] = Cookie(None)):
    if not state.document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = state.get_document(document_id)
    if not session_id or doc.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if doc.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Document is {doc.get('status')}")
    pdf_path = doc.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    title = doc.get("title") or "document"
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{title}.pdf")

@router.get("/{document_id}/final")
async def get_final_pdf(document_id: str, session_id: Optional[str] = Cookie(None)):
    if not state.document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = state.get_document(document_id)
    if not session_id or doc.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if doc.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Document is {doc.get('status')}")
    title = doc.get("title") or "document"
    if doc.get("signed") == "true":
        fp = doc.get("final_pdf_path")
        if fp and os.path.exists(fp):
            return FileResponse(fp, media_type="application/pdf", filename=f"{title}-signed.pdf")
    fp = doc.get("pdf_path")
    if not fp or not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(fp, media_type="application/pdf", filename=f"{title}.pdf")

@router.get("", response_model=DocumentListResponse)
async def list_documents(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        return DocumentListResponse(documents=[])
    ids = state.list_session_documents(session_id)
    documents = []
    for doc_id in ids:
        d = state.get_document(doc_id)
        if not d:
            continue
        documents.append(DocumentResponse(
            document_id=doc_id,
            title=d.get("title", "Untitled"),
            status=d.get("status", "unknown"),
            created_at=d.get("created_at", ""),
            preview_url=f"/api/documents/{doc_id}/preview" if d.get("status") == "completed" else None,
            signed=(d.get("signed") == "true")
        ))
    return DocumentListResponse(documents=documents)

@router.post("/{document_id}/signers", response_model=SignerTokenResponse)
async def add_signer_for_document(
    document_id: str,
    signer: SignerAdd,
    session_id: Optional[str] = Cookie(None),
):
    if not state.document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = state.get_document(document_id)
    if not session_id or doc.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    token = create_signing_token(document_id, signer.signer_email)
    state.add_signer(
        doc_id=document_id,
        name=signer.signer_name,
        email=signer.signer_email,
        token=token,
        expires_at=time.time() + settings.JWT_EXPIRE_HOURS * 3600,
    )
    return SignerTokenResponse(
        token=token,
        signing_url=f"/sign/{token}",
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
    )

# flag :  whitehat2025{9081de6f7a03afb2557eae487af942aa8fe7e85fcce18743cba616a5e839f12c}