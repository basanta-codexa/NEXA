from typing import Any
from schemas import AgentConfig
from tools.default_registry import default_registry
from tools.registry import ToolRegistry


class AgentEngine:

    def __init__(
        self,
        config: AgentConfig,
        llm_client: Any,
        tool_registry: ToolRegistry | None = None
    ):
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry or default_registry

    def get_model_name(self) -> str | None:
        return self.config.model_name

    def get_available_tools(self) -> list[dict[str, Any]]:
        if self.tool_registry:
            return self.tool_registry.describe_tools()
        return []

    def execute_tool(self, tool_name: str, **arguments: Any) -> Any:
        if not self.tool_registry:
            return {"error": "No tool registry configured."}
        return self.tool_registry.execute(tool_name, **arguments)

    def run(
        self,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        max_iterations: int = 5
    ) -> dict[str, Any]:
        """
        Executes an autonomous agent loop:
        1. Formulates conversation history with system prompt, past turns, & user message.
        2. Retrieves registered tool schemas.
        3. Loops up to max_iterations:
           - Queries LLM with conversation history and tool schemas.
           - If LLM requests tool calls:
             - Validates and executes tool via tool_registry.
             - Appends tool output to history.
           - If LLM produces final text response:
             - Terminates and returns response with executed steps.
        """
        messages: list[dict[str, Any]] = []

        if self.config.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.system_prompt
            })

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": user_message
        })

        tool_schemas = self.tool_registry.get_tool_schemas() if self.tool_registry else []
        steps: list[dict[str, Any]] = []

        for _ in range(max_iterations):
            response = self.llm_client.chat(messages=messages, tools=tool_schemas)
            tool_calls = response.get("tool_calls", [])

            # Case A: Model returned final text answer without further tool calls
            if not tool_calls:
                return {
                    "message": user_message,
                    "response": response.get("content", ""),
                    "steps": steps,
                    "configuration": self.config
                }

            # Case B: Model requested one or more tool calls
            messages.append(response)

            for call in tool_calls:
                tool_name = call.get("name")
                arguments = call.get("arguments", {})

                if not tool_name or tool_name not in self.tool_registry.list_tools():
                    tool_result = {"error": f"Tool '{tool_name}' is not registered."}
                else:
                    tool_result = self.tool_registry.execute(tool_name, **arguments)

                steps.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": tool_result
                })

                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": str(tool_result)
                })

        return {
            "message": user_message,
            "response": "Agent reached maximum tool iterations without finishing.",
            "steps": steps,
            "configuration": self.config
        }
