
import inspect
from typing import Callable, Any, get_type_hints
from unicodedata import name
from unicodedata import name


class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._descriptions: dict[str, str] = {}

    def register(
        self,
        name: str,
        function: Callable[..., Any],
        description: str
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered.")

        self._tools[name] = function
        self._descriptions[name] = description

    def create_scoped_registry(self, allowed_tools: list[str]) -> "ToolRegistry":
        """
        Creates a new ToolRegistry instance containing only the allowed tools.
        Guarantees isolation so an agent cannot access unassigned tools.
        """
        scoped = ToolRegistry()
        for name in allowed_tools:
            if name in self._tools:
                scoped._tools[name] = self._tools[name]
                scoped._descriptions[name] = self._descriptions[name]
        return scoped


    def get(self, tool_name: str) -> Callable[..., Any]:
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' is not registered.")

        return self._tools[tool_name]

    def execute(self, tool_name: str, **kwargs: Any) -> Any:
        try:
            self.validate_arguments(tool_name, kwargs)
            function = self.get(tool_name)
            return function(**kwargs)

        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}

        except Exception:
            return {"error": "The tool failed unexpectedly."}



    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def describe_tools(self) -> list[dict[str, Any]]:
        descriptions = []

        for name, function in self._tools.items():
            signature = inspect.signature(function)
            type_hints = get_type_hints(function)

            parameters = []

            for parameter_name, parameter in signature.parameters.items():
                parameter_type = type_hints.get(
                    parameter_name,
                    Any
                )

                parameters.append({
                    "name": parameter_name,
                    "type": getattr(parameter_type, "__name__", str(parameter_type)),
                    "required": (
                        parameter.default is inspect.Parameter.empty
                    )
                })

            descriptions.append({
                "name": name,
                "description": self._descriptions[name],
                "parameters": parameters
            })

        return descriptions

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        schemas = []

        for tool in self.describe_tools():
            properties = {}
            required = []

            for parameter in tool["parameters"]:
                parameter_type = parameter["type"]

                json_type = {
                    "str": "string",
                    "int": "integer",
                    "float": "number",
                    "bool": "boolean"
                }.get(parameter_type, "string")

                properties[parameter["name"]] = {
                    "type": json_type
                }

                if parameter["required"]:
                    required.append(parameter["name"])

            schemas.append({
                "type": "function",
                "function":{
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
                }
            })

        return schemas


    def validate_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> None:
        function = self.get(tool_name)
        signature = inspect.signature(function)

        try:
            signature.bind(**arguments)
        except TypeError as exc:
            raise ValueError(
                f"Invalid arguments for tool '{tool_name}': {exc}"
            ) from exc

        type_hints = get_type_hints(function)

        for parameter_name, value in arguments.items():
            expected_type = type_hints.get(parameter_name)

            if expected_type is None:
                continue

            if expected_type is int and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ValueError(
                    f"Argument '{parameter_name}' must be an integer."
                )

            if expected_type is str and not isinstance(value, str):
                raise ValueError(
                    f"Argument '{parameter_name}' must be a string."
                )

            if expected_type is bool and not isinstance(value, bool):
                raise ValueError(
                    f"Argument '{parameter_name}' must be a boolean."
                )

            if expected_type is float and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                raise ValueError(
                    f"Argument '{parameter_name}' must be a number."
                )
