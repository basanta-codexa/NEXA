from typing import Any

import requests

from llm.llm_client import LLMClient


class OllamaClient(LLMClient):

    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:

        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ],
                    "stream": False
                },
                timeout=120
            )

            response.raise_for_status()

            data = response.json()

            return data["message"]["content"]

        except requests.exceptions.Timeout:
            raise RuntimeError(
                "Ollama request timed out."
            )

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Unable to connect to Ollama."
            )

        except requests.exceptions.HTTPError:
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable."
            )

        except requests.exceptions.RequestException:
            raise RuntimeError(
                "Ollama request failed."
            )

    def generate_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tool_schemas: list[dict[str, Any]]
    ) -> str:

        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ],
                    "tools": tool_schemas,
                    "stream": False
                },
                timeout=300
            )

            response.raise_for_status()

            data = response.json()

            return data["message"]

        except requests.exceptions.Timeout:
            raise RuntimeError(
                "Ollama request timed out."
            )

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Unable to connect to Ollama."
            )

        except requests.exceptions.HTTPError:
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable."
            )

        except requests.exceptions.RequestException:
            raise RuntimeError(
                "Ollama request failed."
            )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json=payload,
                timeout=300
            )

            response.raise_for_status()

            data = response.json()

            raw_message = data.get("message", {})
            raw_tool_calls = raw_message.get("tool_calls", [])
            normalized_tool_calls = []

            for call in raw_tool_calls:
                function_data = call.get("function", {})
                normalized_tool_calls.append({
                    "name": function_data.get("name"),
                    "arguments": function_data.get("arguments", {})
                })

            return {
                "role": "assistant",
                "content": raw_message.get("content") or "",
                "tool_calls": normalized_tool_calls
            }

        except requests.exceptions.Timeout:
            raise RuntimeError(
                "Ollama request timed out."
            )

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Unable to connect to Ollama."
            )

        except requests.exceptions.HTTPError:
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable."
            )

        except requests.exceptions.RequestException:
            raise RuntimeError(
                "Ollama request failed."
            )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.chat(messages=messages, tools=tool_schemas)