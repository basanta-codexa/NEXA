from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models import Document, DocumentChunk
from rag.embeddings import BaseEmbeddingClient, compute_hybrid_score, create_embedding_client
from rag.file_parser import extract_text_from_file
from rag.text_splitter import split_text


def create_document_service(
    db: Session,
    tenant_id: int,
    title: str,
    content: str,
    embedding_client: BaseEmbeddingClient | None = None
) -> Document:
    """
    Creates a new document, chunks its content, computes embeddings for each chunk
    (enriched with document title for high precision), and stores everything with tenant isolation.
    """
    if embedding_client is None:
        embedding_client = create_embedding_client()

    chunk_texts = split_text(content, chunk_size=500, chunk_overlap=50)
    # Include the title in each embedding so title keywords are searchable.
    enriched = [f"Title: {title}\nContent:\n{text}" for text in chunk_texts]
    embeddings = embedding_client.embed_batch(enriched)

    now = datetime.now(UTC)
    document = Document(
        tenant_id=tenant_id,
        title=title,
        content=content,
        created_at=now,
        updated_at=now,
    )

    try:
        # One transaction: a failed commit or embedding leaves no orphan document.
        db.add(document)
        db.flush()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    tenant_id=tenant_id,
                    chunk_index=index,
                    content=text,
                    embedding=embedding,
                    created_at=now,
                )
                for index, (text, embedding) in enumerate(
                    zip(chunk_texts, embeddings, strict=True)
                )
            ]
        )
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        raise

    return document


def create_document_from_file_service(
    db: Session,
    tenant_id: int,
    filename: str,
    file_bytes: bytes,
    embedding_client: BaseEmbeddingClient | None = None
) -> Document:
    """
    Extracts text from uploaded file (.txt, .md, .pdf, .docx, .csv) and ingests it into RAG.
    """
    extracted_text = extract_text_from_file(filename, file_bytes)
    return create_document_service(
        db=db,
        tenant_id=tenant_id,
        title=filename,
        content=extracted_text,
        embedding_client=embedding_client
    )


def get_documents_service(
    db: Session,
    tenant_id: int,
    limit: int | None = None,
    offset: int = 0,
) -> list[Document]:
    """
    Fetches documents belonging to a tenant, newest first.
    """
    query = db.query(Document).filter(Document.tenant_id == tenant_id)
    query = query.order_by(Document.created_at.desc())
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


def get_document_service(db: Session, document_id: int, tenant_id: int) -> Document | None:
    """
    Fetches a single document and its chunks for a tenant.
    """
    return db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == tenant_id
    ).first()


def delete_document_service(db: Session, document_id: int, tenant_id: int) -> bool:
    """
    Deletes a document and cascades deletion of its chunks.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == tenant_id
    ).first()
    if not doc:
        return False
    db.delete(doc)
    db.commit()
    return True


def search_knowledge_service(
    db: Session,
    tenant_id: int,
    query: str,
    top_k: int = 3,
    threshold: float = 0.08,
    embedding_client: BaseEmbeddingClient | None = None
) -> list[dict[str, Any]]:
    """
    Hybrid semantic + lexical retrieval:
    Embeds the user query, scans tenant chunks, computes combined hybrid score
    (dense vector similarity + BM25 keyword overlap), and returns top_k most relevant chunks.
    """
    if not query or not query.strip():
        return []

    top_k = max(1, min(top_k, 20))

    if embedding_client is None:
        embedding_client = create_embedding_client()

    query_embedding = embedding_client.embed(query)
    if not query_embedding:
        return []

    # Fetch all chunks for the tenant (strict tenant isolation)
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.tenant_id == tenant_id
    ).all()

    # Pre-fetch parent documents in memory for fast lookup
    doc_map = {
        d.id: d for d in db.query(Document).filter(Document.tenant_id == tenant_id).all()
    }

    scored_results: list[dict[str, Any]] = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        doc = doc_map.get(chunk.document_id)
        doc_title = doc.title if doc else ""
        target_text = f"{doc_title} {chunk.content}"

        score = compute_hybrid_score(
            query_vec=query_embedding,
            chunk_vec=chunk.embedding,
            query_text=query,
            chunk_text=target_text
        )

        if score >= threshold:
            scored_results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "title": doc_title or "Document",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "similarity": score
            })

    # Sort descending by hybrid score
    scored_results.sort(key=lambda x: x["similarity"], reverse=True)
    return scored_results[:top_k]


def build_grounded_context(retrieved_chunks: list[dict[str, Any]]) -> str:
    """
    Formats retrieved knowledge into a clean, structured grounding block
    suitable for injecting into system prompts with citations.
    """
    if not retrieved_chunks:
        return ""

    context_lines = [
        "Use the following verified knowledge base excerpts to answer the user accurately. "
        "Cite the document title when referencing facts. "
        "If the excerpts do not contain the answer, say you do not know instead of guessing:"
    ]
    for idx, chunk in enumerate(retrieved_chunks, 1):
        context_lines.append(
            f"[{idx}] Source: \"{chunk['title']}\" (Section {chunk['chunk_index']}):\n{chunk['content']}\n"
        )

    return "\n".join(context_lines)
