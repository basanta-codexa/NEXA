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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class OpenAIClient(LLMClient):
    """
    OpenAI-compatible chat-completions client.

    Used for OpenAI itself and for providers that expose an OpenAI-compatible
    API (for example Groq and xAI). Provider-specific routing is handled by
    the factory; this class handles key, base URL, timeout, and retry config.
    """

    def __init__(
        self,
        model_name: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        provider_name: str = "OpenAI",
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        super().__init__(
            model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        if not model_name or not model_name.strip():
            raise ValueError("model_name must not be empty.")

        self._client: OpenAI | None = None
        self._base_url = base_url
        self._api_key_env = api_key_env
        self._provider_name = provider_name
        self._timeout = (
            timeout if timeout is not None else _env_float("LLM_TIMEOUT_SECONDS", 60.0)
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else _env_int("LLM_MAX_RETRIES", 2)
        )

    @property
    def client(self) -> OpenAI:
        # Lazy so importing/creating the client never fails without a key.
        if self._client is None:
            api_key = os.getenv(self._api_key_env)
            if not api_key:
                raise RuntimeError(f"{self._api_key_env} is not set.")

            client_kwargs: dict[str, Any] = {
                "api_key": api_key,
                "timeout": self._timeout,
                "max_retries": self._max_retries,
            }
            base_url = self._base_url
            if base_url is None and self._api_key_env == "OPENAI_API_KEY":
                base_url = os.getenv("OPENAI_BASE_URL")
            if base_url:
                client_kwargs["base_url"] = base_url

            self._client = OpenAI(**client_kwargs)
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
        except RuntimeError:
            # Configuration/setup errors should keep their specific message.
            raise
        except Exception as exc:
            logger.exception(
                "%s request failed for model %s",
                self._provider_name,
                self.model_name,
            )
            raise RuntimeError(f"{self._provider_name} request failed: {exc}") from exc

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
