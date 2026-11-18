from __future__ import annotations

import pytest

from models import DocumentChunk
from rag.embeddings import DeterministicEmbeddingClient, cosine_similarity
from rag.text_splitter import split_text


def test_text_splitter_and_embeddings():
    chunks = split_text("A useful paragraph about refunds.\n\n" * 20, chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)

    client = DeterministicEmbeddingClient(dimensions=64)
    related_a = client.embed("How do I return an item for a refund?")
    related_b = client.embed("Refund and return policy")
    unrelated = client.embed("Quantum mechanics particle physics")
    assert cosine_similarity(related_a, related_b) > cosine_similarity(
        related_a, unrelated
    )


def test_document_lifecycle_and_tenant_isolation(client, tenant, tenant_factory, db):
    other = tenant_factory("rag-other")

    created = client.post(
        "/documents",
        headers=tenant["headers"],
        json={
            "title": "Return Policy",
            "content": "Customers can request a full refund within 30 days of purchase.",
        },
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]

    listed = client.get("/documents", headers=tenant["headers"])
    assert listed.status_code == 200
    assert [doc["id"] for doc in listed.json()["documents"]] == [document_id]

    detail = client.get(f"/documents/{document_id}", headers=tenant["headers"])
    assert detail.status_code == 200
    assert detail.json()["title"] == "Return Policy"
    assert len(detail.json()["chunks"]) >= 1

    search = client.post(
        "/documents/search",
        headers=tenant["headers"],
        params={"query": "What is the refund window?"},
    )
    assert search.status_code == 200
    assert search.json()[0]["title"] == "Return Policy"
    assert "30 days" in search.json()[0]["content"]

    assert (
        client.get(f"/documents/{document_id}", headers=other["headers"]).status_code
        == 404
    )
    other_search = client.post(
        "/documents/search",
        headers=other["headers"],
        params={"query": "refund window"},
    )
    assert other_search.status_code == 200
    assert other_search.json() == []

    deleted = client.delete(f"/documents/{document_id}", headers=tenant["headers"])
    assert deleted.status_code == 200
    assert (
        client.get(f"/documents/{document_id}", headers=tenant["headers"]).status_code
        == 404
    )
    assert (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .count()
        == 0
    )


def test_text_file_upload(client, tenant):
    response = client.post(
        "/documents/upload",
        headers=tenant["headers"],
        files={
            "file": (
                "shipping.txt",
                b"Express shipping takes one business day.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["title"] == "shipping.txt"

    detail = client.get(
        f"/documents/{response.json()['id']}", headers=tenant["headers"]
    )
    assert detail.status_code == 200
    assert detail.json()["chunks"]


def test_agent_run_is_grounded_with_citations(
    client, tenant, agent_factory
):
    client.post(
        "/documents",
        headers=tenant["headers"],
        json={
            "title": "Shipping Guide",
            "content": "Standard shipping takes 3-5 business days. Express shipping takes 1 business day.",
        },
    )
    agent = agent_factory(
        name="RAG Agent",
        system_prompt="You are a support agent. Use the knowledge base.",
    )
    client.patch(
        f"/agents/{agent['id']}/status",
        headers=tenant["headers"],
        json={"status": "active"},
    )

    response = client.post(
        f"/agents/{agent['id']}/run",
        headers=tenant["headers"],
        json={"message": "How long does standard shipping take?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["citations"]
    assert body["citations"][0]["title"] == "Shipping Guide"
    assert "3-5 business days" in body["citations"][0]["content"]


class _RecordingEmbeddingClient:
    def __init__(self):
        self.batch_calls = []

    def embed_batch(self, texts):
        self.batch_calls.append(texts)
        return [[0.1, 0.2] for _ in texts]


class _FailingEmbeddingClient:
    def embed_batch(self, texts):
        raise RuntimeError("embedding service down")


def test_ingestion_embeds_all_chunks_in_one_batch(tenant, db):
    from services.rag_service import create_document_service

    embedding_client = _RecordingEmbeddingClient()

    document = create_document_service(
        db=db,
        tenant_id=tenant["id"],
        title="Batch Guide",
        content="A paragraph. " * 200,
        embedding_client=embedding_client,
    )

    assert len(embedding_client.batch_calls) == 1
    assert len(embedding_client.batch_calls[0]) == len(document.chunks)


def test_failed_ingestion_leaves_no_document(tenant, db):
    from models import Document
    from services.rag_service import create_document_service

    with pytest.raises(RuntimeError, match="embedding service down"):
        create_document_service(
            db=db,
            tenant_id=tenant["id"],
            title="Broken Guide",
            content="Some content.",
            embedding_client=_FailingEmbeddingClient(),
        )

    assert (
        db.query(Document).filter(Document.title == "Broken Guide").count() == 0
    )


def test_embedding_provider_selection(monkeypatch):
    from rag.embeddings import (
        DeterministicEmbeddingClient,
        FastEmbedClient,
        OllamaEmbeddingClient,
        create_embedding_client,
    )

    monkeypatch.setenv("EMBEDDING_PROVIDER", "auto")
    assert isinstance(create_embedding_client(), FastEmbedClient)

    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    assert isinstance(create_embedding_client(), OllamaEmbeddingClient)

    monkeypatch.setenv("EMBEDDING_PROVIDER", "deterministic")
    assert isinstance(create_embedding_client(), DeterministicEmbeddingClient)


def test_ollama_embed_batch_uses_batch_endpoint(monkeypatch):
    from rag.embeddings import OllamaEmbeddingClient

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[1.0], [2.0]]}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("rag.embeddings.requests.post", fake_post)

    client = OllamaEmbeddingClient()
    result = client.embed_batch(["first", "second"])

    assert result == [[1.0], [2.0]]
    assert captured["url"].endswith("/api/embed")
    assert captured["json"]["input"] == ["first", "second"]


def test_member_cannot_create_documents(client, member_user):
    response = client.post(
        "/documents",
        headers=member_user["headers"],
        json={"title": "Nope", "content": "Members cannot write knowledge."},
    )
    assert response.status_code == 403


def test_upload_rejects_empty_file(client, tenant):
    response = client.post(
        "/documents/upload",
        headers=tenant["headers"],
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
