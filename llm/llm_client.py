from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):

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
            "content": "text response or None",
            "tool_calls": [
                {
                    "name": "tool_name",
                    "arguments": {"param": "value"}
                }
            ]
        }
        """
        pass
