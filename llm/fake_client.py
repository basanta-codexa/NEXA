from llm.llm_client import LLMClient


class FakeLLMClient(LLMClient):
    def __init__(self, model_name : str = "fake"):
        self.model_name = model_name

    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:

        return f"[{self.model_name}] Fake response to: {user_message}"
