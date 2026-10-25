import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from dependencies.permissions import Permissions
from dependencies.roles import require_permission
from dependencies.tenant import get_current_tenant_id
from schemas import (
    CreateDocument,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    RAGSearchResult,
)
from services.rag_service import (
    create_document_from_file_service,
    create_document_service,
    delete_document_service,
    get_document_service,
    get_documents_service,
    search_knowledge_service,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents & Knowledge"],
)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post("", response_model=DocumentResponse, status_code=201)
def create_document(
    doc: CreateDocument,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_CREATE)),
):
    return create_document_service(
        db=db,
        tenant_id=tenant_id,
        title=doc.title,
        content=doc.content,
    )


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_CREATE)),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required.")

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_MB} MB limit.",
        )
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    return create_document_from_file_service(
        db=db,
        tenant_id=tenant_id,
        filename=file.filename,
        file_bytes=file_bytes,
    )


@router.get("", response_model=DocumentListResponse)
def get_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_READ)),
):
    docs = get_documents_service(
        db=db,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return {"documents": docs}


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_READ)),
):
    doc = get_document_service(db=db, document_id=document_id, tenant_id=tenant_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_DELETE)),
):
    success = delete_document_service(
        db=db, document_id=document_id, tenant_id=tenant_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.post("/search", response_model=list[RAGSearchResult])
def search_knowledge(
    query: str = Query(min_length=1, max_length=1000),
    top_k: int = Query(default=3, ge=1, le=20),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.DOCUMENT_READ)),
):
    return search_knowledge_service(
        db=db,
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
    )
