from llm.llm_client import LLMClient
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class OpenAIClient(LLMClient):

    def __init__(self, model_name: str):
        self.model_name = model_name
        api_key = os.getenv("OPENAI_API_KEY")

        self.client = OpenAI(api_key=api_key)

    def generate(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:
        response = self.client.responses.create(
            model=self.model_name,
            instructions=system_prompt,
            input=user_message
        )

        return response.output_text