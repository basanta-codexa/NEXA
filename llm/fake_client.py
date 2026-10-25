from typing import Any

from llm.llm_client import LLMClient


class FakeLLMClient(LLMClient):
    """Deterministic client for tests and offline demos."""

    def __init__(
        self,
        model_name: str = "fake",
        canned_response: str | None = None,
        canned_tool_calls: list[dict[str, Any]] | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ):
        super().__init__(
            model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        self.canned_response = canned_response
        self.canned_tool_calls = canned_tool_calls or []
        self.call_count = 0
        self.last_messages: list[dict[str, Any]] = []
        self.last_tools: list[dict[str, Any]] | None = None

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
        self.last_messages = messages
        self.last_tools = tools

        if self.canned_tool_calls and self.call_count == 1:
            return {
                "role": "assistant",
                "content": self.canned_response or "",
                "tool_calls": [
                    {
                        "id": call.get("id") or f"call_fake_{index}",
                        "name": call.get("name"),
                        "arguments": call.get("arguments") or {},
                    }
                    for index, call in enumerate(self.canned_tool_calls)
                ],
            }

        content = self.canned_response or f"[{self.model_name}] Completed task successfully."
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [],
        }
