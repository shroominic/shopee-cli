"""Shopee CLI - interact with Shopee Malaysia from the terminal."""

import click
from rich.console import Console
from rich.table import Table

from shopee_cli.api.orders import ORDER_STATUS_LABELS, get_orders, parse_orders
from shopee_cli.api.product import get_product_page, parse_product_url
from shopee_cli.api.search import search_items
from shopee_cli.auth import login
from shopee_cli.client import ShopeeClient

console = Console()


@click.group()
def main():
    """Shopee CLI - interact with Shopee Malaysia from the terminal."""


@main.command()
def login_cmd():
    """Open browser to log in to Shopee."""
    login()


# Register with the name "login" (can't use as Python function name since it shadows the import)
login_cmd.name = "login"


@main.command()
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Number of results")
@click.option("--sort", "-s", type=click.Choice(["relevancy", "sales", "price", "ctime"]), default="relevancy")
@click.option("--page", "-p", default=1, help="Page number")
def search(query: str, limit: int, sort: str, page: int):
    """Search for products on Shopee."""
    with ShopeeClient(require_auth=False) as client:
        results = search_items(client, keyword=query, limit=limit, sort_by=sort, page=page)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search: {query}")
    table.add_column("#", style="dim", width=3)
    table.add_column("Product", max_width=50)
    table.add_column("Price (RM)", justify="right")
    table.add_column("Sold", justify="right")
    table.add_column("Rating", justify="right")
    table.add_column("Location")

    for i, item in enumerate(results, 1):
        table.add_row(
            str(i),
            item["name"][:50],
            f"{item['price']:.2f}" if item["price"] else "-",
            item["sold"],
            item["rating"],
            item["location"],
        )

    console.print(table)


@main.command()
@click.argument("url_or_ids")
def product(url_or_ids: str):
    """Get product details. Pass a Shopee URL or 'shop_id.item_id'."""
    parsed = parse_product_url(url_or_ids)
    if parsed is None:
        # Try direct shop_id.item_id format
        try:
            parts = url_or_ids.split(".")
            shop_id, item_id = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            console.print("[red]Invalid product URL or ID format.[/red]")
            console.print("Use a Shopee URL or 'shop_id.item_id' format.")
            return
    else:
        shop_id, item_id = parsed

    with ShopeeClient(require_auth=False) as client:
        info = get_product_page(client, shop_id=shop_id, item_id=item_id)

    if not info.get("name"):
        console.print("[red]Product not found.[/red]")
        return

    console.print(f"\n[bold]{info['name']}[/bold]")
    if info["rating"]:
        console.print(f"Rating: {info['rating']} ({info['rating_count']} ratings)")
    if info["sold"]:
        console.print(f"Sold: {info['sold']}")
    if info["price"]:
        price_str = f"RM {info['price']}"
        if info["original_price"]:
            price_str += f"  [dim strikethrough]RM {info['original_price']}[/dim strikethrough]  [red]{info['discount']}[/red]"
        console.print(f"Price: {price_str}")
    if info["description"]:
        console.print(f"\n[dim]{info['description'][:500]}[/dim]")


@main.command()
@click.option(
    "--status", "-s",
    type=click.Choice(list(ORDER_STATUS_LABELS.values()), case_sensitive=False),
    default="All",
    help="Filter by order status",
)
@click.option("--limit", "-l", default=20, help="Number of orders")
def orders(status: str, limit: int):
    """List your Shopee orders."""
    # Map label back to type code
    status_code = 0
    for code, label in ORDER_STATUS_LABELS.items():
        if label.lower() == status.lower():
            status_code = code
            break

    with ShopeeClient() as client:
        data = get_orders(client, list_type=status_code, limit=limit)
        order_list = parse_orders(data)

    if not order_list:
        console.print("[yellow]No orders found.[/yellow]")
        return

    for order in order_list:
        console.print(f"\n[bold]{order['shop_name']}[/bold] - [cyan]{order['status']}[/cyan]")
        console.print(f"  Order: {order['order_id']}")
        for item in order["items"]:
            model = f" ({item['model']})" if item.get("model") else ""
            console.print(f"  - {item['name']}{model} x{item['quantity']}  RM {item['price']:.2f}")


if __name__ == "__main__":
    main()
