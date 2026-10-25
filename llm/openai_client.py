import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from llm.llm_client import LLMClient

load_dotenv()

logger = logging.getLogger(__name__)


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate canonical NEXA messages into OpenAI chat-completions messages."""
    translated: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")

        if role == "assistant" and message.get("tool_calls"):
            translated.append({
                "role": "assistant",
                "content": message.get("content") or None,
                "tool_calls": [
                    {
                        "id": call.get("id") or f"call_{index}",
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": json.dumps(call.get("arguments") or {}),
                        },
                    }
                    for index, call in enumerate(message["tool_calls"])
                ],
            })
            continue

        if role == "tool":
            translated.append({
                "role": "tool",
                "tool_call_id": message.get("tool_call_id") or "call_unknown",
                "content": message.get("content") or "",
            })
            continue

        translated.append({
            "role": role,
            "content": message.get("content") or "",
        })

    return translated


def from_openai_message(message: Any) -> dict[str, Any]:
    """Translate an OpenAI assistant message into the canonical NEXA format."""
    tool_calls: list[dict[str, Any]] = []

    for call in getattr(message, "tool_calls", None) or []:
        raw_arguments = call.function.arguments or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except (TypeError, ValueError):
            logger.warning("Model returned invalid JSON tool arguments: %r", raw_arguments)
            arguments = {}

        tool_calls.append({
            "id": call.id,
            "name": call.function.name,
            "arguments": arguments if isinstance(arguments, dict) else {"value": arguments},
        })

    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": tool_calls,
    }


class OpenAIClient(LLMClient):
    """OpenAI chat-completions client with tool calling and generation params."""

    def __init__(
        self,
        model_name: str,
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
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        # Lazy so importing/creating the client never fails without a key.
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:
        response = self.chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ])
        return response["content"]

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": to_openai_messages(messages),
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.max_tokens is not None:
            payload["max_completion_tokens"] = self.max_tokens

        try:
            completion = self.client.chat.completions.create(**payload)
        except Exception as exc:
            logger.exception("OpenAI request failed for model %s", self.model_name)
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        choice = completion.choices[0]
        result = from_openai_message(choice.message)
        result["finish_reason"] = choice.finish_reason

        usage = getattr(completion, "usage", None)
        if usage is not None:
            result["usage"] = {
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
            }

        return result
