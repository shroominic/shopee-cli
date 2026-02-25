"""Shopee orders API."""

from typing import Any

from shopee_cli.client import ShopeeClient

# Order list type filters
ORDER_TYPE_ALL = 0
ORDER_TYPE_TO_PAY = 1
ORDER_TYPE_TO_SHIP = 2
ORDER_TYPE_SHIPPING = 3
ORDER_TYPE_COMPLETED = 4
ORDER_TYPE_CANCELLED = 5
ORDER_TYPE_RETURN_REFUND = 6

ORDER_STATUS_LABELS = {
    ORDER_TYPE_ALL: "All",
    ORDER_TYPE_TO_PAY: "To Pay",
    ORDER_TYPE_TO_SHIP: "To Ship",
    ORDER_TYPE_SHIPPING: "Shipping",
    ORDER_TYPE_COMPLETED: "Completed",
    ORDER_TYPE_CANCELLED: "Cancelled",
    ORDER_TYPE_RETURN_REFUND: "Return/Refund",
}


def get_orders(
    client: ShopeeClient,
    list_type: int = ORDER_TYPE_ALL,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Get order list."""
    return client.get(
        "/order/get_all_order_and_checkout_list",
        params={
            "list_type": list_type,
            "limit": limit,
            "offset": offset,
        },
    )


def parse_orders(data: dict) -> list[dict]:
    """Extract useful order info from response.

    Response structure: new_data.order_or_checkout_data[].order_list_detail
    """
    entries = data.get("new_data", {}).get("order_or_checkout_data", [])

    results = []
    for entry in entries:
        detail = entry.get("order_list_detail", {})
        status_info = detail.get("status", {})
        status_label = status_info.get("status_label", {}).get("text", "")

        # Order cards contain shop info and product info
        info_card = detail.get("info_card", {})
        order_cards = info_card.get("order_list_cards", [])

        for card in order_cards:
            shop = card.get("shop_info", {})
            order_id = card.get("order_id", "")

            # Extract items from product_info.item_groups[].items[]
            items = []
            product_info = card.get("product_info", {})
            for group in product_info.get("item_groups", []):
                for item in group.get("items", []):
                    items.append({
                        "name": item.get("name", ""),
                        "model": item.get("model_name", ""),
                        "quantity": item.get("amount", 1),
                        "price": item.get("order_price", 0) / 100000,
                        "image": item.get("image", ""),
                    })

            results.append({
                "order_id": order_id,
                "status": status_label,
                "shop_name": shop.get("shop_name", ""),
                "items": items,
            })

    return results
