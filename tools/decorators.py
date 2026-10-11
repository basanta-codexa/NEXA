
from typing import Callable, Any

from tools.registry import ToolRegistry


def tool(
    registry: ToolRegistry,
    name: str,
    description: str
) -> Callable:
    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(name, function, description)
        return function

    return decorator
