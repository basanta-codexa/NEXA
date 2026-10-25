from llm.fake_client import FakeLLMClient
from llm.llm_client import LLMClient
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient


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
        "gpt-*" / "openai/*" -> OpenAI chat completions
        "ollama/*"           -> local Ollama
    """
    if model_name is None or model_name == "fake":
        return FakeLLMClient(
            model_name or "fake",
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    if model_name.startswith("openai/"):
        model_name = model_name.removeprefix("openai/")

    if model_name.startswith("gpt-") or model_name.startswith(("o1", "o3", "o4")):
        return OpenAIClient(
            model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    if model_name.startswith("ollama/"):
        return OllamaClient(
            model_name.removeprefix("ollama/"),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    raise ValueError(
        f"Unsupported model: {model_name}. "
        "Use 'fake', 'ollama/<model>', 'gpt-*', or 'openai/<model>'."
    )
