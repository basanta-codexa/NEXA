import json
import logging
import time
import uuid
from typing import Any

from schemas import AgentConfig
from tools.default_registry import default_registry
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    """Normalize tool arguments returned by an LLM into a dict."""
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except ValueError:
            logger.warning("Could not parse tool arguments: %r", raw_arguments)
            return {}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {"value": raw_arguments}


def _serialize(value: Any) -> str:
    """Serialize tool output for the LLM without ever raising."""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


class AgentEngine:
    """Runs an LLM tool-calling loop against an agent configuration."""

    def __init__(
        self,
        config: AgentConfig,
        llm_client: Any,
        tool_registry: ToolRegistry | None = None,
        max_iterations: int = 5,
    ):
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry or default_registry
        self.max_iterations = max(1, max_iterations)

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
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """
        Executes an autonomous agent loop:
        1. Build messages from system prompt, prior turns, and the new user message.
        2. Send tool schemas to the LLM.
        3. While the LLM requests tools: execute them, append results, ask again.
        4. Return the final text answer plus every tool step that ran.
        """
        iterations = max(1, max_iterations or self.max_iterations)

        messages: list[dict[str, Any]] = []

        if self.config.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.system_prompt,
            })

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        tool_schemas = self.tool_registry.get_tool_schemas() if self.tool_registry else []
        steps: list[dict[str, Any]] = []
        usage: dict[str, int] = {}
        started_at = time.perf_counter()

        for iteration in range(1, iterations + 1):
            llm_started_at = time.perf_counter()
            response = self.llm_client.chat(messages=messages, tools=tool_schemas)
            llm_duration_ms = round((time.perf_counter() - llm_started_at) * 1000, 2)

            if response.get("usage"):
                usage = response["usage"]

            tool_calls = response.get("tool_calls") or []

            # Case A: final text answer.
            if not tool_calls:
                total_duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    "agent_run_completed model=%s iterations=%d tools=%d duration_ms=%s",
                    self.config.model_name,
                    iteration,
                    len(steps),
                    total_duration_ms,
                )
                return {
                    "message": user_message,
                    "response": response.get("content", ""),
                    "steps": steps,
                    "iterations": iteration,
                    "model": self.config.model_name,
                    "usage": usage,
                    "duration_ms": total_duration_ms,
                    "configuration": self.config,
                }

            # Case B: model requested tool calls — append the assistant turn in
            # canonical format so every provider client can translate it.
            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                call_id = call.get("id") or f"call_{uuid.uuid4().hex[:12]}"
                tool_name = call.get("name")
                arguments = _parse_tool_arguments(call.get("arguments"))

                tool_started_at = time.perf_counter()
                if not tool_name or tool_name not in self.tool_registry.list_tools():
                    tool_result: Any = {
                        "error": f"Tool '{tool_name}' is not registered."
                    }
                else:
                    try:
                        tool_result = self.tool_registry.execute(tool_name, **arguments)
                    except Exception as exc:  # registry already guards, belt & braces
                        logger.exception("Tool %s crashed", tool_name)
                        tool_result = {"error": f"Tool '{tool_name}' failed: {exc}"}

                tool_duration_ms = round(
                    (time.perf_counter() - tool_started_at) * 1000, 2
                )
                logger.info(
                    "tool_executed tool=%s tool_call_id=%s duration_ms=%s failed=%s",
                    tool_name,
                    call_id,
                    tool_duration_ms,
                    isinstance(tool_result, dict) and "error" in tool_result,
                )

                steps.append({
                    "tool": tool_name,
                    "tool_call_id": call_id,
                    "arguments": arguments,
                    "result": tool_result,
                    "duration_ms": tool_duration_ms,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "tool_name": tool_name,
                    "content": _serialize(tool_result),
                })

        total_duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "agent_run_max_iterations model=%s iterations=%d",
            self.config.model_name,
            iterations,
        )

        return {
            "message": user_message,
            "response": "Agent reached the maximum number of tool iterations without finishing.",
            "steps": steps,
            "iterations": iterations,
            "model": self.config.model_name,
            "usage": usage,
            "duration_ms": total_duration_ms,
            "configuration": self.config,
        }
