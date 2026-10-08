from llm.fake_client import FakeLLMClient
from llm.openai_client import OpenAIClient
from llm.ollama_client import OllamaClient

def create_llm_client(model_name : str | None):


    if model_name is None:
            return FakeLLMClient("fake")
    if model_name == "fake":
        return FakeLLMClient(model_name)

    if model_name.startswith("gpt-"):
        return OpenAIClient(model_name)

    if model_name.startswith("ollama/"):
        ollama_model = model_name.removeprefix("ollama/")
        return OllamaClient(ollama_model)

    raise ValueError(
         f"Unsupported model: {model_name}"
    )
