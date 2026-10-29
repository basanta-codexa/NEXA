from __future__ import annotations

import pytest

from engine.agent_engine import AgentEngine
from llm.factory import create_llm_client
from llm.fake_client import FakeLLMClient
from schemas import AgentConfig
from tools.default_registry import default_registry


def test_engine_returns_a_direct_response():
    engine = AgentEngine(
        config=AgentConfig(
            model_name="fake",
            system_prompt="You are a helpful assistant.",
        ),
        llm_client=FakeLLMClient(
            model_name="fake",
            canned_response="Hello! How can I help?",
        ),
    )

    result = engine.run("Hello!")
    assert result["response"] == "Hello! How can I help?"
    assert result["steps"] == []


def test_engine_executes_an_autonomous_tool_loop():
    engine = AgentEngine(
        config=AgentConfig(
            model_name="fake",
            system_prompt="Check demonstration orders.",
        ),
        llm_client=FakeLLMClient(
            model_name="fake",
            canned_response="Order 101 has been Shipped.",
            canned_tool_calls=[
                {"name": "get_order_status", "arguments": {"order_id": 101}}
            ],
        ),
        tool_registry=default_registry,
    )

    result = engine.run("What is the status of order 101?")
    assert result["response"] == "Order 101 has been Shipped."
    assert len(result["steps"]) == 1
    assert result["steps"][0]["tool"] == "get_order_status"
    assert result["steps"][0]["arguments"] == {"order_id": 101}
    assert result["steps"][0]["result"] == {"order_id": 101, "status": "Shipped"}


def test_unknown_tool_is_reported_not_executed():
    engine = AgentEngine(
        config=AgentConfig(model_name="fake"),
        llm_client=FakeLLMClient(
            model_name="fake",
            canned_response="That tool is unavailable.",
            canned_tool_calls=[{"name": "not_a_tool", "arguments": {}}],
        ),
        tool_registry=default_registry,
    )

    result = engine.run("Do something")
    assert len(result["steps"]) == 1
    assert "not registered" in result["steps"][0]["result"]["error"]


def test_scoped_registry_only_exposes_allowed_tools():
    scoped = default_registry.create_scoped_registry(["get_order_status"])
    assert scoped.list_tools() == ["get_order_status"]

    empty = default_registry.create_scoped_registry([])
    assert empty.list_tools() == []
    assert empty.get_tool_schemas() == []

    engine = AgentEngine(
        config=AgentConfig(model_name="fake", tools=[]),
        llm_client=FakeLLMClient(
            model_name="fake",
            canned_response="I cannot do that.",
            canned_tool_calls=[
                {"name": "get_order_status", "arguments": {"order_id": 101}}
            ],
        ),
        tool_registry=empty,
    )
    result = engine.run("Check order 101")
    assert "not registered" in result["steps"][0]["result"]["error"]


def test_fake_client_tool_call_sequence():
    client = FakeLLMClient(
        model_name="fake",
        canned_response="",
        canned_tool_calls=[
            {"name": "get_order_status", "arguments": {"order_id": 101}}
        ],
    )
    first = client.chat(messages=[{"role": "user", "content": "Where is order 101?"}])
    assert first["tool_calls"][0]["name"] == "get_order_status"

    second = client.chat(
        messages=[
            {"role": "user", "content": "Where is order 101?"},
            first,
            {"role": "tool", "content": '{"status": "Shipped"}'},
        ]
    )
    assert second["tool_calls"] == []
    assert "Completed task successfully" in second["content"]


def test_tool_argument_validation():
    result = default_registry.execute("get_order_status", order_id="101")
    assert "must be an integer" in result["error"]

    result = default_registry.execute("get_order_status", unknown=101)
    assert "Invalid arguments" in result["error"]


def test_llm_factory_defaults_to_fake_and_rejects_unknown_models():
    client = create_llm_client(None)
    assert isinstance(client, FakeLLMClient)

    client = create_llm_client("fake")
    assert isinstance(client, FakeLLMClient)

    with pytest.raises(ValueError, match="Unsupported model"):
        create_llm_client("not-a-provider/model")
