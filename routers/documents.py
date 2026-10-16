from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from dependencies.tenant import get_current_tenant_id
from schemas import (
    CreateDocument,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    RAGSearchResult
)
from services.rag_service import (
    create_document_service,
    create_document_from_file_service,
    get_documents_service,
    get_document_service,
    delete_document_service,
    search_knowledge_service
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents & Knowledge"]
)


@router.post("", response_model=DocumentResponse)
def create_document(
    doc: CreateDocument,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    new_doc = create_document_service(
        db=db,
        tenant_id=tenant_id,
        title=doc.title,
        content=doc.content
    )
    return new_doc


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    file_bytes = await file.read()
    new_doc = create_document_from_file_service(
        db=db,
        tenant_id=tenant_id,
        filename=file.filename or "uploaded_file.txt",
        file_bytes=file_bytes
    )
    return new_doc


@router.get("", response_model=DocumentListResponse)
def get_documents(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    docs = get_documents_service(db=db, tenant_id=tenant_id)
    return {"documents": docs}


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    doc = get_document_service(db=db, document_id=document_id, tenant_id=tenant_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    success = delete_document_service(db=db, document_id=document_id, tenant_id=tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.post("/search", response_model=list[RAGSearchResult])
def search_knowledge(
    query: str,
    top_k: int = 3,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id)
):
    results = search_knowledge_service(
        db=db,
        tenant_id=tenant_id,
        query=query,
        top_k=top_k
    )
    return results
