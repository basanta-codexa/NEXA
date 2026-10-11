
def get_order_status(order_id: int) -> dict:
    """Return the status of a demonstration order."""

    demo_orders = {
        101: "Shipped",
        102: "Processing",
        103: "Delivered"
    }

    status = demo_orders.get(order_id)

    if status is None:
        return {
            "order_id": order_id,
            "status": "Not found"
        }

    return {
        "order_id": order_id,
        "status": status
    }