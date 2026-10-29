from __future__ import annotations

import os

import pytest

from llm.ollama_client import OllamaClient, build_ollama_options, to_ollama_messages
from tools.default_registry import default_registry


def test_ollama_message_translation_and_options():
    messages = to_ollama_messages(
        [
            {"role": "system", "content": "Be brief."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"name": "get_order_status", "arguments": {"order_id": 101}}
                ],
            },
            {
                "role": "tool",
                "tool_name": "get_order_status",
                "content": '{"status": "Shipped"}',
            },
            {"role": "user", "content": "Thanks"},
        ]
    )
    assert messages[1]["tool_calls"][0]["function"]["name"] == "get_order_status"
    assert messages[2]["tool_name"] == "get_order_status"
    assert build_ollama_options(0.2, 256, 0.9) == {
        "temperature": 0.2,
        "num_predict": 256,
        "top_p": 0.9,
    }


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="set RUN_OLLAMA_TESTS=1 and start Ollama to run this test",
)
def test_ollama_can_request_a_tool():
    client = OllamaClient(
        os.getenv("OLLAMA_TEST_MODEL", "qwen3:4b"),
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        timeout=60,
    )
    response = client.generate_with_tools(
        system_prompt=(
            "You are NEXA. Use get_order_status for order questions. "
            "Never invent a status."
        ),
        user_message="What is the status of order 101?",
        tool_schemas=default_registry.get_tool_schemas(),
    )
    assert response["role"] == "assistant"
    assert isinstance(response["content"], str)
