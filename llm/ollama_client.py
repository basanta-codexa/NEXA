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
