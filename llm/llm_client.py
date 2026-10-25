from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """
    Provider-agnostic LLM interface.

    Canonical message format used by the engine and all clients:

        {"role": "system",    "content": str}
        {"role": "user",      "content": str}
        {"role": "assistant", "content": str,
         "tool_calls": [{"id": str, "name": str, "arguments": dict}]}
        {"role": "tool",      "tool_call_id": str, "tool_name": str, "content": str}

    Each provider client is responsible for translating this format to the
    provider's wire format and back.
    """

    def __init__(
        self,
        model_name: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Send a conversation history and optional tool schemas.

        Returns a normalized dict:
        {
            "role": "assistant",
            "content": "text response or empty string",
            "tool_calls": [
                {"id": "call_...", "name": "tool_name", "arguments": {"param": "value"}}
            ],
            "usage": {"input_tokens": int, "output_tokens": int}  # optional
        }
        """
        pass
