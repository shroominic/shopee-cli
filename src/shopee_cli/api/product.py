"""Shopee product detail via page navigation + DOM scraping.

The product detail API endpoint is protected by af-ac-enc-dat anti-bot headers,
so we navigate to the product page and extract info from the DOM instead.
"""

import re

from shopee_cli.client import ShopeeClient

PRODUCT_URL = "https://shopee.com.my/product/{shop_id}/{item_id}"

EXTRACT_JS = """
const data = {};

// Product name from h1
const h1 = document.querySelector('h1');
data.name = h1 ? h1.innerText.trim() : '';

// Get the full page text for parsing
data.body = document.body.innerText;

return data;
"""


def get_product_page(client: ShopeeClient, shop_id: int, item_id: int) -> dict:
    """Navigate to product page and extract details from DOM."""
    url = PRODUCT_URL.format(shop_id=shop_id, item_id=item_id)
    client.navigate(url, wait=5.0)

    raw = client.run_js(EXTRACT_JS)
    return _parse_page_text(raw)


def _parse_page_text(raw: dict) -> dict:
    """Parse product info from page body text."""
    name = raw.get("name", "")
    body = raw.get("body", "")

    # Extract rating and sold
    # Format: "4.8\n1.6k\nRatings\n6k+ Sold"
    rating = ""
    rating_count = ""
    sold = ""
    match = re.search(r"(\d\.\d)\n([\d.]+k?)\nRatings\n([\d.]+k?\+?) Sold", body)
    if match:
        rating = match.group(1)
        rating_count = match.group(2)
        sold = match.group(3)

    # Extract price - format: "RM12.90" on its own line
    price = ""
    original_price = ""
    discount = ""
    # Look for price after "Sold" section
    sold_idx = body.find("Sold\n")
    if sold_idx >= 0:
        price_section = body[sold_idx:sold_idx + 300]
        # Current price: first "RMxx.xx"
        price_match = re.search(r"\nRM([\d,.]+)", price_section)
        if price_match:
            price = price_match.group(1)
        # Original price and discount: "RM19.90\n-35%"
        orig_match = re.search(r"\nRM[\d,.]+\nRM([\d,.]+)\n(-\d+%)", price_section)
        if orig_match:
            original_price = orig_match.group(1)
            discount = orig_match.group(2)

    # Extract description
    description = ""
    for marker in ("Product Description\n", "PRODUCT DETAILS\n"):
        idx = body.find(marker)
        if idx >= 0:
            desc_text = body[idx + len(marker):]
            for end_marker in ("RATINGS AND REVIEWS", "Ratings and Reviews", "From the same shop"):
                end_idx = desc_text.find(end_marker)
                if end_idx >= 0:
                    desc_text = desc_text[:end_idx]
                    break
            description = desc_text.strip()[:1000]
            break

    return {
        "name": name,
        "price": price,
        "original_price": original_price,
        "discount": discount,
        "rating": rating,
        "rating_count": rating_count,
        "sold": sold,
        "description": description,
    }


def parse_product_url(url: str) -> tuple[int, int] | None:
    """Extract shop_id and item_id from a Shopee product URL.

    Supports formats:
      - https://shopee.com.my/Product-Name-i.{shop_id}.{item_id}
      - https://shopee.com.my/product/{shop_id}/{item_id}
    """
    # Format: /product/shop_id/item_id
    match = re.search(r"/product/(\d+)/(\d+)", url)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Format: -i.shop_id.item_id
    match = re.search(r"-i\.(\d+)\.(\d+)", url)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Try trailing .shop_id.item_id
    try:
        parts = url.rstrip("/").split(".")
        item_id = int(parts[-1])
        shop_id = int(parts[-2])
        return shop_id, item_id
    except (ValueError, IndexError):
        return None
