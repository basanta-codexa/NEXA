from __future__ import annotations

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
