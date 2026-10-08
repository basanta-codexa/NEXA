from schemas import AgentConfig


class AgentEngine:

    def __init__(self, config: AgentConfig, llm_client):
        self.config = config
        self.llm_client = llm_client

    def get_model_name(self) -> str | None:
        return self.config.model_name

    def run(self, user_message: str):

        system_prompt = self.config.system_prompt or ""

        response = self.llm_client.generate(
            system_prompt=system_prompt,
            user_message=user_message
        )

        return {
            "message": user_message,
            "response": response,
            "configuration": self.config
        }
