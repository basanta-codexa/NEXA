from typing import Any
from llm.llm_client import LLMClient


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        model_name: str = "fake",
        canned_response: str | None = None,
        canned_tool_calls: list[dict[str, Any]] | None = None
    ):
        self.model_name = model_name
        self.canned_response = canned_response
        self.canned_tool_calls = canned_tool_calls or []
        self.call_count = 0

    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:
        if self.canned_response:
            return self.canned_response
        return f"[{self.model_name}] Fake response to: {user_message}"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        self.call_count += 1

        # If canned tool calls are configured and this is the first turn, return tool calls
        if self.canned_tool_calls and self.call_count == 1:
            return {
                "role": "assistant",
                "content": self.canned_response or "",
                "tool_calls": self.canned_tool_calls
            }

        # Otherwise return normal assistant message
        content = self.canned_response or f"[{self.model_name}] Completed task successfully."
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": []
        }
