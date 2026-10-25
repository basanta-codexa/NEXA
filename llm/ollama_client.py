import json
import logging
import os
from typing import Any

import requests

from llm.llm_client import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def to_ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate canonical NEXA messages into Ollama /api/chat messages."""
    translated: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")

        if role == "assistant" and message.get("tool_calls"):
            translated.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": [
                    {
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": call.get("arguments") or {},
                        }
                    }
                    for call in message["tool_calls"]
                ],
            })
            continue

        if role == "tool":
            translated.append({
                "role": "tool",
                "tool_name": message.get("tool_name") or "",
                "content": message.get("content") or "",
            })
            continue

        translated.append({
            "role": role,
            "content": message.get("content") or "",
        })

    return translated


def build_ollama_options(
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
) -> dict[str, Any]:
    """Map NEXA agent config to Ollama generation options."""
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if top_p is not None:
        options["top_p"] = top_p
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    return options


class OllamaClient(LLMClient):
    """Ollama /api/chat client with tool calling and generation params."""

    def __init__(
        self,
        model_name: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        host: str | None = None,
        timeout: int = 300,
    ):
        super().__init__(
            model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        self.host = (host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
        self.timeout = timeout

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

    def generate_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tool_schemas: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            tools=tool_schemas,
        )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.chat(messages=messages, tools=tool_schemas)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": to_ollama_messages(messages),
            "stream": False,
        }

        options = build_ollama_options(
            self.temperature,
            self.max_tokens,
            self.top_p,
        )
        if options:
            payload["options"] = options
        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout as exc:
            raise RuntimeError("Ollama request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Unable to connect to Ollama at {self.host}. Is it running?"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        raw_message = data.get("message", {})
        tool_calls: list[dict[str, Any]] = []

        for index, call in enumerate(raw_message.get("tool_calls") or []):
            function_data = call.get("function", {})
            arguments = function_data.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    logger.warning("Ollama returned invalid tool arguments: %r", arguments)
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {"value": arguments}

            tool_calls.append({
                "id": call.get("id") or f"call_ollama_{index}",
                "name": function_data.get("name"),
                "arguments": arguments,
            })

        result: dict[str, Any] = {
            "role": "assistant",
            "content": raw_message.get("content") or "",
            "tool_calls": tool_calls,
        }

        if data.get("prompt_eval_count") is not None or data.get("eval_count") is not None:
            result["usage"] = {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            }

        return result
