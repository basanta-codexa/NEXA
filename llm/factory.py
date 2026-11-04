import os

from llm.fake_client import FakeLLMClient
from llm.llm_client import LLMClient
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient

# OpenAI-compatible providers. Base URLs are configurable because providers
# may move endpoints or be fronted by a proxy/gateway.
_PROVIDER_PRESETS = {
    "groq": {
        "provider_name": "Groq",
        "api_key_env": "GROQ_API_KEY",
        "base_url_env": "GROQ_BASE_URL",
        "default_base_url": "https://api.groq.com/openai/v1",
    },
    "xai": {
        "provider_name": "xAI",
        "api_key_env": "XAI_API_KEY",
        "base_url_env": "XAI_BASE_URL",
        "default_base_url": "https://api.x.ai/v1",
    },
    # Friendly alias for xAI's Grok models.
    "grok": {
        "provider_name": "xAI",
        "api_key_env": "XAI_API_KEY",
        "base_url_env": "XAI_BASE_URL",
        "default_base_url": "https://api.x.ai/v1",
    },
}


def _create_openai_compatible(
    model_name: str,
    profile: dict[str, str],
    *,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
) -> OpenAIClient:
    if not model_name.strip():
        raise ValueError("Model name after the provider prefix must not be empty.")

    base_url = os.getenv(profile["base_url_env"], profile["default_base_url"])
    return OpenAIClient(
        model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        base_url=base_url,
        api_key_env=profile["api_key_env"],
        provider_name=profile["provider_name"],
    )


def create_llm_client(
    model_name: str | None,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
) -> LLMClient:
    """
    Creates a provider client from an agent's model name.

    Supported values:
        None / "fake"        -> deterministic offline client
        "ollama/<model>"     -> local Ollama
        "gpt-*" / "openai/*" -> OpenAI chat completions
        "groq/<model>"       -> Groq (OpenAI-compatible API)
        "xai/<model>"        -> xAI Grok (OpenAI-compatible API)
        "grok/<model>"       -> xAI Grok alias
        "grok-*"             -> xAI Grok

    API keys are read from environment variables:
        OPENAI_API_KEY, GROQ_API_KEY, XAI_API_KEY
    """
    if model_name is None or model_name == "fake":
        return FakeLLMClient(
            model_name or "fake",
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    model = model_name.strip()

    if model.startswith("ollama/"):
        ollama_model = model.removeprefix("ollama/").strip()
        if not ollama_model:
            raise ValueError("Model name after 'ollama/' must not be empty.")
        return OllamaClient(
            ollama_model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    if "/" in model:
        provider, _, provider_model = model.partition("/")
        provider_model = provider_model.strip()
        profile = _PROVIDER_PRESETS.get(provider)
        if profile is not None:
            return _create_openai_compatible(
                provider_model,
                profile,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

    if model.startswith("openai/"):
        model = model.removeprefix("openai/").strip()
        if not model:
            raise ValueError("Model name after 'openai/' must not be empty.")

    if model.startswith("grok-"):
        return _create_openai_compatible(
            model,
            _PROVIDER_PRESETS["xai"],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    if model.startswith("gpt-") or model.startswith(("o1", "o3", "o4")):
        return OpenAIClient(
            model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            provider_name="OpenAI",
            api_key_env="OPENAI_API_KEY",
        )

    raise ValueError(
        f"Unsupported model: {model_name}. "
        "Use 'fake', 'ollama/<model>', 'gpt-*', 'openai/<model>', "
        "'groq/<model>', 'xai/<model>', or 'grok/<model>'."
    )
