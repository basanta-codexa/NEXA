
from tools.registry import ToolRegistry
from tools.order_tools import get_order_status

default_registry = ToolRegistry()

default_registry.register(
    name="get_order_status",
    function=get_order_status,
    description="Retrieves the status of a demonstration order using an order ID."
)
