#!/usr/bin/env python3
"""Quick script to test Shopee API endpoints with saved cookies."""

import json
import sys

from shopee_cli.client import ShopeeClient


def main():
    if len(sys.argv) < 2:
        print("Usage: python explore_api.py <endpoint> [param=value ...]")
        print("Example: python explore_api.py /search/search_items keyword=phone limit=5")
        return

    endpoint = sys.argv[1]
    params = {}
    for arg in sys.argv[2:]:
        key, _, value = arg.partition("=")
        # Try to convert to int
        try:
            value = int(value)
        except ValueError:
            pass
        params[key] = value

    with ShopeeClient() as client:
        print(f"GET {endpoint} {params}")
        data = client.get(endpoint, params=params or None)
        print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
