import pytest

from llm.factory import create_llm_client
from llm.fake_client import FakeLLMClient
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient


def test_groq_prefix_routes_to_groq_provider(monkeypatch):
    monkeypatch.setenv("GROQ_BASE_URL", "https://custom.groq.example/v1")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    client = create_llm_client("groq/llama-3.1-8b-instant")

    assert isinstance(client, OpenAIClient)
    assert client.model_name == "llama-3.1-8b-instant"
    assert client._api_key_env == "GROQ_API_KEY"
    assert client._provider_name == "Groq"
    assert client._base_url == "https://custom.groq.example/v1"


def test_xai_and_grok_prefixes_route_to_xai_provider(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_BASE_URL", raising=False)

    for model_name in ("xai/grok-4", "grok/grok-4", "grok-4"):
        client = create_llm_client(model_name)
        assert isinstance(client, OpenAIClient)
        assert client.model_name == "grok-4"
        assert client._api_key_env == "XAI_API_KEY"
        assert client._provider_name == "xAI"
        assert client._base_url == "https://api.x.ai/v1"


def test_openai_prefix_routes_to_openai_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    client = create_llm_client("openai/gpt-4o-mini")

    assert isinstance(client, OpenAIClient)
    assert client.model_name == "gpt-4o-mini"
    assert client._api_key_env == "OPENAI_API_KEY"
    assert client._provider_name == "OpenAI"


def test_existing_fake_and_ollama_routing_is_preserved():
    assert isinstance(create_llm_client(None), FakeLLMClient)
    assert isinstance(create_llm_client("fake"), FakeLLMClient)
    assert isinstance(create_llm_client("ollama/llama3.2:3b"), OllamaClient)


@pytest.mark.parametrize(
    ("model_name", "message"),
    [
        ("groq/", "must not be empty"),
        ("xai/", "must not be empty"),
        ("grok/", "must not be empty"),
        ("openai/", "must not be empty"),
        ("ollama/", "must not be empty"),
    ],
)
def test_empty_provider_models_are_rejected(model_name, message):
    with pytest.raises(ValueError, match=message):
        create_llm_client(model_name)


def test_unsupported_model_message_lists_provider_options():
    with pytest.raises(ValueError, match="groq/<model>"):
        create_llm_client("not-a-provider/model")


def test_missing_provider_key_has_actionable_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("llm.openai_client.OpenAI", lambda **_: object())

    client = create_llm_client("groq/test-model")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
        _ = client.client
