from __future__ import annotations

import os

import pytest

from llm.factory import create_llm_client


def _require_model(env_name: str) -> str:
    model = os.getenv(env_name)
    if not model:
        pytest.skip(f"set {env_name} to a model name to run this test")
    return model


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_GROQ_TESTS") != "1",
    reason="set RUN_GROQ_TESTS=1 and provide GROQ_API_KEY and GROQ_TEST_MODEL",
)
def test_groq_can_answer_a_simple_request():
    model = _require_model("GROQ_TEST_MODEL")
    client = create_llm_client(f"groq/{model}", temperature=0, max_tokens=128)

    response = client.chat(
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )

    assert isinstance(response["content"], str)
    assert response["content"].strip()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_XAI_TESTS") != "1",
    reason="set RUN_XAI_TESTS=1 and provide XAI_API_KEY and XAI_TEST_MODEL",
)
def test_xai_can_answer_a_simple_request():
    model = _require_model("XAI_TEST_MODEL")
    client = create_llm_client(f"xai/{model}", temperature=0, max_tokens=128)

    response = client.chat(
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )

    assert isinstance(response["content"], str)
    assert response["content"].strip()
