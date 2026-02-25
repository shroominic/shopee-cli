"""Shopee product search via page navigation + DOM scraping.

The search API endpoint is protected by af-ac-enc-dat anti-bot headers,
so we navigate to the search page and extract results from the DOM instead.
"""

import re
from urllib.parse import quote_plus, urlencode

from shopee_cli.client import ShopeeClient

SEARCH_URL = "https://shopee.com.my/search"

# JavaScript to extract search results from the DOM
EXTRACT_JS = """
const items = document.querySelectorAll('[data-sqe="item"]');
const results = [];
for (const item of items) {
    const link = item.querySelector('a[href]');
    const texts = item.innerText.split("\\n").filter(t => t.trim());
    results.push({
        href: link ? link.getAttribute("href") : "",
        texts: texts,
    });
}
return results;
"""


def search_items(
    client: ShopeeClient,
    keyword: str,
    limit: int = 20,
    sort_by: str = "relevancy",
    page: int = 1,
) -> list[dict]:
    """Search for products by navigating to the search page and scraping results."""
    params = {
        "keyword": keyword,
        "by": sort_by,
        "page": page - 1,  # Shopee uses 0-indexed pages
    }
    url = SEARCH_URL + "?" + urlencode(params)
    client.navigate(url, wait=5.0)

    raw_items = client.run_js(EXTRACT_JS)
    return [_parse_dom_item(item) for item in raw_items[:limit]]


def _parse_dom_item(item: dict) -> dict:
    """Parse a single search result item from DOM text content.

    The texts array typically looks like:
    [name, "RM", price, discount?, promo?, rating, "Xk+ sold", delivery, location, "Find Similar"]
    """
    texts = item.get("texts", [])
    href = item.get("href", "")

    name = texts[0] if texts else ""

    # Extract price - find "RM" followed by a number
    price = 0.0
    for i, t in enumerate(texts):
        if t == "RM" and i + 1 < len(texts):
            try:
                price = float(texts[i + 1].replace(",", ""))
            except ValueError:
                pass
            break

    # Extract sold count
    sold = ""
    for t in texts:
        if "sold" in t.lower():
            sold = t
            break

    # Extract rating
    rating = ""
    for t in texts:
        if re.match(r"^\d\.\d$", t):
            rating = t
            break

    # Extract location (usually second to last, before "Find Similar")
    location = ""
    for t in reversed(texts):
        if t not in ("Find Similar", "Ad", "Sponsored") and not t.startswith("< "):
            location = t
            break

    # Extract shop_id and item_id from href
    shop_id = 0
    item_id = 0
    if href:
        match = re.search(r"-i\.(\d+)\.(\d+)", href)
        if match:
            shop_id = int(match.group(1))
            item_id = int(match.group(2))

    return {
        "name": name,
        "price": price,
        "sold": sold,
        "rating": rating,
        "location": location,
        "shop_id": shop_id,
        "item_id": item_id,
        "href": href,
    }
