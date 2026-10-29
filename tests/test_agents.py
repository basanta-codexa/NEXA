from __future__ import annotations

from llm.fake_client import FakeLLMClient
from models import Conversation, Message


def test_agent_crud_and_defaults(client, tenant, agent_factory):
    agent = agent_factory(
        name="CRUD Agent",
        description="initial",
        system_prompt="Be concise.",
        tools=["get_order_status"],
    )
    assert agent["status"] == "draft"
    assert agent["tenant_id"] == tenant["id"]
    assert agent["tools"] == ["get_order_status"]

    listed = client.get("/agents", headers=tenant["headers"])
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["agents"]] == [agent["id"]]

    fetched = client.get(f"/agents/{agent['id']}", headers=tenant["headers"])
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "CRUD Agent"

    updated = client.put(
        f"/agents/{agent['id']}",
        headers=tenant["headers"],
        json={
            "name": "Updated Agent",
            "role": "Billing",
            "language": "Spanish",
            "description": "updated",
            "system_prompt": "Be helpful.",
            "model_name": "fake",
            "temperature": 0.2,
            "max_tokens": 256,
            "top_p": 0.8,
            "tools": [],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Agent"
    assert updated.json()["temperature"] == 0.2
    assert updated.json()["tools"] == []


def test_agent_status_transitions(client, tenant, agent_factory):
    agent = agent_factory()
    path = f"/agents/{agent['id']}/status"

    active = client.patch(path, headers=tenant["headers"], json={"status": "active"})
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active"

    invalid = client.patch(path, headers=tenant["headers"], json={"status": "draft"})
    assert invalid.status_code == 400

    paused = client.patch(path, headers=tenant["headers"], json={"status": "paused"})
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    active_again = client.patch(path, headers=tenant["headers"], json={"status": "active"})
    assert active_again.status_code == 200

    archived = client.patch(path, headers=tenant["headers"], json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    cannot_reopen = client.patch(path, headers=tenant["headers"], json={"status": "active"})
    assert cannot_reopen.status_code == 400


def test_draft_agent_cannot_run(client, tenant, agent_factory):
    agent = agent_factory()
    response = client.post(
        f"/agents/{agent['id']}/run",
        headers=tenant["headers"],
        json={"message": "hello"},
    )
    assert response.status_code == 409, response.text
    assert "not active" in response.json()["detail"]


def test_run_persists_memory_for_a_session(client, tenant, active_agent, db):
    path = f"/agents/{active_agent['id']}/run"

    first = client.post(
        path,
        headers=tenant["headers"],
        json={"message": "My name is Alice.", "session_id": "shared-session"},
    )
    second = client.post(
        path,
        headers=tenant["headers"],
        json={"message": "Do you remember my name?", "session_id": "shared-session"},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["session_id"] == "shared-session"
    assert second.json()["session_id"] == "shared-session"

    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant["id"],
            Conversation.agent_id == active_agent["id"],
            Conversation.session_id == "shared-session",
        )
        .all()
    )
    assert len(conversations) == 1

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversations[0].id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0].content == "My name is Alice."
    assert messages[2].content == "Do you remember my name?"


def test_run_without_session_creates_a_new_session(client, tenant, active_agent, db):
    path = f"/agents/{active_agent['id']}/run"
    first = client.post(path, headers=tenant["headers"], json={"message": "one"})
    second = client.post(path, headers=tenant["headers"], json={"message": "two"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session_id"] != second.json()["session_id"]

    count = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant["id"],
            Conversation.agent_id == active_agent["id"],
        )
        .count()
    )
    assert count == 2


def test_delete_agent_cascades_conversations_and_messages(
    client, tenant, active_agent, db
):
    run = client.post(
        f"/agents/{active_agent['id']}/run",
        headers=tenant["headers"],
        json={"message": "hello", "session_id": "delete-me"},
    )
    assert run.status_code == 200

    deleted = client.delete(
        f"/agents/{active_agent['id']}",
        headers=tenant["headers"],
    )
    assert deleted.status_code == 200, deleted.text

    db.expire_all()
    assert (
        db.query(Conversation)
        .filter(Conversation.agent_id == active_agent["id"])
        .count()
        == 0
    )
    assert (
        db.query(Message)
        .filter(Message.tenant_id == tenant["id"])
        .count()
        == 0
    )
    assert (
        client.get(
            f"/agents/{active_agent['id']}",
            headers=tenant["headers"],
        ).status_code
        == 404
    )


def test_tenant_isolation_for_agent_operations(client, tenant, tenant_factory):
    other = tenant_factory("other")
    private = client.post(
        "/agents",
        headers=tenant["headers"],
        json={
            "name": "Private Agent",
            "role": "Support",
            "language": "English",
            "model_name": "fake",
        },
    )
    assert private.status_code == 200
    agent_id = private.json()["id"]

    assert client.get(f"/agents/{agent_id}", headers=other["headers"]).status_code == 404
    assert (
        client.put(
            f"/agents/{agent_id}",
            headers=other["headers"],
            json={
                "name": "Hijacked",
                "role": "Support",
                "language": "English",
            },
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/agents/{agent_id}", headers=other["headers"]).status_code
        == 404
    )
    assert (
        client.post(
            f"/agents/{agent_id}/run",
            headers=other["headers"],
            json={"message": "steal this"},
        ).status_code
        == 404
    )
    listed_for_other = client.get("/agents", headers=other["headers"]).json()["agents"]
    assert all(item["tenant_id"] == other["id"] for item in listed_for_other)
    assert agent_id not in [item["id"] for item in listed_for_other]


def test_unsupported_model_returns_400(client, tenant, agent_factory):
    agent = agent_factory(model_name="definitely-not-a-model")
    client.patch(
        f"/agents/{agent['id']}/status",
        headers=tenant["headers"],
        json={"status": "active"},
    )

    response = client.post(
        f"/agents/{agent['id']}/run",
        headers=tenant["headers"],
        json={"message": "hello"},
    )
    assert response.status_code == 400, response.text
    assert "Unsupported model" in response.json()["detail"]


def test_agent_tools_are_executed_only_when_scoped(
    client, tenant, agent_factory, monkeypatch
):
    agent = agent_factory(tools=["get_order_status"])
    client.patch(
        f"/agents/{agent['id']}/status",
        headers=tenant["headers"],
        json={"status": "active"},
    )

    def fake_client(*args, **kwargs):
        return FakeLLMClient(
            model_name="fake",
            canned_response="Order 101 has been shipped.",
            canned_tool_calls=[
                {"name": "get_order_status", "arguments": {"order_id": 101}}
            ],
        )

    monkeypatch.setattr("services.agent_service.create_llm_client", fake_client)

    response = client.post(
        f"/agents/{agent['id']}/run",
        headers=tenant["headers"],
        json={"message": "Where is order 101?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response"] == "Order 101 has been shipped."
    assert len(body["steps"]) == 1
    assert body["steps"][0]["tool"] == "get_order_status"
    assert body["steps"][0]["result"]["status"] == "Shipped"


def test_agent_validation(client, tenant):
    response = client.post(
        "/agents",
        headers=tenant["headers"],
        json={
            "name": "Invalid",
            "role": "Support",
            "language": "English",
            "temperature": 5.0,
        },
    )
    assert response.status_code == 422
